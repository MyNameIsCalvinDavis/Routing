from Headers import *
from Debug import *
import ipaddress

class ICMPHandler:
    def __init__(self, ID, linkid, ip, nmask, debug=1):
        self.DEBUG = debug
        self.id = ID

        # If the "parent" ip is ever changed, it should be done with their setIP()
        # function, which will manually update these variables
        self.ip = ip
        self.nmask = nmask
        
        # Used to keep track of outgoing ICMP connections
        self.icmp_table = {}
    
    def sendICMP(self, targetIP, targetID):
        # We take in targetID because we first ARP before calling this function,
        # and must construct the L2 frame

        ICMP = createICMPHeader(8)
        p3 = makePacket_L3(self.ip, targetIP, proto="ICMP", data=ICMP)
        p2 = makePacket_L2("IPv4", self.id, targetID)
        p = makePacket(p2, p3)

        self.icmp_table[ICMP["identifier"]] = False

        if self.DEBUG:
            Debug(self.id, "sending ICMP to", targetIP,
                color="green", f=self.__class__.__name__
            )
        return p

    def handleICMP(self, data):
        if data["L3"]["Data"]["type"] == 8: # Got a request
            ICMP = createICMPHeader(0, identifier=data["L3"]["Data"]["identifier"])
            p3 = makePacket_L3(data["L3"]["DIP"], data["L3"]["SIP"], proto="ICMP", data=ICMP)
            p2 = makePacket_L2("IPv4", self.id, data["L2"]["From"])
            p = makePacket(p2, p3)
            
            if self.DEBUG:
                Debug(self.id, "Received ICMP request from", data["L3"]["SIP"], ", responding",
                    color="green", f=self.__class__.__name__
                )

            return p

        elif data["L3"]["Data"]["type"] == 0: # Got a reply
            if self.DEBUG:
                Debug(self.id, "Received ICMP reply from", data["L3"]["SIP"], 
                    color="green", f=self.__class__.__name__
                )
            if data["L3"]["Data"]["identifier"] in self.icmp_table:
                self.icmp_table[data["L3"]["Data"]["identifier"]] = True
            else:
                if self.DEBUG:
                    Debug(self.id, data["L3"]["Data"]["identifier"], "not in ICMP table - did I send this request?",
                        color="red", f=self.__class__.__name__
                    )
            return
        else:
            if self.DEBUG:
                Debug(self.id, "Received malformed ICMP response type from", data["L2"]["From"], ":", data["L3"]["SIP"], 
                    color="red", f=self.__class__.__name__
                )
