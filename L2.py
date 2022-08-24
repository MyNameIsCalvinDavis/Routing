import random
import time
import threading
from abc import ABC, abstractmethod
import copy
from Headers import *
from DHCP import DHCPServerHandler, DHCPClientHandler

random.seed(123)

# Abstract Base Class
class Device(ABC):
    def __init__(self, connectedTo=[], debug=1): # Device

        # Debug 0 : Show nothing
        # Debug 1 : Show who talks to who
        # Debug 2 : Show who sends what to who
        self.DEBUG = debug

        # For visualization purposes
        self.listen_delay = 0.5

        self.id = "___" + str(random.randint(10000, 99999999))
        self.links = []
        self.buffer = []
        self.mti = {} # MAC to interface
        self.lock = threading.Lock()
        
        self.thread_exit = False
        #self._initConnections(connectedTo)

        # Start the listening thread on this device
        self.lthread = threading.Thread(target=self.listen, args=())
        self.lthread.start()
    
    #def __del__(self):
    #    # If this object falls out of scope, safely terminate the running thread
    #    self.thread_exit = True
    #    if self.DEBUG: print(self.id, "killing thread:", end="")
    #    self.lthread.join() # Wait til the thread terminates
    #    if self.DEBUG: print("DONE")

    @abstractmethod
    def _initConnections(self, connectedTo):
        raise NotImplementedError("Must override this method in the child class")
    
    # Some L2 devices won't have timeouts; too bad
    @abstractmethod   
    def _checkTimeouts(self):
        raise NotImplementedError("Must override this method in the child class")

    def __str__(self):
        s = "\n" + self.id + "\n"
        for item in self.links:
            s += "  " + item.id + "\n"
            if isinstance(item, Link):
                for sub_item in item.dl:
                    s += "    " + sub_item.id + "\n"
            else:
                for sub_item in item.links:
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
            onlink = self.links[0].id
        
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
        if self.DEBUG == 1: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"])
        if self.DEBUG == 2: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"] + "\n    " + str(data))

        self.lock.acquire()
        end.buffer.append(data)
        self.lock.release()

    
    def sendARP(self, targetID, onlinkID=None):
        """ ARP Wrapper for self.send() """
        print(self.DEBUG)
        if self.DEBUG: print(self.id, "sending ARP request to", targetID)
        if onlinkID == None:
            onlinkID = self.links[0].id
        elif not isinstance(onlinkID, str):
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
            if self.DEBUG: print("(ARP)", self.id, "got ARP-Rq, sending ARP-Rp")
            p2 = makePacket_L2("ARP", self.id, data["L2"]["From"]) # Resp has no data
            p = makePacket(p2)
            self.send(p)
        
        # Receiving an ARP Response
        elif data["L2"]["To"] == self.id:
            #if self.DEBUG: genericIgnoreMessage("ARP", data["L2"]["From"])
            if self.DEBUG: print("(ARP)", self.id, "got ARP Response, updating ARP cache")
        else:
            if self.DEBUG: genericIgnoreMessage("ARP", data["L2"]["From"])
            # if self.DEBUG: print("(ARP)", self.id, "ignoring", data["L2"]["From"])#, data)


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
        ids = [x.id for x in self.links]
        if not ID in ids:
            raise ValueError("LinkID " + ID + " not located in " + self.id + " interfaces")

        for link in self.links:
            if link.id == ID:
                return link

    
class L2Device(Device):
    def __init__(self, connectedTo=[], debug=1):
        super().__init__(connectedTo, debug)
        self.itm = {}
        self._initConnections(connectedTo)

    @abstractmethod
    def handleAll(data):
        raise NotImplementedError("Must override this method in the child class")

    def listen(self):
        while True:
            if self.thread_exit: return
            time.sleep(self.listen_delay)
            self._checkTimeouts()
            if self.buffer:
                data = self.buffer.pop(0)
                if self.DEBUG == 1:
                    print(self.id + " got data from " + self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id)
                if self.DEBUG == 2:
                    print(self.id + " got data from " + self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id + "\n    " + str(data))
                
                self.handleAll(data)

    def _initConnections(self, connectedTo):
        """
        Create a link between me and every device in connectedTo, and vice versa.
        """
        for device in connectedTo:
            link = Link([self, device])
            if not link in self.links:
                self.links.append(link)
            if not link in device.links:
                device.links.append(link)
                if isinstance(device, L3Device):
                    device.ip = ("0.0.0.0", link.id)
                    device._associateIPsToLinks() # Possibly in need of a lock


class L3Device(Device):
    def __init__(self, ips=[], connectedTo=[], debug=1): # L3Device
        super().__init__(connectedTo, debug) # L3Device

        # Make ips always be a list, with ["0.0.0.0"] as default
        if ips: self.ips = ips
        else:   self.ips = ["0.0.0.0"]
        if isinstance(self.ips, str): self.ips = [self.ips]

        self.linkid_to_ip = {}
        self._initConnections(connectedTo)

    def listen(self):
        while True:
            if self.thread_exit: return
            time.sleep(self.listen_delay)
            self._checkTimeouts()
            if self.buffer:
                data = self.buffer.pop(0)
                if self.DEBUG == 1:
                    print(self.id + " got data from " + self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id)
                if self.DEBUG == 2:
                    print(self.id + " got data from " + self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id + "\n    " + str(data))
                
                if data["L2"]["EtherType"] == "ARP":
                    self.handleARP(data)
                elif data["L2"]["EtherType"] == "IPv4":
                    # Handle L4 stuff
                    if data["L4"]["DPort"] in [67, 68]: # DHCP
                        self.handleDHCP(data)
                    else:
                        if self.DEBUG: print("(Error)", self.id, "not configured for port", data["L4"]["DPort"])
                else:
                    print(self.id, "ignoring", data["L2"]["From"], data)

    def _initConnections(self, connectedTo):
        """
        Create a link between me and every device in connectedTo, and vice versa.
        Upon forming a link, a device now has an interface and an IP
        """
        for device in connectedTo:
            link = Link([self, device])
            if not link in self.links:
                self.ip = ("0.0.0.0", link.id)
                self.links.append(link)
            if not link in device.links:
                device.links.append(link)
                if isinstance(device, L3Device):
                    device.ip = ("0.0.0.0", link.id)
                    device._associateIPsToLinks() # Possibly in need of a lock

        self._associateIPsToLinks()

    def _associateIPsToLinks(self):
        # Given self.links, associate each with the provided self.ips.
        # If there are more links than IPs, each link gets associated
        # with the default 0.0.0.0
        
        for i in range(len(self.links)):
            try:
                self.linkid_to_ip[self.links[i]] = self.ips[i]
            except IndexError:
                self.linkid_to_ip[self.links[i]] = "0.0.0.0"
                self.ips.append("0.0.0.0")

    @property
    def ip(self):
        # Return the first link's associated ip
        try:
            linkid = self.links[0].id # First link id
            ip = self.linkid_to_ip[linkid]
            return ip
        except Exception as e:
            print("---ERROR: ", e)
            return None
    
    @ip.setter
    def ip(self, val):
        if isinstance(val, tuple): # self.ip = ("0.0.0.0", <LINKID>)
            onlinkid = val[1]
            self.linkid_to_ip[onlinkid] = val[0]
        elif isinstance(val, str): # self.ip = "0.0.0.0"
            onlinkid = self.links[0].id
            self.linkid_to_ip[onlinkid] = val
        else:
            raise("Can't set IP to " + str(type(val)) )

    ###### DHCP

    # By default, a device has DHCP Client functionality
    # And handles it as such

    ## Send D(iscover) or R(equest)
    def sendDHCP(self, context, onlink=None):
        p, link = self.DHCPClient.sendDHCP(context)
        self.send(p, link)
    
    def handleDHCP(self, data):
        p, link = self.DHCPClient.handleDHCP(data)

        # On DORA ACK, no packet is returned to send out
        if p:
            self.send(p, link)
        else:
            # Extract all of the goodies
            
            self.nmask = "255.255.255.255"
            self.gateway = "0.0.0.0"

            if 1 in data["L3"]["Data"]["options"]:
                self.nmask = data["L3"]["Data"]["options"][1]
            if 3 in data["L3"]["Data"]["options"]:
                self.gateway = data["L3"]["Data"]["options"][3]

            self.ip = data["L3"]["Data"]["yiaddr"]
            self.lease = (data["L3"]["Data"]["options"][51], int(time.time()) )
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            self.DHCP_FLAG = 2
            self.current_xid = -1

class Switch(L2Device):
    def __init__(self, connectedTo=[], debug=1): # Switch
        super().__init__(connectedTo, debug) # Switch
        self.id = "{S}" + str(random.randint(10000, 99999999))
        self.itm = {}
    
    def _checkTimeouts(self):
        pass

    # TODO: Dynamic ARP inspection for DHCP packets (DHCP snooping)
    def handleAll(self, data):
        # Before evaluating, add incoming data to ARP table
        self.mti[data["L2"]["From"]] = data["L2"]["FromLink"]
        self.itm[data["L2"]["FromLink"]] = data["L2"]["From"]
        if self.DEBUG == 1: print(self.id, "Updated ARP table:", self.mti)
        
        # ARP table lookup
        if data["L2"]["To"] in self.mti:
            if self.DEBUG: print(self.id, "Found", data["L2"]["To"], "in ARP table")
            # Grab the link ID associated with the TO field (in the ARP table),
            # then get the link object from that ID
            #link = self.getLinkFromID( self.mti[ data["To"] ])
            #self.send(data, link.id)
            self.send(data, self.mti[ data["L2"]["To"] ])

        else: # Flood every interface with the request
            if self.DEBUG: print(self.id, "flooding")
            for link in self.links:
                if link.id != data["L2"]["FromLink"]: # Dont send back on the same link
                    # Python shenanigans: Make sure to flood with a *copy*
                    # and not a reference to the same data dictionary
                    # This is now handled in send()
                    self.send(data, link.id)

class Host(L3Device):
    def __init__(self, ips=[], connectedTo=[], debug=1):
        super().__init__(ips, connectedTo, debug)
        # L2
        self.id = "-H-" + str(random.randint(10000, 99999999))

        # L3
        self.DHCPClient = DHCPClientHandler(self.id, self.links, self.DEBUG)
        self.nmask = ""
        self.gateway = ""
        self.lease = (-1, -1) # (leaseTime, time (s) received the lease)
        self.lease_left = -1
        self.DHCP_FLAG = 0 # 0: No IP --- 1: Awaiting ACK --- 2: Received ACK & has active IP
        self.gateway = ""
    
    def _checkTimeouts(self):
        # DHCP
        if self.lease[0] >= 0:
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            print(self.id, "===", self.lease_left, "/", self.lease[0])
            if self.lease_left <= 0.5 * self.lease[0] and self.DHCP_FLAG != 1:
                if self.DEBUG: print("(DHCP)", self.id, "renewing ip", self.ip)
                self.DHCP_FLAG = 1
                self.sendDHCP("Renew")

############################################################
class Router(L3Device):
    def __init__(self, ips, connectedTo=[], debug=1):
        super().__init__(ips, connectedTo, debug)
        self.id = "=R=" + str(random.randint(10000, 99999999))

    def _checkTimeouts(self):
        pass
        
class Link:
    """ Connects two devices """
    def __init__(self, dl=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.dl = dl

class DHCPServer(L3Device):
    def __init__(self, ips, connectedTo, debug=1): # DHCPServer
        super().__init__(ips, connectedTo, debug) # DHCPServer
        self.id = "=DHCP=" + str(random.randint(10000, 99999999))
        self.nmask = "255.255.255.0"
        print("DHCP IP INIT:", self.ips[0], self.ips)
        self.DHCPServerHandler = DHCPServerHandler(self.ips[0], self.nmask, self.id, self.DEBUG)
        
    def _checkTimeouts(self):
        # DHCP lease expiry check
        # IP: (chaddr, lease_offer, lease_give_time)
        del_ips = []
        for k, v in self.DHCPServerHandler.leased_ips.items():
            time_left = (v[2] + v[1]) - int(time.time())
            if time_left <= 0:
                # For now, just delete the entry. TODO: Clean up entry deletion procedure per RFC
                # Mark the entry as deleted
                del_ips.append(k)

        # Then, actually delete it
        if del_ips:
            for key in del_ips: del self.DHCPServerHandler.leased_ips[k]
            if self.DEBUG: print("(DHCP)", self.id, "deleted entries from lease table")

    def handleDHCP(self, data):
        response, link = self.DHCPServerHandler.handleDHCP(data)
        self.send(response, link)

if __name__ == "__main__":

    #A, B, C = Host(), Host(), Host()
    #S1 = Switch([A])
    #R1 = Router(["10.10.10.1"])
    
    A = Host()
    S1 = Switch([A], debug=0)
    D = DHCPServer("10.10.10.1", [S1])
    A.sendDHCP("Init")
