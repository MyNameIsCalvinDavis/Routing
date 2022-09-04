from L2 import *
from L3 import *
import asyncio


async def main():
    A = Host()
    B = Host()
    R = Router(["1.1.1.1/24", "2.2.2.2/24"], debug=2)
    D1 = DHCPServer("1.1.1.2/24", gateway="1.1.1.1/24", debug=1)
    S1 = Switch([A, B, D1, R], debug=0)

    await A.sendDHCP("init", timeout=5)
    await B.sendDHCP("init", timeout=5)
    
    print("Bs IP: ", B.getIP())
    await A.sendICMP(B.getIP())

if __name__ == "__main__":
    asyncio.run( main() )
