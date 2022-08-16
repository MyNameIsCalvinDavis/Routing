# Routing

The purpose of this project is to provide a network simulation framework up to Layer 4. Several classes are provided, mimicking their hardware equivalents:
 - Device (Abstract Base Class)
 - Switch
 - Host
   - DHCP Client
 - Router
   - DHCP Server
 - Link

In our simulation, we are able to connect a topology together in an intuitive way. Here we form a basic 4 device LAN:

>. <img src="Images/ExDiagram.png" width="40%">

We can initialize it as such:

```python
A, B, C = Host(), Host(), Host()
S1 = Switch([A, B, C])
```

Devices can then speak to each other as expected, via a dict representation of packed frames . In our example, host A sends an ARP request looking for host B. We must pack the frame ourselves, though some of the data can be inferred, and of course you can wrap this functionality:
```python
>>> # The provided Device.sendARP() method abstracts this process
>>> p = makePacket_L2(ethertype="ARP", fr=A.id, to=MAC_BROADCAST, data=data={"ID":B.id})
>>> p
{
  "EtherType":"ARP",
  "From":<A MAC>,
  "To":<MAC BROADCAST ADDR>,
  "FromLink":<LINK ID> # Used identify which interface a frame comes from, in lieu of an actual hardware port
  "Data": {"ID": <B MAC>}
}
```

When we send() data, we don't send TO a host, rather we output on an interface. We then rely on the frame and other hardware to get it where it needs to go. Here, we send p on A's only interface.

```python
>>> A.send(p) # onlink param default value is self.interfaces[0]. Fine for a host with only one interface
```

We can also specify a specific interface, good for devices with several interfaces, like a Router or Switch:

```python
>>> A.send(p, A.interfaces[0])
```

We can see the updated ARP caches of several of the devices, in the form of:
```
<Device ID>:<Interface Link ID>
```
```python
>>> A.mti # MAC to Interface
>>> {'-H-54669064': '[L]71977819'}
>>> S1.mti
>>> {'-H-35937021': '[L]71977819', '-H-54669064': '[L]75483140'}
```
