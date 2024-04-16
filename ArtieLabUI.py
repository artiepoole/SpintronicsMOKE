from WrapperClasses.CameraGrabber import CameraGrabber
from WrapperClasses.LampController import LampController
from WrapperClasses.FrameProcessor import FrameProcessor

import cv2
from PyQt5 import QtCore, QtWidgets, uic
import sys
import numpy as np
import tifffile
import pandas as pd
from datetime import datetime
from pathlib import Path

import time

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import *
from matplotlib.figure import Figure
from skimage import exposure

plt.rcParams['axes.formatter.useoffset'] = False
plt.rcParams['figure.autolayout'] = True


class ArtieLabUI(QtWidgets.QMainWindow):
    def __init__(self):

        super(ArtieLabUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('res/ArtieLab.ui', self)  # Load the .ui file
        right_monitor = QtWidgets.QDesktopWidget().screenGeometry(1)
        self.move(right_monitor.left(), right_monitor.top())
        self.showMaximized()
        self.show()
        self.activateWindow()

        # define variables
        self.mutex = QtCore.QMutex()
        self.close_event = None
        self.background = None
        self.binning = 2

        self.enabled_leds_spi = {"left1": False,
                                 "left2": False,
                                 "right1": False,
                                 "right2": False,
                                 "up1": False,
                                 "up2": False,
                                 "down1": False,
                                 "down2": False}

        self.enabled_led_pairs = {"left": False,
                                  "right": False,
                                  "up": False,
                                  "down": False}

        # Create controller objects and threads
        self.lamp_controller = LampController()
        self.lamp_controller.disable_all()

        self.camera_grabber = CameraGrabber()
        self.camera_thread = QtCore.QThread()
        self.camera_grabber.moveToThread(self.camera_thread)
        self.height, self.width = self.camera_grabber.get_data_dims()
        self.frame_processor = FrameProcessor()
        self.frame_processor_thread = QtCore.QThread()
        self.frame_processor.moveToThread(self.frame_processor_thread)

        self.flickering = False
        self.averaging = False

        self.__connect_signals()
        self.__prepare_views()

        self.camera_grabber.start_live_single_frame()
        self.frame_counter = 0
        self.latest_raw_frame = None
        self.latest_diff_frame_a = None
        self.latest_diff_frame_b = None
        self.latest_processed_frame = None
        self.background = None

        self.raw_frame_stack = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.diff_frame_stack_a = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.diff_frame_stack_b = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.background_raw_stack = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)

    def __connect_signals(self):
        # LED controls
        self.button_left_led1.toggled.connect(self.__on_individual_led)
        self.button_right_led1.toggled.connect(self.__on_individual_led)
        self.button_up_led1.toggled.connect(self.__on_individual_led)
        self.button_down_led1.toggled.connect(self.__on_individual_led)
        self.button_left_led2.toggled.connect(self.__on_individual_led)
        self.button_right_led2.toggled.connect(self.__on_individual_led)
        self.button_up_led2.toggled.connect(self.__on_individual_led)
        self.button_down_led2.toggled.connect(self.__on_individual_led)
        self.button_leds_off.clicked.connect(self.__disable_all_leds)

        self.button_long_pol.toggled.connect(self.__on_long_pol)
        self.button_trans_pol.toggled.connect(self.__on_trans_pol)
        self.button_polar.toggled.connect(self.__on_polar)
        self.button_long_trans.toggled.connect(self.__on_long_trans)
        self.button_pure_long.toggled.connect(self.__on_pure_long)
        self.button_pure_trans.toggled.connect(self.__on_pure_trans)

        # Image Processing Controls
        self.combo_normalisation_selector.currentIndexChanged.connect(self.__on_image_processing_mode_change)
        self.spin_percentile_lower.valueChanged.connect(self.__on_image_processing_spin_box_change)
        self.spin_percentile_upper.valueChanged.connect(self.__on_image_processing_spin_box_change)
        self.spin_clip.valueChanged.connect(self.__on_image_processing_spin_box_change)

        # Averaging controls
        self.button_measure_background.clicked.connect(self.__on_get_new_background)
        self.button_toggle_averaging.toggled.connect(self.__on_averaging)
        self.spin_foreground_averages.valueChanged.connect(self.__on_average_changed)

        # Camera Controls
        self.combo_targetfps.currentIndexChanged.connect(self.__on_exposure_time_changed)
        self.button_pause_camera.toggled.connect(self.__on_pause_button)
        self.button_display_subtraction.toggled.connect(self.__on_show_subtraction)

        # Data Streams and Signals
        self.frame_processor.frame_processed_signal.connect(self.__on_processed_frame)
        self.frame_processor.diff_processed_signal.connect(self.__on_processed_diff)
        self.camera_grabber.frame_ready_signal.connect(self.__on_new_raw_frame)
        self.camera_grabber.difference_frame_ready.connect(self.__on_new_diff_frame)
        self.camera_grabber.camera_ready.connect(self.__on_camera_ready)
        self.camera_grabber.quit_ready.connect(self.__on_quit_ready)

        # saving GUI
        self.button_save_package.clicked.connect(self.__on_save)
        self.button_save_single.clicked.connect(self.__on_save_single)
        self.button_dir_browse.clicked.connect(self.__on_browse)

        # TODO: Add planar subtraction
        # TODO: Add ROI
        # TODO: Add Draw Line feature
        # TODO: Add brightness normalisation
        # TODO: binning mode change handling#
        # TODO: Add plot of intensity
        # TODO: Add change the number of frames
        # TODO: Add histogram plot

    def __prepare_views(self):
        self.stream_window = 'HamamatsuView'
        window_width = self.width
        window_height = self.height
        cv2.namedWindow(
            self.stream_window,
            flags=(cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_FREERATIO))
        cv2.setWindowProperty(self.stream_window, cv2.WND_PROP_TOPMOST, 1.0)
        cv2.setWindowProperty(self.stream_window, cv2.WND_PROP_FULLSCREEN, 1.0)
        cv2.resizeWindow(
            self.stream_window,
            window_width,
            window_height)
        cv2.moveWindow(
            self.stream_window,
            0,
            0)

        self.plots_canvas = FigureCanvasQTAgg(Figure())
        self.intensity_ax = self.plots_canvas.figure.add_subplot(311)
        self.intensity_y = []
        self.intensity_line, = self.intensity_ax.plot(self.intensity_y, 'k+')
        self.intensity_ax.set(title="Raw frame average intensity", xlabel="Frame", ylabel="Average Intensity")

        self.hist_ax = self.plots_canvas.figure.add_subplot(312)
        self.hist_line, = self.hist_ax.plot([], [], 'b-')
        self.hist_ax.set(title="Histogram as Seen", xlabel="Brightness", ylabel="Counts")

        self.blank_ax = self.plots_canvas.figure.add_subplot(313)
        self.blank_line, = self.hist_ax.plot([], [], 'r-')
        self.blank_ax.set(title="Unused Plot", xlabel="", ylabel="")
        self.plots_canvas.figure.tight_layout(pad=0.1)
        self.layout_plot1.addWidget(self.plots_canvas)

    def __update_plots(self):
        length = len(self.intensity_y)
        self.intensity_line.set_xdata(list(range(min(length, 100))))
        self.intensity_line.set_ydata(self.intensity_y[-min(100, length):])
        self.intensity_ax.relim()
        self.intensity_ax.autoscale_view()

        hist_data, hist_bins = exposure.histogram(self.latest_processed_frame)
        self.hist_line.set_xdata(hist_bins)
        self.hist_line.set_ydata(hist_data)
        self.hist_ax.relim()
        self.hist_ax.autoscale_view()

        self.blank_line.set_xdata([])
        self.blank_line.set_ydata([])
        self.blank_ax.relim()
        self.blank_ax.autoscale_view()

        plt.autoscale()
        self.plots_canvas.draw()
        self.plots_canvas.flush_events()

    def __reset_pairs(self):
        self.enabled_led_pairs.update(
            {"left": False,
             "right": False,
             "up": False,
             "down": False})

    def __reset_led_spis(self):
        self.enabled_led_pairs.update(
            {"left1": False,
             "left2": False,
             "right1": False,
             "right2": False,
             "up1": False,
             "up2": False,
             "down1": False,
             "down2": False}
        )

    def __get_lighting_configuration(self):
        if self.button_long_pol.isChecked():
            return "longitudinal and polar"
        elif self.button_trans_pol.isChecked():
            return "transpose and polar"
        elif self.button_polar.isChecked():
            return "polar"
        elif self.button_long_trans.isChecked():
            return "longitudinal and transpose and polar"
        elif self.button_pure_long.isChecked():
            return "pure longitudinal"
        elif self.button_pure_trans.isChecked():
            return "pure transpose"
        else:
            return [self.button_up_led1.isChecked(),
                    self.button_up_led2.isChecked(),
                    self.button_down_led1.isChecked(),
                    self.button_down_led2.isChecked(),
                    self.button_left_led1.isChecked(),
                    self.button_left_led2.isChecked(),
                    self.button_right_led1.isChecked(),
                    self.button_right_led2.isChecked()]

    def __on_image_processing_spin_box_change(self, ignored_event):
        self.frame_processor.set_percentile_lower(self.spin_percentile_lower.value())
        self.frame_processor.set_percentile_upper(self.spin_percentile_upper.value())
        self.frame_processor.set_clip_limit(self.spin_clip.value())

    def __on_image_processing_mode_change(self, mode):
        self.frame_processor.set_mode(mode)
        match mode:
            case -1:
                pass
            case 0:
                self.spin_percentile_lower.setEnabled(False)
                self.spin_percentile_upper.setEnabled(False)
                self.spin_clip.setEnabled(False)
            case 1:
                self.spin_percentile_lower.setEnabled(True)
                self.spin_percentile_upper.setEnabled(True)
                self.spin_clip.setEnabled(False)

                self.frame_processor.set_percentile_lower(self.spin_percentile_lower.value())
                self.frame_processor.set_percentile_upper(self.spin_percentile_upper.value())
                # This is contrast stretching and needs min and max percentiles
            case 2:
                self.spin_percentile_lower.setEnabled(False)
                self.spin_percentile_upper.setEnabled(False)
                self.spin_clip.setEnabled(False)
                # this is auto hist and so no other settings are needed
            case 3:
                self.spin_percentile_lower.setEnabled(False)
                self.spin_percentile_upper.setEnabled(False)
                self.spin_clip.setEnabled(True)
                self.frame_processor.set_clip_limit(self.spin_clip.value())
                # this is Adaptive EQ and needs a clip limit

    def __disable_all_leds(self):
        print("disabling all LEDs")
        self.__reset_led_spis()
        self.__reset_pairs()
        if self.flickering:
            self.__reset_after_flicker_mode()

        self.button_long_pol.setChecked(False)
        self.button_trans_pol.setChecked(False)
        self.button_polar.setChecked(False)
        self.button_long_trans.setChecked(False)
        self.button_pure_long.setChecked(False)
        self.button_pure_trans.setChecked(False)

        self.button_up_led1.setChecked(False)
        self.button_up_led2.setChecked(False)
        self.button_down_led1.setChecked(False)
        self.button_down_led2.setChecked(False)
        self.button_left_led1.setChecked(False)
        self.button_left_led2.setChecked(False)
        self.button_right_led1.setChecked(False)
        self.button_right_led2.setChecked(False)

        self.__update_controller_pairs()

    def __on_individual_led(self, state):

        if not self.flickering:
            self.enabled_leds_spi["up1"] = self.button_up_led1.isChecked()
            self.enabled_leds_spi["up2"] = self.button_up_led2.isChecked()
            self.enabled_leds_spi["down1"] = self.button_down_led1.isChecked()
            self.enabled_leds_spi["down2"] = self.button_down_led2.isChecked()
            self.enabled_leds_spi["left1"] = self.button_left_led1.isChecked()
            self.enabled_leds_spi["left2"] = self.button_left_led2.isChecked()
            self.enabled_leds_spi["right1"] = self.button_right_led1.isChecked()
            self.enabled_leds_spi["right2"] = self.button_right_led2.isChecked()
            self.__update_controller_spi()

    def __on_long_pol(self, checked):
        if checked:
            if self.flickering:
                self.__reset_after_flicker_mode()
            self.enabled_led_pairs.update(
                {"left": False,
                 "right": False,
                 "up": True,
                 "down": False})
            self.__reset_led_spis()

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(True)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)

            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_long_trans.setChecked(False)
            self.button_pure_long.setChecked(False)
            self.button_pure_trans.setChecked(False)

            self.__update_controller_pairs()
        else:
            self.__check_for_no_modes()

    def __on_trans_pol(self, checked):

        if checked:
            if self.flickering:
                self.__reset_after_flicker_mode()
            self.enabled_led_pairs.update({"left": True,
                                           "right": False,
                                           "up": False,
                                           "down": False})
            self.__reset_led_spis()

            self.button_up_led1.setChecked(False)
            self.button_up_led2.setChecked(False)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(True)
            self.button_left_led2.setChecked(True)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)

            self.button_long_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_long_trans.setChecked(False)
            self.button_pure_long.setChecked(False)
            self.button_pure_trans.setChecked(False)

            self.__update_controller_pairs()
        else:
            self.__check_for_no_modes()

    def __on_polar(self, checked):

        if checked:
            if self.flickering:
                self.__reset_after_flicker_mode()
            self.__reset_pairs()
            self.enabled_leds_spi.update(
                {"left1": False,
                 "left2": False,
                 "right1": False,
                 "right2": False,
                 "up1": True,
                 "up2": False,
                 "down1": True,
                 "down2": False})
            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(False)
            self.button_down_led1.setChecked(True)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)

            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_long_trans.setChecked(False)
            self.button_pure_long.setChecked(False)
            self.button_pure_trans.setChecked(False)

            self.__update_controller_spi()
        else:
            self.__check_for_no_modes()

    def __on_long_trans(self, checked):
        if checked:
            if not self.flickering:
                self.__prepare_for_flicker_mode()
            else:
                self.lamp_controller.stop_flicker()
            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_pure_long.setChecked(False)
            self.button_pure_trans.setChecked(False)

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(True)
            self.button_left_led1.setChecked(True)
            self.button_left_led2.setChecked(True)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)


            self.lamp_controller.continuous_flicker(0)


        else:
            self.__check_for_no_modes()

    def __on_pure_long(self, checked):
        if checked:
            if not self.flickering:
                self.__prepare_for_flicker_mode()
            else:
                self.lamp_controller.stop_flicker()
            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_long_trans.setChecked(False)
            self.button_pure_trans.setChecked(False)

            self.lamp_controller.continuous_flicker(1)

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(True)
            self.button_down_led1.setChecked(True)
            self.button_down_led2.setChecked(True)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
        else:
            self.__check_for_no_modes()

    def __on_pure_trans(self, checked):
        if checked:
            if not self.flickering:
                self.__prepare_for_flicker_mode()
            else:
                self.lamp_controller.stop_flicker()
            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_long_trans.setChecked(False)
            self.button_pure_long.setChecked(False)

            self.lamp_controller.continuous_flicker(2)

            self.__prepare_for_flicker_mode()

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(True)
            self.button_right_led1.setChecked(True)
            self.button_right_led2.setChecked(True)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
        else:
            self.__check_for_no_modes()

    def __prepare_for_flicker_mode(self):

        self.frame_processor.subtracting = False
        self.button_display_subtraction.setEnabled(False)
        # TODO: Add cv2 windows for raw frames

        self.flickering = True

        self.mutex.lock()
        self.camera_grabber.running = False
        self.mutex.unlock()

        self.button_up_led1.setEnabled(False)
        self.button_up_led2.setEnabled(False)
        self.button_down_led1.setEnabled(False)
        self.button_down_led2.setEnabled(False)
        self.button_left_led1.setEnabled(False)
        self.button_left_led2.setEnabled(False)
        self.button_right_led1.setEnabled(False)
        self.button_right_led2.setEnabled(False)

        self.button_up_led1.setChecked(False)
        self.button_up_led2.setChecked(False)
        self.button_down_led1.setChecked(False)
        self.button_down_led2.setChecked(False)
        self.button_left_led1.setChecked(False)
        self.button_left_led2.setChecked(False)
        self.button_right_led1.setChecked(False)
        self.button_right_led2.setChecked(False)

    def __on_camera_ready(self):
        """
        Whenever the camera is stopped, this is automatically called but cannot be instigated until after the method
        that changed the running mode has been executed fully. If paused, this is ignored and unpausing manually
        restarts the camera.
        :return:
        """
        if not self.button_pause_camera.isChecked():
            if self.flickering:
                self.camera_grabber.start_live_difference_mode()
                print("Camera grabber starting difference mode")
            else:
                self.camera_grabber.start_live_single_frame()
                print("Camera grabber starting normal mode")

    def __reset_after_flicker_mode(self):
        self.lamp_controller.stop_flicker()
        self.camera_grabber.running = False
        self.flickering = False

        self.button_display_subtraction.setEnabled(True)
        self.frame_processor.subtracting = self.button_display_subtraction.isChecked()
        # TODO: hide the CV2 windows for the raw pos/neg

        print("Resetting after flicker mode")
        self.button_up_led1.setEnabled(True)
        self.button_up_led2.setEnabled(True)
        self.button_down_led1.setEnabled(True)
        self.button_down_led2.setEnabled(True)
        self.button_left_led1.setEnabled(True)
        self.button_left_led2.setEnabled(True)
        self.button_right_led1.setEnabled(True)
        self.button_right_led2.setEnabled(True)


    def __check_for_no_modes(self):
        any_modes = self.button_long_pol.isChecked() + self.button_trans_pol.isChecked() + self.button_polar.isChecked() + self.button_long_trans.isChecked() + self.button_pure_long.isChecked() + self.button_pure_trans.isChecked()
        if any_modes == 0:
            self.__disable_all_leds()

    def __update_controller_pairs(self):
        self.lamp_controller.enable_assortment_pairs(self.enabled_led_pairs)

    def __update_controller_spi(self):
        # I assumed the numbering would go outside then inside, but it goes inside then outside
        value = self.enabled_leds_spi["left1"] * 2 \
                + self.enabled_leds_spi["left2"] * 1 \
                + self.enabled_leds_spi["right1"] * 8 \
                + self.enabled_leds_spi["right2"] * 4 \
                + self.enabled_leds_spi["up1"] * 32 \
                + self.enabled_leds_spi["up2"] * 16 \
                + self.enabled_leds_spi["down1"] * 128 \
                + self.enabled_leds_spi["down2"] * 64
        self.lamp_controller.enable_leds(value)

    def __on_new_raw_frame(self, raw_frame):
        self.latest_raw_frame = raw_frame
        self.intensity_y.append(np.mean(raw_frame, axis=(0, 1)))
        if self.averaging:
            if self.frame_counter % self.averages < len(self.raw_frame_stack):
                self.raw_frame_stack[self.frame_counter % self.averages] = raw_frame
            else:
                self.raw_frame_stack = np.append(self.raw_frame_stack, np.expand_dims(raw_frame, 0), axis=0)
            if len(self.raw_frame_stack) > self.averages:
                self.raw_frame_stack = self.raw_frame_stack[-self.averages:]
            self.frame_counter += 1
            self.frame_processor.process_frame(np.mean(self.raw_frame_stack, axis=0))
        else:
            self.frame_processor.process_frame(raw_frame)

    def __on_new_diff_frame(self, frame_a, frame_b):
        intensity_a = np.mean(frame_a, axis=(0, 1))
        intensity_b = np.mean(frame_b, axis=(0, 1))
        self.intensity_y.append(intensity_a)
        self.intensity_y.append(intensity_b)
        if self.averaging:
            if self.frame_counter % self.averages < len(self.diff_frame_stack_a):
                self.diff_frame_stack_a[self.frame_counter % self.averages] = frame_a
                self.diff_frame_stack_b[self.frame_counter % self.averages] = frame_b
            else:
                self.diff_frame_stack_a = np.append(self.diff_frame_stack_a, np.expand_dims(frame_a, 0), axis=0)
                self.diff_frame_stack_b = np.append(self.diff_frame_stack_b, np.expand_dims(frame_b, 0), axis=0)
            if len(self.diff_frame_stack_a) > self.averages:
                self.diff_frame_stack_a = self.diff_frame_stack_a[-self.averages:]
                self.diff_frame_stack_b = self.diff_frame_stack_b[-self.averages:]
            self.frame_counter += 1
            self.frame_processor.process_diff(np.mean(self.diff_frame_stack_a, axis=0),
                                              np.mean(self.diff_frame_stack_b, axis=0))
        else:
            self.latest_diff_frame_a = frame_a
            self.latest_diff_frame_b = frame_b
            self.frame_processor.process_diff(frame_a, frame_b)

    def __on_processed_frame(self, processed_frame):
        self.latest_processed_frame = processed_frame
        cv2.imshow(self.stream_window, processed_frame)
        self.__update_plots()
        cv2.waitKey(1)

    def __on_processed_diff(self, diff, diff_processed):
        self.latest_diff_frame = diff
        self.latest_processed_frame = diff_processed
        cv2.imshow(self.stream_window, diff_processed)
        self.__update_plots()
        cv2.waitKey(1)

    def __on_get_new_background(self, ignored_event):
        self.mutex.lock()
        self.camera_grabber.running = False
        self.mutex.unlock()
        frames = self.camera_grabber.grab_n_frames(self.spin_background_averages.value())
        self.background_raw_stack = frames
        self.background = np.mean(frames, axis=0)
        self.frame_processor.background = self.background
        if self.flickering:
            self.camera_grabber.start_live_difference_mode()
        else:
            self.camera_grabber.start_live_single_frame()
        print("Background Measured")

    def __on_exposure_time_changed(self, exposure_time_idx):
        self.mutex.lock()
        self.camera_grabber.running = False
        self.mutex.unlock()
        self.camera_grabber.set_exposure_time(exposure_time_idx)

    def __on_average_changed(self, value):
        self.averages = value

    def __on_averaging(self, enabled):
        if enabled:
            self.button_toggle_averaging.setText("Disable Averaging (F3)")
            print("Averaging enabled")
            self.averaging = True
            self.camera_grabber.running = False
            self.averages = self.spin_foreground_averages.value()
            self.frame_counter = 0
            self.raw_frame_stack = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
            self.diff_frame_stack_a = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
            self.diff_frame_stack_b = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        else:
            self.button_toggle_averaging.setText("Enable Averaging (F3)")
            print("Averaging disabled")
            self.averaging = False
            self.camera_grabber.running = False
            self.raw_frame_stack = None
            self.diff_frame_stack_a = None
            self.diff_frame_stack_b = None

    def __on_show_subtraction(self, subtracting):
        if subtracting:
            self.button_display_subtraction.setText("Ignore Background (F2)")
            self.frame_processor.subtracting = True
        else:
            self.button_display_subtraction.setText("Show Subtraction (F2)")
            self.frame_processor.subtracting = False

    def __on_pause_button(self, paused):
        if paused:
            self.camera_grabber.running = False
            self.button_pause_camera.setText("Unpause (F4)")
            if self.flickering:
                self.lamp_controller.pause_flicker(paused)
        else:
            self.button_pause_camera.setText("Pause (F4)")
            if self.flickering:
                self.lamp_controller.pause_flicker(paused)
                self.camera_grabber.start_live_difference_mode()
            else:
                self.camera_grabber.start_live_single_frame()

    def __on_save(self, event):
        # TODO: Add the difference frame processing to this. Currently this only works for single light source modes
        meta_data = {
            'description': "Image acquired using B204 MOKE owned by the Spintronics Group and University of "
                           "Nottingham using ArtieLab V0-2024.04.05.",
            'camera': 'Hamamatsu C11440',
            'sample': self.line_prefix.text(),
            'lighting configuration': [self.__get_lighting_configuration()],
            'binnning': self.combo_binning.currentText(),
            'lens': self.combo_lens.currentText(),
            'magnification': self.combo_magnification.currentText(),
            'target fps': self.combo_targetfps.currentText(),
            'correction': self.line_correction.text(),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        contents = []
        file_path = Path(self.line_directory.text()).joinpath(
            datetime.now().strftime("%Y-%m-%d--%H-%M-%S") + '_' + self.line_prefix.text().strip().replace(' ',
                                                                                                          '_') + '.h5')
        print("Saving to: " + str(file_path) + ' This takes time. Please be patient.')
        try:
            store = pd.HDFStore(str(file_path))
        except:
            print("Cannot save to this file/location: " + file_path + '. Does it exist? Do you have write permissions?')
            return

        if self.button_toggle_averaging.isChecked():
            if self.check_save_avg.isChecked():
                key = 'frame_avg'
                contents.append(key)
                store[key] = pd.DataFrame(self.latest_raw_frame)
            if self.check_save_stack.isChecked():
                for i in range(self.raw_frame_stack.shape[0]):
                    key = 'stack_' + str(i)
                    contents.append(key)
                    store[key] = pd.DataFrame(self.raw_frame_stack[i])
        else:
            if self.check_save_avg.isChecked():
                print("Average not saved: measuring in single frame mode")
            if self.check_save_stack.isChecked():
                print("Stack not saved: measuring in single frame mode")
            key = 'frame'
            contents.append(key)
            store[key] = pd.DataFrame(self.latest_raw_frame)
        if self.check_save_as_seen.isChecked():
            if self.button_toggle_averaging.isChecked():
                if self.button_display_subtraction.isChecked():
                    key = f'averaged({self.spin_foreground_averages.value()}) and subtracted'
                else:
                    key = f'averaged({self.spin_foreground_averages.value()})'
            elif self.button_display_subtraction.isChecked():
                key = 'subtracted'
            else:
                key = 'single'
            meta_data['normalisation'] = f'type: {self.combo_normalisation_selector.currentText()} ' + \
                                         f'lower: {self.spin_percentile_lower.value()} ' + \
                                         f'upper: {self.spin_percentile_upper.value()} ' + \
                                         f'clip: {self.spin_clip.value()}'
            contents.append(key)
            store[key] = pd.DataFrame(self.latest_processed_frame)
        if self.check_save_background.isChecked():
            if self.background is not None:
                key = 'background_avg'
                contents.append(key)
                store[key] = pd.DataFrame(self.background)
            else:
                print("Background not saved: no background measured")
        if self.check_save_bkg_stack.isChecked():
            if self.background is not None:
                for i in range(len(self.background_raw_stack)):
                    key = 'bkg_stack_' + str(i)
                    contents.append(key)
                    store[key] = pd.DataFrame(self.background_raw_stack[i])
            else:
                print("Background stack not saved: no background measured")
        meta_data['contents'] = [contents]
        store['meta_data'] = pd.DataFrame(meta_data)
        store.close()
        print("Saving done.")

    def __on_save_single(self, event):
        # Assemble metadata
        meta_data = {
            'description': "Image acquired using B204 MOKE owned by the Spintronics Group and University of Nottingham using ArtieLab V0-2024.04.05.",
            'camera': 'Hamamatsu C11440',
            'sample': self.line_prefix.text(),
            'lighting configuration': self.__get_lighting_configuration(),
            'binnning': self.combo_binning.currentText(),
            'lens': self.combo_lens.currentText(),
            'magnification': self.combo_magnification.currentText(),
            'target fps': self.combo_targetfps.currentText(),
            'correction': self.line_correction.text(),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'normalisation': f'type: {self.combo_normalisation_selector.currentText()} ' +
                             f'lower: {self.spin_percentile_lower.value()} ' +
                             f'upper: {self.spin_percentile_upper.value()} ' +
                             f'clip: {self.spin_clip.value()}',
            'contents': 'frame_0'
        }
        if self.button_toggle_averaging.isChecked():
            if self.button_display_subtraction.isChecked():
                meta_data['type'] = 'averaged and subtracted'
                meta_data['averages'] = self.spin_foreground_averages.value()
            else:
                meta_data['type'] = 'averaged'
                meta_data['averages'] = self.spin_foreground_averages.value()
        elif self.button_display_subtraction.isChecked():
            meta_data['type'] = 'subtracted'
            meta_data['averages'] = 1
        else:
            meta_data['type'] = 'single'
            meta_data['averages'] = 1
        file_path = Path(self.line_directory.text()).joinpath(
            datetime.now().strftime("%Y-%m-%d--%H-%M-%S") + '_' + self.line_prefix.text().strip().replace(' ',
                                                                                                          '_') + '.tiff')
        # file_path.mkdir(parents=True, exist_ok=True)

        tifffile.imwrite(str(file_path), self.latest_processed_frame, photometric='minisblack', metadata=meta_data)
        print("saved file as " + str(file_path))

    def __on_browse(self, event):
        startingDir = str(Path(r'C:\Users\User\Desktop\USERS'))
        destDir = QtWidgets.QFileDialog.getExistingDirectory(None,
                                                             'Choose Save Directory',
                                                             startingDir,
                                                             QtWidgets.QFileDialog.ShowDirsOnly)
        self.line_directory.setText(str(Path(destDir)))

    def closeEvent(self, event):
        self.close_event = event
        # time.sleep(0.1)
        self.lamp_controller.close()
        self.mutex.lock()
        self.camera_grabber.closing = True
        self.camera_grabber.running = False
        self.mutex.unlock()
        cv2.destroyAllWindows()

    def __on_quit_ready(self):
        print("Closing threads and exiting")
        self.camera_thread.quit()
        self.frame_processor_thread.quit()
        super(ArtieLabUI, self).closeEvent(self.close_event)
        sys.exit()


if __name__ == '__main__':
    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook


    def my_exception_hook(exctype, value, traceback):
        # Print the error and traceback
        print(exctype, value, traceback)
        # Call the normal Exception hook after
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)


    # Set the exception hook to our wrapping function
    sys.excepthook = my_exception_hook

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('fusion')
    window = ArtieLabUI()
    try:
        sys.exit(app.exec_())
    except:
        print("Exiting")
    print("test")
    print(app.exit())
