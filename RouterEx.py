import random
import time
import threading

random.seed(123)

class Device:
    def __init__(self, rID="1.1.1.1/24"):
        self.links = []
        self.lastDev = 0

        self.rID = rID.split("/")[0]
        self.mask = rID.split("/")[1]

    def sendData(self, nextHop, data):
        nextHop.data = (self.id, nextHop.id, data)
    
    @property
    def data(self): # This is a syntactic requirement, nothing more
        return None

    @data.setter
    def data(self, data):
        # When data is "set", actually just send it to the
        # next destination
        
        # (Src, Dst, data)
        if data[1] == self.id:
            print("Data reached me! I'm", self.id)
        #elif data[0] == self.id:
        #    print("Received data that I sent, is there a loop?", self.id)
        #    # Kill it
        else:
            # Send it as normal, atm just randomly
            nextHop = ""
            for link in self.links:
                for d in link.dl:
                    if d.id == self.id:
                        continue
                    else:
                        nextHop = d
            print(self.id, "==>", nextHop.id, data)
            time.sleep(1)

            # Send data to next destination
            x = threading.Thread(target=self.sendData, args=(nextHop, data,))
            x.start()

    def __str__(self):
        s = "\n"
        if isinstance(self, Router): s += "(" + self.id + ")\n"
        if isinstance(self, Switch): s += "{" + self.id + "}\n"
        for link in self.links:
            s += "  [" + link.id + "]\n"
            for device in link.dl:
                s += "    (" + device.id + ")\n"
        return s[:-1]

class Router(Device):

    def __init__(self, rID="1.1.1.1/24"):
        super().__init__(rID)
        # Until subnets exist, this will do
        self.id = "R" + str(random.randint(10000, 99999999))
        self.rt = {}

class Switch(Device):

    def __init__(self, rID="1.1.1.1/24"):
        super().__init__(rID)
        self.id = "S" + str(random.randint(10000, 99999999))
        self.at = {}
        self.links = []

class Link():
    # Connects Devices
    def __init__(self, dl=[]):
        self.id = "L" + str(random.randint(10000, 99999999))
        self.dl = dl # Device list
    
    def __str__(self):
        return str([x.id for x in self.dl])
    
def initRLinks(links):
    # Ensure devices have link associations
    for link in links:
        #print("Eval: Link", link.id) 
        for device in link.dl:
            if link not in device.links:
                #print("Adding", link.id, "to", device.id)
                device.links.append(link)
                #print(" Total Length of", device.id, "links: ", len(device.links))


# I don't feel like implementing a DHCP server
A = Router("1.1.1.1/24")
B = Router("1.1.1.2/24")
C = Router("1.1.1.3/24")

S1 = Switch("1.1.1.4/24")

L1 = Link( [S1, A] )
L2 = Link( [S1, B] )
L3 = Link( [S1, C] )

initRLinks([L1, L2, L3])

print(A, B, C, S1)

A.data = "Hello"
