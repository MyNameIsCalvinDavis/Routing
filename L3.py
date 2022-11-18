from Device import *
from ARP import *
from DHCP import *
from Debug import Debug
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
        self.linkid_to_ip = {} # For getting the IP on an interface
        self.DHCP_FLAG = 0 # 0: No IP --- 1: Awaiting ACK --- 2: Received ACK & has active IP

        # Make ips always be a list, with ["0.0.0.0/32"] as default
        #if ips:
        #    for ip in self.ips:
        #        if 
        #else:   self.ips = ["0.0.0.0"]

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
        
        # Give this handler the ability to ask for an interface's IP
        self.ARPHandler = ARPHandler(self.id, self.links, self.DEBUG, ipfunc=self.getIP)
        
    async def handleData(self, data):
        """
        Handle data as a L3 device would. All this does is read the L2/L3 information
        and forward the data to the correct handler, depending on port / ethertype / etc
        
        :param data: See `Headers.makePacket()`, dict
        """
        if data["L2"]["To"] not in [self.id, MAC_BROADCAST]: # L2 destination check
            print(self.id, "got L2 frame, ignoring")
            return

        if data["L2"]["EtherType"] == "ARP": # L2 multiplexing
            #self.handleARP(data)
            await self.handleARP(data)
        
        elif data["L2"]["EtherType"] == "IPv4": # L3 multiplexing
            
            if data["L3"]["DIP"] not in [self.getIP(), IP_BROADCAST]:
                print(self.id, "ignoring data from", data["L3"]["SIP"])
                return

            #https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
            if data["L3"]["Protocol"] == "UDP": # 17

                # Handle UDP protocols

                # DHCP
                if data["L4"]["DPort"] in [67, 68]: # L4 multiplexing
                    self.handleDHCP(data)
                # elif...
                # elif...
                # elif...
                else:
                    if self.DEBUG: 
                        Debug(self.id, data["L4"]["DPort"], "not configured!", 
                            color="red", f=self.__class__.__name__
                        )
                    #if self.DEBUG: print("(Error)", self.id, "not configured for port", data["L4"]["DPort"])
            
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
            if not link in self.links:
                #self.ip = ("0.0.0.0", link.id)
                self.setIP("0.0.0.0", link.id)
                self.links.append(link)
            if not link in device.links:
                device.links.append(link)
                if isinstance(device, L3Device):
                    device.setIP("0.0.0.0", link.id)
                    device._associateIPsToLinks() # Possibly in need of a lock

        self._associateIPsToLinks()

    def _associateIPsToLinks(self):
        """
        Given self.links, associate each with the provided self.ips.
        If there are more links than IPs, each link gets associated
        with the default 0.0.0.0.
        """
        for i in range(len(self.links)):
            try:
                self.linkid_to_ip[self.links[i].id] = self.ips[i]
                #self.ip_to_linkid[self.ips[i]] = self.links[i].id
            except IndexError:
                self.linkid_to_ip[self.links[i].id] = "0.0.0.0"
                #self.ip_to_linkid[self.ips[i]] = self.links[0]
                self.ips.append("0.0.0.0")
    
    def getIP(self, linkID=None):
        """
        Return the IP for linkID. By default, return the first link's IP, good
        for single interface devices.

        :param linkID: optional, the ID of the desired link
        """

        if not linkID: linkID = self.links[0].id
        try: return self.linkid_to_ip[linkID]
        except: return None # For devices with no IP

    def setIP(self, val, linkID=None):
        """
        Set the IP of a link. By default, set the first link's IP, good for
        single interface devices.
        
        :param val: The IP to set
        :param linkID: optional, the ID of the desired link
        """

        assert isinstance(val, str)
        if not linkID: linkID = self.links[0].id
        self.linkid_to_ip[linkID] = val
        #self.ip_to_linkid[val] = linkID

    
    ###### DHCP

    # By default, a L3Device has DHCP Client functionality

    ## Send D(iscover) or R(equest)
    async def sendDHCP(self, context, onlink=None, timeout=5):
        p, link = self.DHCPClient.sendDHCP(context)
        #print("===", self.id, "using tx", p["L3"]["Data"]["xid"])
        self.send(p, link)

        # If timeout, block for that many seconds waiting for the event
        # representing a complete DHCP transaction
        now = time.time()
        if timeout:
            while (time.time() - now) < timeout:
                if self.checkEvent("DHCP"):
                    self.deleteEvent("DHCP")
                    return True
                await asyncio.sleep(0)
        return False
                
    def handleDHCP(self, data):
        p, link = self.DHCPClient.handleDHCP(data)

        # On DORA ACK, no packet is returned to send out
        if p: 
            self.send(p, link)
        else:
            self.fireEvent("DHCP")

            # Extract all of the goodies
            self.nmask = "255.255.255.255"
            self.gateway = ""

            if 1 in data["L3"]["Data"]["options"]:
                self.nmask = data["L3"]["Data"]["options"][1]
            if 3 in data["L3"]["Data"]["options"]:
                self.gateway = data["L3"]["Data"]["options"][3]

            #self.ip = data["L3"]["Data"]["yiaddr"]
            self.setIP(data["L3"]["Data"]["yiaddr"])

            self.lease = (data["L3"]["Data"]["options"][51], int(time.time()) )
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            self.DHCP_FLAG = 2
            self.current_xid = -1

class Host(L3Device):
    def __init__(self, ips=[], connectedTo=[], debug=1):
        self.id = "-H-" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id)

        # L3
        self.DHCPClient = DHCPClientHandler(self.id, self.links, self.DEBUG)
        #self.nmask = ""
        #self.gateway = ""
        #self.lease = (-1, -1) # (leaseTime, time (s) received the lease)
        #self.lease_left = -1
    
    async def _checkTimeouts(self):
        # DHCP
        try:
            if self.lease[0] >= 0:
                self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
                if self.DEBUG==2: 
                    Debug(self.id, "===", self.lease_left, "/", self.lease[0], 
                        f=self.__class__.__name__
                    )
                if self.lease_left <= 0.5 * self.lease[0] and self.DHCP_FLAG != 1:
                    #if self.DEBUG: print("(DHCP)", self.id, "renewing ip", self.getIP())
                    if self.DEBUG: 
                        Debug(self.id, "renewing ip", self.getIP(), color="green", 
                            f=self.__class__.__name__
                        )
                    self.DHCP_FLAG = 1
                    #print("(DHCP)", self.id, "renewing IP", self.getIP())
                    await self.sendDHCP("Renew")
        except: pass
        return 
                
    def handleDHCP(self, data):
        # A host will only respond to its transaction
        if data["L3"]["Data"]["xid"] == self.DHCPClient.current_tx:
            super().handleDHCP(data)
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

    async def handleData(self, data):
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
            #self.handleARP(data)
            await self.handleARP(data)
        
            """
            elif data["L2"]["EtherType"] == "IPv4": # L3 multiplexing
                
                # I just got an IP packet
                # Forward the packet to the respective link
                # based on my routing table
                # If I dont have that network, drop it and complain

                # TODO: Default gateways

                # IP should be in the form "x.x.x.x/y" or "x.x.x.x"
                to_ip = data["L3"]["DIP"]
                if ipaddress.ip_address(to_ip) in ipaddress.ip_network(to_ip, )
                pass
            """
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

        self.gateway = gateway

        print("DHCP IP INIT:", self.ips[0], self.ips, self.nmasks)
        self.DHCPServerHandler = DHCPServerHandler(self.ips[0], self.nmasks[0], self.id, self.gateway, debug)
        
    async def _checkTimeouts(self):
        # DHCP lease expiry check
        # IP: (chaddr, lease_offer, lease_give_time)
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

    def handleDHCP(self, data):
        if self.DEBUG:
            Debug(self.id, "got DHCP from " + Debug.colorID(data["L2"]["From"]), 
                color="green", f=self.__class__.__name__
            )
        #print(self.id, "got DHCP from", data["L2"]["From"])
        response, link = self.DHCPServerHandler.handleDHCP(data)
        self.send(response, link)
