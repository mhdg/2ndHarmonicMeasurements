import logging
import sys
# import random
# import tempfile
# import pyqtgraph as pg
from time import sleep
import numpy as np

# import keithley2400
# from pymeasure.instruments import Instrument
# from pymeasure.log import console_log
from pymeasure.experiment import Results
from pymeasure.display.Qt import QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, FloatParameter, Parameter
# from pymeasure.experiment import Parameter, IntegerParameter
from pymeasure.experiment import unique_filename
# from pymeasure.instruments.keithley import Keithley2400
from pymeasure.instruments.signalrecovery import DSP7265
from Instruments.deltaelektronika import SM7045D

log = logging.getLogger('')
log.addHandler(logging.NullHandler())


class Measure2ndHarmonic(Procedure):

    current = FloatParameter('Magnet Current',
                             units='A', default=1)
    delay = FloatParameter('Delay Time',
                           units='s', default=0.35)
    max_angle = FloatParameter('Maximum Angle',
                               units='deg', default=180)
    ramp_rate = FloatParameter('Magnet Ramping Rate',
                               units='A/s', default=0.1)
    fieldcal = FloatParameter('Magnetic Field Calibration',
                              units='T/A', default=13.69)
    Lockin1_use = Parameter('Lock-in 1')
    Lockin2_use = Parameter('Lock-in 2')

    # degrees per edge
    # it moves at degpulse at both the rise and fall of a pulse
    degpulse = FloatParameter('Degrees per step',
                              units='deg/step', default=(90 / 50 / 2))

    # Define motorsteps where +1 is CW step and -1 is CCW step
    motorstep = 0

    DATA_COLUMNS = [
        'Angle (deg)',
        'Magnet Current (A)',
        'Magnetic Field (T)',
        'Lock-In 1 X (V)',
        'Lock-In 1 Y (V)',
        'Lock-In 2 X (V)',
        'Lock-In 2 Y (V)'
    ]

    """
    ###########################################################################
    ###########################################################################
    #############################  STARTUP PROCEDURE  #########################
    ###########################################################################
    ###########################################################################
    """

    def startup(self):
        log.info("Setting up instruments")

        self.lockin = DSP7265("GPIB::12")
        self.lockin.dac3 = 0.
        self.lockin.dac4 = 0.

        self.lockin2 = DSP7265("GPIB::11")

        self.source = SM7045D("GPIB::8")
        log.info("Ramping magnet power supply to zero and enabling it.")
        self.source.ramp_to_zero(self.ramp_rate)
        self.source.enable()

        sleep(5)

    """
    ###########################################################################
    ###########################################################################
    #############################  EXECUTE PROCEDURE  #########################
    ###########################################################################
    ###########################################################################
    """

    def step_motor(self, delay=None):
        """
        Step the rotation motor
        """
        if self.lockin.dac3 < 2.5:
            self.lockin.dac3 = 5.
        else:
            self.lockin.dac3 = 0.

        print("Step: dac3: {:.1f}, dac4: {:.1f}, motorstep: {:d}".format(
            self.lockin.dac3, self.lockin.dac4, self.motorstep))

        # Add or subtract one to the number of motor steps
        if self.lockin.dac4 < 2.5:
            self.motorstep += 1
        else:
            self.motorstep -= 1

        # Wait for the motor to stop moving
        if delay is not None:
            sleep(delay)
        else:
            sleep(self.delay)

    def home_motor(self):
        # SETTING DIRECTION OF ROTATION
        # 0 = CLOCKWISE; 5 = COUNTERCLOCKWISE
        if self.motorstep > 0:
            self.lockin.dac4 = 5.
        else:
            self.lockin.dac4 = 0.

        # Rotate the sample back to 0
        while not self.motorstep == 0.:
            self.step_motor(delay=0.350)

    def calc_angle(self):
        return self.degpulse * self.motorstep

    def calc_magfield(self):
        return self.current * self.fieldcal

    def measure(self):
        log.debug("Measuring angle: %g deg." % self.calc_angle())
        data = {
            'Angle (deg)': self.calc_angle(),
            'Magnet Current (A)': self.current,
            'Magnetic Field (T)': self.calc_magfield(),
            'Lock-In 1 X (V)': self.lockin.x,
            'Lock-In 1 Y (V)': self.lockin.y,
            'Lock-In 2 X (V)': self.lockin2.x,
            'Lock-In 2 Y (V)': self.lockin2.y,
        }
        self.emit('results', data)

    def measurement_procedure(self, Npulses, progress0=0, progress1=100):
        for i in range(Npulses):
            self.measure()
            self.emit('progress', progress0 +
                      (progress1 - progress0) * i / Npulses)
            if self.should_stop():
                log.warning("Catch stop command in procedure")
                return

            self.step_motor()

        self.measure()
        self.emit('progress', progress1)

    def execute(self):
        """
        Prepare this specific measurement
        """

        # Setting Magnetic Field
        self.source.ramp_to_current(self.current, self.ramp_rate)

        # Number of pulses (per degree times degree)
        Npulses = round((1 / self.degpulse) * self.max_angle)

        # Number of motor steps is initially zero.
        self.motorstep = 0

        """
        #############################      CLOCKWISE      ####################
        """
        # SETTING DIRECTION OF ROTATION
        # 0 = CLOCKWISE; 5 = COUNTERCLOCKWISE
        self.lockin.dac4 = 0.
        sleep(self.delay)
        log.info("Starting to rotate the sample clockwise.")
        self.measurement_procedure(Npulses, 0, 50)

        """
        #############################  COUNTERCLOCKWISE   #####################
        """
        # SETTING DIRECTION OF ROTATION
        # 0 = CLOCKWISE; 5 = COUNTERCLOCKWISE
        self.lockin.dac4 = 5.
        sleep(self.delay)
        log.info("Starting to rotate the sample clockwise.")
        self.measurement_procedure(Npulses, 50, 100)

        """
        #############################  COUNTERCLOCKWISE   #####################
        """

    """
    ###########################################################################
    ###########################################################################
    #############################  SHUTDOWN PROCEDURE  ########################
    ###########################################################################
    ###########################################################################
    """

    def shutdown(self):
        log.info("Shutting down.")

        # Ramp magnet current back to zero.
        self.source.ramp_to_zero(self.ramp_rate)
        sleep(1)

        # Disable magnet power supply.
        self.source.disable()

        # Rotate the motor back to 0
        self.home_motor()

        # Setting DACs to zero.
        self.lockin.dac3 = 0.
        self.lockin.dac4 = 0.

        log.info("Finished")


###############################################################################
###############################################################################
###############################################################################

class MainWindow(ManagedWindow):

    def __init__(self):
        super(MainWindow, self).__init__(
            procedure_class=Measure2ndHarmonic,
            displays=[
                'current', 'max_angle'
            ],
            x_axis='Angle (deg)',
            y_axis='Lock-In 1 X (V)'
        )
        self.setWindowTitle('2ndHarmonic VS Angle')

    def _setup_ui(self):
        super(MainWindow, self)._setup_ui()
        self.inputs.hide()
        self.inputs = fromUi('gui_2ndHarmonic_inputs.ui')

    def queue(self):

        maxcurrent = self.inputs.max_curr.value()
        mincurrent = self.inputs.min_curr.value()
        currentstep = self.inputs.curr_step.value()

        currents = np.arange(mincurrent, maxcurrent + currentstep, currentstep)

        for k, curr in enumerate(currents):
            # Change this to the desired directory
            directory = self.inputs.folder.text()

            filename = unique_filename(
                directory, prefix=self.inputs.samplename.text(),
                ext='txt', datetimeformat='')

            procedure = Measure2ndHarmonic()
            procedure.current = curr
            procedure.max_angle = self.inputs.max_angle.value()
            procedure.delay = self.inputs.delay.value()
            procedure.Lockin1_use = self.inputs.Lockin1_use.currentText()
            procedure.Lockin2_use = self.inputs.Lockin2_use.currentText()

            results = Results(procedure, filename)
            experiment = self.new_experiment(results)

            self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
