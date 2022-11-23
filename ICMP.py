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

        # Interesting problem - unlike other handlers, this one needs an updated IP and netmask
        # so we pass in the interface itself here to grab those items, because the interface
        # will be the single point of contact for updating the IP for whatever needs to use it

        # A possible solution for this is to update everything manually in the
        # setIP() function in L3Device, which does not maintain a single point of contact
        # for the interface object but does for the function
        #self.interface = interface

        self.icmp_table = {}
    
    async def sendICMP(self, targetIP, targetID):
        # We take in targetID because we first ARP before calling this function,
        # and must construct the L2 frame
        ICMP = createICMPHeader(8)
        p3 = makePacket_L3(self.ip, targetIP, proto="ICMP", data=ICMP)
        p2 = makePacket_L2("IPv4", self.id, targetID)
        p = makePacket(p2, p3)

        if self.DEBUG:
            Debug(self.id, "sending ICMP to", targetIP,
                color="green", f=self.__class__.__name__
            )
        return p

    async def handleICMP(self, data):
        if data["L3"]["Data"]["type"] == 8: # Got a request
            ICMP = createICMPHeader(0)
            p3 = makePacket_L3(data["L3"]["DIP"], data["L3"]["SIP"], proto="ICMP", data=ICMP)
            p2 = makePacket_L2("IPv4", self.id, data["L2"]["From"])
            p = makePacket(p2, p3)
            
            if self.DEBUG:
                Debug(self.id, "got ICMP request, responding",
                    color="green", f=self.__class__.__name__
                )

            return p

        elif data["L3"]["Data"]["type"] == 0: # Got a reply
            if self.DEBUG:
                Debug(self.id, "Received ICMP packet from", data["L2"]["From"], ":", data["L3"]["SIP"], 
                    color="green", f=self.__class__.__name__
                )
            return
        else:
            if self.DEBUG:
                Debug(self.id, "Received malformed ICMP response type from", data["L2"]["From"], ":", data["L3"]["SIP"], 
                    color="red", f=self.__class__.__name__
                )
