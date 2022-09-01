from Device import *
from ARP import *
from DHCP import *
import asyncio
import random
from Debug import Debug



class L3Device(Device):
    def __init__(self, ips=[], connectedTo=[], debug=1, ID=None): # L3Device
        """
        A Device that operates primarily on L3. This class defines a standard handleData()
        function to be expanded upon. At the moment, all L3 devices handle the same way.

        :param connectedTo: List of Devices
        :param debug: See `Device.DEBUG`
        :param ID: Optionally a child class can provide its ID to be used with inits of some Handler, like DHCP or ARP
        """
        self.linkid_to_ip = {}

        # Make ips always be a list, with ["0.0.0.0"] as default
        if ips: self.ips = ips
        else:   self.ips = ["0.0.0.0"]
        if isinstance(self.ips, str): self.ips = [self.ips]

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
            
            #if data["L3"]["DIP"] != self.getIP() and data["L3"]["DIP"] != IP_BROADCAST: # L3 destination check
            if data["L3"]["DIP"] not in [self.getIP(), IP_BROADCAST]:
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
                #self.handleICMP(data)
                await self.handleICMP(data)
        else:
            if self.DEBUG: 
                Debug(self.id, "ignoring", data["L2"]["From"], 
                    color="yellow", f=self.__class__.__name__
                )
        
        return
    

    async def _checkTimeouts(self):
        return

    async def sendICMP(self, targetIP, onlinkID=None):
        """
        After DHCP, gateway IP is known
        Send an ARP looking for gateway's MAC, if not held
        R responds, now we have their MAC
        Create packet: L2, L3
        Send it
        Router receives it in handleICMP
            Is this to me (L2): yes
            Is the destination subnet in my routing table
                Yes: send it on that interface
                No: Send to default gateway
                Else: Drop packet

        Router sends to H2
        Packet is addressed to H2 over L3, not L2

        """
        return
        print(self.id, "ICMP init")
        if not onlinkID:
            onlinkID = self.interfaces[0].id
        
        try: self.gateway
        except:
            print(self.id, "DHCP not configured")

        print(self.id, "gateway:", self.gateway)
        # At this point, device knows gateway IP
        # Let's find its MAC
        print(self.id, "async sleep time")
        print(self.id, self.ARPHandler.mti)
        asyncio.sleep(4)
        print(self.id, self.ARPHandler.mti)
        
        
        # Given an IP:
        # If the IP is in our network:
            # Obtain the IP's MAC address via ARP
                # Send ARP, then set some flag
                # In checktimeouts, check this flags timeout (5s?)
            # Once a MAC has been obtained, send an ICMP packet to that MAC
            # If no MAC, assume failure. Retransmit?
        # If not:
            # Create the ICMP packet and send it to the gateway
            # ARP the gateway, send to gateway


        #p3 = makePacket_L3(self.getIP(), data["L3"]["SIP"], proto="ICMP")
        #p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST)
        #p = makePacket(p2, p3, p4)
        #self.send(p, onlinkID)
        
    def handleICMP(self, data):
        # Receive an ICMP packet
        # For now, just fire it back
        
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
            except IndexError:
                self.linkid_to_ip[self.links[i].id] = "0.0.0.0"
                self.ips.append("0.0.0.0")
    
    def getIP(self, linkID=None):
        """
        Return the IP for linkID. By default, return the first link's IP, good
        for single interface devices.

        :param linkID: optional, the ID of the desired link
        """

        if not linkID: linkID = self.links[0].id
        return self.linkid_to_ip[linkID]

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
                    return
                await asyncio.sleep(0)
        return
                
    def handleDHCP(self, data):
        p, link = self.DHCPClient.handleDHCP(data)

        # On DORA ACK, no packet is returned to send out
        if p: 
            self.send(p, link)
        else:
            self.fireEvent("DHCP")
            # Extract all of the goodies
            #print(self.id, "got ACK?", data)
            self.nmask = "255.255.255.255"
            self.gateway = "0.0.0.0"

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
        self.nmask = ""
        self.gateway = ""
        self.lease = (-1, -1) # (leaseTime, time (s) received the lease)
        self.lease_left = -1
        self.DHCP_FLAG = 0 # 0: No IP --- 1: Awaiting ACK --- 2: Received ACK & has active IP
        self.gateway = ""
    
    async def _checkTimeouts(self):
        # DHCP
        if self.lease[0] >= 0:
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            if self.DEBUG: 
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
        return 
                
    def handleDHCP(self, data):
        # A host will only respond to its transaction
        if data["L3"]["Data"]["xid"] == self.DHCPClient.current_tx:
            #print("===", self.id, "responding to", data["L2"]["From"], "\n",\
            #    "==My TX:", self.DHCPClient.current_tx, "incoming:", data["L3"]["Data"]["xid"])
            super().handleDHCP(data)
        else:
            
            #print("-----", self.id, "ignoring DHCP from", data["L2"]["From"], "\n",\
            #    "==My TX:", self.DHCPClient.current_tx, "incoming:", data["L3"]["Data"]["xid"])
            #print("-----", self.id, "ignoring DHCP from", data["L2"]["From"])

            #if self.DEBUG: print(self.id, "ignoring DHCP from", data["L2"]["From"])
            if self.DEBUG: 
                Debug(self.id, "ignoring DHCP from", data["L2"]["From"], 
                    color="yellow", f=self.__class__.__name__
                )

class Router(L3Device):
    def __init__(self, ips, connectedTo=[], debug=1):
        self.id = "=R=" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id)

    async def _checkTimeouts(self):
        return

class DHCPServer(L3Device):
    def __init__(self, ips, connectedTo=[], debug=1): # DHCPServer
        self.id = "=DHCP=" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id) # DHCPServer

        self.nmask = "255.255.255.0"
        #print("DHCP IP INIT:", self.ips[0], self.ips)
        self.DHCPServerHandler = DHCPServerHandler(self.ips[0], self.nmask, self.id, debug)
        
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
