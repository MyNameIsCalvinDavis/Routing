
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
    S1 = Switch(A, B, C)
    
    A.sendARP(C.id)

def Ex2():
    """
    A           C
    |           |
    S1----------S2
    |           |
    B           D
    """
    A, B, C, D = Host(), Host(), Host(), Host()

    S1 = Switch([A, B])
    S2 = Switch([C, D, S1])

    A.sendARP(D.id)

if __name__ == "__main__":
    Ex2()




