import random
import time
import threading
import os, sys
from Debug import *
from Device import Device
from L2 import *
from L3 import *

import asyncio
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

from abc import ABC, abstractmethod
import copy
from Headers import *
from DHCP import DHCPServerHandler, DHCPClientHandler
from ARP import ARPHandler
from Device import Device
import pprint

random.seed(123)

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



"""
TODO: A static IP host doesn't know where the gateway is

"""

class Switch(L2Device):
    def __init__(self, connectedTo=[], debug=1): # Switch
        self.id = "{S}" + str(random.randint(10000, 99999999))
        super().__init__(connectedTo, debug, self.id) # Switch

    async def _checkTimeouts(self):
        return

    # TODO: Dynamic ARP inspection for DHCP packets (DHCP snooping)
    async def handleData(self, data):
        # Before evaluating, add incoming data to switch table
        self.ARPHandler.switch_table[data["L2"]["From"]] = data["L2"]["FromLink"]

        #self.itm[data["L2"]["FromLink"]] = data["L2"]["From"]
        #if self.DEBUG == 1: print(self.id, "Updated ARP table:", self.ARPHandler.mti)
        
        # ARP table lookup
        if data["L2"]["To"] in self.ARPHandler.switch_table:
            if self.DEBUG: print(self.id, "Found", data["L2"]["To"], "in ARP table")
            # Grab the link ID associated with the TO field (in the ARP table),
            # then get the link object from that ID
            self.send(data, self.ARPHandler.switch_table[ data["L2"]["To"] ])

        else: # Flood every interface with the request
            if self.DEBUG: print(self.id, "flooding")
            for link in self.links:
                if link.id != data["L2"]["FromLink"]: # Dont send back on the same link
                    self.send(data, link.id)

class Link:
    """ Connects two devices """
    def __init__(self, dl=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.dl = dl







