import random


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

        self.DHCPClient = None
        self.ARPHandler = None
        self.ICMPHandler = None

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

