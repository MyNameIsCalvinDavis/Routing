import random
import asyncio
import Handlers


class Link:
    """ Connects two devices """
    def __init__(self, connected=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.connected = connected
    
    def get_other(self, x):
        if len(self.connected) < 2: raise LookupError("This link only has one interface")
        return self.connected[1] if self.connected[0] == x else self.connected[0]
    
    def add(self, x):
        self.connected.append(x)

    def __contains__(self, d):
        return d in self.connected

class Interface:
    def __init__(self, _parent, id, ip=None):
        self.id = "{} ({}{})".format(_parent.id, "I", id)
        self.link = Link([self])
        self._parentDevice = _parent

        self.config = {
            "ip": ip if ip else "0.0.0.0",
            "gateway": None,
            "netmask": None
        }

        self.handlers = {
            #"DHCP": Handlers.DHCP_Client(self, debug=self.DEBUG),
            "ARP": Handlers.ARP(self, 1),
            #"ICMP": Handlers.ICMP(self, "0.0.0.0", debug=self.DEBUG)
        }

    @property
    def ip(self):
        return self.config["ip"]

    def __str__(self):
        return "(" + self.id + ":" + self.ip + ")"
    def __repr__(self):
        return "(" + self.id + ":" + self.ip + ")"

