from L2 import *
from L3 import *
import asyncio
import time

def pprint(*args, end="\n"):
    Debug("", *args, color="white", f="main")
    
async def DHCPTest():

    A = Host()
    D1 = DHCPServer("1.1.1.2/24", gateway="1.1.1.1/24", debug=1)
    S1 = Switch([A, D1], debug=0)

    await A.sendDHCP("init", timeout=5)
    time.sleep(1)
    pprint("As IP: ", A.getIP())

async def ARPTest():
    A = Host(["1.1.1.2/24"])
    B = Host(["1.1.1.3/24"])
    S1 = Switch([A, B])
    await A.sendARP(B.getIP())

async def ICMPTest_SameSubnet():
    A = Host(["1.1.1.2/24"])
    B = Host(["1.1.1.3/24"])
    S1 = Switch([A, B], debug=0)
    A.interfaces[0].gateway="abc"
    B.interfaces[0].gateway="abc"
    await A.sendICMP(B.getIP())
    await A.sendICMP(B.getIP())


async def ICMPTest_DifferentSubnet():
    #A = Host(["1.1.1.2/24"])
    #B = Host(["2.2.2.2/24"])
    #R1 = Router(["1.1.1.1/24", "2.2.2.1/24"], [A, B])
    #A.interfaces[0].gateway="abc"
    #B.interfaces[0].gateway="abc"
    #await A.sendICMP(B.getIP())
    #await A.sendICMP(B.getIP())
    pass

async def SendArpToRouter():
    A = Host(["1.1.1.2/24"])
    R1 = Router(["1.1.1.1/24"], [A])
    await A.sendARP(R1.getIP())

async def main():
    #await DHCPTest()
    #await ARPTest()
    #await ICMPTest_SameSubnet()
    await SendArpToRouter()


if __name__ == "__main__":
    asyncio.run( main() )
