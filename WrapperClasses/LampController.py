import nidaqmx as nidaq
from ctypes import *
import numpy as np
from nidaqmx.constants import LineGrouping, AcquisitionType
from nidaqmx.stream_writers import DigitalSingleChannelWriter
from itertools import chain

flatten = chain.from_iterable


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
        self.__resting_state_noSPI = self.__DATA_CONST + self.__SS_CONST
        self.__resting_state_SPI = self.__DATA_CONST + self.__SS_CONST + self.__MODE_CONST
        self.dev = nidaq.system.device.Device('Dev1')
        self.dev.reset_device()

        self.TTL_output_task = nidaq.Task()

        self.TTL_output_task.do_channels.add_do_chan('Dev1/port0/line0:7')
        self.TTL_stream = DigitalSingleChannelWriter(self.TTL_output_task.out_stream, True)
        self.SPI_task = nidaq.Task()

        self.SPI_task.do_channels.add_do_chan('Dev1/port1/line1:4')
        self.SPI_stream = DigitalSingleChannelWriter(self.SPI_task.out_stream, True)
        self.SPI_task.write(self.__resting_state_noSPI)
        self.__SPI_enabled = False
        self.enable_SPI()

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
            print("disabling SPI")
            self.disable_SPI()
        self.TTL_stream.write_one_sample_port_byte(
            left * self.__LEFT_CONST + right * self.__RIGHT_CONST + up * self.__UP_CONST + down * self.__DOWN_CONST)

    def close(self):
        self.TTL_output_task.close()
        self.SPI_task.close()
        self.dev.reset_device()

    def enable_SPI(self):
        self.SPI_task.write(self.__resting_state_SPI)
        time.sleep(50e-3)
        self.__SPI_enabled = True

    def disable_SPI(self):
        self.SPI_task.write(self.__resting_state_noSPI)
        time.sleep(50e-3)
        self.__SPI_enabled = False

    def write_SPI(self, command, value):
        '''
        Constructs a command message and sends it.
        :param command:
        :param value:
        :return:
        '''

        if not self.__SPI_enabled:
            self.enable_SPI()

        mode_array = [self.__MODE_CONST] * 48
        #  ss_array = [0] * 32   # Since this is only added and its always zero, we can ignore this.

        command_array = [int(i) * self.__DATA_CONST for i in list(format(command, '08b'))]
        command_array = list(flatten(zip(command_array, command_array, command_array)))  # doubles the data: 10101010 -> 1100110011001100

        value_array = [int(i) * self.__DATA_CONST for i in list(format(value, '08b'))]
        value_array = list(flatten(zip(value_array, value_array, value_array)))  # doubles the data: 10101010 -> 1100110011001100

        byte_array = command_array + value_array

        clock_array = [0, self.__SCK_CONST, 0] * 16   # total length of 32

        write_array = [self.__MODE_CONST + self.__DATA_CONST]  # Set SS low before the transfer.

        time.sleep(100e-6)
        for bit in range(len(clock_array)):
            write_array.append(clock_array[bit] + byte_array[bit] + mode_array[bit])  # append the data. SS is always zero.

        print(write_array)
        for bit in write_array:
            self.SPI_stream.write_one_sample_port_byte(bit)
            time.sleep(50e-6)

        self.SPI_stream.write_one_sample_port_byte(self.__resting_state_SPI - self.__SS_CONST)
        time.sleep(100e-6)
        self.SPI_stream.write_one_sample_port_byte(self.__resting_state_SPI)


if __name__ == '__main__':
    import time

    controller = LampController()
    controller.disable_all()
    # time.sleep(1)
    controller.enable_left()
    time.sleep(1)
    # Sets brightness of all LEDs to max
    controller.write_SPI(int('0xB9', 16), int('0xB4', 16))
    time.sleep(1)# Swaps between alterneating even and odd LEDs all on
    for loop in range(100):
        controller.write_SPI(int('0xA0', 16), int('0x50', 16))
        time.sleep(0.1)
        controller.write_SPI(int('0xA0', 16),  int('0x05', 16))
        time.sleep(0.1)
    # print("enable all?")
    # controller.TTL_stream.write_one_sample_port_byte(15)
    # print("enable all?")
    # time.sleep(3)
    # controller.enable_assortment(True, True, True, True)
    # print("enable all!")
    # controller.enable_assortment(True, True, True, True)
    # time.sleep(3)
    # controller.close()
    # time.sleep(1)
    # for i in range(20):
    #     controller.enable_SPI()
    #
    #     controller.disable_SPI()


    controller.close()

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
