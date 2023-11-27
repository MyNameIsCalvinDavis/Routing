from Headers import *
from Debug import *

class ARP:
    def __init__(self, _parent, debug=1):
        self.DEBUG = debug
        self._parentInterface = _parent
        self.id = _parent.id
        self.ip = _parent.ip
        self.arp_cache = {} # IP to MAC/ID 

    async def create(self, targetIP):
        """ 
        Create an ARP Request
        """
        
        # Set the IP to a missing value, to be checked later
        # once the response comes in
        self.arp_cache[targetIP] = False
        
        if self.DEBUG:
            Debug(self.id, "sending ARP request to", targetIP,
                color="green", f=self.__class__.__name__
            )

        # Make the frame
        ARP = arp_header(1, self.id, self.ip, 0, targetIP)
        p2 = makePacket_L2("ARP", self.id, MAC_BROADCAST, data=ARP)
        p = makePacket(p2)
        return p

    async def handle(self, data):
        """ 
        Process an ARP request and generate a response
        """
        if self.ip == "0.0.0.0/32":
            if self.DEBUG:
                Debug(self.id, "has no IP - ignoring ARP",
                    color="yellow", f=self.__class__.__name__
                ) 
            return

        # Receiving an ARP Request
        if data["L2"]["To"] == MAC_BROADCAST and data["L2"]["Data"]["OP"] == 1:
            
            # Do I have the IP requested?
            if self._parentInterface.ip == data["L2"]["Data"]["TPA"]:
                if self.DEBUG:
                    Debug(self.id, "got Request from", data["L2"]["From"], "- sending Response",
                        color="green", f=self.__class__.__name__
                    )
                ARP = arp_header(2, fr=self.id, frIP=self.ip, 
                    to=data["L2"]["Data"]["SHA"], toIP=data["L2"]["Data"]["SPA"])
                p2 = makePacket_L2("ARP", self.id, data["L2"]["From"], data=ARP)
                p = makePacket(p2)
                return p
        
        # Receiving an ARP Response
        elif data["L2"]["To"] == self.id and data["L2"]["Data"]["OP"] == 2:
            if data["L2"]["Data"]["SPA"] not in self.arp_cache:
                # Produced if the IP that gets updated is not the one I requested originally
                Debug(self.id, "Got ARP response for a missing IP - did I request this? Dropping frame", self.arp_cache,
                    color="yellow", f=self.__class__.__name__
                )
                return None

            if self.DEBUG:
                Debug(self.id, "updating ARP cache:", data["L2"]["Data"]["SPA"], "=", data["L2"]["From"],
                    color="green", f=self.__class__.__name__
                )

            if self.DEBUG == 2:
                Debug(self.id, "old ARP cache info:", self.arp_cache,
                    color="blue", f=self.__class__.__name__
                )

            # Update the local ARP cache with the received data
            # x.x.x.x = -H-123123123
            self.arp_cache[data["L2"]["Data"]["SPA"]] = data["L2"]["From"]
            if self.DEBUG == 2:
                Debug(self.id, "new ARP cache info:", self.arp_cache,
                    color="blue", f=self.__class__.__name__
                )

        else:
            if self.DEBUG: genericIgnoreMessage("ARP", self.id, data["L2"]["From"])
        return None#, None

