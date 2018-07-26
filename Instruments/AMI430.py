#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2016 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import (
    truncated_discrete_set, strict_discrete_set,
    truncated_range
)
from time import sleep
import numpy as np
import re


class AMI430(Instrument):
    """ Represents the AMI 430 Power supply
    and provides a high-level for interacting with the instrument.

    .. code-block:: python

        magnet = AMI430("GPIB::1")

        
        magnet.coilconst = 1.182                 # kGauss/A
        magnet.voltage_limit = 2.2               # Sets the voltage limit in V

        magnet.target_current = 10               # Sets the target current to 10 A
        magnet.target_field = 1                  # Sets target field to 1 kGauss

        magnet.ramp_rate_current = 0.0357       # Sets the ramp rate in A/s
        magnet.ramp_rate_field = 0.0422         # Sets the ramp rate in kGauss/s
        magnet.ramp                             # Initiates the ramping
        magnet.pause                            # Pauses the ramping
        magnet.status                           # Returns the status of the magnet
    
        magnet.ramp_to_current(5)             # Ramps the current to 5 A

        magnet.shutdown()                     # Ramps the current to zero and disables output

    """

    coilconst = Instrument.control(
        "COIL?", "CONF:COIL %g",
        """ A floating point property that sets the coil contant
        in kGauss/A. """
    )

    voltage_limit = Instrument.control(
        "VOLT:LIM?", "CONF:VOLT:LIM %g",
        """ A floating point property that sets the voltage limit
        for charging/discharging the magnet. """
    )

    target_current = Instrument.control(
        "CURR:TARG?", "CONF:CURR:TARG %g",
        """ A floating point property that sets the target current
        in A for the magnet. """
    )

    target_field = Instrument.control(
        "FIELD:TARG?", "CONF:FIELD:TARG %g",
        """ A floating point property that sets the target field
        in kGauss for the magnet. """
    )

    ramp_rate_current = Instrument.control(
        "RAMP:RATE:CURR:1?", "CONF:RAMP:RATE:CURR 1,%g",
        """ A floating point property that sets the current ramping 
        rate in A/s. """
    )

    ramp_rate_field = Instrument.control(
        "RAMP:RATE:FIELD:1?", "CONF:RAMP:RATE:FIELD 1,%g",
        """ A floating point property that sets the field ramping 
        rate in kGauss/s. """
    )

    magnet_current = Instrument.measurement("CURR:MAG?",
        """ Reads the current in Amps of the magnet.
        """
    )

    supply_current = Instrument.measurement("CURR:SUPP?",
        """ Reads the current in Amps of the power supply.
        """
    )

    field = Instrument.measurement("FIELD:MAG?",
        """ Reads the field in kGauss of the magnet.
        """
    )

    state = Instrument.measurement("STATE?",
        """ Reads the field in kGauss of the magnet.
        """
    )

    def zero(self):
        """ Initiates the ramping of the magnetic field to zero
        current/field with ramping rate previously set. """
        self.write("ZERO")

    def pause(self):
        """ Pauses the ramping of the magnetic field. """
        self.write("PAUSE")

    def ramp(self):
        """ Initiates the ramping of the magnetic field to set
        current/field with ramping rate previously set.
        """
        self.write("RAMP")

    def has_persistant_switch_enabled(self):
        """ Returns a boolean if the persistant switch is enabled. """
        return bool(self.ask("PSwitch?"))

    def enable_persistant_switch(self):
        """ Enables the persistant switch. """
        self.write("PSwitch 1")

    def disable_persistant_switch(self):
        """ Disables the persistant switch. """
        self.write("PSwitch 0")

    def status(self):
        if(state==1):
            magnet_status = "RAMPING"
        if(state==2):
            magnet_status = "HOLDING"
        if(state==3):
            magnet_status = "PAUSED"
        if(state==4):
            magnet_status = "Ramping in MANUAL UP"
        if(state==5):
            magnet_status = "Ramping in MANUAL DOWN"
        if(state==6):
            magnet_status = "ZEROING CURRENT in progress"
        if(state==7):
            magnet_status = "QUENCH!!!"
        if(state==8):
            magnet_status = "AT ZERO CURRENT"
        if(state==9):
            magnet_status = "Heating Persistent Switch"
        if(state==10):
            magnet_status = "Cooling Persistent Switch"

        return magnet_status

    def ramp_to_current(self, current, rate):
        """ Heats up the persistent switch and
        ramps the current with set ramp rate.
        """
        self.enable_persistant_switch()

        self.target_current = current
        self.ramp_rate_current = rate

        for i in range(600):
            if(self.state == 2):
                return
            sleep(1)

        self.ramp()

    def shutdown(self):
        """ Turns on the persistent switch,
        ramps down the current to zero, and turns off the persistent switch.
        """
        self.enable_persistant_switch()

        for i in range(600):
            if(self.state == 2):
                return
            sleep(1)
        self.ramp_rate_current = 0.0357

        self.zero()