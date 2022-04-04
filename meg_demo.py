""" meg_demo.py

Original author:   William Gross

    v1:   4/1/2022
        A demo program to show you how to use the Python library for the MEG
        interface box.
"""

print('\nMEG USB Demo!\n\n')

print("""First, let me help you if you're having trouble finding the USB device. Once
you know what this is... you can delete all of this and just use the known
port (e.g., "COM3"). Make sure the MEG box is plugged into the USB for this
to work.\n """)
import serial.tools.list_ports
import sys
from time import sleep

a = [x for x in serial.tools.list_ports.grep('Arduino')]
print('I found %d USB device%s plugged into this computer that are named "Arduino":' % (len(a),"" if len(a)==1 else "s"))
for aa in a:
    print('\t' + str(aa))
if len(a)==0:
    print('Please plug the MEG USB box into this computer to continue...')
    sys.exit()
print('I\'m going to use %s\n\n' % a[0].device)

meg_port = a[0].device
sleep(1)

print("Now on to the show!\n")

from meg_comm import MEGComm

meg = MEGComm(port=meg_port)

meg.start()

print("Outputting 100ms square wave tags to each output now...")
for i in range(5):
    print(i+1)
    meg.sendTag(i+1)
    sleep(0.5)

sleep(0.5)

print("""
Now I will display any button presses. Each button press is captured as (button number, ms received)

The timing is acquired on the microcontroller using a hardware interrupt, so it's pretty accurate. It's in terms
of the internal clock on the box (which starts when you run `start()`), so if you want to align it to some other
experimental clock, you'll need to figure out the offset.

The current clock time on the MEG USB box is %d ms.
""" % meg.getTime())
while True:
    resps = meg.getResp()
    if len(resps)>0:
        print(resps)
    sleep(0.1)
