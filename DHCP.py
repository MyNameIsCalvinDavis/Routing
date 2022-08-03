from Headers import *
import time

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

    def generateIP(self):
        while True:
            x = "10.10.10." + str(random.randint(2, 254))
            if self.DEBUG: print("(DHCP)", self.id, "Finding an IP:", x, "for client")
            if not x in self.leased_ips:
                #self.leased_ips.append(x)
                return x

    def handleDHCP(self, data): # O of DORA

        # Process D(iscover) request
        if data["L3"]["Data"]["op"] == 1 and data["L3"]["Data"][53] == 1:  
            # Send DHCP Offer
            clientip = self.generateIP()
            # Broadcast (flags=0) a response (op=2)
            DHCP = createDHCPHeader(op=2, chaddr=data["L3"]["Data"][61], yiaddr=clientip, options={
                    1:self.nmask, # Netmask
                    3:self.ip, # Router IP
                    6:"", # Not doing DNS
                    51: self.lease_offer,
                    53:2, # DHCP Offer
                    54:self.ip # DHCP Server identifier
                })

            p4 = makePacket_L4_UDP(67, 68)
            p3 = makePacket_L3(self.ip, "255.255.255.255", DHCP)
            
            # Check if the client wants the message broadcast or unicast
            if data["L3"]["Data"]["flags"]:
                p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST, data["L2"]["FromLink"])
            else:
                p2 = makePacket_L2("IPv4", self.id, data["L2"]["From"], data["L2"]["FromLink"])

            p = makePacket(p2, p3, p4)

            if self.DEBUG: print("(DHCP)", self.id, "received Discover from", data["L2"]["From"])
            if self.DEBUG: print("(DHCP)", self.id, "sending Offer to", data["L2"]["From"])
            if self.DEBUG == 2: print(p)
            #self.send(p, data["L2"]["FromLink"])
            return p, data["L2"]["FromLink"]

        # Process R(equest)
        elif data["L3"]["Data"]["op"] == 1 and data["L3"]["Data"][53] == 3:
            # Send a DHCP Ack
            
            if data["L3"]["Data"]["ciaddr"] == "0.0.0.0": # R(equest)
                yiaddr = data["L3"]["Data"][50]
            else:
                # For some reason, the client doesnt have to send option 50 here
                # and the server instead looks at ciaddr for the renewal
                yiaddr = data["L3"]["Data"]["ciaddr"]
                
            DHCP = createDHCPHeader(op=2, chaddr=data["L3"]["Data"][61], yiaddr=yiaddr, options={
                    1:self.nmask, # Netmask
                    3:self.ip, # Router IP
                    6:"", # Not doing DNS
                    51: self.lease_offer,
                    53:5, # DHCP Ack
                    54:self.ip # DHCP Server identifier
                }) # TODO: Add lease expriation / updating

            p4 = makePacket_L4_UDP(67, 68)
            p3 = makePacket_L3(self.ip, "255.255.255.255", DHCP)

            # Check if the client wants the message broadcast or unicast
            if data["L3"]["Data"]["flags"]:
                p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST, data["L2"]["FromLink"])
            else:
                p2 = makePacket_L2("IPv4", self.id, data["L2"]["From"], data["L2"]["FromLink"])

            p = makePacket(p2, p3, p4)

            if self.DEBUG: print("(DHCP)", self.id, "received Request from", data["L2"]["From"])
            if self.DEBUG: print("(DHCP)", self.id, "sending Ack to", data["L2"]["From"])
            if self.DEBUG == 2: print(p)
            #self.send(p, data["L2"]["FromLink"])
            return p, data["L2"]["FromLink"]

        else:
            if self.DEBUG: print(self.id, "Ignoring")

class DHCPClient:
    def __init__(self, haddr, interfaces, DEBUG):

        self.id = haddr
        self.interfaces = interfaces
        self.DEBUG = DEBUG
        
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
        if data["L3"]["Data"]["op"] == 2 and data["L3"]["Data"][53] == 2 and data["L3"]["Data"]["xid"] == self.current_tx:  
            
            if self.DEBUG: print("(DHCP)", self.id, "received DHCP Offer, sending Request (broadcast)")
            self.DHCP_FLAG = 1
            self.offered_ip = data["L3"]["Data"]["yiaddr"]
            self.DHCP_IP = data["L3"]["Data"][6]
            self.DHCP_MAC = data["L2"]["From"]

            # Send R(equest)
            # Broadcast by default (flags=1)
            DHCP = createDHCPHeader(chaddr=self.id, flags=1, options={
                50:self.offered_ip, # Client requesting this IP
                53:3, # Request
                54:self.DHCP_IP, # DHCP siaddr
                61:self.id, # Client MAC / ID
                # 55: [1, 3, 6, ...]
            })
            
            self.current_tx = DHCP["xid"]
            p4 = makePacket_L4_UDP(68, 67)
            p3 = makePacket_L3("0.0.0.0", "255.255.255.255", DHCP)
            p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST)
            
            p = makePacket(p2, p3, p4)
            #self.send(p)
            return p, None

        # Process A(CK)
        elif data["L3"]["Data"]["op"] == 2 and data["L3"]["Data"][53] == 5 and data["L3"]["Data"]["xid"] == self.current_tx: 

            self.gateway = data["L3"]["Data"][3]
            self.ip = data["L3"]["Data"]["yiaddr"]
            self.nmask = data["L3"]["Data"][1]
            self.lease = (data["L3"]["Data"][51], int(time.time()) )
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            self.DHCP_FLAG = 2
            self.current_xid = -1
            if self.DEBUG: print("(DHCP)", self.id, "received DHCP ACK from", data["L2"]["From"]+".", "New IP:", self.ip)
        else:
            if self.DEBUG: self.genericIgnoreMessage("IPv4", data["L2"]["From"])
            #if self.DEBUG: print(self.id, "ignoring DHCP", data["L2"]["From"])
        return None, None

    # Send D(iscover) or R(equest)
    def sendDHCP(self, context, onlink=None):
        if onlink == None:
            onlink = self.interfaces[0]
        
        # Send D(iscover)
        if context == "Init": 
            print("(DHCP)", self.id, "sending DHCP Discover")
            
            # (flags=1) Tell server to broadcast back, not unicast
            DHCP = createDHCPHeader(chaddr=self.id, options={
                61:self.id, # Client MAC / ID
                53:1 # Discover
                # 55: [1, 3, 6, ...]
            })

            self.current_tx = DHCP["xid"]

            p4 = makePacket_L4_UDP(68, 67)
            p3 = makePacket_L3("0.0.0.0", "255.255.255.255", DHCP) # MAC included
            p2 = makePacket_L2("IPv4", self.id, MAC_BROADCAST, onlink.id)
            p = makePacket(p2, p3, p4)
            #self.send(p)
            return p, None
        
        # Send R(equest)
        if context == "Renew":
            print("(DHCP)", self.id, "sending DHCP Request (Renewal)")

            # Renew: ciaddr filled (NOT option 50) (why not? who knows)
            DHCP = createDHCPHeader(chaddr=self.id, ciaddr=self.ip, options={
                53:3, # Request
                61:self.id, # Client MAC / ID
                # 55: [1, 3, 6, ...]
            })

            self.current_tx = DHCP["xid"]
            
            # Now that the IP is active, unicast to DHCP server
            p4 = makePacket_L4_UDP(68, 67)
            p3 = makePacket_L3(self.ip, self.DHCP_IP, DHCP)
            p2 = makePacket_L2("IPv4", self.id, self.DHCP_MAC)
            
            p = makePacket(p2, p3, p4)
            #self.send(p)
            return p, None
