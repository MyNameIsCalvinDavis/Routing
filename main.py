from L2 import *
from L3 import *
import asyncio


async def main():
    #A, B, C = Host(), Host(), Host()
    #S1 = Switch([A])
    #R1 = Router(["10.10.10.1"])
    #A = Host()
    #R1 = Router("10.10.10.1")
    #S1 = Switch([A, R1])
    #A.sendARP(R1.id)
    
    #A = Host()
    #S1 = Switch([A], debug=0)
    #D = DHCPServer("10.10.10.1", [S1])
    #A.sendDHCP("Init")

    A = Host()
    B = Host()
    D1 = DHCPServer("1.1.1.2", debug=1)
    S1 = Switch([A, B, D1], debug=0)

    await A.sendDHCP("init", timeout=None)
    await B.sendDHCP("init", timeout=None)

if __name__ == "__main__":
    asyncio.run( main() )
