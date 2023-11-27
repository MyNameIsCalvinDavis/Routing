from L2 import *
from L3 import *
import asyncio
import time

def pprint(*args, end="\n"):
    Debug("", *args, color="white", f="main")

async def topology2():
    """
                                          3.3.3.0
                 A               B           C 
        1.1.1.0  |               |           | 
                 R1 ------------ S1 -------- R2          D
                        <--- 2.2.2.0 --->    |           |
                                             |  4.4.4.0  |
                                             S2 -------- S3
    A: 1.1.1.2
    R1: 1.1.1.1, 2.2.2.1
    B: 2.2.2.2
    R2: 2.2.2.10, 3.3.3.1, 4.4.4.1
    C: 3.3.3.2
    D: 4.4.4.2
    """
    A = Host(["1.1.1.2/24"])

    B = Host(["2.2.2.2/24"])
    S1 = Switch([B], debug=0)

    R1 = Router(["1.1.1.1/24", "2.2.2.1/24"], [A, S1], debug=2)
    A.interfaces[0].gateway = "1.1.1.1/24"

    #B.interfaces[0].gateway = "2.2.2.10/24" # Bs default gateway is R2!
    B.interfaces[0].gateway = "2.2.2.1/24" # Bs default gateway is R1!

    C = Host(["3.3.3.2/24"])

    # 4.4.4.0/24
    D = Host(["4.4.4.2/24"])
    S3 = Switch([D], debug=0)
    S2 = Switch([S3], debug=0)

    R2 = Router(["2.2.2.10/24", "3.3.3.1/24", "4.4.4.1/24"], [S1, C, S2])
    return A, B, C, D, R1, R2, S1, S2, S3

async def topology1():
    """
    A ----- B
            |
    C ----- D
    A: 1.1.1.2
    B: 1.1.1.3
    C: 1.1.1.4
    D: 1.1.1.5
    """
    A = Device(["1.1.1.2/24"])
    B = Device(["1.1.1.3/24"], [A])
    C = Device(["1.1.1.4/24"])
    D = Device(["1.1.1.5/24", "1.1.1.6/24"], [C, B])
    return A, B, C, D

async def DeviceTest():
    # Test to see if Device initialization and basic connection works
    devices = await topology1()
    for device in devices:
        print([x.ip for x in device.interfaces])
        print(device)
        

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
    # A --- S --- R --- S --- B
    A = Host(["1.1.1.2/24"])
    B = Host(["2.2.2.2/24"])

    S1 = Switch([A], debug=0)
    S2 = Switch([B], debug=0)
    R1 = Router(["1.1.1.1/24", "2.2.2.1/24"], [S1, S2])

    A.interfaces[0].gateway="1.1.1.1/24"
    B.interfaces[0].gateway="2.2.2.1/24"
    A.sendICMP(B.getIP())


def ICMPTest_DifferentSubnet2():
    """
    Given topology1():
    A -> B
    """
    A, B, C, D, R1, R2, S1, S2, S3 = topology1()
    print(S1)
    print(R1)
    A.sendICMP(B.getIP())

def ICMPTest_DifferentSubnet3():
    """
    Given topology1():
    A -> C
    """
    A, B, C, D, R1, R2, S1, S2, S3 = topology1()

    # Add 1.1.1.0/24 route to R2
    route = ("S", "1.1.1.0/24", "2.2.2.1/24", R2.interfaces[0])
    R2.addRoute(route)
    
    # Add 3.3.3.0/24 route to R1
    route = ("S", "3.3.3.0/24", "2.2.2.10/24", R1.interfaces[1])
    R1.addRoute(route)
    R2.DEBUG = 1
    S1.DEBUG = 0

    A.sendICMP(C.getIP())
    

def ARP_Router_to_Host():
    A = Host(["1.1.1.2/24"])
    R1 = Router(["1.1.1.1/24"], [A, B])
    A.sendARP(B.getIP())

def SendArpToRouter():
    A = Host(["1.1.1.2/24"])
    R1 = Router(["1.1.1.1/24"], [A])
    A.sendARP(R1.getIP())
    R1.sendARP(A.getIP())

async def main():
    await DeviceTest()
    #DHCPTest()
    #await ARPTest()
    #ICMPTest_SameSubnet()
    #ICMPTest_DifferentSubnet1()
    #ICMPTest_DifferentSubnet2()
    #ICMPTest_DifferentSubnet3()
    #SendArpToRouter()



if __name__ == "__main__":
    asyncio.run( main() )
    #main()
