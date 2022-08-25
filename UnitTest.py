import unittest
import sys
import io
from contextlib import redirect_stdout
from L2 import *


"""

Many of these tests look for correct stdout output instead of
actual data, since most packets/frames are sent along in a multithreaded
way and become impossible to capture reliably. To do so, I'd have to either
put locks everywhere, or add explicit functionality in each and every 
written function in the project to return test specific information.

Instead, we just rely upon the already present debug info. This makes
adding new tests less of a pain in the ass, and lets us not worry about
test writing when writing new functions.

"""

def config(*args):
    for device in args:
        device.listen_delay = 0

def kill(*args):
    for device in args:
        device.thread_exit = True

    for device in args:
        device.lthread.join()

def err(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class SwitchTestCase(unittest.TestCase):
    
    # Connect a switch to various stuff in various ways
    def test_SwitchInit(self):
        # Does init work?

        S1 = Switch()
        S2 = Switch([S1])
        
        for link in S1.links:
            if not "[L]" in link.id:
                self.fail("Switch links contain a non-link")

        self.assertEqual( len(S1.links), 1)
        self.assertEqual( len(S2.links), 1)
        kill(S1, S2)
    
    def test_Connection_01(self):
        # 1 Connect a switch to something with no links
        # 2 Connect a switch to something with links
        A = Host()
        S1 = Switch([A]) # 1
        S2 = Switch([A]) # 2
        kill(S1, S2, A)

    def test_Connection_02(self):
        # 1 Connect something to a switch with no links
        # 2 Connect something to a switch with links
        # 3 Connect something to a thing(s) connected to a switch
        S1 = Switch()
        A = Host([S1]) # 1
        B = Host([S1]) # 2
        C = Host([B, A, S1]) # 3
        kill(S1, A, B, C)

    def test_Connection_03(self):
        # 1 Connect N switches
        S1 = Switch()
        S2 = Switch([S1])
        S3 = Switch()
        S4 = Switch([S1, S2, S3])
        kill(S1, S2, S3, S4)
    
class HostTestCase(unittest.TestCase):
    def setUp(self):
        """
        H --- S --- R
        """

        self.A = Host()
        self.R1 = Router("10.10.10.1")
        self.S1 = Switch([self.A, self.R1])

        config(self.A, self.R1, self.S1)
        self.output = io.StringIO()

    def tearDown(self):
        kill(self.A, self.R1, self.S1)
        
    def test_sendRecvARP(self):

        # Send an ARP request to R1 from A, check response
        expected = "(ARP) " + self.A.id + " got ARP Response, updating ARP cache"

        with redirect_stdout(self.output):
            self.A.sendARP(self.R1.id)

            for i in range(50): # Timeout of 5s
                if expected in self.output.getvalue():
                    self.assertTrue(True)
                    break
                time.sleep(0.1)
            else:
                err("\n\n++++++++++\nOutput:")
                err(self.output.getvalue())
                err("++++++++++++++++")
                self.fail("SendRectARP failed")

    def test_recvSendARP(self):
        # Send an ARP request to A from R1, check recv and send responses
        expected = "(ARP) " + self.A.id + " got ARP-Rq, sending ARP-Rp"
        expected2 = "(ARP) " + self.R1.id + " got ARP Response, updating ARP cache"
        
        with redirect_stdout(self.output):
            self.R1.sendARP(self.A.id)

            for i in range(50): # Timeout of 5s
                if expected in self.output.getvalue() and expected2 in self.output.getvalue():
                    self.assertTrue(True)
                    break
                time.sleep(0.1)
            else:
                self.fail("RecvSendARP failed")

if __name__ == "__main__":
    """
    Every test grabs the output of debug info and asserts things about that output
    """

    unittest.main(module=__name__, exit=False) 
    print("DONE")



























