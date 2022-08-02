import random
import time
import threading
from abc import ABC, abstractmethod
import copy
import Headers

random.seed(123)

MAC_BROADCAST="FFFF"


"""
TODO
ARP resolves an IP to a MAC. So DHCP must run before anything else
Make sure ARP only communicates over L2, and provides L3 information
    - Sending ARPS should correctly use L2
    - Receiving ARPS should correctly identify L2 and provide L3? info (where does the data go? frame or packet?)
Make sure DHCP 


"""

subnet = []

#def initLinks(links):
#    # Ensure devices on links internalize their link association
#    for link in links:
#        for device in link.dl:
#            if link not in device.interfaces:
#                device.interfaces.append(link)

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

    # Debug 0 : Show nothing
    # Debug 1 : Show who talks to who
    # Debug 2 : Show who sends what to who
    DEBUG=1

    def __init__(self, connectedTo=[]):
        self.id = "___" + str(random.randint(10000, 99999999))
        self.interfaces = []
        self.buffer = []
        self.mti = {} # MAC to interface
        self.lock = threading.Lock()

        # Start the listening thread on this device
        x = threading.Thread(target=self.listen, args=())
        x.start()


        self._initConnections(connectedTo)


    def _initConnections(self, connectedTo):
        """
        Create a link between me and every device in connectedTo, and vice versa.
        """
        for device in connectedTo:
            link = Link([self, device])
            if not link in self.interfaces:
                self.interfaces.append(link)
            if not link in device.interfaces:
                device.interfaces.append(link)

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
        Send data (a dictionary defined by makePacket()) on a link object.
        
        Essentially this method finds the device on the other end of onlink,
        then appends data to its buffer. By default, it sends data out on the
        first interface on this device. For multi interface Devices like a Switch
        or Router, onlink (Link instance) may be defined.
        
        All Devices expect data in the form of a dictionary, defined by the
        makePacket() function.
        """

        assert isinstance(data, dict)
        if onlink: assert isinstance(onlink, str)
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
        if Device.DEBUG == 1: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"])
        if Device.DEBUG == 2: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"] + "\n    " + str(data))

        self.lock.acquire()
        end.buffer.append(data)
        self.lock.release()


    def listen(self):
        while True:
            time.sleep(0.5)
            self._checkTimeouts()
            if self.buffer:
                data = self.buffer.pop(0)

                if Device.DEBUG == 1:
                    print(self.id + " got data from " + self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id)
                if Device.DEBUG == 2:
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

    # Most devices handle ARPs the same way
    def handleARP(self, data):
        # Update local ARP cache, regardless of match
        self.mti[data["L2"]["From"]] = data["L2"]["FromLink"]

        # Receiving an ARP Request
        if data["L2"]["To"] == MAC_BROADCAST and data["L2"]["Data"]["ID"] == self.id:
            if Device.DEBUG: print(self.id, "got ARP-Rq, sending ARP-Rp")
            p2 = makePacket_L2("ARP", self.id, data["L2"]["From"]) # Resp has no data
            p = makePacket(p2)
            self.send(p)
        
        # Receiving an ARP Response
        elif data["L2"]["To"] == self.id:
            if Device.DEBUG: print("To me!", self.id, "updating ARP table")
        else:
            if Device.DEBUG: print(self.id, "ignoring", data["L2"]["From"])#, data)


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

    # Routers & Hosts need this but Switches do not, so instead of 
    # doing the right (?) thing and overriding listen() in the child
    # classes, I'm just doing this because it ends up being less duplicated code.
    # The alternative is each subclass that uses timeouts will implement both their
    # own version of listen, and their own version of this method, which will
    # get messy. I could also break up the class hierarchy, but that would
    # make the inheritence unintuitive - instead, all devices must implement
    # this function, even if they do nothing with it.
    @abstractmethod   
    def _checkTimeouts(self):
        raise NotImplementedError("Must override this method in the child class")
        
    @abstractmethod
    def handleDHCP(self):
        raise NotImplementedError("Must override this method in the child class")
            
class Host(Device):
    def __init__(self, connectedTo=[]):
        super().__init__(connectedTo)
        # L2
        self.id = "-H-" + str(random.randint(10000, 99999999))

        # L3
        self.ip = ""
        self.offered_ip = ""
        self.nmask = ""
        self.gateway = ""
        self.lease = (-1, -1) # (leaseTime, time (s) received the lease)
        self.lease_left = -1
        self.DHCP_FLAG = 0 # 0: No IP --- 1: Awaiting ACK --- 2: Received ACK & has active IP
        self.DHCP_MAC = ""
        self.DHCP_IP = ""
        self.gateway = ""
        
        # On init, begin the DHCP DORA cycle to obtain an IP
        #self.sendDHCP("Init")
    
    def _checkTimeouts(self):
        # DHCP
        
        if self.lease[0] >= 0:
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            print(self.id, "===", self.lease_left, "/", self.lease[0])
            if self.lease_left <= 0.5 * self.lease[0] and self.DHCP_FLAG != 1:
                if DEBUG: print("(DHCP)", self.id, "renewing ip", self.ip)
                print("Renewing")
                self.DHCP_FLAG = 1
                self.sendDHCP("Renew")

    def handleDHCP(self, data): # R of DORA
        
        if Device.DEBUG == 2: print("(DHCP)", self.id, "got", data)
        if data["L3"]["Data"]["op"] == 2 and data["L3"]["Data"][53] == 2:  # Process O(ffer) request
            
            if Device.DEBUG: print("(DHCP)", self.id, "received DHCP Offer, sending Request (broadcast)")
            self.DHCP_FLAG = 1
            self.offered_ip = data["L3"]["Data"]["yiaddr"]
            
            self.DHCP_IP = data["L3"]["Data"][6]
            self.DHCP_MAC = data["L2"]["From"]

            # Send Request // TODO Check unicast/Broadcast stuff
            DHCP = Headers.createDHCPHeader(chaddr=self.id, options={
                50:self.offered_ip, # Client requesting this IP
                53:3, # Request
                54:self.DHCP_IP, # DHCP siaddr
                61:self.id, # Client MAC / ID
                # 55: [1, 3, 6, ...]
            })

            p3 = makePacket_L3("0.0.0.0", "255.255.255.255", DHCP)
            p2 = makePacket_L2("DHCP", self.id, MAC_BROADCAST)
            
            p = makePacket(p2, p3)
            self.send(p)
        elif data["L3"]["Data"]["op"] == 2 and data["L3"]["Data"][53] == 5: # Process A(CK)

            if Device.DEBUG: print("(DHCP)", self.id, "received DHCP ACK from", data["L2"]["From"])
            self.gateway = data["L3"]["Data"][3]
            self.ip = data["L3"]["Data"]["yiaddr"]
            self.nmask = data["L3"]["Data"][1]
            self.lease = (data["L3"]["Data"][51], int(time.time()) )
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            self.DHCP_FLAG = 2
        else:
            if Device.DEBUG: print(self.id, "ignoring DHCP", data["L2"]["From"])
        

    def sendDHCP(self, context, onlink=None): # D of DORA
        if onlink == None:
            onlink = self.interfaces[0]

        if context == "Init": # Start DORA cycle
            print("(DHCP)", self.id, "sending DHCP Discover")
            
            # The only thing the DHCP server will read is the chaddr,
            # so we don't care about the other values
            DHCP = Headers.createDHCPHeader(chaddr=self.id, options={
                61:self.id, # Client MAC / ID
                53:1 # Discover
                # 55: [1, 3, 6, ...]
            })

            p3 = makePacket_L3("0.0.0.0", "255.255.255.255", DHCP) # MAC included
            p2 = makePacket_L2("DHCP", self.id, MAC_BROADCAST, onlink.id)
            p = makePacket(p2, p3)
            self.send(p)
        if context == "Renew":
            print("(DHCP)", self.id, "sending DHCP Request (Renewal)")
            # Send Request // TODO Check unicast/Broadcast stuff

            # Renew: ciaddr filled (NOT option 50)
            DHCP = Headers.createDHCPHeader(chaddr=self.id, ciaddr=self.ip, options={
                53:3, # Request
                61:self.id, # Client MAC / ID
                # 55: [1, 3, 6, ...]
            })
            
            # Now that the IP is active, unicast to DHCP server
            p3 = makePacket_L3(self.ip, self.DHCP_IP, DHCP)
            p2 = makePacket_L2("DHCP", self.id, self.DHCP_MAC)
            
            p = makePacket(p2, p3)
            self.send(p)


class Switch(Device):
    def __init__(self, connectedTo=[]):
        super().__init__(connectedTo)
        self.id = "{S}" + str(random.randint(10000, 99999999))
        self.itm = {}
    
    def _checkTimeouts(self):
        pass

    def handleARP(self, data):
        self.handleAll(data)
    
    def handleDHCP(self, data):
        self.handleAll(data)

    def handleAll(self, data):
        # Before evaluating, add incoming data to ARP table
        self.mti[data["L2"]["From"]] = data["L2"]["FromLink"]
        self.itm[data["L2"]["FromLink"]] = data["L2"]["From"]
        if Device.DEBUG == 1: print(self.id, "Updated ARP table:", self.mti)
        
        # ARP table lookup
        if data["L2"]["To"] in self.mti:
            if Device.DEBUG: print(self.id, "Found", data["L2"]["To"], "in ARP table")
            # Grab the link ID associated with the TO field (in the ARP table),
            # then get the link object from that ID
            #link = self.getLinkFromID( self.mti[ data["To"] ])
            #self.send(data, link.id)
            self.send(data, self.mti[ data["L2"]["To"] ])

        else: # Flood every interface with the request
            if Device.DEBUG: print(self.id, "flooding")
            for link in self.interfaces:
                if link.id != data["L2"]["FromLink"]: # Dont send back on the same link
                    # Python shenanigans: Make sure to flood with a *copy*
                    # and not a reference to the same data dictionary
                    # This is now handled in send()
                    self.send(data, link.id)

# Also a DHCP server
class Router(Device):
    def __init__(self, connectedTo=[]):
        super().__init__(connectedTo)
        self.id = "=R=" + str(random.randint(10000, 99999999))

        # DHCP Server
        self.ip = "10.10.10.1"
        self.nmask = "255.255.255.0"
        self.leased_ips = []
        self.lease_offer = 20
    
    def _checkTimeouts(self):
        pass

    def handleDHCP(self, data): # O of DORA

        # Process D(iscover) request
        if data["L3"]["Data"]["op"] == 1 and data["L3"]["Data"][53] == 1:  
            # Send DHCP Offer
            if Device.DEBUG: print("(DHCP)", self.id, "received Discover from", data["L2"]["From"])
            clientip = self.generateIP()
            # Broadcast (flags=0) a response (op=2)
            DHCP = Headers.createDHCPHeader(op=2, chaddr=data["L3"]["Data"][61], yiaddr=clientip, options={
                    1:self.nmask, # Netmask
                    3:self.ip, # Router IP
                    6:"", # Not doing DNS
                    51: self.lease_offer,
                    53:2, # DHCP Offer
                    54:self.ip # DHCP Server identifier
                })

            p3 = makePacket_L3(self.ip, "255.255.255.255", DHCP)
            p2 = makePacket_L2("DHCP", self.id, data["L2"]["From"], data["L2"]["FromLink"]) # TODO: Broadcast?
            # We assume that a host can accept a DHCP unicast packet at this point,
            # so do not issue another broadcast
            p = makePacket(p2, p3)

            if Device.DEBUG: print("(DHCP)", self.id, "sending Offer to", data["L2"]["From"])
            if Device.DEBUG == 2: print(p)
            self.send(p, data["L2"]["FromLink"])

        # Process R(equest)
        elif data["L3"]["Data"]["op"] == 1 and data["L3"]["Data"][53] == 3:
            # Send a DHCP Ack
            
            if data["L3"]["Data"]["ciaddr"] == "0.0.0.0": # R(equest)
                yiaddr = data["L3"]["Data"][50]
            else:
                # For some reason, the client doesnt have to send option 50 here
                # and the server instead looks at ciaddr for the renewal
                yiaddr = data["L3"]["Data"]["ciaddr"]
                
            DHCP = Headers.createDHCPHeader(op=2, chaddr=data["L3"]["Data"][61], yiaddr=yiaddr, options={
                    1:self.nmask, # Netmask
                    3:self.ip, # Router IP
                    6:"", # Not doing DNS
                    51: self.lease_offer,
                    53:5, # DHCP Ack
                    54:self.ip # DHCP Server identifier
                }) # TODO: Add lease expriation / updating

            p3 = makePacket_L3(self.ip, "255.255.255.255", DHCP)
            p2 = makePacket_L2("DHCP", self.id, data["L2"]["From"], data["L2"]["FromLink"])
            # We assume that a host can accept a DHCP unicast packet at this point,
            # so do not issue another broadcast
            p = makePacket(p2, p3)

            if Device.DEBUG: print("(DHCP)", self.id, "sending Ack to", data["L2"]["From"])
            if Device.DEBUG == 2: print(p)
            self.send(p, data["L2"]["FromLink"])

        else:
            if Device.DEBUG: print(self.id, "Ignoring")
    def generateIP(self):
        while True:
            x = "10.10.10." + str(random.randint(2, 254))
            if Device.DEBUG: print("(DHCP)", self.id, "Finding an IP:", x, "for client")
            if not x in self.leased_ips:
                #self.leased_ips.append(x)
                return x


class Link:
    """ Connects two devices """
    def __init__(self, dl=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.dl = dl

if __name__ == "__main__":

    A, B, C = Host(), Host(), Host()
    R1 = Router()
    S1 = Switch([A, R1])
    
    print(A, B, C, R1)
    print(S1)

    A.sendDHCP("Init")
    #A.sendARP(B.id)
