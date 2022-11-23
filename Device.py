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
from ICMP import ICMPHandler
import L2
import pprint

random.seed(123)

"""
Asyncio is being used to simulate sent packet timeouts. One
design decision was to make any sendX() function blocking, without
also blocking the main thread. I do this because I want a sendX() function
to wait until a response to that packet has been received, but not lock up
the main thread while doing so.

Asyncio handles this problem by calling some sendX(), and then internally
calling `await asyncio.sleep(0)` in a loop for T (timeout) seconds until some
condition has been met. This condition is often a flag in the specific handler
being changed as a result of a final packet, like a DHCP ACK, or an ARP Response
flag. Looping like this also frees up the CPU to do other tasks while it waits
asynchronously, meaning the function blocks, but the program does not.

This is a necessary design decision because in traditional multithreaded
socket programming, you make a new thread to handle a single connection.
Here, a single thread handles an entire device, and individual packets and
frames instead. To avoid creating a million threads for every sent out
packet or frame, we use asyncio.

As a result, many of the functions here use the async modifier, not necessarily
because they are designed to be asynchronous, but because they are another
coroutine which can be jumped to following `await asyncio.sleep(0)` in a
timeout loop somewhere.
"""

# Abstract Base Class
class Device(ABC):
    def __init__(self, connectedTo=[], debug=1, ID=None): # Device
        """
        Base class which represents all devices. All Devices can:
            - Send ARP Requests and receive ARP responses
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
        self.interfaces = []

        # To be used as a recipient for send(), read by listen()
        self.listen_buffer = []

        self.lock = threading.Lock()
        self.thread_exit = False
        self._initConnections(connectedTo)

        # ARP
        #self.ARPHandler = ARPHandler(self.id, self.interfaces, self.DEBUG)
        
        # Asyncio requires silly nonsense when paired with threading
        def async_listen_start():
            asyncio.run(self.listen())

        # Start the listening thread on this device
        self.lthread = threading.Thread(target=async_listen_start, args=())
        self.lthread.start()

    def __del__(self):
        # If this object falls out of scope, safely terminate the running thread
        # Without leveraging multiprocessing or pkill, we can't kill it directly (unsafely)
        self.thread_exit = True
    
    async def listen(self):
        while True:
            if self.thread_exit: return
            await asyncio.sleep(self.listen_delay)
            await self._checkTimeouts()
            if self.listen_buffer:
                data = self.listen_buffer.pop(0)
                # Grab the interface it came in on
                interface = findInterfaceFromLinkID(data["L2"]["FromLink"], self.interfaces)
                if self.DEBUG == 1: 
                    Debug(self.id, "got data from", Debug.colorID(self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id), 
                        color="green", f=self.__class__.__name__
                    )
                if self.DEBUG == 2:
                    Debug(self.id, "got data from", Debug.colorID(self.getOtherDeviceOnInterface(data["L2"]["FromLink"]).id),
                        data, 
                        color="blue", f=self.__class__.__name__
                    )
                await self.handleData(data, interface)
    
    @abstractmethod
    async def handleData(self, data, oninterface):
        """
        Should be prepared to handle incoming data on whatever layer and process
        it accordingly. Ex: A switch should handle (or redirect) ARP-related data,
        but can probably normally forward anything above L3.
        """
        raise NotImplementedError("Must override this method in the child class")

    @abstractmethod
    def _initConnections(self, connectedTo):
        """
        - Create a Link between me and every other_device in ConnectedTo
        - Create an Interface with that Link, append to self.interfaces
        - Create another Interface with that Link, append to other_device.interfaces

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

    async def sendARP(self, targetIP, oninterface=None, timeout=5):
        print(self.id + " sending ARP to " + targetIP)
        """
        Send an ARP request to another device on the same subnet. By default,
        send out this request on the first interface.
        
        :param targetIP: IP of target device
        :param oninterface: optional, the interface object to send the request on
        """
        
        if not oninterface:
            oninterface = self.interfaces[0]

        if not isinstance(targetIP, str):
            raise ValueError("TargetIP must be string, given: " + str(targetIP) )
        
        # Internally:
        # Establish targetIP as -1 and change it upon receiving an ARP response
        print(self.id + str(self.interfaces))
        p = oninterface.ARPHandler.sendARP(targetIP)
        self.send(p, oninterface)

        # Here, check whether or not the target ip has been populated with an ID (MAC)
        now = time.time()
        if timeout:
            while (time.time() - now) < timeout:
                if oninterface.ARPHandler.arp_cache[targetIP] != -1:
                    # ARP Response received!
                    return oninterface.ARPHandler.arp_cache[targetIP]
                await asyncio.sleep(0) # Bad practice? I dont know what im doing
        return False
            

    async def handleARP(self, data, oninterface=None):
        """
        Handle incoming ARP data

        :param data: See `Headers.makePacket()`, dict
        """
        if not oninterface:
            oninterface = self.interfaces[0]

        p = oninterface.ARPHandler.handleARP(data)

        if p: self.send(p, oninterface)
        #else:
        #    # Fire an event
        #    self.fireEvent("ARPRESPONSE")

    def send(self, data, oninterface=None):
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
        if oninterface:
            assert isinstance(oninterface, L2.Interface)
            assert "_I_" in oninterface.id
        if oninterface == None:
            oninterface = self.interfaces[0]

        # Is data in the right format?
        for k, v in data.items():
            if v == "": continue
            if not k in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"] or not isinstance(v, dict):
                print("Data: ", data)
                raise ValueError("data not in the correct format")

        # Don't modify the original dict
        # This 26 character line represents at least 6 hours of my day
        data = copy.deepcopy(data)

        #onlinkID = self.getInterfaceFromID(oninterfaceID).linkid
        data["L2"]["FromLink"] = oninterface.linkid

        end = self.getOtherDeviceOnInterface(oninterface.linkid)

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
    
    def getInterfaceFromID(self, ID):
        """
        Given an Interface ID, return its instance

        :returns: Interface
        """
        if not isinstance(ID, str): raise ValueError("ID must be of type <str>")
        if not "_I_" in ID: raise ValueError("Provided ID " + ID + " not a link ID")
        
        for interface in self.interfaces:
            if interface.id == ID:
                return interface
        else:
            raise ValueError("LinkID " + ID + " not located in " + self.id + " interfaces")

    def getLinkFromID(self, ID):
        """
        Given a Link ID, return its instance
            
        :returns: Link
        """
        if not isinstance(ID, str): raise ValueError("ID must be of type <str>")
        if not "[L]" in ID: raise ValueError("Provided ID " + ID + " not a link ID")
        
        for interface in self.interfaces:
            if interface.linkid == ID:
                return interface.link
        else:
            raise ValueError("LinkID " + ID + " not located in " + self.id + " interfaces")
