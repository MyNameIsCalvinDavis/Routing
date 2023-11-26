# Timeout Logic
In a threaded environment, was:

```python
now = time.time()
if timeout: # function param
    while (time.time() - now) < timeout:
        if oninterface.DHCPClient.DHCP_FLAG == 2:
            # IP received / renewed!
            return True
```
In an async environment, in a Device:

```python
async def _check_for_val():
    while self.handler["DHCP_Client"].DHCP_FLAG != 2:
        await async.sleep(0)
    return True
await async.wait_for(_check_for_val() , timeout)
```

# Class Anatomy
Devices that inherit do so because they need to overload the Handle method, which should otherwise be standard for L3+ Devices. Everything else should be a Handler.


```
Device
    Params
        interfaces # where handlers live
        mac
        route_table
            # Hosts will only have static routing tables 
        ip_forward = 0
        read_buffer = []
    Funcs
        send # Also handles timeout
        handle
            L2
                MAC DST: To me?
                Y: Goto L3
                N: Drop
            L3
                ETHTYPE
                ARP?
                    Target IP: To me?
                    Y: Arp_Handler()
                    N: Drop
                IPv4?
                    Dst IP: To me? 
                    N: Route based on ip_forward
                    Y: Continue

                    PROTOCOL
                    ICMP?
                        ICMP_Handler()
                    TCP?
                        ...
                    UDP?
                        DHCP?
                            DHCP_Handler()
                    OSPF / RIP / etc?
                        # Purely for routing table generation
                        if ip_forwarding: handle_route_info
                        N: Drop
        route
            # Devices should be able to route even if its bad practice for anything other than a router
        handle_route_info
            pass
        listen
            # Async while loop
```
Router is just a device with ip_forwarding enabled
```
Router (Device)
    __init__(static_routes)
        ip_forwarding = 1
        routing_table = static_routes
    handle_route_info
        ...
```
Switch handler overwritten to just look at L2
```
Switch (Device)
    Params
        switch_table
    Funcs
        + handle
            L2
                add incoming mac to switch_table
                consult switch_table for forwarding
                forward / broadcast
```
Interfaces contain handlers and ip information. Interfaces are meant to process packet data as much as they can, though some things (like a recv buffer) have been put in the parent to avoid code duplication and to make Interfaces generalizable. This is a limitation of OOP, where an actual device would have one namespace in the firmware. I'm trying to avoid passing data from child to child (Device interfaces) and so am having the parent class do any interface multiplexing.

An incoming packet will hit a Device, be sent down to the appropriate Interface to be handle()'d by that Interface's appropriate handler, which will in turn process the data and generate a response (or update / return data) which gets returned up the stack back to the Device
```
Interface
    Params
        _ip
        handlers = {
            "DHCP": <DHCP_Client/Server instance>
            "ARP": <ARP Instance>
            ...
        }
        arp_cache = {}
        link = <Link Instance>
    Funcs
        @property
        ip
            return self._ip
            # DHCP handler automatically updates _ip

        @ip.setter
        ip
            # Caution: DHCP not tracking ip change this way
```
It may make sense to have connected interfaces just have an object reference to the neighboring interface they're connected to, but having a class here for it opens up the option to more tightly control the connection in the future if I want to add degredation / logging / etc
```
Link
    __init__ (x, y)
        connected = [x, y] # Two Items
    get_other(x)
        return c[1] if c[0] == x else c[0]
```

# Handlers
Handlers, should be plugg-able into an Interface. Their job is to manage state and process incoming data, and variably generate a response to be dealt with by the parent Device

```
DHCP_Server
    Params
        leased_ips
        options = {} # See RFC for server options
    Funcs
        handle # and return a response to the caller
               # or update params
```
https://docs.oracle.com/cd/E23824_01/html/821-1453/dhcp-overview-35a.html
DHCP Client interfaces are independent, but have some globals, such as "Host name, NIS domain name, and time zone". The DHCP client is also responsible for modifying the Device routing table, but we're gonna ignore that
```
DHCP_Client 
    Params
        DHCP_STAGE # D / O / R / A tracker
        ip
        lease_time
    Funcs
        handle
            if D: return self.create(O)
            if O: return self.create(R)
            ...
        create
            D / O / R / A
```
```
ARP
    Params
        arp_cache
    Funcs
        handle
        create
```