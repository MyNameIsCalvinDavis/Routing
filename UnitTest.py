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

def err(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class HostTestCase(unittest.TestCase):
    def setUp(self):
        """
        H --- S --- R
        """
        self.A = Host()
        self.R1 = Router()
        self.S1 = Switch([self.A, self.R1])
        self.A.send_delay = 0
        self.R1.send_delay = 0
        self.S1.send_delay = 0
        self.output = io.StringIO()

    def tearDown(self):
        self.A.thread_exit = True
        self.R1.thread_exit = True
        self.S1.thread_exit = True
        
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



























