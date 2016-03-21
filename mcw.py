'''Header for using PsychoPy at MCW's MEG

Parallel Port access
--------------------------

The parallel port can be read from (to get button presses) and sent data (to
have data "tags" recorded alongside the MEG signal).

Sending data is easy, just send an 8-bit number (1-255) with :meth:`send_tag`.
To be able to read data, you need to create and instance of the :class:`ParallelDaemon` class,
which will then monitor the parallel port on a seperate process and collect any
key presses it finds. For example::

    p = ParallelDaemon()
    p.start()
    ...
    if p.has_data():
        for (time,data) in p.get_data():
            print 'You pressed %d at time %d!' % (data,time)

    p.stop()
'''

from psychopy import parallel, core, clock
import time
if core.havePyglet:
    import pyglet
from multiprocessing import Queue, Process
from Queue import Empty
import atexit

###### Routines for accessing the parallel port interface:

tag_port = 0x0378
data_port = 0x0379

class ParallelDaemon(object):
    '''Runs a loop on a seperate process to monitor parallel port and record data with timestamps'''
    def __init__(self,poll_time=10,address=data_port):
        self.queue = Queue()
        self.poll_time = poll_time
        self.monitor_process = None
        self._port = None
        self.address = address
        try:
            self._port = parallel.ParallelPort(address=address)
        except:
            # Will fail on OSX since it has no parallel port, and
            # the dummy class won't allow you to initiate at an address
            pass

    def start(self):
        self.stop()
        self.monitor_process = Process(target=self._start_monitor)
        self.monitor_process.start()
        atexit.register(self.stop)

    def stop(self):
        if self.monitor_process:
            self.monitor_process.terminate()

    def _start_monitor(self):
        last_data = 0
        while True:
            time.sleep(self.poll_time/1000.)
            if self._port:
                new_data = self._port.readData()
                if new_data!=last_data and new_data!=0:
                    last_data = new_data
                    self.queue.put((clock.getTime(),new_data))

    def has_data(self):
        '''``Boolean`` of whether new data has been detected'''
        return self.queue.empty()==False

    def get_data(self):
        data = []
        try:
            while True:
                data.append(self.queue.get(False))
        except Empty:
            pass
        return data

try:
    _tag_port = parallel.ParallelPort(tag_port)
except:
    _tag_port = None

def send_tag(number,width=10):
    '''Send ``number`` to the parallel port, to be recorded on the "tag" channel of the MEG system.
    Allows for accurate timing of events by creating time-stamps of events alongside the MEG data.
    Will hold ``number`` for ``width``ms, then reset back to zero'''
    if _tag_port:
        tag_port.setData(number)
        core.wait(float(width)/1000)
        tag_port.setData(0)
