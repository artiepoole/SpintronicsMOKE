import nidaqmx as nidaq
from ctypes import *
import numpy as np
from nidaqmx.constants import LineGrouping


class LampController:
    def __init__(self):
        self.dev = nidaq.system.device.Device('Dev1')
        self.dev.reset_device()

        self.digital_output_task = nidaq.Task()

        self.digital_output_task.do_channels.add_do_chan('Dev1/port0/line0:7', '', line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)

    def disable_all(self):
        self.output_byte_as_array = np.array([0] * 8, np.uint8)
        self.digital_output_task.write(0)

    def enable_left(self):
        self.digital_output_task.write([1])

    def enable_top(self):
        self.digital_output_task.write([4])

    def enable_right(self):
        self.digital_output_task.write([2])

    def enable_bottom(self):
            self.digital_output_task.write([8])
    def close(self):
        self.digital_output_task.close()
        self.dev.reset_device()


if __name__ == '__main__':

    import time
    controller = LampController()
    controller.disable_all()

    for i in range(100):
        controller.enable_left()
        time.sleep(1e-1)
        controller.enable_top()
        time.sleep(1e-1)

    time.sleep(1)
    controller.enable_left()
    time.sleep(1)
    controller.enable_right()
    time.sleep(1)
    controller.enable_top()
    time.sleep(1)
    controller.enable_bottom()
    time.sleep(1)
    controller.disable_all()
    time.sleep(1)
    controller.close()


