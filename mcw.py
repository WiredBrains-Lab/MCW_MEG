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

from psychopy import core, clock,visual,event
import time
if core.havePyglet:
    import pyglet
from multiprocessing import Queue, Process
from Queue import Empty
import atexit

###### Projector setup:
# Projector: Panasonic PT D87700UK
# PDF Manual: http://www.projectorcentral.com/pdf/projector_spec_3149.pdf

projector_refresh_rate = 120

def projector_window():
    '''Creates and returns the Window object configured for the MEG projector'''
    win = visual.Window((800,600),color="black",fullscr=True,allowGUI=False,units="pix",useFBO=False)
    print 'Assuming refresh rate is set to %f' % projector_refresh_rate
    measure_framerate = win.getActualFrameRate()
    print 'Measured refresh rate = %f' % measure_framerate
    if abs(measure_framerate-projector_refresh_rate)/projector_refresh_rate > 0.01:
        print 'WARNING!! Measured refresh rate was %.2f, expecting %.2f.\nTiming may not be accurate if relying on frame rate!' % (measure_framerate,projector_refresh_rate)
    
    return win


###### Routines for accessing the parallel port interface:

try:
    from ctypes import windll
    pport = windll.inpout32
except:
    pport = None


tag_port = 0x0378
data_port = 0x0379
zero = 135

class ParallelDaemon(object):
    '''Runs a loop on a seperate process to monitor parallel port and record data with timestamps'''
    def __init__(self,poll_time=0.1,address=data_port):
        self.queue = Queue()
        self.poll_time = poll_time
        self.monitor_process = None
        self.address = address

    def start(self):
        self.stop()
        self.monitor_process = Process(target=self._start_monitor)
        self.monitor_process.start()
        atexit.register(self.stop)

    def stop(self):
        if self.monitor_process:
            self.monitor_process.terminate()

    def _start_monitor(self):
        import sys
        print 'starting up'
        last_data = zero
        while True:
            time.sleep(self.poll_time/1000.)
            if pport:
                new_data = pport.Inp32(self.address)
                if new_data!=last_data and new_data!=zero:
                    self.queue.put((clock.getTime(),new_data))
                last_data = new_data

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

def parallel_out(number):
    '''Sets the parallel port to the given number'''
    if pport:
        pport.Out32(tag_port,number)

def send_tag(number,width=10):
    '''Send ``number`` to the parallel port, to be recorded on the "tag" channel of the MEG system.
    Allows for accurate timing of events by creating time-stamps of events alongside the MEG data.
    Will hold ``number`` for ``width``ms, then reset back to zero'''
    parallel_out(number)
    core.wait(float(width)/1000)
    parallel_out(0)
