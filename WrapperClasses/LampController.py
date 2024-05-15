import logging

import nidaqmx as nidaq
import numpy as np
from nidaqmx.constants import LineGrouping, AcquisitionType, SampleTimingType
from nidaqmx.stream_writers import DigitalSingleChannelWriter
from itertools import chain
import math
import time

flatten = chain.from_iterable


class LampController:
    def __init__(self, reset=False):
        """
        :param bool reset: Choose whether to reset the DAQ card or not. Because DAQ based controllers are
        all using the same DAQ device, this should only be true for the first of these two objects to be created.
        """
        logging.info("Initialising LampController")
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

        self.frame_rate = 20

        if reset:
            logging.info("Resetting DAQ card")
            self.dev.reset_device()

        self.TTL_output_task = nidaq.Task()

        self.TTL_output_task.do_channels.add_do_chan('Dev1/port0/line0:4')
        self.TTL_stream = DigitalSingleChannelWriter(self.TTL_output_task.out_stream, True)

        self.SPI_task = nidaq.Task()

        self.SPI_task.do_channels.add_do_chan('Dev1/port1/line1:4')
        self.SPI_stream = DigitalSingleChannelWriter(self.SPI_task.out_stream, True)
        self.SPI_task.write(self.__resting_state_noSPI)
        self.__SPI_enabled = False
        logging.info("Setting all brightness to max")
        self.set_all_brightness(180)

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

    def enable_assortment_pairs(self, pairs):
        """

        :param dict pairs: dictionary of booleans containing "left", "right", "up", "down".
        :return:
        """
        if self.__SPI_enabled:
            self.disable_spi()

        send_byte = (pairs["left"] * self.__LEFT_CONST +
                     pairs["right"] * self.__RIGHT_CONST +
                     pairs["up"] * self.__UP_CONST +
                     pairs["down"] * self.__DOWN_CONST)
        logging.info("Enabling Pairs: " + str(send_byte))
        self.TTL_stream.write_one_sample_port_byte(send_byte)

    def close(self, reset):
        logging.info("Closing LampController")
        self.TTL_output_task.close()
        self.SPI_task.close()
        if reset:
            self.dev.reset_device()

    def enable_spi(self):
        logging.info("Enabling SPI")
        self.SPI_task.write(self.__resting_state_SPI)
        time.sleep(50e-3)
        self.__SPI_enabled = True

    def disable_spi(self):
        logging.info("Disabling SPI")
        self.SPI_task.write(self.__resting_state_noSPI)
        time.sleep(50e-3)
        self.__SPI_enabled = False

    def enable_leds(self, led_byte: int):
        if not self.__SPI_enabled:
            self.enable_spi()
        logging.info("Enabling SPI: " + str(led_byte))
        self._write_spi(int('0xA0', 16), led_byte)

    def set_all_brightness(self, brightness: int):
        """
        Set the brightness of all LEDs simultaneously
        :param brightness: the brightness between 0 and 180
        :return:
        """
        enabled = self.__SPI_enabled
        if not self.__SPI_enabled:
            self.enable_spi()
        logging.info("Setting all brightnesses to: " + str(brightness))
        self._write_spi(int('0xA9', 16), brightness)
        if not enabled:
            self.disable_spi()

    def set_one_brightness(self, brightness: int, led: int):
        """
        Set the brightness of one LED at a time
        :param brightness: the brightness between 0 and 180
        :param led: Integer value for LEDS from 1 to 8
        :return:
        """
        enabled = self.__SPI_enabled
        if not self.__SPI_enabled:
            self.enable_spi()
        logging.info(f" Setting LED: {led} to Brightness: {brightness}")
        self._write_spi(int('0xA0', 16) + led, brightness)
        if not enabled:
            self.disable_spi()

    def set_some_brightness(self, brightnesses: list, leds: list):
        """
        Set the brightness of one LED at a time
        :param brightness: the brightness between 0 and 180
        :param led: Integer value for LEDS from 1 to 8
        :return:
        """
        enabled = self.__SPI_enabled
        if not self.__SPI_enabled:
            self.enable_spi()
        for i in range(len(brightnesses)):
            logging.info(f"Setting LED: {leds[i]} to Brightness: {brightnesses[i]}")
            self._write_spi(int('0xA0', 16) + leds[i], brightnesses[i])
        if not enabled:
            self.disable_spi()

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

    def continuous_flicker(self, mode):
        self.disable_spi()
        self.TTL_output_task.stop()
        logging.info("Enabling LED flicker mode with mode: " + str(mode))
        match mode:
            case 0:
                # long trans pol
                pairs_pos = 1
                pairs_neg = 4
            case 1:
                # pure long
                pairs_pos = 4
                pairs_neg = 8
            case 2:
                # pure pol
                pairs_pos = 1
                pairs_neg = 2
        # TODO: Implement checking of exposure time to change this trigger rate
        n_samples = 2 * math.ceil((1 / self.frame_rate) * 1e3) + 24  # 12 ms for lights to change.
        pulse_width_in_samples = 1
        delay_in_samples = 6
        out_array = np.zeros(shape=[
            n_samples])  # 120 sample is 120 ms. This means that the on off rate is 50ms per light. Exposure time is 50ms so this is too short

        out_array[0:n_samples // 2] = pairs_pos
        out_array[delay_in_samples:delay_in_samples+pulse_width_in_samples] = pairs_pos + 16
        out_array[n_samples // 2:] = pairs_neg
        out_array[
        n_samples // 2 + delay_in_samples:n_samples // 2 + delay_in_samples + pulse_width_in_samples] = pairs_neg + 16

        self.TTL_output_task.stop()
        self.TTL_output_task.timing.cfg_samp_clk_timing(1000, sample_mode=AcquisitionType.CONTINUOUS,
                                                        samps_per_chan=n_samples)
        self.TTL_stream.write_many_sample_port_byte(out_array.astype(np.uint8))

    def stop_flicker(self):
        logging.info("Stopping LED flicker mode")
        self.TTL_output_task.stop()
        self.TTL_output_task.timing.samp_timing_type = SampleTimingType.ON_DEMAND
        self.TTL_stream.write_one_sample_port_byte(0)

    def pause_flicker(self, paused):
        logging.info("Pausing LED flicker")
        if paused:
            self.enable_spi()
        else:
            self.disable_spi()


if __name__ == '__main__':
    import time

    controller = LampController()
    controller.disable_all()
    controller.enable_left_pair()
    time.sleep(1)

    controller.continuous_flicker(0)

    time.sleep(2)
    controller.continuous_flicker(1)

    time.sleep(200)
    controller.continuous_flicker(2)

    time.sleep(2)

    controller.stop_flicker()
    time.sleep(1)
    controller.enable_left_pair()
    time.sleep(2)
    controller.close(True)

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
