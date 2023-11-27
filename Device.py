import random
import time
import asyncio
import os, sys

#from abc import ABC, abstractmethod
import copy
from Headers import *
from L1 import *
from Debug import Debug
#from DHCP import DHCPServerHandler, DHCPClientHandler
#from ARP import ARPHandler
#from ICMP import ICMPHandler
from Handlers import ARP
import ipaddress
import pprint

random.seed(123)

# Abstract Base Class
class Device():
    def __init__(self, ips=[], connectedTo=[], debug=1): # Device

        assert type(connectedTo) == type([])

        for i in connectedTo:
            assert isinstance(i, Device)

        # Debug 0 : Show nothing
        # Debug 1 : Show who talks to who
        # Debug 2 : Show who sends what to who
        self.DEBUG = debug

        # For visualization purposes
        self.listen_delay = 0.25
        self.id = "_D_" + str(random.randint(10000, 99999999))

        self.interfaces = []

        # To be used as a recipient for send(), read by listen()
        self.read_buffer = []
        self.ip_forward = 0

        self._initConnections(connectedTo, ips)

    def _initConnections(self, connectedTo, ips):
        for idx, device in enumerate(connectedTo):
            # Are we already connected?
            local = 0
            remote = 0
            for mi in self.interfaces:
                for yi in device.interfaces:
                    if mi in yi.link:
                        remote += 1
                    if yi in mi.link:
                        local += 1
            
            if local > 2 or remote > 2:
                raise ValueError(self.id, device.id, "contain multiple interfaces to each other")
            
            if local != remote:
                raise ValueError("Interface mismatch between", self.id, device.id)

            # We contain no interfaces to each other
            if local == 0 and remote == 0:
                local_i = Interface(self, idx)
                remote_i = Interface(device, len(device.interfaces))
                self.interfaces.append(local_i)
                device.interfaces.append(remote_i)

                # Connect links
                local_i.link.add(remote_i)
                remote_i.link = local_i.link

        # Associate provided IPs to each interface
        # If there are more interfaces than IPs, they get 0.0.0.0/32
        if ips: # Dont do this for L2 devices
            for i in range(len(self.interfaces)):
                try:
                    self.interfaces[i].config["ip"] = ips[i]
                except IndexError:
                    self.interfaces[i].config["ip"] = "0.0.0.0/32"

    async def listen(self):
        while True:
            self._checkTimeouts()
            await asyncio.sleep(self.listen_delay)

            if self.read_buffer:
                data = self.listen_buffer.pop(0)
                # Grab the interface it came in on
                interface = findInterfaceFromID(data["L2"]["From"], self.interfaces)
                if self.DEBUG == 1:
                    Debug(interface.id, "got data from", Debug.colorID(interface.link.get_other(interface).id), 
                        color="green", f=self.__class__.__name__
                    )
                if self.DEBUG == 2:
                    Debug(interface.id, "got data from", Debug.colorID(interface.link.get_other(interface).id),
                        data, 
                        color="blue", f=self.__class__.__name__
                    )

                await self.handleData(data, interface)

    async def handleData(self, data, oninterface):
        
        # L2: To me?
        if data["L2"]["To"] not in [oninterface.id, MAC_BROADCAST]:
            return

        # ===================================================
        # Checking ETHTYPE

        # ARP - Drop if not to me
        if data["L2"]["ethertype"] == "ARP" and data["L2"]["ethertype"]["tpa"] == oninterface.ip:
            await self._callHandler("ARP", oninterface, data)
        
        # IPv4 - Route (if ip_forward enabled) if not to me else drop
        elif data["L2"]["ethertype"] == "IPv4":
            
            # To my IP?
            if data["L3"]["dip"] not in [oninterface.ip, IP_BROADCAST]:
                print(oninterface.id, "ignoring data from", data["L3"]["sip"])
                return
            
            #https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
            # UDP
            if data["L3"]["protocol"] == "UDP": # 17

                # DHCP
                if data["L4"]["DPort"] in [67, 68]: # L4 multiplexing
                    await self._callHandler("DHCP", oninterface, data)

                else:
                    if self.DEBUG: 
                        Debug(oninterface.id, data["L4"]["DPort"], "not configured!", 
                            color="red", f=self.__class__.__name__
                        )
            # ICMP
            elif data["L3"]["Protocol"] == "ICMP": # 1
                await self._callHandler("ICMP", oninterface, data)

        else:
            if self.DEBUG: 
                Debug(oninterface.id, "ignoring", data["L2"]["From"], data["L2"]["EtherType"],
                    color="yellow", f=self.__class__.__name__
                )

    async def _callHandler(self, proto, oninterface, data):
        d = await self.oninterface.handlers[proto].handle(data)
        if d: await self.send(d, oninterface)
        
    async def _checkTimeouts(self):
        """
        Should be executed periodically either by listen() or some other non-main thread,
        can be empty if a device has no periodic checks to make, but must be implemented.
        """
        pass
        # DHCP
        # try:
        #     for interface in self.interfaces:
        #         if interface.DHCPClient.lease[0] >= 0:
        #             interface.DHCPClient.lease_left = (interface.DHCPClient.lease[0] + interface.DHCPClient.lease[1]) - int(time.time())
        #             if self.DEBUG == 2: 
        #                 Debug(self.id, "===", interface.DHCPClient.lease_left, "/", interface.DHCPClient.lease[0], 
        #                     f=self.__class__.__name__
        #                 )
        #             if interface.DHCPClient.lease_left <= 0.5 * interface.DHCPClient.lease[0] and interface.DHCPClient.DHCP_FLAG != 1:
        #                 if self.DEBUG: 
        #                     Debug(self.id, "renewing ip", self.getIP(), color="green", 
        #                         f=self.__class__.__name__
        #                     )
        #                 interface.DHCPClient.DHCP_FLAG = 1
        #                 self.sendDHCP("Renew")
        # except: pass
        # return 

    async def sendARP(self, targetIP, oninterface=None, timeout=5, result=None):
        """
        Wrapper for oninterface.handler["ARP"].create(), handles sanity checking
        and timeout
        """

        if not oninterface: oninterface = self.interfaces[0]
        assert isinstance(targetIP, str)
        assert isinstance(oninterface, Interface)
        
        p = oninterface.handlers["ARP"].create(targetIP)
        self.send(p, oninterface)

        # Timeout logic
        async def _check_for_val():
            while oninterface.handler["ARP"].arp_cache != True:
                await asyncio.sleep(0)
        
        try:
            await asyncio.wait_for(_check_for_val(), timeout)
            return oninterface.handler["ARP"].arp_cache[targetIP]
        except TimeoutError:
            if self.DEBUG:
                Debug(self.id, "ARP timeout for", targetIP,
                    color="red", f=self.__class__.__name__
                )
            del oninterface.ARPHandler.arp_cache[targetIP]
        return False

    def send(self, data, oninterface=None):
        """
        Send data on an interface
        
        :param data: See `Headers.makePacket()`, dict
        :param onLinkID: optional, id parameter of link to be send out on
        """
        
        assert isinstance(data, dict)
        if not oninterface: oninterface = self.interfaces[0]
        assert isinstance(oninterface, Interface)

        # Is data in the right format?
        for k, v in data.items():
            if v == "": continue
            if not k in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"] or not isinstance(v, dict):
                print("Data: ", data)
                raise ValueError("data not in the correct format")

        # Don't modify the original dict
        data = copy.deepcopy(data)
        data["L2"]["From"] = oninterface.id

        end_int = oninterface.link.get_other(oninterface)
        end = end._parentDevice
        

        if self.DEBUG:
            Debug(oninterface.id, "==>", Debug.colorID(end_int.id), "via", oninterface.link.id, "ul", 
                color="green", f=self.__class__.__name__
            )
        
        end.read_buffer.append(data)

    def __str__(self):
        """
        Quickly see a device's connected links / devices
        """
        s = self.id + "\n"
        for interface in self.interfaces:
            s += "    " + interface.id + " ==> " + interface.link.get_other(interface).id + "\n"

        return s

async def main():
    A = Device(["1.1.1.1/24"])
    B = Device(["1.1.1.2/24"], [A])
    C = Device(["1.1.1.3/24"], [A, B])
    print(A)
    print(B)
    print(C)

if __name__ == "__main__":
    asyncio.run(main())    