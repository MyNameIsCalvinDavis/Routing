from Headers import *
import time

# This DHCP S/C implements most of the "MUST" functionality
# described in RFC2131, with the exception being retransmission
# of lost or dropped packets. Not all options are implemented.

# For example, DHCPNAK is not implemented as it is technically
# "SHOULD" functionality per 3.1.4, so the server silently
# rejects invalid requests instead

# https://datatracker.ietf.org/doc/html/rfc2131#section-2.2
# https://www.netmanias.com/en/post/techdocs/5998/dhcp-network-protocol/understanding-the-basic-operations-of-dhcp
# https://avocado89.medium.com/dhcp-packet-analysis-c84827e162f0

# TODO: Implement DHCP Client retransmission / timeouts
# TODO: DHCP Snooping
# TODO: Verify lease expiration


# Not a Device, just deals with DHCP functionality
# then returns output to the host / whatever it's inside of
class DHCPServer:
    def __init__(self, ip, nmask, haddr, DEBUG):
        self.ip = ip
        self.nmask = nmask
        self.leased_ips = {}
        self.lease_offer = 20
        self.id = haddr
        self.DEBUG = DEBUG
        
        # TODO Add DHCP NAK / etc messages
        
        # Keep track of states for ongoing client transactions,
        # client is deleted after DHCP ACK
        #self.client_msgtype = {}

    
    def handleRequestedOptions(self, data):
        """
        Receive and parse opts (a list of #s) from the client's option 55
        Return a dict with each option filled out
        Not all options are implemented

        See https://www.iana.org/assignments/bootp-dhcp-parameters/bootp-dhcp-parameters.xhtml#options
        """
        
        result = {}
        if not 55 in data["L3"]["Data"]["options"]:
            return result

        for opt in data["L3"]["Data"]["options"][55]: # TODO: What options can a client request?
            if opt == 1: # Subnet mask
                result[opt] = self.nmask
            if opt == 3: # Router Addr
                result[opt] = self.ip
            if opt == 6: # DNS Server
                result[opt] = "" # Not doing DNS
            if opt == 51: # Lease Offer
                result[opt] = self.lease_offer
            if opt == 54: # DHCP Server IP
                result[opt] = self.ip

        return result
                
    def generateIP(self):
        while True:
            x = "10.10.10." + str(random.randint(2, 254))
            if self.DEBUG: print("(DHCP)", self.id, "Finding an IP:", x, "for client")
            if not x in self.leased_ips:
                return x

    def handleDHCP(self, data): # Send (O)ffer

        # Process D(iscover) request
        if data["L3"]["Data"]["op"] == 1 and data["L3"]["Data"]["options"][53] == 1:  
            # Send DHCP Offer
            clientip = self.generateIP()

            # Check clients requested options & satisfy them, if any
            requested_options = self.handleRequestedOptions( data )

            # RFC2131 S4.3.1 Table 3
            # Server must send: 51      53      54      55 if applicable
            #                   Lease   MsgType SrvID   Requested Params
            server_options = {
                51: self.lease_offer,
                53: 2, # DHCP Offer
                54: self.ip # DHCP Server ID
            }

            options = mergeDicts(requested_options, server_options)

            # Broadcast (flags=0) a response (op=2) # TODO: Verify with table 4.3.1$3
            DHCP = createDHCPHeader(op=2, 
                    chaddr=data["L3"]["Data"]["chaddr"],
                    yiaddr=clientip,
                    options=options
                )
            p4 = makePacket_L4_UDP(67, 68)
            p3 = makePacket_L3(self.ip, "255.255.255.255", DHCP)
            
            # Check if the client wants the message broadcast or unicast
            p2 = makePacket_L2("IPv4", 
                    self.id, # From
                    MAC_BROADCAST if data["L3"]["Data"]["flags"] else data["L2"]["From"], # To
                    data["L2"]["FromLink"] # Onlink
                )

            #if data["L3"]["Data"]["flags"]:
            #    p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST, data["L2"]["FromLink"])
            #else:
            #    p2 = makePacket_L2("IPv4", self.id, data["L2"]["From"], data["L2"]["FromLink"])

            p = makePacket(p2, p3, p4)

            if self.DEBUG: print("(DHCP)", self.id, "received Discover from", data["L2"]["From"])
            if self.DEBUG: print("(DHCP)", self.id, "sending Offer to", data["L2"]["From"])
            if self.DEBUG == 2: print(p)
            return p, data["L2"]["FromLink"]

        # Process R(equest)
        elif data["L3"]["Data"]["op"] == 1 and data["L3"]["Data"]["options"][53] == 3:
            # Send a DHCP Ack
            
            # Client sent option 50, the requested / assigned IP
            if data["L3"]["Data"]["ciaddr"] == "0.0.0.0": # R(equest)
                yiaddr = data["L3"]["Data"]["options"][50]
            else: #R(enewal)
                yiaddr = data["L3"]["Data"]["ciaddr"]
            
            # Check clients requested options & satisfy them, if any
            requested_options = self.handleRequestedOptions( data )

            # RFC2131 S4.3.1 Table 3
            # Server must send: 51      53      54      55 if applicable
            #                   Lease   MsgType SrvID   Requested Params
            server_options = {
                51: self.lease_offer,
                53: 5, # DHCP ACK
                54: self.ip # DHCP Server ID
            }

            options = mergeDicts(requested_options, server_options)

            # Broadcast (flags=0) a response (op=2) # TODO: Verify with table 4.3.1$3
            DHCP = createDHCPHeader(op=2, 
                    chaddr=data["L3"]["Data"]["chaddr"],
                    yiaddr=yiaddr,
                    options=options
                )

            p4 = makePacket_L4_UDP(67, 68)
            p3 = makePacket_L3(self.ip, "255.255.255.255", DHCP)

            # Check if the client wants the message broadcast or unicast
            p2 = makePacket_L2("IPv4", 
                    self.id, # From
                    MAC_BROADCAST if data["L3"]["Data"]["flags"] else data["L2"]["From"], # To
                    data["L2"]["FromLink"] # Onlink
                )
            p = makePacket(p2, p3, p4)

            if self.DEBUG: print("(DHCP)", self.id, "received Request from", data["L2"]["From"])
            if self.DEBUG: print("(DHCP)", self.id, "sending Ack to", data["L2"]["From"])
            if self.DEBUG == 2: print(p)
            
            # IP: (chaddr, lease_offer, lease_give_time)
            # Update leased IP
    
            
            # If client defines a client identifier (61), use it
            # otherwise clientID is chaddr + IP
            # TODO: Find out how this table is actually formatted
            if 61 in data["L3"]["Data"]["options"]:
                self.leased_ips[yiaddr] = (data["L3"]["Data"]["options"][61], self.lease_offer, time.time())
            else:
                combo = data["L2"]["From"] + yiaddr
                self.leased_ips[yiaddr] = (combo, self.lease_offer, time.time())

            return p, data["L2"]["FromLink"]

        else:
            if self.DEBUG: print(self.id, "Ignoring")

class DHCPClient:
    def __init__(self, haddr, interfaces, DEBUG):

        self.id = haddr
        self.interfaces = interfaces
        self.DEBUG = DEBUG
        
        self.requested_options = [1,3,6]
        
        # L3
        self.ip = ""
        self.nmask = ""
        self.gateway = ""
        self.offered_ip = ""
        self.lease = (-1, -1) # (leaseTime, time (s) received the lease)
        self.DHCP_FLAG = 0 # 0: No IP --- 1: Awaiting ACK --- 2: Received ACK & has active IP
        self.DHCP_MAC = ""
        self.DHCP_IP = ""
        self.gateway = ""
        self.current_tx = ""

    def handleDHCP(self, data):
        
        ######
        if self.DEBUG == 2: print("(DHCP)", self.id, "got", data)

        # Process O(ffer)
        if data["L3"]["Data"]["op"] == 2 and data["L3"]["Data"]["options"][53] == 2 and data["L3"]["Data"]["xid"] == self.current_tx:  
            # Send R(equest)
            
            if self.DEBUG: print("(DHCP)", self.id, "received DHCP Offer, sending Request (broadcast)")
            self.DHCP_FLAG = 1
            self.offered_ip = data["L3"]["Data"]["yiaddr"]
            self.DHCP_IP = data["L3"]["SIP"] if not 6 in data["L3"]["Data"]["options"] else data["L3"]["Data"]["options"][6]
            self.DHCP_MAC = data["L2"]["From"] # Not reliable if not on same network

            # RFC2131 S4.4.1 Table 5
            # Client must send: 50      53      54
            #                   AddrRq  MsgType SrvID                                
            options = {
                50: self.offered_ip,
                53: 3, # Request
                54: self.DHCP_IP, # DHCP siaddr
                55: self.requested_options # Same as before
            }

            DHCP = createDHCPHeader(chaddr=self.id, flags=1, options=options)

            p4 = makePacket_L4_UDP(68, 67)
            p3 = makePacket_L3("0.0.0.0", "255.255.255.255", DHCP)
            p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST)
            p = makePacket(p2, p3, p4)

            #self.current_tx = DHCP["xid"]
            return p, None

        # Process A(CK)
        elif data["L3"]["Data"]["op"] == 2 and data["L3"]["Data"]["options"][53] == 5 and data["L3"]["Data"]["xid"] == self.current_tx: 
            
            if 1 in self.requested_options:
                self.nmask = data["L3"]["Data"]["options"][1]
            if 3 in self.requested_options:
                self.gateway = data["L3"]["Data"]["options"][3]
            # if 6 in ... (DNS)

            self.ip = data["L3"]["Data"]["yiaddr"]
            self.lease = (data["L3"]["Data"]["options"][51], int(time.time()) )
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            self.DHCP_FLAG = 2
            self.current_xid = -1
            if self.DEBUG: print("(DHCP)", self.id, "received DHCP ACK from", data["L2"]["From"]+".", "New IP:", self.ip)
        else:
            if self.DEBUG: genericIgnoreMessage("DHCP", data["L2"]["From"])
            #if self.DEBUG: print(self.id, "ignoring DHCP", data["L2"]["From"])
        return None, None

    # Send D(iscover) or R(equest)
    def sendDHCP(self, context, onlink=None):
        if onlink == None:
            onlink = self.interfaces[0]
        
        # Send D(iscover)
        if context == "Init": 
            print("(DHCP)", self.id, "sending DHCP Discover")
            
            # RFC2131 S4.4.1 Table 5
            # Client must send: 53
            #                   MsgType
            options = {
                53: 1, # Discover
                55: self.requested_options
            }

            DHCP = createDHCPHeader(chaddr=self.id, options=options)
            
            p4 = makePacket_L4_UDP(68, 67)
            p3 = makePacket_L3("0.0.0.0", "255.255.255.255", DHCP) # MAC included
            p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST, onlink.id)
            p = makePacket(p2, p3, p4)

            self.current_tx = DHCP["xid"]
            return p, None
        
        # Send R(equest) renewal
        if context == "Renew":
            print("(DHCP)", self.id, "sending DHCP Request (Renewal)")

            # RFC2131 S4.4.1 Table 5
            # Client must send: 53
            #                   MsgType
            options = {
                53: 3, # Request
                55: self.requested_options
            }

            # Renew: ciaddr filled (NOT option 50)
            DHCP = createDHCPHeader(chaddr=self.id, ciaddr=self.ip, options=options)

            # Now that the IP is active, unicast to DHCP server
            p4 = makePacket_L4_UDP(68, 67)
            p3 = makePacket_L3(self.ip, self.DHCP_IP, DHCP)
            p2 = makePacket_L2("IPv4", self.id, self.DHCP_MAC)
            p = makePacket(p2, p3, p4)

            self.current_tx = DHCP["xid"]
            return p, None
