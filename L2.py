from Device import *
from L3 import L3Device


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
        self.lthread.start()

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
                if self.DEBUG == 2:
                    Debug(self.id, "Initializing connection with", type(device), device.id,
                        color="blue", f=self.__class__.__name__
                    )
                if isinstance(device, L3Device):
                    your_interface.DHCPClient = DHCPClientHandler(device.id, link.id, debug=1)
                    your_interface.ICMPHandler = ICMPHandler(device.id, link.id, "0.0.0.0", None, debug=1)
                    your_interface.ARPHandler = ARPHandler(device.id, link.id, "0.0.0.0", debug=1)
                    device._associateIPsToInterfaces() # Possibly in need of a lock
                #else:
                    #print(self.id, type(device))

"""
TODO: A static IP host doesn't know where the gateway is

"""

class Switch(L2Device):
    def __init__(self, connectedTo=[], debug=1): # Switch
        self.id = "{S}" + str(random.randint(10000, 99999999))
        self.switch_table = {}

        super().__init__(connectedTo, debug, self.id) # Switch

    def _checkTimeouts(self):
        return

    # TODO: Dynamic ARP inspection for DHCP packets (DHCP snooping)
    def handleData(self, data, oninterface):
        # In this case a Switch does not care about which interface it came in on
        # Before evaluating, add incoming data to switch table
        self.switch_table[data["L2"]["From"]] = data["L2"]["FromLink"]

        # Switch table lookup
        if data["L2"]["To"] in self.switch_table:
            if self.DEBUG: 
                Debug(self.id, "Found", data["L2"]["To"], "in switch table",
                    color="green", f=self.__class__.__name__
                )
            
            # Find which interface to send out to, based on the To field
            for interface in self.interfaces:
                if self.switch_table[ data["L2"]["To"] ] == interface.linkid:
                    self.send(data, interface)
                    break

        else: # Flood every interface with the request
            if self.DEBUG:
                Debug(self.id, "flooding interfaces",
                    color="green", f=self.__class__.__name__
                )
            for interface in self.interfaces:
                if interface.linkid != data["L2"]["FromLink"]: # Dont send back on the same link
                    self.send(data, interface)

