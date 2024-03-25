import nidaqmx as nidaq
from ctypes import *
import numpy as np
from nidaqmx.constants import LineGrouping, AcquisitionType
from nidaqmx.stream_writers import DigitalSingleChannelWriter


class LampController:
    def __init__(self):
        self.__UP_CONST = 4
        self.__DOWN_CONST = 8
        self.__LEFT_CONST = 1
        self.__RIGHT_CONST = 2

        self.__SCK_CONST = 2
        self.__DATA_CONST = 4
        self.__SS_CONST = 8
        self.__MODE_CONST = 16

        self.dev = nidaq.system.device.Device('Dev1')
        self.dev.reset_device()

        self.TTL_output_task = nidaq.Task()

        self.TTL_output_task.do_channels.add_do_chan('Dev1/port0/line0:7')
        self.TTL_stream = DigitalSingleChannelWriter(self.TTL_output_task.out_stream, True)
        self.SPI_task = nidaq.Task()
        self.SPI_task.do_channels.add_do_chan('Dev1/port1/line1:4')
        self.SPI_stream = DigitalSingleChannelWriter(self.SPI_task.out_stream)
        self.SPI_stream.write_one_sample_port_byte(self.__SS_CONST)  # set SS high
        self.__SPI_enabled = False

    def disable_all(self):
        if self.__SPI_enabled:
            self.disable_SPI()
        # self.output_byte_as_array = np.array([0] * 8, np.uint8)
        self.TTL_stream.write_one_sample_port_byte(0)

    def enable_left(self):
        if self.__SPI_enabled:
            self.disable_SPI()
        self.TTL_stream.write_one_sample_port_byte(self.__LEFT_CONST)

    def enable_up(self):
        if self.__SPI_enabled:
            self.disable_SPI()
        self.TTL_stream.write_one_sample_port_byte(self.__UP_CONST)

    def enable_right(self):
        if self.__SPI_enabled:
            self.disable_SPI()
        self.TTL_stream.write_one_sample_port_byte(self.__RIGHT_CONST)

    def enable_down(self):
        if self.__SPI_enabled:
            self.disable_SPI()
        self.TTL_stream.write_one_sample_port_byte(self.__DOWN_CONST)

    def enable_assortment(self, left, right, up, down):
        '''

        :param bool left: True to enable left pair
        :param bool right: True to enable right  pair
        :param bool up: True to enable up pair
        :param bool down: True to enable down pair
        :return:
        '''
        if self.__SPI_enabled:
            self.disable_SPI()
        self.TTL_stream.write_one_sample_port_byte(
            [left * self.__LEFT_CONST + right * self.__RIGHT_CONST + up * self.__UP_CONST + down * self.__DOWN_CONST])

    def close(self):
        self.TTL_output_task.close()
        self.SPI_task.close()
        self.dev.reset_device()

    def enable_SPI(self):
        self.SPI_task.write(self.__SS_CONST + self.__MODE_CONST)
        time.sleep(50e-3)# Set SS high and mode high
        self.__SPI_enabled = True

    def disable_SPI(self):
        self.SPI_task.write(self.__SS_CONST)
        time.sleep(50e-3)  # Set SS high and mode low
        self.__SPI_enabled = False

    def write_SPI(self, command, value):
        self.enable_SPI()
        command_array = [int(i) for i in list(format(command, '08b'))]
        # command_array.reverse()
        value_array = [int(i) for i in list(format(value, '08b'))]
        # value_array.reverse()
        # self.SPI_task.write(self.__MODE_CONST + self.__SS_CONST)  # set SS high and mode high to enable SPI
        self.SPI_task.write(self.__MODE_CONST)  # set ss low 5ms before transmission
        # time.sleep(10e-5)
        for bit in command_array:
            self.SPI_task.write(self.__DATA_CONST * bit + self.__MODE_CONST) # Set the data and SS low before clock signal
            # time.sleep(2e-5)
            self.SPI_task.write(self.__DATA_CONST * bit + self.__SCK_CONST + self.__MODE_CONST)  # Raise the clock
            # time.sleep(2e-5)
            self.SPI_task.write(self.__DATA_CONST * bit + self.__MODE_CONST)  # Lower the clock
            # time.sleep(2e-5)
        # time.sleep(5e-5)  # delay between bytes
        for bit in value_array:
            self.SPI_task.write(self.__DATA_CONST * bit + self.__MODE_CONST)  # Set the data before clock signal
            # time.sleep(2e-5)
            self.SPI_task.write(self.__DATA_CONST * bit + self.__SCK_CONST + self.__MODE_CONST)  # Raise the clock
            # time.sleep(2e-5)
            self.SPI_task.write(self.__DATA_CONST * bit + self.__MODE_CONST)  # Lower the clock
            # time.sleep(2e-5)
        # time.sleep(3e-5)  # total of 5ms after data before disabling SPI
        self.SPI_task.write(self.__SS_CONST + self.__MODE_CONST)  # Set SS high and mode high


if __name__ == '__main__':
    import time

    controller = LampController()
    controller.disable_all()
    time.sleep(1)
    controller.write_SPI(160, 85)
    time.sleep(3)
    # controller.enable_assortment(True, True, True, True)
    # time.sleep(5)
    controller.close()
    # time.sleep(1)
    # controller.close()

    # for i in range(100):
    #     controller.enable_left()
    #     time.sleep(1e-1)
    #     controller.enable_up()
    #     time.sleep(1e-1)

    # time.sleep(1)
    # controller.enable_left()
    # time.sleep(1)
    # controller.enable_right()
    # time.sleep(1)
    # controller.enable_up()
    # time.sleep(1)
    # controller.enable_down()
    # time.sleep(1)
    # controller.disable_all()
    # time.sleep(1)
    # controller.close()
