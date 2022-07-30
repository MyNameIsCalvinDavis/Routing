import random
import time
import threading

random.seed(123)

MAC_BROADCAST="FFFF"

subnet = []

def initLinks(links):
    # Ensure devices on links internalize their link association
    for link in links:
        for device in link.dl:
            if link not in device.interfaces:
                device.interfaces.append(link)

def makePacket(name="", fr="", to="", fromlink="", data=""):
    return {
        "Name":name,
        "From":fr,
        "To":to,
        "FromLink":fromlink,
        "Data":data
    }
class Device:
    def __init__(self):
        self.id = "___" + str(random.randint(10000, 99999999))
        self.interfaces = []
        self.buffer = []
        self.lock = threading.Lock()

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
        if onlink == None:
            onlink = self.interfaces[0]
        end = self.getOtherInterface(onlink)
        p = makePacket(data["Name"], data["From"], data["To"], onlink.id, data["Data"])
        s = self.id + " ==> "+ self.getOtherInterface(onlink).id + " via "+ p["FromLink"] + "\n"
        s += "    " + str(data)

        print(s)

        self.lock.acquire()
        end.buffer.append(p)
        self.lock.release()

    def getOtherInterface(self, onlink):
        # Find the other device on a link
        if onlink.dl[0].id == self.id:
            return onlink.dl[1]
        else:
            return onlink.dl[0]

    def getLinkFromID(self, ID):
        for link in self.interfaces:
            if link.id == ID:
                return link
            

class Router(Device):
    def __init__(self):
        super().__init__()
        self.id = "=R=" + str(random.randint(10000, 99999999))
        
        # Start the listening thread on this device
        x = threading.Thread(target=self.work, args=())
        x.start()

    def work(self):
        while True:
            time.sleep(0.5)
            if self.buffer:
                data = self.buffer.pop(0)
                s = self.id + " got data from " + self.getOtherInterface(self.getLinkFromID(data["FromLink"])).id + "\n" + "    " + str(data)
                print(s)
                if data["Name"] == "DHCP-1":
                    # Get the interface it was on
                    data = makePacket("DHCP-2", self, data["From"], data["FromLink"])
                    self.send(data, data["FromLink"])

class Host(Device):
    def __init__(self):
        super().__init__()
        self.id = "-H-" + str(random.randint(10000, 99999999))
        self.mti = {}

        # Start the listening thread on this device
        x = threading.Thread(target=self.work, args=())
        x.start()

    def work(self):
        while True:
            time.sleep(0.5)
            if self.buffer:
                data = self.buffer.pop(0)
                s = self.id + " got data from " + self.getOtherInterface(self.getLinkFromID(data["FromLink"])).id + "\n" + "    " + str(data)
                print(s)
                
                if data["Name"] == "ARP":
                    # Receiving an ARP Request
                    if data["To"] == MAC_BROADCAST and data["Data"]["ID"] == self.id:
                        # Make a response
                        print(self.id, "got ARP-Rq, sending ARP-Rp")
                        p = makePacket("ARP", self.id, data["From"])
                        self.send(p)
                    
                    # Receiving an ARP Response
                    elif data["To"] == self.id:
                        print("To me!", self.id, "updating ARP table")
                        self.mti[data["From"]] = data["FromLink"]
                    else:
                        print(self.id, "ignoring", data["From"])#, data)

                elif data["Name"] == "DHCP" and data["To"] == self.id:
                    pass
                else:
                    print(self.id, "ignoring", data["From"], data)
                
"""
ARP:
{
    "Name:"ARP",
    "From":FROMADDR
}
"""
class Switch(Device):
    def __init__(self):
        super().__init__()
        self.id = "{S}" + str(random.randint(10000, 99999999))
        self.mti = {} # MAC to interface
        self.itm = {}

        # Start the listening thread on this device
        x = threading.Thread(target=self.work, args=())
        x.start()

    def work(self):
        while True:
            time.sleep(0.5)
            if self.buffer:
                data = self.buffer.pop(0)
                s = self.id + " got data from " + self.getOtherInterface(self.getLinkFromID(data["FromLink"])).id + "\n" + "    " + str(data)
                print(s)
            
                # Before evaluating, add incoming data to ARP table
                self.mti[data["From"]] = data["FromLink"]
                self.itm[data["FromLink"]] = data["From"]
                print("Updated ARP table:", self.mti)

                # ARP table lookup
                if data["To"] in self.mti:
                    print("Found in ARP table")
                    # Grab the link ID associated with the TO field (in the ARP table),
                    # then get the link object from that ID
                    link = self.getLinkFromID( self.mti[ data["To"] ])
                    self.send(data, link)

                else: # Flood every interface with the request
                    print(self.id, "flooding")
                    for link in self.interfaces:
                        end = self.getOtherInterface(link)
                        if end.id != data["From"]: # Dont send to self, or back to sender
                            self.send(data, link)
                            
class Link:
    def __init__(self, dl=[]):
        self.id = "[L]" + str(random.randint(10000, 99999999))
        self.dl = dl

A = Host()
B = Host()
C = Host()

S1 = Switch()

L1 = Link([A, S1])
L2 = Link([B, S1])
L3 = Link([C, S1])

initLinks([L1, L2, L3])


print(A, B, C)
print(S1)


print("Host A", A.id, "sending to host B", B.id)

p = makePacket("ARP", A.id, MAC_BROADCAST, data={"ID":B.id})
A.send(p)


