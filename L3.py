from Device import *
from ARP import *
from DHCP import *
from Debug import Debug
import L2
from Headers import removeHostBits
import asyncio
import random
import ipaddress

class L3Device(Device):
    def __init__(self, ips=[], connectedTo=[], debug=1, ID=None): # L3Device
        """
        A Device that operates primarily on L3. This class defines a standard handleData()
        function to be expanded upon. At the moment, all L3 devices handle the same way.

        :param connectedTo: List of Devices
        :param debug: See `Device.DEBUG`
        :param ID: Optionally a child class can provide its ID to be used with inits of some Handler, like DHCP or ARP
        """
        if isinstance(ips, str): ips = [ips]

        self.ips = []
        self.nmasks = []
        self.cidr_nmasks = []
        for item in ips:
            l = item.split("/")
            self.ips.append(l[0])
            self.cidr_nmasks.append(l[1])
            netmask = '.'.join([str((0xffffffff << (32 - int(l[1])) >> i) & 0xff) for i in [24, 16, 8, 0]])

            # TODO Use header func here
            self.nmasks.append(netmask)
        super().__init__(connectedTo, debug, ID) # L3Device
        
        self.ARPHandler = ARPHandler(self.id, self.interfaces, self.DEBUG, ipfunc=self.getIP)
        
    async def handleData(self, data, oninterface):
        """
        Handle data as a L3 device would. All this does is read the L2/L3 information
        and forward the data to the correct handler, depending on port / ethertype / etc
        
        :param data: See `Headers.makePacket()`, dict
        """
        if data["L2"]["To"] not in [self.id, MAC_BROADCAST]: # L2 destination check
            print(self.id, "got L2 frame not for me, ignoring")
            return

        if data["L2"]["EtherType"] == "ARP": # L2 multiplexing
            await self.handleARP(data)
        
        # ===================================================

        elif data["L2"]["EtherType"] == "IPv4": # L3 multiplexing
            
            
            #if data["L3"]["DIP"] not in [self.getIP(data["L2"]["To"]), IP_BROADCAST]:
            if data["L3"]["DIP"] not in [oninterface.ip, IP_BROADCAST]:
                print(self.getIP(data["L2"]["To"]))
                print(data)
                print(self.id, "ignoring data from", data["L3"]["SIP"])
                return
            
            #https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
            if data["L3"]["Protocol"] == "UDP": # 17

                # Handle UDP protocols

                # DHCP
                if data["L4"]["DPort"] in [67, 68]: # L4 multiplexing
                    self.handleDHCP(data, oninterface)
                # elif...
                # elif...
                # elif...
                else:
                    if self.DEBUG: 
                        Debug(self.id, data["L4"]["DPort"], "not configured!", 
                            color="red", f=self.__class__.__name__
                        )
            
            elif data["L3"]["Protocol"] == "ICMP": # 1
                await self.handleICMP(data)
        else:
            if self.DEBUG: 
                Debug(self.id, "ignoring", data["L2"]["From"], data["L2"]["EtherType"],
                    color="yellow", f=self.__class__.__name__
                )
        
        return
    

    async def _checkTimeouts(self):
        return

    async def sendICMP(self, targetIP, onlinkID=None):

        if not onlinkID:
            onlinkID = self.links[0].id

        try: self.gateway
        except:
            raise ValueError(self.id + " has no gateway; configure or use DHCP")
        
        if not self.getIP():
            raise ValueError(self.id + " has no IP; configure or use DHCP")

        # We know that we have a gateway and an IP
        # So construct a packet with ICMP stuff
        
        # L3: SIP: Me, DIP: targetIP, proto=ICMP
        # L2: 
            # If on the same subnet,
                # If we have this IPs ID already, L2 to that device ID
                # If not, ARP first (timeout) then L2 to the device ID
            # If not
                # If we have gateway ID: Send to gateway ID
                # If not, ARP gateway (timeout), then send to gateway ID
        
        # For now, assume always on another subnet
        # And always ARP the gateway
        
        #if targetIP not in self.ARPHandler.arp_cache:
        #    # Send an ARP Request to the targetIP, blocking
        #    x = await self.sendARP(targetIP)
        
        
        # ARP the gateway
        print("Sending ARP")
        if await self.sendARP(self.gateway): # Success
            p2 = makePacket_L2("IPv4", self.id, self.ARPHandler.arp_cache[self.gateway] )
        else: # Failure
            raise ValueError("ICMP Failed - no gateway")
        
        p3 = makePacket_L3(self.getIP(), targetIP, proto="ICMP")
        p = makePacket(p2, p3)

        # Send the ICMP packet to gateway
        print(self.id, "sending ICMP to gateway @", self.gateway)
        self.send(p, onlinkID)

        return
        
    def handleICMP(self, data):
        # Receive an ICMP packet
        # For now, just fire it back
        
        print(self.id, "got ICMP data from", data["L2"]["From"])
        return
        #p3 = makePacket_L3(self.data["L3"]["DIP"], data["L3"]["SIP"], proto="ICMP")
        #p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST)
        #p = makePacket(p2, p3, p4)

        #self.send(p, data["L2"]["FromLink"]


    def _initConnections(self, connectedTo):
        """
        Create a link between me and every device in connectedTo, and vice versa.
        Upon forming a link, a device now has an interface and an IP. Same as L2Device,
        just that we now also associate IPs with links.

        :param connectedTo: A list of Devices
        """
        for device in connectedTo:
            link = Link([self, device])
            my_interface = Interface(link, "0.0.0.0")
            your_interface = Interface(link, "0.0.0.0")
            
            my_interface.DHCPClient = DHCPClientHandler(self.id, debug=1)

            if not my_interface in self.interfaces:
                self.interfaces.append(my_interface)
            if not your_interface in device.interfaces:
                device.interfaces.append(your_interface)
                if isinstance(device, L3Device):
                    your_interface.DHCPClient = DHCPClientHandler(device.id, debug=1)
                    device._associateIPsToInterfaces() # Possibly in need of a lock

        self._associateIPsToInterfaces()

    def _associateIPsToInterfaces(self):
        """
        Associate all of our new Interfaces with the provided self.ips.
        If there are more interfaces than IPs, each interface gets 0.0.0.0
        """
        for i in range(len(self.interfaces)):
            try:
                self.interfaces[i].ip = self.ips[i]      
            except IndexError:
                self.interfaces[i].ip = "0.0.0.0"
                self.ips.append("0.0.0.0")

    def getIP(self, ID=None):
        """
        Return the IP for linkID or interfaceID. By default, return the first interface's IP, good
        for single interface devices.

        :param linkID: optional, the ID of the desired link
        """
        
        # Default, no provided interface
        if not ID:
            ID = self.interfaces[0].id

        # User provided an interface ID
        if "_I_" in ID:
            for interface in self.interfaces:
                if ID == interface.id:
                    return interface.ip
            else:
                raise ValueError(self.id + " getIP did not find an ip for interface " + ID)
        
        # User provided a link ID
        elif "[L]" in ID:
            for interface in self.interfaces:
                if interface.linkid == ID:
                    return interface.ip
            else:
                raise ValueError(self.id + " getIP did not find an ip for link " + ID)

        else:
            raise ValueError(self.id + " Can only pass in LinkIDs or interfaceIDs to getIP, not " + ID)

    def setIP(self, val, interface=None):
        """
        Set the IP of an interface. By default, set the first link's IP, good for
        single interface devices.
        
        :param val: The IP to set
        :param linkID: optional, the ID of the desired link
        """
        
        assert isinstance(interface, L2.Interface)
        assert isinstance(val, str)
        
        if not interface:
            interface = self.interfaces[0]
        
        interface.ip = val
        #for i in self.interfaces:
        #    if interface.id == i.id:
        #        interface.ip = val
        #        return True
        #else:
        #    print(self.id, "setIP did not find an interface for", val, "interfaces:", self.interfaces)
        #    raise

# TODO: Associate DHCP info (lease, mask, gateway, etc) per interface instead of per device
class Host(L3Device):
    def __init__(self, ips=[], connectedTo=[], debug=1):
        self.id = "-H-" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id)

    async def _checkTimeouts(self):

        # DHCP
        try: # TODO Clean up try
            for interface in self.interfaces:
                if interface.DHCPClient.lease[0] >= 0:
                    interface.DHCPClient.lease_left = (interface.DHCPClient.lease[0] + interface.DHCPClient.lease[1]) - int(time.time())
                    if self.DEBUG == 2: 
                        Debug(self.id, "===", interface.DHCPClient.lease_left, "/", interface.DHCPClient.lease[0], 
                            f=self.__class__.__name__
                        )
                    if interface.DHCPClient.lease_left <= 0.5 * interface.DHCPClient.lease[0] and interface.DHCPClient.DHCP_FLAG != 1:
                        if self.DEBUG: 
                            Debug(self.id, "renewing ip", self.getIP(), color="green", 
                                f=self.__class__.__name__
                            )
                        interface.DHCPClient.DHCP_FLAG = 1
                        await self.sendDHCP("Renew")
        except: pass
        return 
                
    ## Send D(iscover) or R(equest)
    async def sendDHCP(self, context, oninterface=None, timeout=5):
        # Internally:
        # Have a flag set for what stage the DHCP client is on, see DHCPClientHandler.DHCP_FLAG
        if not oninterface:
            oninterface = self.interfaces[0]
            
        p = oninterface.DHCPClient.sendDHCP(context)
        self.send(p, oninterface)

        now = time.time()
        if timeout:
            while (time.time() - now) < timeout:
                if oninterface.DHCPClient.DHCP_FLAG == 2:
                    # IP received / renewed!
                    return True
        return False
                
    def handleDHCP(self, data, oninterface):
        # Get interface for the incoming data
        
        if data["L3"]["Data"]["xid"] == oninterface.DHCPClient.current_tx:
            p = oninterface.DHCPClient.handleDHCP(data, oninterface)
            # On DORA ACK, no packet is returned to send out
            if p: 
                self.send(p, oninterface)
            else:
                # Extract all of the goodies
                oninterface.nmask = "255.255.255.255"
                oninterface.gateway = ""

                if 1 in data["L3"]["Data"]["options"]:
                    oninterface.nmask = data["L3"]["Data"]["options"][1]
                if 3 in data["L3"]["Data"]["options"]:
                    oninterface.gateway = data["L3"]["Data"]["options"][3]

                self.setIP(data["L3"]["Data"]["yiaddr"], oninterface)

                oninterface.DHCPClient.lease = (data["L3"]["Data"]["options"][51], int(time.time()) )
                oninterface.DHCPClient.lease_left = (oninterface.DHCPClient.lease[0] + oninterface.DHCPClient.lease[1]) - int(time.time())
                oninterface.DHCPClient.DHCP_FLAG = 2
                oninterface.DHCPClient.current_xid = -1
        else:
            if self.DEBUG: 
                Debug(self.id, "ignoring DHCP from", data["L2"]["From"], 
                    color="yellow", f=self.__class__.__name__
                )

class Router(L3Device):
    def __init__(self, ips, connectedTo=[], debug=1):
        self.id = "=R=" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id)
        
        # After super(), we have:
        # ips [x.x.x.x/y, x.x.x.x/y]
        # self.ips [x.x.x.x, x.x.x.x]
        # self.nmasks [y, y]
        # self.links [...]
        
        # Make a static routing table for ip/m:linkid association
        self.routing_table = {}
        for index, item in enumerate(ips):
            self.routing_table[item] = self.links[index]

    async def handleData(self, data, oninterface):
        """
        Unlike an L3 Device, a router doesn't usually respond to or interact with hosts
        directly, it just sends them to another network.
        
        :param data: See `Headers.makePacket()`, dict
        """
        if data["L2"]["To"] not in [self.id, MAC_BROADCAST]: # L2 destination check
            print(self.id, "got L2 frame, ignoring")
            return
        
        # TODO Consider moving this code to the listener
        if data["L2"]["EtherType"] == "ARP": # L2 multiplexing
            await self.handleARP(data)
        else:
            if self.DEBUG: 
                Debug(self.id, "ignoring", data["L2"]["From"], data["L2"]["EtherType"],
                    color="yellow", f=self.__class__.__name__
                )
        
        return

class DHCPServer(L3Device):
    def __init__(self, ips, gateway, connectedTo=[], debug=1): # DHCPServer
        self.id = "=DHCP=" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id) # DHCPServer

        # TODO: Move stuff to Interface class, including DHCP Server info?
        self.gateway = gateway

        self.DHCPServerHandler = DHCPServerHandler(self.ips[0], self.nmasks[0], self.id, self.gateway, debug, self.interfaces)
        
    async def _checkTimeouts(self):
        # DHCP lease expiry check
        del_ips = []
        for k, v in self.DHCPServerHandler.leased_ips.items():
            time_left = (v[2] + v[1]) - int(time.time())
            if time_left <= 0:
                # For now, just delete the entry. TODO: Clean up entry deletion procedure per RFC
                # Mark the entry as deleted
                del_ips.append(k)
        return 

        # Then, actually delete it
        if del_ips:
            for key in del_ips: del self.DHCPServerHandler.leased_ips[k]
            if self.DEBUG: print("(DHCP)", self.id, "deleted entries from lease table")

    def handleDHCP(self, data, oninterface):
        if self.DEBUG:
            Debug(self.id, "got DHCP from " + Debug.colorID(data["L2"]["From"]), 
                color="green", f=self.__class__.__name__
            )
        response = self.DHCPServerHandler.handleDHCP(data, oninterface)
        self.send(response, oninterface)
