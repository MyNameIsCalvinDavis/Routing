
from L2 import *

def Ex1():
    """
    A
    |
    S1--C
    |
    B
    """
    A, B, C = Host(), Host(), Host()
    S1 = Switch()
    
    L1 = Link([A, S1])
    L2 = Link([B, S1])
    L3 = Link([C, S1])
    
    initLinks([L1, L2, L3])

    ###

    p = 

def Ex2():
    """
    A           C
    |           |
    S1----------S2
    |           |
    B           D
    """
    A, B, C, D = Host(), Host(), Host(), Host()
    S1, S2 = Switch(), Switch()

    L1 = Link([A, S1])
    L2 = Link([B, S1])
    L3 = Link([C, S2])
    L4 = Link([D, S2])
    L5 = Link([S1, S2])

    initLinks([L1, L2, L3, L4, L5])
