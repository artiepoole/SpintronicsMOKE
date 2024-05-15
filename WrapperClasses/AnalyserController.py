import logging

import nidaqmx as nidaq
import numpy as np
from nidaqmx.stream_writers import DigitalSingleChannelWriter
import time


class AnalyserController:
    def __init__(self, reset=False):
        """
        :param bool reset: Choose whether to reset the DAQ card or not. Because DAQ based controllers are
        all using the same DAQ device, this should only be true for the first of these two objects to be created.
        """
        logging.info("Initialising AnalyserController")

        self.dev = nidaq.system.device.Device('Dev1')

        self.FINE = 8
        self.DIR = 2
        self.CLOCK = 4
        self.ENABLE = 1
        self.STEPS_PER_DEGREE = 222
        self.position_in_steps = 0
        self.position_in_degrees = 0

        if reset:
            logging.info("Resetting DAQ card")
            self.dev.reset_device()

        self.stepper_task = nidaq.Task()

        self.stepper_task.do_channels.add_do_chan('Dev1/port2/line0:3')
        self.stepper_stream = DigitalSingleChannelWriter(self.stepper_task.out_stream, True)

    def _step_forward(self, steps, fine=False):
        logging.info(f"moving {steps} steps")
        data = np.zeros(steps * 2)
        data += self.FINE * fine
        data[::2] += self.CLOCK
        for value in data:
            self.stepper_stream.write_one_sample_port_byte(value)
            time.sleep(2e-3)
            self.position_in_steps += 1
            self.position_in_degrees += 1/self.STEPS_PER_DEGREE

    def _step_backward(self, steps, fine=False):
        logging.info(f"moving -{steps} steps")
        data = np.zeros(steps * 2)
        data += self.FINE * fine + self.DIR
        data[::2] += self.CLOCK
        for value in data:
            self.stepper_stream.write_one_sample_port_byte(value)
            time.sleep(2e-3)
            self.position_in_steps -= 1
            self.position_in_degrees -= 1/self.STEPS_PER_DEGREE

    def move(self, degrees):
        """
        Rotate the polariser a number of degrees (positive or negative). Rate of movement is approx 1 degree per second.
        :param degrees: number of degrees to rotate
        :return None:
        """
        if abs(degrees) == 0:
            return
        steps = abs(degrees) * self.STEPS_PER_DEGREE
        if degrees > 0:
            self._step_forward(steps)
        else:
            self._step_backward(steps)

    def close(self, reset=False):
        logging.info("Closing LampController")
        self.stepper_task.close()
        if reset:
            self.dev.reset_device()


if __name__ == "__main__":
    controller = AnalyserController()
    controller._step_forward(10000, False)
    print("Going back")
    time.sleep(2)
    controller._step_backward(10000, False)
