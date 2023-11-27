import random

"""
Supported Protocols:
DHCP
ARP
"""

MAC_BROADCAST = "FFFF"
IP_BROADCAST = "255.255.255.255"
#random.seed(123)

def mergeDicts(x, y):
    """
    It turns out that merging two dicts differs heavily 
    depending on the python version you use, so we home 
    brew a solution to not worry about differences within 
    3.x versions of python

    importantly, y overwrites keys in x if overlap
    """

    for k, v in y.items():
        x[k] = v
    
    return x

def removeHostBits(s): # TODO: Fix for non-24 masks
    s = s.split("/")[0].split(".")
    s[-1] = "0"
    s = ".".join(s)
    return s

def splitAddr(s):
    l = s.split("/")
    netmask = '.'.join([str((0xffffffff << (32 - int(l[1])) >> i) & 0xff) for i in [24, 16, 8, 0]])
    return l[0], netmask

def genericIgnoreMessage(inproto, ID, fr=None):
    s = ""
    if fr: s = "from " + fr
    print("("+inproto+")", ID, "ignoring data", s)

def findInterfaceFromID(ID, interfaces):
    if not ID or not interfaces:
        raise ValueError("ID or interfaces is None")
    for interface in interfaces:
        if interface.id == ID:
            return interface
    else:
        raise ValueError("Could not find interface from IntID:" + ID)


def makePacket(L2="", L3="", L4="", L5="", L6="", L7=""):
    """
    The standard packet format used in this project. Each entry
    represents an OSI layer, which has its own packing function
    elsewhere in this file.
    """
    
    d = {
        "L2":L2,
        "L3":L3,
        "L4":L4,
        "L5":L5,
        "L6":L6,
        "L7":L7 
    }
    
    for k, v in d.items():
        if v != "" and not isinstance(v, dict):
            raise ValueError("Arguments must be of type <dict>")

    return d

# An ethernet frame
def makePacket_L2(ethertype="", fr="", to="", data=""):
    return {
        "EtherType":ethertype, # Defines which protocol is encapsulated in data
        "From":fr,
        "To":to,
        "FromLink":None, # This is automatically filled by Device.send()
        "Data":data, # ARP packet, IP packet, DHCP packet, etc
    }

# an IP packet
def ip_header(sip, dip, data="", proto=None, TTL=10 ):
    if data: assert isinstance(data, dict)
    if proto: assert isinstance(proto, str)
    return {
        "Version":4, # Make a new parameter if you love 6 so much
        "HLEN":0, # unimplemented until we care about fragmentation
        "TOS":0, # unused
        "TotalLength":0, # no checksums here
        "ID":random.randint(0, 2**16), # fragmentation
        "Flags":0, # fragmentation
        "FOffset":0,
        "TTL":TTL,

        # https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
        # For "Protocol" we'll probably just use names to not confuse ourselves
        "Protocol":proto,
        "Checksum":0,
        "sip":sip, # Src, Dst
        "dip":dip,
        "Data":data
    }

# UDP
def makePacket_L4_UDP(sp="", dp="", data="", length="", checksum=""):
    return {
        "SPort":sp,
        "DPort":dp,
        "Length":length,
        "Checksum":checksum,
        "Data":data
    }


#https://www.rfc-editor.org/rfc/rfc6747
#http://www.tcpipguide.com/free/t_ARPMessageFormat.htm
"""

Technically these are the fields this RFC defines,
but I'll be cutting some of them out as they won't be used

ARP RFC 6747
ARP REQUEST PACKET FORMAT                       ARP RESPONSE FORMAT (same thing)
0        7        15       23       31          0        7        15       23       31
+--------+--------+--------+--------+           +--------+--------+--------+--------+        
|       HT        |        PT       |           |       HT        |        PT       |
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|  HAL   |  PAL   |        OP       |           |  HAL   |  PAL   |        OP       |        
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|         S_HA (bytes 0-3)          |           |         S_HA (bytes 0-3)          |        
+--------+--------+--------+--------+           +--------+--------+--------+--------+
| S_HA (bytes 4-5)|S_L32 (bytes 0-1)|           | S_HA (bytes 4-5)|S_L32 (bytes 0-1)|        
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|S_L32 (bytes 2-3)|S_NID (bytes 0-1)|           |S_L32 (bytes 2-3)|S_NID (bytes 0-1)|        
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|         S_NID (bytes 2-5)         |           |         S_NID (bytes 2-5)         |
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|S_NID (bytes 6-7)| T_HA (bytes 0-1)|           |S_NID (bytes 6-7)| T_HA (bytes 0-1)|
+--------+--------+--------+--------+           +--------+--------+--------+--------+        
|         T_HA (bytes 3-5)          |           |         T_HA (bytes 3-5)          |
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|         T_L32 (bytes 0-3)         |           |         T_L32 (bytes 0-3)         |
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|         T_NID (bytes 0-3)         |           |         T_NID (bytes 0-3)         |
+--------+--------+--------+--------+           +--------+--------+--------+--------+
|         T_NID (bytes 4-7)         |           |         T_NID (bytes 4-7)         |
+--------+--------+--------+--------+           +--------+--------+--------+--------+
"""
def arp_header(op, fr, frIP, to, toIP):
    d = {
        "HT":"Ethernet",
        "PT":"IPv4", # We won't be using anything other than IPv4 for the time being
        "HAL":6,
        "PAL":4, # From http://www.tcpipguide.com/free/t_ARPMessageFormat.htm
        "OP":op,
        "SHA":fr,
        "SPA":frIP,
        "THA":to,
        "TPA":toIP
    }

    #for option_name, option_value in options.items():
    #    d[option_name] = option_value

    return d


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
flags               1: Broadcast --- 0: unicast
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
def createDHCPHeader(op=1, htype=1, hardwareaddrlen=6,
                     hops=-1, xid=None,
                     seconds=0, flags=1, ciaddr="0.0.0.0", yiaddr="0.0.0.0",
                     siaddr="0.0.0.0",giaddr="0.0.0.0", chaddr="", options={}):
    
    if not xid:
        xid = random.randint(1000000000, 9999999999)


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
        "file":"",
        "options":options
    }

    #for option_name, option_value in options.items():
    #    d[option_name] = option_value

    return d

"""
ICMP RFC 792
 0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |     Type      |     Code      |          Checksum             |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |           Identifier          |        Sequence Number        |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |     Data ...
   +-+-+-+-+-
Type                8 (Echo Request) or 0 (Echo Reply)
Code                0
Checksum            Checksum
Identifier          Code to aid in matching echos and replies
Seq Number          Same as Identifier? TODO
"""
def createICMPHeader(typ, code=0, identifier=None, snum=None): # Only echo requests / replies, we ignore the rest

    if not identifier:
        identifier = random.randint(0, 999999)
    if not snum:
        snum = random.randint(0, 999999)
    """
    To form an echo reply message, the source and destination
    addresses are simply reversed, the type code changed to 0,
    and the checksum recomputed.
    """
    d = {
        "type":int(typ),
        "code":int(code),
        "identifier":int(identifier),
        "SNum":int(snum),
    }

    return d
