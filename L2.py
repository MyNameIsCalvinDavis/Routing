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

    def _initConnections(self, connectedTo):
        """
        Create a link between me and every device in connectedTo, and vice versa.

        :param connectedTo: A list of Devices
        """
        for device in connectedTo:
            link = Link([self, device])
            my_interface = Interface(link, "0.0.0.0", self.id)
            your_interface = Interface(link, "0.0.0.0", device.id)

            # Create my interface to you
            if not my_interface in self.interfaces:
                self.interfaces.append(my_interface)

            # Create your interface to me
            if not your_interface in device.interfaces:
                device.interfaces.append(your_interface)
                if isinstance(device, L3Device):
                    device._associateIPsToInterfaces() # Possibly in need of a lock

"""
TODO: A static IP host doesn't know where the gateway is

"""

class Switch(L2Device):
    def __init__(self, connectedTo=[], debug=1): # Switch
        self.id = "{S}" + str(random.randint(10000, 99999999))
        self.switch_table = {}

        super().__init__(connectedTo, debug, self.id) # Switch

    async def _checkTimeouts(self):
        return

    # TODO: Dynamic ARP inspection for DHCP packets (DHCP snooping)
    async def handleData(self, data, oninterface):
        # In this case a Switch does not care about which interface it came in on

        # Before evaluating, add incoming data to switch table
        self.switch_table[data["L2"]["From"]] = data["L2"]["FromLink"]

        # Switch table lookup
        if data["L2"]["To"] in self.switch_table:
            if self.DEBUG: print(self.id, "Found", data["L2"]["To"], "in switch table")
            
            # Find which interface to send out to, based on the To field
            for interface in self.interfaces:
                if self.switch_table[ data["L2"]["To"] ] == interface.linkid:
                    self.send(data, interface)
                    break

        else: # Flood every interface with the request
            if self.DEBUG: print(self.id, "flooding")
            for interface in self.interfaces:
                if interface.linkid != data["L2"]["FromLink"]: # Dont send back on the same link
                    self.send(data, interface)

class Link:
    """ Connects two devices """
    def __init__(self, dl=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.dl = dl

class Interface:
    def __init__(self, link, ip, parentID):
        self.id = "_I_" + str(random.randint(10000, 99999999))
        self.link = link
        self.linkid = link.id
        self.ip = ip

        self.DHCPClient = DHCPClientHandler(parentID, self.linkid)

        # Will also have gateway / nmask, and anything else important per interface
        self.gateway = ""
        self.nmask = ""
        # Note: This information may or may not conflict with whatever is in self.DHCPClient.
        # If this interface was configured with DHCP, they will be the same
        # If not, then the DHCPClient contains defualt into and should not be referred to

    def __str__(self):
        return "(" + self.id + ":" + self.ip + ")"
    def __repr__(self):
        return "(" + self.id + ":" + self.ip + ")"






