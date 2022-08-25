import random
import time
import threading
from abc import ABC, abstractmethod
import copy
from Headers import *
from DHCP import DHCPServerHandler, DHCPClientHandler
from ARP import ARPHandler

random.seed(123)

# Abstract Base Class
class Device(ABC):
    def __init__(self, connectedTo=[], debug=1, ID=None): # Device
        """
        Base class which represents all devices. All Devices can:
            - Send ARP Requests and receive ARP responses
            - Utilize DHCP Client functionality
            - Get information about the devices attached to them
        
        All Devices must:
            - _initConnections() with devices in connectedTo
            - listen() for incoming data. Must be a while loop query on self.buffer, nothing else
                - _checkTimeouts() in this listener, or another managed thread
        
        :param connectedTo: List of Devices
        :param debug: See below
        :param ID: Optionally a child class can provide its ID to be used with inits of some Handler, like DHCP or ARP
        """

        # Debug 0 : Show nothing
        # Debug 1 : Show who talks to who
        # Debug 2 : Show who sends what to who
        self.DEBUG = debug

        # For visualization purposes
        self.listen_delay = 0.5
        
        if ID: self.id = ID
        else: self.id = "___" + str(random.randint(10000, 99999999))
        self.links = []
        self.buffer = []
        self.lock = threading.Lock()

        self.thread_exit = False
        self._initConnections(connectedTo)

        # ARP
        self.ARPHandler = ARPHandler(self.id, self.links, self.DEBUG)

        # Start the listening thread on this device
        self.lthread = threading.Thread(target=self.listen, args=())
        self.lthread.start()
    
    def __del__(self):
        # If this object falls out of scope, safely terminate the running thread
        # Without leveraging multiprocessing or pkill, we can't kill it directly (unsafely)
        self.thread_exit = True
    
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
                
                self.handleData(data)
    #@abstractmethod
    #def listen(self):
    #    """
    #    Executed by self.lthread, should be querying self.buffer and directing the
    #    data to wherever it should go based on its contents
    #    """
    #    raise NotImplementedError("Must override this method in the child class")
    
    @abstractmethod
    def handleData(self, data):
        raise NotImplementedError("Must override this method in the child class")

    @abstractmethod
    def _initConnections(self, connectedTo):
        """
        Should populate self.links and the links in connectedTo's Devices with
        a Link object representing a single connection, from self Device

        :param connectedTo: A list of Devices
        """
        raise NotImplementedError("Must override this method in the child class")
    
    # Some L2 devices won't have timeouts; too bad
    @abstractmethod   
    def _checkTimeouts(self):
        """
        Should be executed periodically either by listen() or some other non-main thread,
        can be empty if a device has no periodic checks to make, but must be implemented.
        """
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
    
    def sendARP(self, targetID, onLinkID=None):
        """
        Send an ARP request to another device on the same subnet
        
        :param targetID: id parameter of target device
        :param onLinkID: optional, id parameter of link to be send out on
        """
        assert isinstance(targetID, str)
        if onLinkID: assert isinstance(onLinkID, str)

        p, link = self.ARPHandler.sendARP(targetID, onLinkID)
        self.send(p, link)

    def handleARP(self, data):
        """
        Handle incoming ARP data

        :param data: See `Headers.makePacket()`, dict
        """
        p, link = self.ARPHandler.handleARP(data)
        if p: self.send(p, link)

    def send(self, data, onlinkID=None):
        #print("    ", self.id, "sending to", onlinkID)
        """
        Send data on a link.
        
        This method finds the device on the other end of the given linkID,
        then appends data to its buffer. By default, it sends data out on the
        first interface on this device. For multi interface Devices like a Switch
        or Router, onlinkID may be defined.
        
        :param data: See `Headers.makePacket()`, dict
        :param onLinkID: optional, id parameter of link to be send out on
        """
        
        assert isinstance(data, dict)
        if onlinkID:
            assert isinstance(onlinkID, str)
            assert "[L]" in onlinkID
        if onlinkID == None:
            onlinkID = self.links[0].id

        #print("    Post:", self.id, "sending to", onlinkID)
        
        # Is data in the right format?
        for k, v in data.items():
            if v == "": continue
            if not k in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"] or not isinstance(v, dict):
                print("Data: ", data)
                raise ValueError("data not in the correct format")

        # Don't modify the original dict
        # This 26 character line represents at least 6 hours of my day
        data = copy.deepcopy(data)

        data["L2"]["FromLink"] = onlinkID

        end = self.getOtherDeviceOnInterface(onlinkID)
        if self.DEBUG == 1: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"])
        if self.DEBUG == 2: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"] + "\n    " + str(data))

        self.lock.acquire()
        end.buffer.append(data)
        self.lock.release()

    def getOtherDeviceOnInterface(self, onlinkID):
        """
        Given a link ID, find the single device on the other end of it

        :param onLinkID: id parameter of a link
        :returns: Device instance
        """
        if not isinstance(onlinkID, str): raise ValueError("onlinkID must be of type <str>")
        onlink = self.getLinkFromID(onlinkID)
        # Find the other device on a link
        if onlink.dl[0].id == self.id:
            return onlink.dl[1]
        else:
            return onlink.dl[0]

    def getLinkFromID(self, ID):
        """
        Given a Link ID, return its Link instance
            
        :returns: Link instance
        """

        if not isinstance(ID, str): raise ValueError("ID must be of type <str>")
        if not "[L]" in ID: raise ValueError("Provided ID " + ID + " not a link ID")

        # First, check to see if that link is on this devices interfaces at all
        ids = [x.id for x in self.links]
        #print("    My links:", ids)
        if not ID in ids:
            raise ValueError("LinkID " + ID + " not located in " + self.id + " interfaces")

        for link in self.links:
            if link.id == ID:
                return link

    
class L2Device(Device):
    def __init__(self, connectedTo=[], debug=1, ID=None):
        """
        A Device that operates primarily on L2. A Layer 2 device must define how it handles
        frames with handleData(), defined in Device.

        :param connectedTo: List of Devices
        :param debug: See `Device.DEBUG`
        :param ID: Optionally a child class can provide its ID to be used with inits of some Handler, like DHCP or ARP
        """
        super().__init__(connectedTo, debug, ID)
        self.itm = {}

    def _initConnections(self, connectedTo):
        """
        Create a link between me and every device in connectedTo, and vice versa.

        :param connectedTo: A list of Devices
        """
        for device in connectedTo:
            link = Link([self, device])
            if not link in self.links:
                #print("    ", self.id, "appending", link.id, "to my links")
                self.links.append(link)
            if not link in device.links:
                #print("    ", self.id, "appending", link.id, "to", device.id, "links")
                device.links.append(link)
                if isinstance(device, L3Device):
                    device.setIP("0.0.0.0", link.id)
                    device._associateIPsToLinks() # Possibly in need of a lock


class L3Device(Device):
    def __init__(self, ips=[], connectedTo=[], debug=1, ID=None): # L3Device
        """
        A Device that operates primarily on L3. This class defines a standard handleData()
        function to be expanded upon. At the moment, all L3 devices handle the same way.

        :param connectedTo: List of Devices
        :param debug: See `Device.DEBUG`
        :param ID: Optionally a child class can provide its ID to be used with inits of some Handler, like DHCP or ARP
        """
        self.linkid_to_ip = {}

        # Make ips always be a list, with ["0.0.0.0"] as default
        if ips: self.ips = ips
        else:   self.ips = ["0.0.0.0"]
        if isinstance(self.ips, str): self.ips = [self.ips]

        super().__init__(connectedTo, debug, ID) # L3Device
    
    def handleData(self, data):
        """
        Handle data as a L3 device would. All this does is read the L2/L3 information
        and forward the data to the correct handler, depending on port / ethertype / etc
        
        :param data: See `Headers.makePacket()`, dict
        """
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
        Upon forming a link, a device now has an interface and an IP. Same as L2Device,
        just that we now also associate IPs with links.

        :param connectedTo: A list of Devices
        """
        for device in connectedTo:
            link = Link([self, device])
            if not link in self.links:
                #self.ip = ("0.0.0.0", link.id)
                self.setIP("0.0.0.0", link.id)
                self.links.append(link)
            if not link in device.links:
                device.links.append(link)
                if isinstance(device, L3Device):
                    device.setIP("0.0.0.0", link.id)
                    device._associateIPsToLinks() # Possibly in need of a lock

        self._associateIPsToLinks()

    def _associateIPsToLinks(self):
        """
        Given self.links, associate each with the provided self.ips.
        If there are more links than IPs, each link gets associated
        with the default 0.0.0.0.
        """
        for i in range(len(self.links)):
            try:
                self.linkid_to_ip[self.links[i].id] = self.ips[i]
            except IndexError:
                self.linkid_to_ip[self.links[i].id] = "0.0.0.0"
                self.ips.append("0.0.0.0")
    
    def getIP(self, linkID=None):
        """
        Return the IP for linkID. By default, return the first link's IP, good
        for single interface devices.

        :param linkID: optional, the ID of the desired link
        """

        if not linkID: linkID = self.links[0].id
        return self.linkid_to_ip[linkID]

    def setIP(self, val, linkID=None):
        """
        Set the IP of a link. By default, set the first link's IP, good for
        single interface devices.
        
        :param val: The IP to set
        :param linkID: optional, the ID of the desired link
        """

        assert isinstance(val, str)
        if not linkID: linkID = self.links[0].id
        self.linkid_to_ip[linkID] = val

    #@ip.setter
    #def ip(self, val):
    #    """
    #    Set the ip of this Device. When set to a single string, it updates the first link's
    #    associated ip. When set to a tuple in the form of (<IP>, <LINKID>), it updates
    #    the linkid_to_ip dictionary for that linkID.

    #    :param val: Whatever ip is being set to, str, tup(str, str)
    #    """
    #    if isinstance(val, tuple): # self.ip = ("0.0.0.0", <LINKID>)
    #        onlinkid = val[1]
    #        self.linkid_to_ip[onlinkid] = val[0]
    #    elif isinstance(val, str): # self.ip = "0.0.0.0"
    #        onlinkid = self.links[0].id
    #        self.linkid_to_ip[onlinkid] = val
    #    else:
    #        raise("Can't set IP to " + str(type(val)) )
    
    ###### DHCP

    # By default, a L3Device has DHCP Client functionality

    ## Send D(iscover) or R(equest)
    def sendDHCP(self, context, onlink=None):
        p, link = self.DHCPClient.sendDHCP(context)
        self.send(p, link)
    
    def handleDHCP(self, data):
        p, link = self.DHCPClient.handleDHCP(data)

        # On DORA ACK, no packet is returned to send out
        if p: self.send(p, link)
        else:
            # Extract all of the goodies
            
            self.nmask = "255.255.255.255"
            self.gateway = "0.0.0.0"

            if 1 in data["L3"]["Data"]["options"]:
                self.nmask = data["L3"]["Data"]["options"][1]
            if 3 in data["L3"]["Data"]["options"]:
                self.gateway = data["L3"]["Data"]["options"][3]

            #self.ip = data["L3"]["Data"]["yiaddr"]
            self.setIP(data["L3"]["Data"]["yiaddr"])

            self.lease = (data["L3"]["Data"]["options"][51], int(time.time()) )
            self.lease_left = (self.lease[0] + self.lease[1]) - int(time.time())
            self.DHCP_FLAG = 2
            self.current_xid = -1

class Switch(L2Device):
    def __init__(self, connectedTo=[], debug=1): # Switch
        self.id = "{S}" + str(random.randint(10000, 99999999))
        super().__init__(connectedTo, debug, self.id) # Switch
        self.itm = {}

    def _checkTimeouts(self):
        pass

    # TODO: Dynamic ARP inspection for DHCP packets (DHCP snooping)
    def handleData(self, data):
        # Before evaluating, add incoming data to ARP table
        self.ARPHandler.mti[data["L2"]["From"]] = data["L2"]["FromLink"]
        self.itm[data["L2"]["FromLink"]] = data["L2"]["From"]
        if self.DEBUG == 1: print(self.id, "Updated ARP table:", self.ARPHandler.mti)
        
        # ARP table lookup
        if data["L2"]["To"] in self.ARPHandler.mti:
            if self.DEBUG: print(self.id, "Found", data["L2"]["To"], "in ARP table")
            # Grab the link ID associated with the TO field (in the ARP table),
            # then get the link object from that ID
            self.send(data, self.ARPHandler.mti[ data["L2"]["To"] ])

        else: # Flood every interface with the request
            if self.DEBUG: print(self.id, "flooding")
            for link in self.links:
                if link.id != data["L2"]["FromLink"]: # Dont send back on the same link
                    self.send(data, link.id)

class Host(L3Device):
    def __init__(self, ips=[], connectedTo=[], debug=1):
        self.id = "-H-" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id)

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
                if self.DEBUG: print("(DHCP)", self.id, "renewing ip", self.getIP())
                self.DHCP_FLAG = 1
                self.sendDHCP("Renew")

############################################################
class Router(L3Device):
    def __init__(self, ips, connectedTo=[], debug=1):
        self.id = "=R=" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id)

    def _checkTimeouts(self):
        pass
        
class Link:
    """ Connects two devices """
    def __init__(self, dl=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.dl = dl

class DHCPServer(L3Device):
    def __init__(self, ips, connectedTo, debug=1): # DHCPServer
        self.id = "=DHCP=" + str(random.randint(10000, 99999999))
        super().__init__(ips, connectedTo, debug, self.id) # DHCPServer

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
    #A = Host()
    #R1 = Router("10.10.10.1")
    #S1 = Switch([A, R1])
    #A.sendARP(R1.id)
    
    A = Host()
    S1 = Switch([A], debug=0)
    D = DHCPServer("10.10.10.1", [S1])
    A.sendDHCP("Init")
