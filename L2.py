import random
import time
import threading
from abc import ABC, abstractmethod
import copy

random.seed(123)

MAC_BROADCAST="FFFF"

# Debug 0 : Show nothing
# Debug 1 : Show who talks to who
# Debug 2 : Show who sends what to who
DEBUG=0



subnet = []

def initLinks(links):
    # Ensure devices on links internalize their link association
    for link in links:
        for device in link.dl:
            if link not in device.interfaces:
                device.interfaces.append(link)

def makePacket(L2="", L3="", L4="", L5="", L6="", L7=""):
    
    d = {
        "L2":L2,
        "L3":L3,
        "L4":L4,
        "L5":L5,
        "L6":L6,
        "L7":L7
    }
    
    for k, v in d.items():
        if v != "" and not isinstance(v, dict):
            raise ValueError("Arguments must be of type <dict>")

    return d
# Called a packet & not a frame for consistency's sake
def makePacket_L2(ethertype="", fr="", to="", fromlink="", data=""):
    return {
        "EtherType":ethertype, # Defines which protocol is encapsulated in data
        "From":fr,
        "To":to,
        "FromLink":fromlink,
        "Data":data, # ARP packet, IP packet, DHCP packet, etc
    }


def makePacket_L3(sip="", dip="", data=""):
    return {
        "SIP":sip, # Src, Dst
        "DIP":dip,
        "Data":data
    }

# Abstract Base Class
class Device(ABC):
    def __init__(self):
        self.id = "___" + str(random.randint(10000, 99999999))
        self.interfaces = []
        self.buffer = []
        self.mti = {} # MAC to interface
        self.lock = threading.Lock()

        # Start the listening thread on this device
        x = threading.Thread(target=self.listen, args=())
        x.start()

    def __str__(self):
        s = "\n" + self.id + "\n"
        for item in self.interfaces:
            s += "  " + item.id + "\n"
            if isinstance(item, Link):
                for sub_item in item.dl:
                    s += "    " + sub_item.id + "\n"
            else:
                for sub_item in item.interfaces:
                    s += "    " + sub_item.id + "\n"
            
        return s 
    
    def send(self, data, onlink=None):
        """
        Send data (a dictionary defined by makePacket_L2()) on a link object.
        
        Essentially this method finds the device on the other end of onlink,
        then appends data to its buffer. By default, it sends data out on the
        first interface on this device. For multi interface Devices like a Switch
        or Router, onlink (Link instance) may be defined.
        
        All Devices expect data in the form of a dictionary, defined by the
        makePacket_L2() function.
        """

        assert isinstance(data, dict)
        if onlink == None:
            onlink = self.interfaces[0].id
        
        # Is data in the right format?
        for k, v in data.items():
            if v == "": continue
            if not k in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"] or not isinstance(v, dict):
                print("Data: ", data)
                raise ValueError("data not in the correct format")

        # Don't modify the original dict
        # This 26 character line represents at least 6 hours of my day
        data = copy.deepcopy(data)

        # You see, this makes a copy
        #p2 = makePacket_L2(data["L2"]["EtherType"], data["L2"]["From"], data["L2"]["To"], onlink, data["L2"]["Data"])
        #p = makePacket(p2)
        
        # And this does not
        data["L2"]["FromLink"] = onlink # It was you!

        end = self.getOtherDeviceOnInterface(onlink)
        if DEBUG == 1: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"])
        if DEBUG == 2: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"] + "\n    " + str(data))

        self.lock.acquire()
        end.buffer.append(data)
        self.lock.release()


    def listen(self):
        while True:
            time.sleep(0.5)
            if self.buffer:
                data = self.buffer.pop(0)

                if DEBUG == 1:
                    print(self.id + " got data from " + self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id)
                if DEBUG == 2:
                    print(self.id + " got data from " + self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id + "\n    " + str(data))
                    
                if data["L2"]["EtherType"] == "ARP":
                    self.handleARP(data)
                elif data["L2"]["EtherType"] == "DHCP":
                    self.handleDHCP(data)
                else:
                    print(self.id, "ignoring", data["L2"]["From"], data)
    
    def sendARP(self, targetID, onlinkID=None):
        """ ARP Wrapper for self.send() """
        if onlinkID == None:
            onlinkID = self.interfaces[0].id
        elif not isinstance(onlink, str):
            raise ValueError("onlinkID must be of type <str>")


        p2 = makePacket_L2("ARP", self.id, MAC_BROADCAST, onlinkID, {"ID":targetID})
        p = makePacket(p2)
        self.send(p, onlinkID)

    # @abstractmethod
    # def handleARP(self):
    #     raise NotImplementedError("Must override this method in the child class")
    
    # Most devices handle ARPs the same way
    def handleARP(self, data):
        # Update local ARP cache, regardless of match
        self.mti[data["L2"]["From"]] = data["L2"]["FromLink"]

        # Receiving an ARP Request
        if data["L2"]["To"] == MAC_BROADCAST and data["L2"]["Data"]["ID"] == self.id:
            if DEBUG: print(self.id, "got ARP-Rq, sending ARP-Rp")
            p2 = makePacket_L2("ARP", self.id, data["L2"]["From"]) # Resp has no data
            p = makePacket(p2)
            self.send(p)
        
        # Receiving an ARP Response
        elif data["L2"]["To"] == self.id:
            if DEBUG: print("To me!", self.id, "updating ARP table")
        else:
            if DEBUG: print(self.id, "ignoring", data["L2"]["From"])#, data)

    @abstractmethod
    def handleDHCP(self):
        raise NotImplementedError("Must override this method in the child class")

    def getOtherDeviceOnInterface(self, onlinkID):
        if not isinstance(onlinkID, str): raise ValueError("onlinkID must be of type <str>")
        onlink = self.getLinkFromID(onlinkID)
        # Find the other device on a link
        if onlink.dl[0].id == self.id:
            return onlink.dl[1]
        else:
            return onlink.dl[0]

    def getLinkFromID(self, ID):
        # Given an ID of a link attached to this device,
        # return the object
        

        if not isinstance(ID, str): raise ValueError("ID must be of type <str>")

        # First, check to see if that link is on this devices interfaces at all
        ids = [x.id for x in self.interfaces]
        if not ID in ids:
            raise ValueError("LinkID " + ID + " not located in " + self.id + " interfaces")


        for link in self.interfaces:
            if link.id == ID:
                return link
            
class Host(Device):
    def __init__(self):
        super().__init__()
        self.id = "-H-" + str(random.randint(10000, 99999999))
        self.ip = ""

        # On init, begin the DHCP DORA cycle to obtain an IP
        #self.sendDHCP("Init")
    
    def handleDHCP(self, data):
        pass

    def sendDHCP(self, context, onlink=None):
        if context == "Init": # Start DORA cycle
            if onlink == None:
                onlink = self.interfaces[0]

            # It has layers, like an ogre, or a cake
            # DHCP data is currently in the data field for L3, not sure if that should be L2 instead
            p3 = makePacket_L3("0.0.0.0", "255.255.255.255", {"CID":self.id}) # MAC included
            p2 = makePacket_L2("DHCP", self.id, MAC_BROADCAST, onlink.id)
            p = makePacket(p2, p3)
            self.send(p)


class Switch(Device):
    def __init__(self):
        super().__init__()
        self.id = "{S}" + str(random.randint(10000, 99999999))
        self.itm = {}

    def handleARP(self, data):
        self.handleAll(data)
    
    def handleDHCP(self, data):
        self.handleAll(data)

    def handleAll(self, data):
        # Before evaluating, add incoming data to ARP table
        self.mti[data["L2"]["From"]] = data["L2"]["FromLink"]
        self.itm[data["L2"]["FromLink"]] = data["L2"]["From"]
        if DEBUG == 1: print(self.id, "Updated ARP table:", self.mti)
        
        # ARP table lookup
        if data["L2"]["To"] in self.mti:
            if DEBUG: print(self.id, "Found", data["L2"]["To"], "in ARP table")
            # Grab the link ID associated with the TO field (in the ARP table),
            # then get the link object from that ID
            #link = self.getLinkFromID( self.mti[ data["To"] ])
            #self.send(data, link.id)
            self.send(data, self.mti[ data["L2"]["To"] ])

        else: # Flood every interface with the request
            if DEBUG: print(self.id, "flooding")
            for link in self.interfaces:
                end = self.getOtherDeviceOnInterface(link.id)
                if end.id != data["L2"]["From"]: # Dont send to self, or back to sender
                    # Python shenanigans: Make sure to flood with a *copy*
                    # and not a reference to the same data dictionary
                    # This is now handled in send()
                    self.send(data, link.id)

# Also a DHCP server
class Router(Device):
    def __init__(self):
        super().__init__()
        self.id = "=R=" + str(random.randint(10000, 99999999))

        # DHCP Server
        self.ip = "10.10.10.1"
        self.mask = "255.255.255.0"
        self.leased_ips = []

    def handleDHCP(self, data):
        # Receiving a client discover
        if data["L3"]["SIP"] == "0.0.0.0" and data["L3"]["DIP"] == "255.255.255.255":
            if DEBUG: print("Router got a DHCP Discover request")
            if DEBUG == 2: print(data)
            # Send DHCP offer request
            clientip = self.generateIP()
            p3 = makePacket_L3(self.ip, "255.255.255.255", {
                "CIP":clientip, "CID":data["L3"]["Data"]["CID"], "SMASK":self.mask, "Gateway":self.ip,
                "Lease":60
                })
            # We assume that a host can accept a DHCP unicast packet at this point,
            # so do not issue another broadcast
            p2 = makePacket_L2("DHCP", self.id, data["L2"]["From"], data["L2"]["FromLink"])
            
            p = makePacket(p2, p3)

            if DEBUG: print("Router DHCP sending on", data["L2"]["FromLink"])
            if DEBUG == 2: print(p)
            self.send(p, data["L2"]["FromLink"])
        else:
            if DEBUG: print(self.id, "Ignoring")
    def generateIP(self):
        while True:
            x = "10.10.10." + str(random.randint(2, 254))
            if DEBUG: print(self.id, "Finding an IP:", x, "for client (DHCP)")
            if not x in self.leased_ips:
                self.leased_ips.append(x)
                return x


class Link:
    """ Connects two devices """
    def __init__(self, dl=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.dl = dl

if __name__ == "__main__":

    DEBUG = 1
        
    A, B, C = Host(), Host(), Host()
    R1 = Router()
    S1 = Switch()
    
    L1 = Link([A, S1])
    L2 = Link([B, S1])
    L3 = Link([C, S1])
    L4 = Link([R1, S1])
    
    initLinks([L1, L2, L3, L4])
    
    print(A, B, C, R1)
    print(S1)

    A.sendDHCP("Init")
    
    #A.sendARP(B.id)
