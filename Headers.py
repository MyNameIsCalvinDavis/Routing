import random

"""
Supported Protocols:
DHCP
ARP

"""



"""
DHCP RFC 2131
0                   1                   2                   3
0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|     op (1)    |   htype (1)   |   hlen (1)    |   hops (1)    |
+---------------+---------------+---------------+---------------+
|                            xid (4)                            |
+-------------------------------+-------------------------------+
|           secs (2)            |           flags (2)           |
+-------------------------------+-------------------------------+
|                          ciaddr  (4)                          |
+---------------------------------------------------------------+
|                          yiaddr  (4)                          |
+---------------------------------------------------------------+
|                          siaddr  (4)                          |
+---------------------------------------------------------------+
|                          giaddr  (4)                          |
+---------------------------------------------------------------+
|                          chaddr  (16)                         |
+---------------------------------------------------------------+
|                          sname   (64)                         |
+---------------------------------------------------------------+
|                          file    (128)                        |
+---------------------------------------------------------------+
|                          options (variable)                   |
+---------------------------------------------------------------+
OP                  Request 1 (D / R) or Response 2 (O / A)
htype               1 for ethernet, all we use here
hardwareaddrlen     Length of hardware address
hops                TTL
xid                 Transaction ID, randomly generated
seconds             Seconds since start of DORA from client, recorded by server
flags               0: Broadcast --- 1: unicast
ciaddr              Client address
yiaddr              IP being offered by the server to the client
siaddr              IP of DHCP server
giaddr              IP of gateway
chaddr              MAC of client
sname, file         optional fields, not used here
options             DORA uses message 53, which is all we will use. This field will 
                    contain instead a single number, D(1) O(2) R(3) A(5)
"""
# https://www.netmanias.com/en/post/techdocs/5998/dhcp-network-protocol/understanding-the-basic-operations-of-dhcp
# https://avocado89.medium.com/dhcp-packet-analysis-c84827e162f0
# Should fill in: op, xid, ciaddr, yiaddr, siaddr, giaddr, chaddr
def createDHCPHeader(op=1, htype=1, hardwareaddrlen=6,
                     hops=-1, xid=random.randint(1000000000, 9999999999),
                     seconds=0, flags=0, ciaddr="0.0.0.0", yiaddr="0.0.0.0",
                     siaddr="0.0.0.0",giaddr="0.0.0.0", chaddr="", options={}):

    d = {
        "op":op,
        "htype":htype,
        "hardwareaddrlen":hardwareaddrlen,
        "hops":hops, # No limit by default
        "xid":xid,
        "seconds":seconds,
        "flags":flags,
        "ciaddr":ciaddr,
        "yiaddr":yiaddr,
        "siaddr":siaddr,
        "giaddr":giaddr,
        "chaddr":chaddr,
        "sname":"",
        "file":""
    }

    for option_name, option_value in options.items():
        d[option_name] = option_value

    return d
        


