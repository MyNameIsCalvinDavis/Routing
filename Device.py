import random
import time
import asyncio
import os, sys

#from abc import ABC, abstractmethod
import copy
from Headers import *
from L1 import *
from Debug import Debug
from DHCP import DHCPServerHandler, DHCPClientHandler
from ARP import ARPHandler
from ICMP import ICMPHandler
import ipaddress
import pprint

random.seed(123)

# Abstract Base Class
class Device():
    async def __init__(self, ips=[], connectedTo=[], debug=1): # Device

        assert type(connectedTo) == type([])
        assert type(ID) == type("")

        for i in connectedTo:
            assert isinstance(i, Device)


        # Debug 0 : Show nothing
        # Debug 1 : Show who talks to who
        # Debug 2 : Show who sends what to who
        self.DEBUG = debug

        # For visualization purposes
        self.listen_delay = 0.25
        self.id = "___" + str(random.randint(10000, 99999999))

        self.interfaces = []
        

        # To be used as a recipient for send(), read by listen()
        self.read_buffer = []
        self.ip_forward = 0

        self._initConnections(connectedTo, ips)

    async def listen(self):
        while True:
            self._checkTimeouts()
            await asyncio.sleep(self.listen_delay)

            if self.read_buffer:
                data = self.listen_buffer.pop(0)
                # Grab the interface it came in on
                interface = findInterfaceFromLinkID(data["L2"]["FromLink"], self.interfaces)
                if self.DEBUG == 1: 
                    Debug(self.id, "got data from", Debug.colorID(self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id), 
                        color="green", f=self.__class__.__name__
                    )
                if self.DEBUG == 2:
                    Debug(self.id, "got data from", Debug.colorID(self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id),
                        data, 
                        color="blue", f=self.__class__.__name__
                    )

                await self.handleData(data, interface)

    async def handleData(self, data, oninterface):
        
        # L2: To me?
        if data["L2"]["To"] not in [self.id, MAC_BROADCAST]:
            return

        # ===================================================
        # Checking ETHTYPE

        # ARP - Drop if not to me
        if data["L2"]["EtherType"] == "ARP" and data["L2"]["ethertype"]["TPA"] == oninterface.ip:
                self.handleARP(data, oninterface)
        
        # IPv4 - Route (if ip_forward enabled) if not to me else drop
        elif data["L2"]["EtherType"] == "IPv4":
            
            # To my IP?
            if data["L3"]["DIP"] not in [oninterface.ip, IP_BROADCAST]:
                print(self.id, "ignoring data from", data["L3"]["sip"])
                return
            
            #https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml

            # UDP
            if data["L3"]["protocol"] == "UDP": # 17

                # DHCP
                if data["L4"]["DPort"] in [67, 68]: # L4 multiplexing
                    await self._callHandler("ICMP", oninterface, data)

                else:
                    if self.DEBUG: 
                        Debug(self.id, data["L4"]["DPort"], "not configured!", 
                            color="red", f=self.__class__.__name__
                        )
            # ICMP
            elif data["L3"]["Protocol"] == "ICMP": # 1
                await self._callHandler("ICMP", oninterface, data)

        else:
            if self.DEBUG: 
                Debug(self.id, "ignoring", data["L2"]["From"], data["L2"]["EtherType"],
                    color="yellow", f=self.__class__.__name__
                )

    async def _callHandler(self, proto, oninterface, data):
        d = await self.oninterface.handlers[proto].handle(data)
        if d: await self.send(d, oninterface)
    
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
                local_i = Interface(self, "0.0.0.0")
                remote_i = Interface(device, "0.0.0.0")
                self.interfaces.append(local_i)
                device.interfaces.append(remote_i)

                # Connect links
                local_i.link.add(remote_i)
                remote_i.link = self.interfaces.link

        # Associate provided IPs to each interface
        # If there are more interfaces than IPs, they get 0.0.0.0/32
        if ips: # Dont do this for L2 devices
            for i in range(len(self.interfaces)):
                try:
                    self.interfaces[i].config["ip"] = ips[i]
                except IndexError:
                    self.interfaces[i].config["ip"] = "0.0.0.0/32"
        
    
    # Some L2 devices won't have timeouts; too bad
    @abstractmethod   
    def _checkTimeouts(self):
        """
        Should be executed periodically either by listen() or some other non-main thread,
        can be empty if a device has no periodic checks to make, but must be implemented.
        """
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

    def sendARP(self, targetIP, oninterface=None, timeout=5, result=None):
        """
        Send an ARP request to another device on the same subnet. By default,
        send out this request on the first interface.
        
        :param targetIP: IP of target device
        :param oninterface: optional, the interface object to send the request on
        """
        
        if not oninterface:
            oninterface = self.interfaces[0]
        
        assert isinstance(oninterface, Interface)

        if not isinstance(targetIP, str):
            #print(targetIP, type(targetIP))
            raise ValueError("TargetIP must be string, given: " + str(targetIP) )
        
        # Internally:
        # Establish targetIP as -1 and change it upon receiving an ARP response
        p = oninterface.ARPHandler.sendARP(targetIP)
        self.send(p, oninterface)

        # Here, check whether or not the target ip has been populated with an ID (MAC)
        now = time.time()
        b = 0
        if timeout:
            while (time.time() - now) < timeout:
                if oninterface.ARPHandler.arp_cache[targetIP] != False:
                    # ARP Response received!
                    if result:
                        result[0] = oninterface.ARPHandler.arp_cache[targetIP]
                    return oninterface.ARPHandler.arp_cache[targetIP]

        if self.DEBUG:
            Debug(self.id, "ARP timeout for", targetIP,
                color="red", f=self.__class__.__name__
            )
        del oninterface.ARPHandler.arp_cache[targetIP]
        return False

    def send(self, data, oninterface=None):
        """
        Send data on a link.
        
        This method finds the device on the other end of the given linkID,
        then appends data to its buffer. By default, it sends data out on the
        first interface on this device. For multi interface Devices like a Switch
        or Router, onlinkID may be defined.
        
        :param data: See `Headers.makePacket()`, dict
        :param onLinkID: optional, id parameter of link to be send out on
        """
        
        assert isinstance(data, dict)
        if oninterface:
            assert isinstance(oninterface, Interface)
            assert "_I_" in oninterface.id
        if oninterface == None:
            oninterface = self.interfaces[0]

        # Is data in the right format?
        for k, v in data.items():
            if v == "": continue
            if not k in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"] or not isinstance(v, dict):
                print("Data: ", data)
                raise ValueError("data not in the correct format")

        # Don't modify the original dict
        # This 26 character line represents at least 6 hours of my day
        data = copy.deepcopy(data)

        data["L2"]["FromLink"] = oninterface.linkid

        #end = self.getOtherDeviceOnInterface(oninterface.linkid)
        end = oninterface.link.get_other(oninterface)._parentDevice

        if self.DEBUG:
            Debug(self.id, "==>", Debug.colorID(end.id), "via", Debug.color(data["L2"]["FromLink"], "ul"), 
                color="green", f=self.__class__.__name__
            )
        
        end.listen_buffer.append(data)

    # def getOtherDeviceOnInterface(self, onlinkID):
    #     """
    #     Given a link ID, find the single device on the other end of it

    #     :param onLinkID: id parameter of a link
    #     :returns: Device instance
    #     """
    #     if not isinstance(onlinkID, str): raise ValueError("onlinkID must be of type <str>")
    #     onlink = self.getLinkFromID(onlinkID)
    #     # Find the other device on a link
    #     if onlink.dl[0].id == self.id:
    #         return onlink.dl[1]
    #     else:
    #         return onlink.dl[0]
    
    # def getInterfaceFromID(self, ID):
    #     """
    #     Given an Interface ID, return its instance

    #     :returns: Interface
    #     """
    #     if not isinstance(ID, str): raise ValueError("ID must be of type <str>")
    #     if not "_I_" in ID: raise ValueError("Provided ID " + ID + " not a link ID")
        
    #     for interface in self.interfaces:
    #         if interface.id == ID:
    #             return interface
    #     else:
    #         raise ValueError("LinkID " + ID + " not located in " + self.id + " interfaces")

    # def getLinkFromID(self, ID):
    #     """
    #     Given a Link ID, return its instance
            
    #     :returns: Link
    #     """
    #     if not isinstance(ID, str): raise ValueError("ID must be of type <str>")
    #     if not "[L]" in ID: raise ValueError("Provided ID " + ID + " not a link ID")
        
    #     for interface in self.interfaces:
    #         if interface.linkid == ID:
    #             return interface.link
    #     else:
    #         raise ValueError("LinkID " + ID + " not located in " + self.id + " interfaces")
    def __str__(self):
        """
        Quickly see a device's connected links / devices
        """
        s = self.id + "\n"
        for interface in self.interfaces:
            s += "    " + self.id + " ==> " + interface.linkid + " ==> " + self.getOtherDeviceOnInterface(interface.linkid).id + "\n"

        return s