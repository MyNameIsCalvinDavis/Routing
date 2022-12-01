from L2 import *
from L3 import *
import asyncio
import time

def pprint(*args, end="\n"):
    Debug("", *args, color="white", f="main")
    
def DHCPTest():

    A = Host()
    D1 = DHCPServer("1.1.1.2/24", gateway="1.1.1.1/24", debug=1)
    S1 = Switch([A, D1], debug=0)

    A.sendDHCP("init", timeout=5)
    time.sleep(1)
    pprint("As IP: ", A.getIP())

def ARPTest():
    A = Host(["1.1.1.2/24"])
    B = Host(["1.1.1.3/24"])
    S1 = Switch([A, B])
    A.sendARP(B.getIP())

def ICMPTest_SameSubnet():
    A = Host(["1.1.1.2/24"])
    B = Host(["1.1.1.3/24"])
    S1 = Switch([A, B], debug=0)
    A.interfaces[0].gateway="abc"
    B.interfaces[0].gateway="abc"
    A.sendICMP(B.getIP())
    B.sendICMP(A.getIP())

def ICMPTest_DifferentSubnet1():
    # A --- S -- R -- S--- B
    A = Host(["1.1.1.2/24"])
    B = Host(["2.2.2.2/24"])

    S1 = Switch([A], debug=0)
    S2 = Switch([B], debug=0)
    R1 = Router(["1.1.1.1/24", "2.2.2.1/24"], [S1, S2])

    A.interfaces[0].gateway="1.1.1.1/24"
    B.interfaces[0].gateway="2.2.2.1/24"
    A.sendICMP(B.getIP())

def ARP_Router_to_Host():
    A = Host(["1.1.1.2/24"])
    R1 = Router(["1.1.1.1/24"], [A, B])
    A.sendARP(B.getIP())

def SendArpToRouter():
    A = Host(["1.1.1.2/24"])
    R1 = Router(["1.1.1.1/24"], [A])
    A.sendARP(R1.getIP())
    R1.sendARP(A.getIP())

def main():
    #DHCPTest()
    #ARPTest()
    #ICMPTest_SameSubnet()
    ICMPTest_DifferentSubnet1()
    #SendArpToRouter()
    #SendArpToRouter()



if __name__ == "__main__":
    #asyncio.run( main() )
    main()
