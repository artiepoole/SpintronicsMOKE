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
        self.enable_spi()  # not sure whether to enable or not at the start but it does not matter, really.

    def disable_all(self):
        if self.__SPI_enabled:
            self.disable_spi()
        # self.output_byte_as_array = np.array([0] * 8, np.uint8)
        self.TTL_stream.write_one_sample_port_byte(0)

    def enable_left_pair(self):
        if self.__SPI_enabled:
            self.disable_spi()
        self.TTL_stream.write_one_sample_port_byte(self.__LEFT_CONST)

    def enable_up_pair(self):
        if self.__SPI_enabled:
            self.disable_spi()
        self.TTL_stream.write_one_sample_port_byte(self.__UP_CONST)

    def enable_right_pair(self):
        if self.__SPI_enabled:
            self.disable_spi()
        self.TTL_stream.write_one_sample_port_byte(self.__RIGHT_CONST)

    def enable_down_pair(self):
        if self.__SPI_enabled:
            self.disable_spi()
        self.TTL_stream.write_one_sample_port_byte(self.__DOWN_CONST)

    def enable_assortment_pairs(self, left, right, up, down):
        """

        :param bool left: True to enable left pair
        :param bool right: True to enable right  pair
        :param bool up: True to enable up pair
        :param bool down: True to enable down pair
        :return:
        """
        if self.__SPI_enabled:
            print("disabling SPI")
            self.disable_spi()
        self.TTL_stream.write_one_sample_port_byte(
            left * self.__LEFT_CONST + right * self.__RIGHT_CONST + up * self.__UP_CONST + down * self.__DOWN_CONST)

    def close(self):
        self.TTL_output_task.close()
        self.SPI_task.close()
        self.dev.reset_device()

    def enable_spi(self):
        self.SPI_task.write(self.__resting_state_SPI)
        time.sleep(50e-3)
        self.__SPI_enabled = True

    def disable_spi(self):
        self.SPI_task.write(self.__resting_state_noSPI)
        time.sleep(50e-3)
        self.__SPI_enabled = False

    def enable_leds(self, led_byte: int):
        self._write_spi(int('0xA0', 16), led_byte)

    def enable_leds_bools(self, led0: bool, led1: bool, led2: bool, led3: bool, led4: bool, led5: bool, led6: bool,
                          led7: bool):
        self.enable_leds(led0 * 1 + led1 * 2 + led2 * 4 + led3 * 8 + led4 * 16 + led5 * 32 + led6 * 64 + led7 * 128)

    def enable_leds_list(self, leds: list):
        values = [1, 2, 4, 8, 16, 32, 64, 128]
        self.enable_leds(sum([a * b for a, b in zip(leds, values)]))

    def _write_spi(self, command, value):
        """
        Constructs a command message and sends it. It doesn't always work if the data bit is not set before the
        rising and falling edge for some reason and so the data bit is set then the clock is raised and lowered and
        then the clock is dropped.
        :param uint8 command: The command code: 0xA0 for which LEDs on, 0xA1 to 0xA8 adjusts start brightness for LEDS 1 to 8
        and 0xA9 for all brightnesses. 0xB1 to 0xB8 adjusts start brightness for LEDS 1 to 8. 0xB9 adjusts all start
        brightnesses
        :param uint8 value: For turning LEDs on and off it's the integer version of the binary for each LED. For brightness
        it's binary value between 0 and 180
        :return None:
        """

        if not self.__SPI_enabled:
            self.enable_spi()

        mode_array = [self.__MODE_CONST] * 48

        command_array = [int(i) * self.__DATA_CONST for i in list(format(command, '08b'))]  # int to binary
        # triples the data: 10101010 -> 111000111000111000111000
        command_array = list(
            flatten(zip(command_array, command_array, command_array)))

        value_array = [int(i) * self.__DATA_CONST for i in list(format(value, '08b'))]  # int to binary
        # triples the data: 10101010 -> 111000111000111000111000
        value_array = list(
            flatten(zip(value_array, value_array, value_array)))

        byte_array = command_array + value_array  # Send the command then the value

        clock_array = [0, self.__SCK_CONST, 0] * 16  # clock goes 010 for each bit of data

        write_array = [self.__resting_state_SPI - self.__SS_CONST]  # begin transmission by lowering SS

        time.sleep(100e-6)
        # Create the array of bytes to be sent
        for bit in range(len(clock_array)):
            write_array.append(
                clock_array[bit] + byte_array[bit] + mode_array[bit])

        # Send the data
        for bit in write_array:
            self.SPI_stream.write_one_sample_port_byte(bit)
            time.sleep(50e-6)  # The DAQ is slow so could remove this

        # set SS low and leave everything else in resting state.
        self.SPI_stream.write_one_sample_port_byte(self.__resting_state_SPI - self.__SS_CONST)
        time.sleep(100e-6)
        # return to resting state, leaving MODE, SS and DATA high.
        self.SPI_stream.write_one_sample_port_byte(self.__resting_state_SPI)


if __name__ == '__main__':
    import time

    controller = LampController()
    controller.disable_all()
    # time.sleep(1)
    controller.enable_left_pair()
    time.sleep(1)
    # Sets brightness of all LEDs to max
    controller._write_spi(int('0xA9', 16), int('0xB4', 16))
    time.sleep(1)  # Swaps between alterneating even and odd LEDs all on
    for loop in range(10):
        controller.enable_leds(int('0x50', 16))
        time.sleep(0.1)
        controller.enable_leds_bools(0, 1, 0, 1, 0, 0, 0, 0)
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
