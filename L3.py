from Device import *

class L3Device(Device):
    def __init__(self, ID=None, ips=[], connectedTo=[], debug=1): # L3Device
        """
        A Device that operates primarily on L3. This class defines a standard handleData()
        function to be expanded upon. At the moment, all L3 devices handle the same way.

        :param connectedTo: List of Devices
        :param debug: See `Device.DEBUG`
        :param ID: Optionally a child class can provide its ID to be used with inits of some Handler, like DHCP or ARP
        """
        if isinstance(ips, str): ips = [ips]
        
        self.ips = []               # 192.168.0.1
        self.nmasks = []            # 255.255.255.0
        self.cidr_nmasks = []       # 24
        for item in ips:
            l = item.split("/")
            self.ips.append(l[0])
            self.cidr_nmasks.append(l[1])
            netmask = '.'.join([str((0xffffffff << (32 - int(l[1])) >> i) & 0xff) for i in [24, 16, 8, 0]])
            self.nmasks.append(netmask)
        super().__init__(connectedTo, debug, ID) # L3Device
        
        
    def handleData(self, data, oninterface):
        """
        Handle data as a L3 device would. All this does is read the L2/L3 information
        and forward the data to the correct handler, depending on port / ethertype / etc
        
        :param data: See `Headers.makePacket()`, dict
        """
        
        if not oninterface:
            oninterface = self.interfaces[0]

        if data["L2"]["To"] not in [self.id, MAC_BROADCAST]: # L2 destination check
            print(self.id, "got L2 frame not for me, ignoring")
            return

        if data["L2"]["EtherType"] == "ARP": # L2 multiplexing
            self.handleARP(data, oninterface)

        
        # ===================================================

        elif data["L2"]["EtherType"] == "IPv4": # L3 multiplexing
            
            #if data["L3"]["DIP"] not in [self.getIP(data["L2"]["To"]), IP_BROADCAST]:
            if data["L3"]["DIP"] not in [oninterface.ip, IP_BROADCAST]:

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
                # await self.handleICMP(data, oninterface)
                self.handleICMP(data, oninterface)
        else:
            if self.DEBUG: 
                Debug(self.id, "ignoring", data["L2"]["From"], data["L2"]["EtherType"],
                    color="yellow", f=self.__class__.__name__
                )
        
        return
    
    def _checkTimeouts(self):
        return

    def sendICMP(self, targetIP, oninterface=None, timeout=5):
        if not oninterface:
            oninterface = self.interfaces[0]
        if not oninterface.gateway:
            raise ValueError(self.id + " has no gateway; configure or use DHCP")
        if not self.getIP():
            raise ValueError(self.id + " has no IP; configure or use DHCP")
        if self.DEBUG:   
            Debug(self.id, "Initialize sendICMP()",
                color="green", f=self.__class__.__name__
            )


        # Grab the targetID:
        # - If on our subnet, grab the targetIP ID
        # - If not, grab the gateway ID
        if ipaddress.ip_address(targetIP) in ipaddress.IPv4Network(oninterface.ip + "/" + oninterface.nmask, strict=False):
            if targetIP in oninterface.ARPHandler.arp_cache:
                targetID = oninterface.ARPHandler.arp_cache[targetIP]
            else:
                Debug(self.id, targetIP, "(same subnet) not in local ARP cache, sending ARP",
                    color="yellow", f=self.__class__.__name__
                )

                # Have a thread manage the ARP connection independent from this thread
                targetID = [None]
                x = threading.Thread(target=self.sendARP, args=(targetIP, oninterface), kwargs={"result":targetID})
                x.start()
                x.join() # Block and wait for the thread to finish
                targetID = targetID[0]

        else: # Not in subnet
            if oninterface.gateway in oninterface.ARPHandler.arp_cache:
                targetID = oninterface.ARPHandler.arp_cache[targetIP]
            else:
                Debug(self.id, targetIP, "(different subnet) not in local ARP cache, ARPing gateway", oninterface.gateway,
                    color="yellow", f=self.__class__.__name__
                )
                gateway_ip = oninterface.gateway.split("/")[0]
                #targetID = await self.sendARP(gateway_ip, oninterface)


                # Have a thread manage the ARP connection independent from this thread
                targetID = [None]
                x = threading.Thread(target=self.sendARP, args=(gateway_ip, oninterface), kwargs={"result":targetID})
                x.start()
                x.join() # Block and wait for the thread to finish
                targetID = targetID[0]

        if not targetID: # On failed ARP
            Debug(self.id + " ICMP Failed - could not reach " + targetIP,
                color="red", f=self.__class__.__name__
            )
            return False
        
        # Send the ICMP request
        p = oninterface.ICMPHandler.sendICMP(targetIP, targetID)
        self.send(p, oninterface)
         
        # Internally:
        # Check whether or not the target ip has been populated with an ID (MAC)
        now = time.time()
        if timeout:
            while (time.time() - now) < timeout:
                if oninterface.ICMPHandler.icmp_table[p["L3"]["Data"]["identifier"]]:
                    # ICMP Response received!
                    del oninterface.ICMPHandler.icmp_table[p["L3"]["Data"]["identifier"]]
                    return True
        
        if self.DEBUG:
            Debug(self.id, "ICMP timeout for", targetIP,
                color="red", f=self.__class__.__name__
            )
        del oninterface.ICMPHandler.icmp_table[p["L3"]["Data"]["identifier"]]
        return False
        
    def handleICMP(self, data, oninterface=None):
        if not oninterface:
            oninterface = self.interfaces[0]
        
        # We'll only ever get a request, and for now we don't care about its data
        p = oninterface.ICMPHandler.handleICMP(data)

        if p: # Got a request
            self.send(p, oninterface)

    def _initConnections(self, connectedTo):
        """
        Create a link between me and every device in connectedTo, and vice versa.
        Upon forming a link, a device now has an interface and an IP. Same as L2Device,
        just that we now also associate IPs with links.

        :param connectedTo: A list of Devices
        """
        for device in connectedTo:
            link = Link([self, device])
            my_interface = Interface(link, "0.0.0.0", self.id)
            your_interface = Interface(link, "0.0.0.0", device.id)
            
            my_interface.DHCPClient = DHCPClientHandler(self.id, link.id, debug=self.DEBUG)
            my_interface.ICMPHandler = ICMPHandler(self.id, link.id, "0.0.0.0", None, debug=self.DEBUG)
            my_interface.ARPHandler = ARPHandler(self.id, link.id, "0.0.0.0", debug=self.DEBUG)

            if not my_interface in self.interfaces:
                self.interfaces.append(my_interface)
            if not your_interface in device.interfaces:
                device.interfaces.append(your_interface)
                if isinstance(device, L3Device):
                    your_interface.DHCPClient = DHCPClientHandler(device.id, link.id, debug=device.DEBUG)
                    your_interface.ICMPHandler = ICMPHandler(device.id, link.id, "0.0.0.0", None, debug=device.DEBUG)
                    your_interface.ARPHandler = ARPHandler(device.id, link.id, "0.0.0.0", debug=device.DEBUG)
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
                self.interfaces[i].nmask = self.nmasks[i]
                self.interfaces[i].ICMPHandler.ip = self.ips[i]
                self.interfaces[i].ICMPHandler.nmask = self.nmasks[i]
                self.interfaces[i].ARPHandler.ip = self.ips[i]
            except IndexError:
                self.interfaces[i].ip = "0.0.0.0"
                self.interfaces[i].nmask = None
                self.interfaces[i].ICMPHandler.ip = "0.0.0.0"
                self.interfaces[i].ICMPHandler.nmask = None
                self.interfaces[i].ARPHandler.ip = "0.0.0.0"
                self.ips.append("0.0.0.0")
                self.nmasks.append(None)

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
        single interface devices. Also update the internal handler IPs of the interface.
        
        :param val: The IP to set
        :param linkID: optional, the ID of the desired link
        """
        
        assert isinstance(interface, Interface)
        assert isinstance(val, str)
        
        if not interface:
            interface = self.interfaces[0]
        
        interface.ip = val
        interface.ICMPHandler.ip = val
        interface.ARPHandler.ip = val
        interface.DHCPClient.ip = val

# TODO: Associate DHCP info (lease, mask, gateway, etc) per interface instead of per device
class Host(L3Device):
    def __init__(self, ips=[], connectedTo=[], debug=1):
        self.id = "-H-" + str(random.randint(10000, 99999999))
        super().__init__(self.id, ips, connectedTo, debug)
        self.lthread.start()

    def _checkTimeouts(self):

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
                        self.sendDHCP("Renew")
        except: pass
        return 
                
    ## Send D(iscover) or R(equest)
    def sendDHCP(self, context, oninterface=None, timeout=5):
        if not oninterface:
            oninterface = self.interfaces[0]
            
        # Internally:
        # Have a flag set for what stage the DHCP client is on, see DHCPClientHandler.DHCP_FLAG
        p = oninterface.DHCPClient.sendDHCP(context)
        self.send(p, oninterface)

        now = time.time()
        if timeout:
            while (time.time() - now) < timeout:
                if oninterface.DHCPClient.DHCP_FLAG == 2:
                    # IP received / renewed!
                    return True


        if self.DEBUG: 
            Debug(self.id, "DHCP timeout",
                color="red", f=self.__class__.__name__
            )
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
    def __init__(self, ips, connectedTo=[], default_route=None, debug=1):
        self.id = "=R=" + str(random.randint(10000, 99999999))
        self.default_route = default_route
        super().__init__(self.id, ips, connectedTo, debug)
        
        assert len(ips) == len(connectedTo)

        # Check to see if targetIP is in my subnet
        #if ipaddress.ip_address(targetIP) in ipaddress.IPv4Network(oninterface.ip + "/" + oninterface.nmask, strict=False):
        
        # Establish directly connected networks 
        self.routing_table = []
        for index, item in enumerate(ips):
            network_obj = ipaddress.IPv4Network(item, strict=False)
            # no.exploded = "x.x.x.0/y"
            # no.network_address.exploded = "x.x.x.0"
            # no.prefixlen = 24
            # no.netmask.exploded = "255.255.255.0"
            
            # Could be an address but we're making it a network
            dest_addr = ipaddress.ip_network(self.ips[index] + "/32")
            network_addr = ipaddress.ip_network(self.ips[index] + "/" + self.cidr_nmasks[index], strict=False)

            routeL = ("L", dest_addr, self.interfaces[index])
            routeC = ("C", network_addr, self.interfaces[index])

            self.routing_table.append(routeL)
            self.routing_table.append(routeC)

        self.lthread.start()
    
    def addRoute(self, route):
        # For now we only do S(tatic) routes
        # ("S", "192.168.1.2/24", "192.162.1.1/24", outgoing_interface)
        # Type  Destination       NextHop           OI
        assert route[0] == "S"
        assert isinstance(route[1], str)
        assert isinstance(route[2], str)
        assert isinstance(route[3], Interface)
        
        data = ("S", ip.ipaddress.IPv4Network(route[1], strict=False), ip.ipaddress.IPv4Network(route[2], strict=False), route[3])
        self.routing_table.append(data)


    def handleData(self, data, oninterface):
        """
        A router will directly interpret L2 data addressed to it, and will route
        all L3 data, including L3 data addressed to itself.
        
        Some relevant info on routing table construction:
        https://www.ciscopress.com/articles/article.asp?p=2756479&seqNum=6
        https://docs.oracle.com/cd/E36784_01/html/E37474/ipplan-43.html
        https://learningnetwork.cisco.com/s/question/0D53i00000Ksx63CAB/what-is-a-local-route

        :param data: See `Headers.makePacket()`, dict
        """
        
        if not oninterface:
            oninterface = self.interfaces[0]

        if data["L2"]["To"] not in [self.id, MAC_BROADCAST]: # L2 destination check
            print(self.id, "got L2 frame not for me, ignoring")
            return

        if data["L2"]["EtherType"] == "ARP": # L2 multiplexing
            self.handleARP(data, oninterface)
        
        # ===================================================
        
        elif data["L2"]["EtherType"] == "IPv4": # L3 multiplexing
            """
            - Sort the table by prefixlength
            - To match an incoming ip on the routing table:
            - For through the sorted routing table and find the first match
                - if match is on a directly connected network (C)
                    - check if in arp table, arp target, send to target
                - elif match is on my IP (L)
                    - super().handleData()
                - else
                    if match.nexthop in ARP cache, etc. etc. etc
                    else: ARP first then send
                - else?
                    drop packet
            """

            self.routing_table = sorted(self.routing_table, key=lambda x: ipaddress.ip_network(x[1], strict=False).prefixlen)
            for route in self.routing_table:
                dip = ipaddress.ip_address(data["L3"]["DIP"])
                if dip in route[1]: # Found a match
                    if self.DEBUG == 2:
                        Debug(self.id, "found a matching path for", dip, "on route", route,
                            color = "blue", f=self.__class__.__name__
                        )

                    if route[0] == "L": # Packet was send to me (router) directly
                        pass
                    elif route[0] == "C": # Packet is going to a directly connected network
                        # ("C", DST_NTWK, Interface)

                        # Is the DIP in the outgoing interface's arp cache?
                        if data["L3"]["DIP"] in route[2].ARPHandler.arp_cache: # If in my ARP cache, send
                            data["L2"]["From"] = self.id
                            data["L2"]["To"] = route[2].ARPHandler.arp_cache[ data["L3"]["DIP"] ]
                            self.send(data, route[2])

                        else: # Else ARP targetIP
                            targetID = [None]
                            x = threading.Thread(target=self.sendARP, args=(data["L3"]["DIP"], route[2]), kwargs={"result":targetID})
                            x.start()
                            x.join() # Block and wait for the thread to finish
                            targetID = targetID[0]

                            if targetID:
                                data["L2"]["From"] = self.id
                                data["L2"]["To"] = targetID
                                if self.DEBUG:
                                    Debug(self.id, "Forwarding ICMP packet to", data["L3"]["DIP"],
                                        color = "green", f=self.__class__.__name__
                                    )
                                self.send(data, route[2])
                                return True
                            else:
                                Debug(self.id, "ARP failed, dropping packet",
                                    color="red", f=self.__class__.__name__    
                                )
                            return False
                    """
                    elif route[0] == "S": # Needs to be routed forward to nexthop
                        #if data["L3"]["DIP"] in oninterface.arp_cache:
                        if route[2] in oninterface.arp_cache:
                            
                            #p2 = makePacket_L2("IPv4", self.id, oninterface.arp_cache[ data["L3"]["DIP"] ])
                            #p = makePacket(p2)

                            data["L2"]["From"] = self.id
                            data["L2"]["To"] = oninterface.arp_cache[ route[2] ]
                            self.send(data, route[3])
                            return True
                        else: # Send ARP
                            #targetID = await self.sendARP(route[2], "aaaaa")
                            targetID = -1
                            raise
                            if targetID:
                                #p2 = makePacket_L2("IPv4", self.id, targetID)
                                #p = makePacket(p2)
                                data["L2"]["From"] = self.id
                                data["L2"]["To"] = oninterface.arp_cache[ route[2] ]
                                self.send(data, route[3])
                                return True
                            else:
                                Debug(self.id, "ARP failed, dropping packet",
                                    color="red", f=self.__class__.__name__    
                                )
                            return False
                    """
                    else:
                        Debug(self.id, "No matching route type, dropping packet",
                            color="red", f=self.__class__.__name__    
                        )
            else:
                Debug(self.id, "Failed to find a match for packet, dropping",
                    color="yellow", f=self.__class__.__name__    
                )
                        

            pass           

class DHCPServer(L3Device):
    def __init__(self, ips, gateway, connectedTo=[], debug=1): # DHCPServer
        self.id = "=DHCP=" + str(random.randint(10000, 99999999))

        # TODO: Move stuff to Interface class, including DHCP Server info?
        self.gateway = gateway

        super().__init__(self.id, ips, connectedTo, debug) # DHCPServer

        self.DHCPServerHandler = DHCPServerHandler(self.ips[0], self.nmasks[0], self.id, self.gateway, debug, self.interfaces)
        self.lthread.start()
    def _checkTimeouts(self):
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
        #if self.DEBUG:
        #    Debug(self.id, "got DHCP from " + Debug.colorID(data["L2"]["From"]), 
        #        color="green", f=self.__class__.__name__
        #    )
        response = self.DHCPServerHandler.handleDHCP(data, oninterface)
        self.send(response, oninterface)

