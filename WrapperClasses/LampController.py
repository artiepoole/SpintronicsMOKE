import nidaqmx as nidaq
from ctypes import *
import numpy as np
from nidaqmx.constants import LineGrouping


class LampController:
    def __init__(self):
        self.dev = nidaq.system.device.Device('Dev1')
        self.dev.reset_device()

        self.digital_output_task = nidaq.Task()

        self.digital_output_task.do_channels.add_do_chan('Dev1/port0/line0:7', '',
                                                         line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        self.__UP_CONST = 4
        self.__DOWN_CONST = 8
        self.__LEFT_CONST = 1
        self.__RIGHT_CONST = 2

    def disable_all(self):
        self.output_byte_as_array = np.array([0] * 8, np.uint8)
        self.digital_output_task.write(0)

    def enable_left(self):
        self.digital_output_task.write([1])

    def enable_up(self):
        self.digital_output_task.write([4])

    def enable_right(self):
        self.digital_output_task.write([2])

    def enable_down(self):
        self.digital_output_task.write([8])

    def enable_assortment(self, left, right, up, down):
        '''

        :param bool left: True to enable left pair
        :param bool right: True to enable right  pair
        :param bool up: True to enable up pair
        :param bool down: True to enable down pair
        :return:
        '''

        self.digital_output_task.write(
            [left * self.__LEFT_CONST + right * self.__RIGHT_CONST + up * self.__UP_CONST + down * self.__DOWN_CONST])

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
        controller.enable_up()
        time.sleep(1e-1)

    time.sleep(1)
    controller.enable_left()
    time.sleep(1)
    controller.enable_right()
    time.sleep(1)
    controller.enable_up()
    time.sleep(1)
    controller.enable_down()
    time.sleep(1)
    controller.disable_all()
    time.sleep(1)
    controller.close()
