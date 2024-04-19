import nidaqmx as nidaq
import numpy as np
from nidaqmx.constants import LineGrouping, AcquisitionType, SampleTimingType
from nidaqmx.stream_writers import DigitalSingleChannelWriter


class MagnetController:
    def __init__(self, reset=False):
        """
        :param bool reset: Choose whether to reset the DAQ card or not. Because LampController and MagnetController are
        both using the same DAQ device, this should only be true for the first of these two objects to be created.
        """
        print("MagnetController: Initialising MagnetController")

        if reset:
            print("MagnetController: Resetting DAQ card")
            self.dev = nidaq.system.device.Device('Dev1')
            self.dev.reset_device()

        self.analogue_input_task = nidaq.Task()
        self.analogue_input_task.ai_channels.add_ai_voltage_chan('Dev1/ai0')

        self.analogue_output_task = nidaq.Task()
        self.analogue_output_task.ao_channels.add_ao_voltage_chan('Dev1/ao0')
        self.voltages = np.linspace(-10, 10, 100)
        self.field_from_volts = np.linspace(-10, 10, 100)
        self.currents = np.linspace(-10, 10, 100)
        self.field_from_currents = np.linspace(-10, 10, 100)

    def set_calibration(self, voltages, field_from_volts, currents, field_from_currents):
        self.voltages = voltages
        self.field_from_volts = field_from_volts
        self.currents = currents
        self.field_from_currents = field_from_currents
        print("MagnetController: Calibration Updated")

    def interpolate_voltage(self, target_field):
        right = np.where(self.field_from_volts > target_field)[0][0]
        left = np.where(self.field_from_volts < target_field)[0][-1]
        low_volt = self.voltages[left]
        high_volt = self.voltages[right]
        low_field = self.field_from_volts[left]
        high_field = self.field_from_volts[right]
        return low_volt + ((target_field - low_field) / (high_field - low_field)) * (high_volt - low_volt)
