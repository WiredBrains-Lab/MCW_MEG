""" meg_comm.py

Original author:   William Gross

    v1:   4/1/2022
        Written to solve the issues with sending tags and recieving inputs from
        the MEG scanner at MCW. This library is the companion for a USB box made
        with an Arduino to interface to the MEG system.
    v1.1: 4/26/2022
        Updated to new PCB box
    v1.2: 5/11/2022
        Added funcs
"""


""" Usage:
        See `meg_demo.py` or the help docstrings below.
"""
import serial
import struct
from time import sleep
import serial.tools.list_ports

# Constants that shouldn't be changed:
_megbox_baudrate = 115200
_megbox_numbuttons = 4
_MP_STARTCODE    = b'x'
_MP_GETTIME      = b't'
_MP_ADDTIME      = b'a'
_MP_OUTON        = b'o'
_MP_OUTOFF       = b'l'
_MP_OUTPULSE     = b'p'
_MP_READRESPS    = b'r'
_MP_RESP_PSTART  = b'['
_MP_RESP_PEND    = b']'
_MP_RESP_START   = b'<'
_MP_RESP_END     = b'>'
_MP_NUMRESP      = b'X'

def autodetect_ports():
    a = [x for x in serial.tools.list_ports.grep('Arduino')]
    if len(a)==0:
        return None
    return a[0].device

class MEGComm(object):
    def __init__(self,
        port=None
    ):
        if port==None:
            port = autodetect_ports()
            if port==None:
                raise Exception('Cannot autodetect port. Please supply manually.')
        self.port = port
        self.baudrate = _megbox_baudrate
        self.ser = None

    def start(self):
        self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=0.1)
        sleep(0.1) # Takes a second to start up

    def stop(self):
        if self.ser != None:
            self.ser.close()

    def __del__(self):
        self.stop()

    def _send_code(self,command,arg=None):
        msg = _MP_STARTCODE + command
        if arg != None:
            msg += struct.pack("B",arg)
        self.ser.write(msg)

    def _read(self):
        return self.ser.read_until()

    def _convert_long(self,b):
        if len(b) != 4:
            return None
        return sum([b[i]<<(i*8) for i in range(4)])

    """ getTime()

    Returns the current time on the internal clock (so that button RTs make sense)
    """
    def getTime(self):
        self._send_code(_MP_GETTIME)
        resp = self._read()
        if len(resp)!=4:
            return None
        else:
            return self._convert_long(resp)

    """ sendTag(i)

    Send a square wave pulse to output pin #i (first pin = 1)
    """
    def sendTag(self,i):
        self._send_code(_MP_OUTPULSE,i-1)

    """ sendByte(i)

    Send a square wave pulse to output pins corresponding to the binary representation of `i`
    """
    def sendByte(self,i):
        if i<0 or i>255:
            raise Exception('Called sendByte with a non-byte number!')
        bin = '{0:08b}'.format(i)
        for j in range(8):
            self._send_code(_MP_OUTPULSE,int(bin[j]))

    """ pinOn(i)

    Turn on pin #i (first pin = 1)
    """
    def pinOn(self,i):
        self._send_code(_MP_OUTON,i-1)

    """ pinOff(i)

    Turn on pin #i (first pin = 1)
    """
    def pinOff(self,i):
        self._send_code(_MP_OUTOFF,i-1)

    """ getResp(times=False)

    Polls for recent responses. Returns a list of button responses since the last call.
    Will return a list of `Tuple`s, each with the button number and
    the time of the button press (using the internal clock).
    """
    def getResp(self):
        def safeget(resp,i,inc=1):
            if i==None:
                return (None,None)
            if i>=len(resp):
                return (None,None)
            if inc==1:
                r = resp[i]
            else:
                r = resp[i:i+inc]
            i += inc
            if i>=len(resp):
                return (r,None)
            return (r,i)
        def getSecond(a):
            return a[1]
        self._send_code(_MP_READRESPS)
        resp = self._read()
        i = 0
        presses = []
        (r,i) = safeget(resp,i)
        if r==None or r != _MP_NUMRESP[0]:
            print('Error receiving responses: char %d bad NUMRESP' % i)
            return presses
        (r,i) = safeget(resp,i)
        if r==None or r not in range(_megbox_numbuttons + 1):
            print('Error receiving responses: char %d bad number of button responses' % i)
            return presses
        numbutton = r
        for k in range(numbutton):
            (r,i) = safeget(resp,i)
            if r==None or r != _MP_RESP_PSTART[0]:
                print('Error receiving responses: char %d bad PSTART' % i)
                return presses
            (r,i) = safeget(resp,i)
            if r==None or r not in range(_megbox_numbuttons):
                print('Error receiving responses: char %d bad button number' % i)
                return presses
            curbutton = r
            (r,i) = safeget(resp,i)
            if r==None:
                print('Error receiving responses: char %d bad number of responses' % i)
                return presses
            num_presses = r
            for j in range(num_presses):
                (r,i) = safeget(resp,i)
                if r==None or r != _MP_RESP_START[0]:
                    print('Error receiving responses: char %d bad START' % i)
                    return presses
                (r,i) = safeget(resp,i,4)
                if r==None:
                    print('Error receiving responses: char %d bad button time' % i)
                    return presses
                rt = self._convert_long(r)
                (r,i) = safeget(resp,i)
                if r==None or r != _MP_RESP_END[0]:
                    print('Error receiving responses: char %d bad END' % i)
                    return presses
                presses.append((curbutton+1,rt))
                presses.sort(key=getSecond)
            (r,i) = safeget(resp,i)
            if r==None or r != _MP_RESP_PEND[0]:
                print('Error receiving responses: char %d bad PEND' % i)
                return presses
        return presses
