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
    # A --- S --- R --- S --- B
    A = Host(["1.1.1.2/24"])
    B = Host(["2.2.2.2/24"])

    S1 = Switch([A], debug=0)
    S2 = Switch([B], debug=0)
    R1 = Router(["1.1.1.1/24", "2.2.2.1/24"], [S1, S2])

    A.interfaces[0].gateway="1.1.1.1/24"
    B.interfaces[0].gateway="2.2.2.1/24"
    A.sendICMP(B.getIP())

def topology1():
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
    #B.interfaces[0].gateway = "2.2.2.10/24" # Bs default gateway is R2!
    S1 = Switch([B], debug=0)

    R1 = Router(["1.1.1.1/24", "2.2.2.1/24"], [A, S1])
    A.interfaces[0].gateway = "1.1.1.1/24"
    B.interfaces[0].gateway = "2.2.2.1/24" # Bs default gateway is R1!

    C = Host(["3.3.3.2/24"])

    # 4.4.4.0/24
    D = Host(["4.4.4.2/24"])
    S3 = Switch([D], debug=0)
    S2 = Switch([S3], debug=0)

    R2 = Router(["2.2.2.10/24", "3.3.3.1/24", "4.4.4.1/24"], [S1, C, S2])
    return A, B, C, D, R1, R2, S1, S2, S3

def ICMPTest_DifferentSubnet2():
    A, B, C, D, R1, R2, S1, S2, S3 = topology1()
    print(S1)
    print(R1)
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
    #ICMPTest_DifferentSubnet1()
    ICMPTest_DifferentSubnet2()
    #SendArpToRouter()



if __name__ == "__main__":
    #asyncio.run( main() )
    main()
