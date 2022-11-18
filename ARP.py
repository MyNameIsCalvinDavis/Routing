from Headers import *
from Debug import *

class ARPHandler:
    def __init__(self, ID, links, debug=1, ipfunc=None):
        self.DEBUG = debug
        self.id = ID
        self.links = links

        # Used to identify an outgoing packet and its response,
        # and identify whether a sendX() has completed
        self.id_counter = 0

        # The table that stores internal connection information
        self.conn_table = {}
        # {1:False, 2:True, ...}
        
        # A function passed in from whoever uses this handler
        # to get an IP of that interface / device
        if ipfunc:
            self.getIP = ipfunc
        else:
            self.getIP = None

        self.arp_cache = {} # IP to MAC/ID 

    def sendARP(self, targetIP, onlinkID=None):
        """ 
        ARP Wrapper for self.send()

        :param targetID: The IP of the target device
        :param onlinkID: Link to be sent on, default None targets first link on self.links
        :returns: The response packet, dict
        :returns: The linkID it should be sent out on, str
        """
        
        # Set the IP to a missing value, to be checked later
        # once the response comes in
        self.arp_cache[targetIP] = -1
        
        if self.DEBUG:
            Debug(self.id, "sending ARP request to", targetIP,
                color="green", f=self.__class__.__name__
            )
        if onlinkID == None:
            onlinkID = self.links[0].id
        elif not isinstance(onlinkID, str):
            raise ValueError("onlinkID must be of type <str>")

        # Make the frame
        ARP = createARPHeader(1, self.id, self.getIP(), 0, targetIP)
        p2 = makePacket_L2("ARP", self.id, MAC_BROADCAST, onlinkID, ARP)
        p = makePacket(p2)
        return p, onlinkID

    def handleARP(self, data):
        """ 
        Process an ARP request and generate a response
        
        :param data: See `Headers.makePacket()`, dict
        :returns: The response packet, dict
        :returns: The linkID it should be sent out on, str
        """
        
        # If an ip function hasnt been provided to the class, then this device has no IP,
        # so it can ignore the ARP request
        if not self.getIP:
            if self.DEBUG:
                Debug(self.id, "has no IP - ignoring ARP",
                    color="yellow", f=self.__class__.__name__
                ) 
            return

        # Receiving an ARP Request
        if data["L2"]["To"] == MAC_BROADCAST and data["L2"]["Data"]["OP"] == 1:
            
            # Do I have the IP requested?
            if self.getIP(data["L2"]["FromLink"]) == data["L2"]["Data"]["TPA"]:
                if self.DEBUG:
                    Debug(self.id, "got Request from", data["L2"]["From"], "- sending Response",
                        color="green", f=self.__class__.__name__
                    )
                ARP = createARPHeader(2, fr=self.id, frIP=self.getIP(), to=data["L2"]["Data"]["SHA"], toIP=data["L2"]["Data"]["SPA"])
                p2 = makePacket_L2("ARP", self.id, data["L2"]["From"], data=ARP) # Resp has no data
                p = makePacket(p2)
                return p, data["L2"]["FromLink"]
        
        # Receiving an ARP Response
        elif data["L2"]["To"] == self.id and data["L2"]["Data"]["OP"] == 2:
            if self.DEBUG:
                Debug(self.id, "updating ARP cache:", data["L2"]["Data"]["TPA"], "=", data["L2"]["From"],
                    color="green", f=self.__class__.__name__
                )
            
            if data["L2"]["Data"]["SPA"] not in self.arp_cache:
                # Produced if the IP that gets updated is not the one I requested originally
                Debug(self.id, "Got ARP response for a missing IP - did I request this?", self.arp_cache,
                    color="yellow", f=self.__class__.__name__
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
        return None, None

