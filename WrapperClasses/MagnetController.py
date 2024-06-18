import nidaqmx as nidaq
import numpy as np
import logging
from nidaqmx.constants import AcquisitionType
import sys

from math import log10, floor


class MagnetController:
    def __init__(self, reset=False):
        """
        :param bool reset: Choose whether to reset the DAQ card or not. Because DAQ based controllers are
        all using the same DAQ device, this should only be true for the first of these two objects to be created.
        """
        self.sample_rate = 1000
        self.frequency = 0.01
        self.target_voltage = 0.0
        self.target_offset_voltage = 0.0
        logging.info("Initialising MagnetController")
        try:
            self.dev = nidaq.system.device.Device('Dev1')
        except:
            logging.error("Failed to connect to DAQ card. Is it on?")
            sys.exit(-1)
        if reset:
            logging.info("Resetting DAQ card")
            self.dev.reset_device()

        self.analogue_input_task = nidaq.Task()
        in_chan = self.analogue_input_task.ai_channels.add_ai_voltage_chan('Dev1/ai0')
        in_chan.ai_rng_low = -10
        in_chan.ai_rng_high = 10
        self.analogue_input_task.timing.cfg_samp_clk_timing(
            1000,
            sample_mode=AcquisitionType.CONTINUOUS,
            samps_per_chan=1000,
        )
        self.analogue_input_stream = self.analogue_input_task.in_stream

        self.analogue_input_task.start()

        self.analogue_output_task = nidaq.Task()
        self.analogue_output_task.ao_channels.add_ao_voltage_chan('Dev1/ao0')

        self.voltages = np.linspace(-10, 10, 100)
        self.field_from_volts = np.linspace(-10, 10, 100)
        self.currents = np.linspace(-10, 10, 100)
        self.field_from_currents = np.linspace(-10, 10, 100)
        self.mode = None

    def set_calibration(self, voltages, field_from_volts, currents, field_from_currents):
        """
        Update the calibration data, usually from file.
        :param np.ndarray[float] voltages: Applied voltage values
        :param np.ndarray[float] field_from_volts: Measured field values
        :param np.ndarray[float] currents: Applied current values
        :param np.ndarray[float] field_from_currents: measured field values
        :return:
        """
        self.voltages = voltages
        self.field_from_volts = field_from_volts
        self.currents = currents
        self.field_from_currents = field_from_currents

    def interpolate_voltage(self, target_field):
        """
        :param float target_field: Desired field in mT
        :return float: the corresponding Voltage to supply from calibration file
        """
        right_idx = np.clip(self.field_from_volts.searchsorted(target_field), 1, len(self.field_from_volts) - 1)
        return np.interp(
            target_field,
            self.field_from_volts[right_idx - 1:right_idx + 1],
            self.voltages[right_idx - 1:right_idx + 1]
        )

    def interpolate_field(self, measured_voltage):
        """
        :param float measured_voltage: Current in volts given by the PSU.
        :return float: the corresponding value in mT from the calibration.
        """
        right_idx = np.clip(self.voltages.searchsorted(measured_voltage), 1, len(self.voltages) - 1)
        return np.interp(
            measured_voltage,
            self.voltages[right_idx - 1:right_idx + 1],
            self.field_from_volts[right_idx - 1:right_idx + 1]
        )

    def update_output(self):
        """
        Updates the data on the DAQ card to set the desired output.
        If the mode is None then this simply doesn't ever start the task but allows the values to be updated so that
        when DC or AC is clicked, the output will happen.
        :return:
        """
        self.analogue_output_task.stop()
        if self.mode == "DC":
            n_samples = 100
            self.analogue_output_task.timing.cfg_samp_clk_timing(
                self.sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=n_samples,
            )

            data = np.ones(n_samples) * self.target_voltage
            self.analogue_output_task.write(data, auto_start=False)
            self.analogue_output_task.start()
            logging.debug(f"Set voltage to {self.target_voltage} VDC")
        elif self.mode == "AC":
            n_samples = int(round(
                1 / self.frequency,
                -int(floor(log10(abs(1 / self.frequency)))) + 3
            ) * 1000)
            self.analogue_output_task.timing.cfg_samp_clk_timing(
                self.sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=n_samples,
            )
            times = np.arange(n_samples) / self.sample_rate
            wave = self.target_voltage * np.sin(self.frequency * 2 * np.pi * times) + self.target_offset_voltage
            if len(wave[np.abs(wave) > 10]) > 0:
                wave[wave > 10] = 10
                wave[wave < -10] = -10
                logging.warning("The voltage is clipping. " +
                                "Please reduce offset or target field.")
            self.analogue_output_task.write(wave, auto_start=False)
            self.analogue_output_task.start()

            logging.debug(f"Outputting AC Waveform with Peak to Peak voltage of: {self.target_voltage}")
        elif self.mode == None:
            n_samples = 100
            self.analogue_output_task.timing.cfg_samp_clk_timing(
                self.sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=n_samples,
            )

            data = np.zeros(n_samples)
            self.analogue_output_task.write(data, auto_start=False)
            self.analogue_output_task.start()
            logging.debug(f"Set voltage to {self.target_voltage} VDC")

    def get_current_amplitude(self):
        """
        Gets the latest field measurement from the PSU via the DAQ card.
        :return: field after calibration and raw voltage from PSU.
        :rtype: tuple[float, float]
        """

        voltage = self.analogue_input_task.read()
        field = self.interpolate_field(voltage)
        return field, voltage

    def get_amplitude_values(self):
        """
        Gets the latest field measurement from the PSU via the DAQ card.
        :return: field after calibration and raw voltage from PSU.
        :rtype: tuple[float, float]
        """
        try:
            voltages = self.analogue_input_task.read(nidaq.constants.READ_ALL_AVAILABLE)
        except nidaq.errors.DaqReadError:
            logging.warning("DAQmx hates you for not reading the magnetic field data for too long.")
            self.analogue_input_task.stop()
            self.analogue_input_task.start()
            return [], []


        fields = [self.interpolate_field(voltage) for voltage in voltages]
        return fields, voltages

    def set_target_field(self, new_value):
        """
        Attempts to set the target field by converting this to a voltage value from the
        calibration file.
        :param float new_value: Target field value in mT
        :return:
        """
        self.target_voltage = self.interpolate_voltage(new_value)
        self.update_output()

    def set_target_offset(self, new_value):
        """
        Attempts to set the target offset field by converting this to a voltage value from the
        calibration file.
        :param float new_value: Target field value in mT
        :return:
        """
        self.target_offset_voltage = self.interpolate_voltage(new_value)
        self.update_output()

    def set_frequency(self, new_value):
        self.frequency = new_value
        self.update_output()

    def reset_field(self):
        self.target_voltage = 0.0
        self.target_offset_voltage = 0.0
        self.update_output()

    def close(self, reset):
        logging.info(f"Closing magnet controller")
        self.analogue_input_task.stop()
        self.analogue_output_task.close()
        self.analogue_input_task.close()
        if reset:
            self.dev.reset_device()

    def pause_instream(self):
        self.analogue_input_task.stop()


    def resume_instream(self):
        self.analogue_input_task.start()



if __name__ == '__main__':
    import time
    import matplotlib.pyplot as plt
    from collections import deque
    data_queue = deque(maxlen=10000)
    controller = MagnetController(reset=True)
    controller.mode = "AC"
    controller.set_target_field(0)
    controller.set_frequency(0.7)
    time.sleep(1.1)
    data = controller.get_amplitude_values()
    plt.figure()
    plt.plot(data[0])
    data_queue.append(data)
    time.sleep(0.01)
    data = controller.get_amplitude_values()
    plt.figure()
    plt.plot(data[0])
    new = np.setdiff1d(np.array(data_queue), np.array(data))
    print(len(new))
    plt.figure()
    plt.plot(new)
    plt.pause(1)
    print(len(data[0]))
    controller.close(True)
    plt.show()
