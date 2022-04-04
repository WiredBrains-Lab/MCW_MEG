# MCW_MEG
Example scripts and libraries to make developing tasks for the MEG system at the Medical College of Wisconsin easier

Originally, this housed the `mcw.py` script that allowed interfacing through the parallel port. This
script no longer works on 64-bit systems, and so I started developing a USB interface box instead.

## Files:

* `meg_comm.py`: the Python library to use the USB interface box
* `meg_demo.py`: and example Python script to show you how the interface works
* `MEG_Box_Arduino`: the Arduino source code loaded onto the interface box. You don't need to use this (unless you're making another box). Just placed here for reference
