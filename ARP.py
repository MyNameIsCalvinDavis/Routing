from Headers import *

class ARPHandler:
    def __init__(self, ID, links, debug=1, ipfunc=None):
        self.DEBUG = debug
        self.id = ID
        self.links = links
        
        # A function passed in from whoever uses this handler
        # to get an IP of that interface / device
        if ipfunc:
            self.getIP = ipfunc
        else:
            self.getIP = None

        self.switch_table = {} # MAC to interface
        # K: Device.id
        # V: LinkID

    def sendARP(self, targetIP, onlinkID=None):
        """ 
        ARP Wrapper for self.send()

        :param targetID: The IP of the target device
        :param onlinkID: Link to be sent on, default None targets first link on self.links
        :returns: The response packet, dict
        :returns: The linkID it should be sent out on, str
        """
        print(self.DEBUG)
        if self.DEBUG: print(self.id, "sending ARP request to", targetID)
        if onlinkID == None:
            onlinkID = self.links[0].id
        elif not isinstance(onlinkID, str):
            raise ValueError("onlinkID must be of type <str>")
        

        p2 = makePacket_L2("ARP", self.id, MAC_BROADCAST, onlinkID, {"IP":targetIP})
        p = makePacket(p2)
        #self.send(p, onlinkID)
        return p, onlinkID

    def handleARP(self, data):
        """ 
        Process an ARP request and generate a response
        
        :param data: See `Headers.makePacket()`, dict
        :returns: The response packet, dict
        :returns: The linkID it should be sent out on, str
        """
        # Update local ARP cache, regardless of match
        self.switch_table[data["L2"]["From"]] = data["L2"]["FromLink"]
        
        # If an ip function hasnt been provided, then this device has no IP,
        # so it can ignore the ARP request
        if not self.getIP:
            print(self.id, "has no IP - ignoring ARP")
            return

        # Receiving an ARP Request
        if data["L2"]["To"] == MAC_BROADCAST:
            
            # Do I have the IP requested?
            if self.getIP(data["L2"]["FromLink"]) == data["L2"]["Data"]["IP"]:
                if self.DEBUG: print("(ARP)", self.id, "got ARP-Rq, sending ARP-Rp")
                p2 = makePacket_L2("ARP", self.id, data["L2"]["From"]) # Resp has no data
                p = makePacket(p2)
                return p, data["L2"]["FromLink"]
        
        # Receiving an ARP Response
        elif data["L2"]["To"] == self.id:
            if self.DEBUG: print("(ARP)", self.id, "got ARP Response, updating ARP cache")
        else:
            if self.DEBUG: genericIgnoreMessage("ARP", self.id, data["L2"]["From"])
        return None, None

