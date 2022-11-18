import random
import time
import threading
import os, sys
import asyncio

from abc import ABC, abstractmethod
import copy
from Headers import *
from Debug import Debug
from DHCP import DHCPServerHandler, DHCPClientHandler
from ARP import ARPHandler
import pprint

random.seed(123)

"""
Asyncio is being used to simulate sent packet timeouts. I could home
bake this functionality without coroutines by having various flags
and some framework or tuple format be respected, but that's another
format on top of all the other ones here, and I'd rather not make myself
and anyone else who uses this memorize or understand such a format.

Instead we go with coroutines, where a timeout is sending out
a packet and calling `await asyncio.sleep(n)` with n being the max
timeout. If the data exists / was changed, we consider
the send() a success, otherwise we consider the packet lost and
retransmit / etc. I'm not yet sure how this will work with
something like a TCP connection or a stream, if I get that far.

This ends up being a lot less code in the long run and is something I
can wrap with a more user friendly timeout framework later
"""

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

        # To be used as a recipient for send(), read by listen()
        self.listen_buffer = []

        # To be used as an immutable history of all received data on this device
        self.received_data = ()

        self._events = set()

        self.lock = threading.Lock()

        self.thread_exit = False
        self._initConnections(connectedTo)

        # ARP
        self.ARPHandler = ARPHandler(self.id, self.links, self.DEBUG)
        
        def async_listen_start():
            asyncio.run(self.listen())

        # Start the listening thread on this device
        #self.lthread = threading.Thread(target=self.listen, args=())
        self.lthread = threading.Thread(target=async_listen_start, args=())
        self.lthread.start()

    def fireEvent(self, *args):
        # Events are fired when things happen, whatever they may be.
        # We let the user define events arbitrarily, without a specific format,
        # such that they may create and listen for their own events
        
        if args in self._events:
            raise ValueError("Cannot add duplicate event, " + str(args) + " already in events")
        else:
            self._events.add(args)

    def deleteEvent(self, *args):
        # After checking for an event and finding it, you should delete it
        self._events.remove(args)

    def checkEvent(self, *args):
        if args in self._events:
            return True
        return False
    
    def __del__(self):
        # If this object falls out of scope, safely terminate the running thread
        # Without leveraging multiprocessing or pkill, we can't kill it directly (unsafely)
        self.thread_exit = True
    
    async def listen(self):
        while True:
            if self.thread_exit: return
            #time.sleep(self.listen_delay)
            await asyncio.sleep(self.listen_delay)
            await self._checkTimeouts()
            if self.listen_buffer:
                data = self.listen_buffer.pop(0)
                if self.DEBUG == 1: 
                    Debug(self.id, "got data from", Debug.colorID(self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id), 
                        color="green", f=self.__class__.__name__
                    )
                if self.DEBUG == 2:
                    Debug(self.id, "got data from", Debug.colorID(self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id),
                        str(data), 
                        color="green", f=self.__class__.__name__
                    )
                await self.handleData(data)
    
    @abstractmethod
    async def handleData(self, data):
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
    async def _checkTimeouts(self):
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
    
    async def sendARP(self, targetIP, onLinkID=None, timeout=5):
        """
        Send an ARP request to another device on the same subnet
        
        :param targetID: id parameter of target device
        :param onLinkID: optional, id parameter of link to be send out on
        """
        if not isinstance(targetIP, str):
            raise ValueError("TargetIP must be string, given: " + str(targetIP) )
        if onLinkID: assert isinstance(onLinkID, str)
        
        # Internally:
        # Establish targetIP as -1 and change it upon receiving an ARP response
        p, link = self.ARPHandler.sendARP(targetIP, onLinkID)
        self.send(p, link)

        # Here, check whether or not the target ip has been populated with an ID (MAC)
        now = time.time()
        if timeout:
            while (time.time() - now) < timeout:
                if self.ARPHandler.arp_cache[targetIP] != -1:
                    # ARP Response received!
                    return True
                await asyncio.sleep(0) # Bad practice? I dont know what im doing
        return False
            

    async def handleARP(self, data):
        """
        Handle incoming ARP data

        :param data: See `Headers.makePacket()`, dict
        """
        p, link = self.ARPHandler.handleARP(data)
        if p: self.send(p, link)
        #else:
        #    # Fire an event
        #    self.fireEvent("ARPRESPONSE")

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
        if self.DEBUG:
            Debug(self.id, "==>", Debug.colorID(end.id), "via", Debug.color(data["L2"]["FromLink"], "ul"), 
                color="green", f=self.__class__.__name__
            )
        #if self.DEBUG == 1: print(self.id + " ==> "+ end.id + " via "+ data["L2"]["FromLink"])

        self.lock.acquire()
        end.listen_buffer.append(data)
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
