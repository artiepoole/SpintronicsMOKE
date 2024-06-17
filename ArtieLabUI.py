import sys
from collections import deque
from datetime import datetime
from pathlib import Path

import pandas as pd
import tifffile
from PyQt5 import uic
import cv2

import pyqtgraph as pg

from SweeperUIs import AnalyserSweepDialog, FieldSweepDialog
from WrapperClasses import *

import os.path
from os import listdir
from os.path import isfile, join
import sys

import numpy as np
from PyQt5 import QtCore, QtWidgets, uic, QtGui

import logging
from logging.handlers import RotatingFileHandler

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')


class ArtieLabUI(QtWidgets.QMainWindow):
    """
    The main GUI class for ArtieLab which encompasses all working functionality of the MOKE system.
    """
    def __init__(self):
        # Loads the UI file and sets it to full screen
        super(ArtieLabUI, self).__init__()
        uic.loadUi('res/ArtieLab.ui', self)
        self.__prepare_logging()
        right_monitor = QtWidgets.QDesktopWidget().screenGeometry(1)
        self.move(right_monitor.left(), right_monitor.top())

        # Define variables
        self.mutex = QtCore.QMutex()
        self.binning = 2
        self.BUFFER_SIZE = 2
        self.frame_buffer = deque(maxlen=self.BUFFER_SIZE)
        self.item_semaphore = QtCore.QSemaphore(0)
        self.spaces_semaphore = QtCore.QSemaphore(self.BUFFER_SIZE)
        self.plot_timer = QtCore.QTimer(self)
        self.magnetic_field_timer = QtCore.QTimer(self)
        self.image_timer = QtCore.QTimer(self)

        self.enabled_leds_spi = {
            "left1": False,
            "left2": False,
            "right1": False,
            "right2": False,
            "up1": False,
            "up2": False,
            "down1": False,
            "down2": False
        }

        self.LED_brightnesses = {
            "left1": 180,
            "left2": 180,
            "right1": 180,
            "right2": 180,
            "up1": 180,
            "up2": 180,
            "down1": 180,
            "down2": 180
        }

        self.enabled_led_pairs = {
            "left": False,
            "right": False,
            "up": False,
            "down": False
        }

        self.led_binary_enum = {
            "left1": 2,
            "left2": 1,
            "right1": 8,
            "right2": 4,
            "up1": 32,
            "up2": 16,
            "down1": 128,
            "down2": 64
        }

        self.led_id_enum = {
            "left1": 2,
            "left2": 1,
            "right1": 4,
            "right2": 3,
            "up1": 6,
            "up2": 5,
            "down1": 8,
            "down2": 7
        }

        # Create controller objects and threads
        self.lamp_controller = LampController(reset=True)
        self.magnet_controller = MagnetController()
        self.analyser_controller = AnalyserController()
        self.lamp_controller.disable_all()

        self.frame_processor = FrameProcessor(self)
        self.frame_processor_thread = QtCore.QThread()
        self.frame_processor.moveToThread(self.frame_processor_thread)
        self.frame_processor_thread.start()

        self.camera_grabber = CameraGrabber(self)
        self.camera_thread = QtCore.QThread()
        self.camera_grabber.moveToThread(self.camera_thread)
        self.camera_thread.start()

        self.height, self.width = self.camera_grabber.get_data_dims()

        # Program flow control
        self.flickering = False
        self.paused = False
        self.close_event = None
        self.get_background = False
        self.LED_control_all = False
        self.exposure_time = 0.05
        self.roi = (0, 0, 0, 0)
        self.latest_processed_frame = np.zeros((1024, 1024), dtype=np.uint16)
        self.recording = False
        self.recording_store = None
        self.recording_meta_data = None
        self.recording_contents = []
        self.recording_fields = []
        self.recording_angles = []

        self.__populate_calibration_combobox()

        self.__connect_signals()
        self.__prepare_views()

        # Actually display the window
        self.showMaximized()
        self.show()
        self.activateWindow()

        # Start image acquisition and update loops
        QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_single_frame",
                                        QtCore.Qt.ConnectionType.QueuedConnection)
        QtCore.QMetaObject.invokeMethod(self.frame_processor, "start_processing",
                                        QtCore.Qt.ConnectionType.QueuedConnection)
        self.start_time = time.time()
        # Assigned so that restarting these timers can use the same rate. All in ms
        self.image_timer_rate = 33  # Maxfps is 30 anyway
        self.plot_timer_rate = 200  # Doesn't need to be so often
        self.magnetic_field_timer_rate = 5  # max frequency of 10Hz detectable but this is performance limited.
        self.image_timer.start(self.image_timer_rate)
        self.plot_timer.start(self.plot_timer_rate)
        self.magnetic_field_timer.start(self.magnetic_field_timer_rate)
        self.button_long_pol.setChecked(True)
        self.__on_long_pol(True)
        self.__on_image_processing_mode_change(3)

    def __connect_signals(self):
        """
        Connects all signals between buttons and pyqt signals enabling communication between threads.
        :return None:
        """
        # LED controls
        self.button_left_led1.clicked.connect(self.__on_individual_led)
        self.button_right_led1.clicked.connect(self.__on_individual_led)
        self.button_up_led1.clicked.connect(self.__on_individual_led)
        self.button_down_led1.clicked.connect(self.__on_individual_led)
        self.button_left_led2.clicked.connect(self.__on_individual_led)
        self.button_right_led2.clicked.connect(self.__on_individual_led)
        self.button_up_led2.clicked.connect(self.__on_individual_led)
        self.button_down_led2.clicked.connect(self.__on_individual_led)
        self.button_leds_off.clicked.connect(self.__disable_all_leds)
        # LED Modes
        self.button_long_pol.clicked.connect(self.__on_long_pol)
        self.button_trans_pol.clicked.connect(self.__on_trans_pol)
        self.button_polar.clicked.connect(self.__on_polar)
        self.button_long_trans.clicked.connect(self.__on_long_trans)
        self.button_pure_long.clicked.connect(self.__on_pure_long)
        self.button_pure_trans.clicked.connect(self.__on_pure_trans)
        # LED Brightness
        self.button_LED_control_all.clicked.connect(self.__on_control_change)
        self.button_LED_reset_all.clicked.connect(self.__reset_brightness)
        self.scroll_LED_brightness.valueChanged.connect(self.__on_brightness_slider)
        self.scroll_blocker = QtCore.QSignalBlocker(self.scroll_LED_brightness)
        self.scroll_blocker.unblock()
        # TODO: Add brightness normalisation

        # Image Processing Controls
        self.combo_normalisation_selector.currentIndexChanged.connect(self.__on_image_processing_mode_change)
        self.spin_percentile_lower.editingFinished.connect(self.__on_image_processing_spin_box_change)
        self.spin_percentile_upper.editingFinished.connect(self.__on_image_processing_spin_box_change)
        self.spin_clip.editingFinished.connect(self.__on_image_processing_spin_box_change)
        self.button_ROI_select.clicked.connect(self.__select_roi)
        self.button_draw_line.clicked.connect(self.__draw_line)
        self.button_flip_line.clicked.connect(self.__on_flip_line)
        self.button_clear_roi.clicked.connect(self.__on_clear_roi)
        self.button_clear_line.clicked.connect(self.__on_clear_line)
        self.frame_processor.frame_processor_ready.connect(self.__on_frame_processor_ready)
        self.frame_processor.new_raw_frame_signal.connect(self.__on_frame_processor_new_raw_frame)
        self.frame_processor.new_processed_frame_signal.connect(self.__on_frame_processor_new_processed_frame)

        # Averaging controls
        self.button_measure_background.clicked.connect(self.__on_get_new_background)
        self.button_toggle_averaging.clicked.connect(self.__on_averaging)
        self.spin_foreground_averages.editingFinished.connect(self.__on_average_changed)

        # Camera Controls
        # self.combo_targetfps.currentIndexChanged.connect(self.__on_exposure_time_changed)
        self.spin_exposure_time.editingFinished.connect(self.__on_exposure_time_changed)
        self.combo_binning.currentIndexChanged.connect(self.__on_binning_mode_changed)
        self.button_pause_camera.clicked.connect(self.__on_pause_button)
        self.button_display_subtraction.clicked.connect(self.__on_show_subtraction)
        self.button_record.clicked.connect(self.__on_record_button)

        # Data Streams and Signals
        self.camera_grabber.camera_ready.connect(self.__on_camera_ready)
        self.camera_grabber.quit_ready.connect(self.__on_quit_ready)

        # saving GUI
        self.button_save_package.clicked.connect(self.__on_save)
        self.button_save_single.clicked.connect(self.__on_save_single)
        self.button_dir_browse.clicked.connect(self.__on_browse)

        # Magnetic Field Control

        self.combo_calib_file.currentIndexChanged.connect(self.__on_change_calibration)
        self.spin_mag_amplitude.editingFinished.connect(self.__on_change_field_amplitude)
        self.spin_mag_offset.editingFinished.connect(self.__on_change_field_offset)
        self.spin_mag_freq.editingFinished.connect(self.__on_change_mag_freq)

        self.button_zero_field.clicked.connect(self.__set_zero_field)
        self.button_DC_field.clicked.connect(self.__on_DC_field)
        self.button_AC_field.clicked.connect(self.__on_AC_field)
        self.button_invert_field.clicked.connect(self.__on_invert_field)

        # Analyser Controls
        self.button_move_analyser_back.clicked.connect(self.__rotate_analyser_backward)
        self.button_move_analyser_for.clicked.connect(self.__rotate_analyser_forward)
        self.button_minimise_analyser.clicked.connect(self.__on_find_minimum)

        # Special Function Controls
        self.button_analy_sweep.clicked.connect(self.__on_analyser_sweep)
        self.button_hyst_sweep.clicked.connect(self.__on_hysteresis_sweep)

        # Plot controls
        self.magnetic_field_timer.timeout.connect(self.__update_field_measurement)
        self.plot_timer.timeout.connect(self.__update_plots)
        self.image_timer.timeout.connect(self.__update_images)
        self.spin_number_of_points.editingFinished.connect(self.__on_change_plot_count)
        self.spin_mag_point_count.editingFinished.connect(self.__on_change_mag_plot_count)
        self.button_reset_plots.clicked.connect(self.__on_reset_plots)

    def __prepare_logging(self):
        """
        The multicolour logging box in the GUI and the log file are both set up here.
        :return None:
        """
        self.log_text_box = HTMLBasedColorLogger(self)

        # self.log_text_box.setFormatter(
        # logging.Formatter('%(asctime)s %(levelname)s %(module)s - %(message)s', "%H:%M:%S"))
        # logging.Formatter(CustomLoggingFormatter())
        logging.getLogger().addHandler(self.log_text_box)
        self.log_text_box.setFormatter(CustomLoggingFormatter())
        logging.getLogger().setLevel(logging.INFO)
        self.layout_logging.addWidget(self.log_text_box.widget)

        fh = RotatingFileHandler('ArtieLabUI.log',
                                 mode='a',
                                 maxBytes=1024 * 1024,
                                 backupCount=1,
                                 encoding=None,
                                 delay=False,
                                 errors=None
                                 )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                '%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'))
        logging.getLogger().addHandler(fh)

    def __prepare_views(self):
        """
        Prepares the empty camera view(s) and the graph axes
        :return:
        """
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

        self.plots_canvas = pg.GraphicsLayoutWidget()
        self.layout_plots.addWidget(self.plots_canvas)

        self.intensity_plot = self.plots_canvas.addPlot(
            row=0,
            col=0,
            title="Intensity",
            left="mean intensity",
            bottom="time (s)"
        )
        self.intensity_line = self.intensity_plot.plot(list(self.frame_processor.frame_times),
                                                       list(self.frame_processor.intensities_y), pen="k")
        self.hist_plot = self.plots_canvas.addPlot(
            row=1,
            col=0,
            title="Histogram as seen",
            left="counts",
            bottom="intensity"
        )
        self.hist_line = self.hist_plot.plot(self.frame_processor.latest_hist_bins,
                                             self.frame_processor.latest_hist_data, pen="k")
        self.roi_plot = self.plots_canvas.addPlot(
            row=2,
            col=0,
            title="ROI Intensity",
            left="mean intensity",
            bottom="time (s)"
        )
        self.roi_line = self.roi_plot.plot([], pen="k")
        self.roi_plot.hide()

        self.line_profile_plot = self.plots_canvas.addPlot(
            row=3,
            col=0,
            title="Line Profile",
            left="intensity",
            bottom="pixel index"
        )
        self.line_profile_line = self.line_profile_plot.plot([], [], pen="k")
        self.line_profile_plot.hide()

        self.mag_plot_canvas = pg.GraphicsLayoutWidget()
        self.layout_mag_plot.addWidget(self.mag_plot_canvas)

        self.mag_plot = self.mag_plot_canvas.addPlot(
            row=0,
            col=0,
            title="Magnetic Field",
            left="Field (mT)",
            bottom="time (s)"
        )
        self.mag_y = deque(maxlen=100)
        self.mag_t = deque(maxlen=100)
        self.mag_line = self.mag_plot.plot(self.mag_t, self.mag_y, pen="k")

    def __populate_calibration_combobox(self):
        """
        Loads the last used calibration file if possible else searches in the local Coil Calibrations directory else
        asks for user input.
        :return None: """
        # Magnetic field calibration stuff
        if os.path.isfile('res/last_calibration_location.txt'):
            with open('res/last_calibration_location.txt', 'r') as file:
                dir = file.readline()
                logging.info(f"Previous calibration file directory found.")
        elif os.path.isdir("Coil Calibrations\\"):
            dir = "Coil Calibrations\\"
            logging.warning("No calibration location found, trying: " + str(dir))
        else:
            logging.warning("Default calib file location not found. Asking for user input.")
            self.calib_file_dir = QtWidgets.QFileDialog.getExistingDirectory(
                None,
                'Choose Calibration File Directory',
                QtWidgets.QFileDialog.ShowDirsOnly
            )
        self.calib_file_dir = dir
        logging.info(f"Loading calibration files from {dir}")
        file_names = [f for f in listdir(dir) if isfile(join(dir, f)) and ".txt" in f]
        if file_names:
            self.calibration_dictionary = {i + 1: name for i, name in enumerate(file_names)}
            # +1 because 0 is "None"

            strings = [name.replace('.txt', '') for name in file_names]
            strings = [name.replace('_fit', '') for name in strings]
            self.combo_calib_file.clear()
            self.combo_calib_file.addItem("None")
            self.combo_calib_file.addItems(strings)
        else:
            logging.warning(" No magnet calibration files found.")

    def __update_plots(self):
        """
        Updates all the graph axes. Is called by a continuously running timer: self.plot_timer
        :return None:
        """
        # Sometimes, the update can be called between the appending to frame times and to intensities
        length = min([self.frame_processor.frame_times.__len__(), self.frame_processor.intensities_y.__len__()])
        if length > 0:
            self.intensity_line.setData(
                np.array(self.frame_processor.frame_times)[0:length] - np.min(self.frame_processor.frame_times),
                list(self.frame_processor.intensities_y)[0:length]
            )

        self.hist_line.setData(
            self.frame_processor.latest_hist_bins,
            self.frame_processor.latest_hist_data
        )

        # The time taken to measure a frame is calculated from the difference in frame times so must be 2 or more frames.
        if len(self.frame_processor.frame_times) > 1:
            n_to_avg = min(10, self.frame_processor.frame_times.__len__())
            self.line_FPSdisplay.setText(
                "%.3f" % (1 / (np.mean(np.diff(np.array(self.frame_processor.frame_times)[-n_to_avg:]))))
            )

        # After starting a ROI measurement, these deques will have different lengths so must take the last values
        # from the frame times until they are both fully populated.
        length = min([self.frame_processor.frame_times.__len__(), self.frame_processor.roi_int_y.__len__()])
        if sum(self.frame_processor.roi) > 0 and length > 0:
            self.roi_line.setData(
                np.array(self.frame_processor.frame_times)[-length:] - np.min(self.frame_processor.frame_times),
                list(self.frame_processor.roi_int_y)[-length:]
            )

        if self.frame_processor.line_coords is not None and len(self.frame_processor.latest_profile) > 0:
            self.line_profile_line.setData(
                self.frame_processor.latest_profile
            )

        self.mag_line.setData(self.mag_t, self.mag_y)

        if self.frame_processor.averaging:
            if self.flickering:
                progress = (self.frame_processor.diff_frame_stack_a.shape[0] /
                            self.spin_foreground_averages.value() * 100)
            else:
                progress = (self.frame_processor.raw_frame_stack.shape[0] /
                            self.spin_foreground_averages.value() * 100)
            self.bar_averaging.setValue(int(progress))
        else:
            self.bar_averaging.setValue(0)

    def __update_images(self):
        """
        Updates the CV2 display(s) with latest frame data.
        :return None:
        """
        frame = self.latest_processed_frame
        # frame = cv2.applyColorMap((frame//255).astype(np.uint8), cv2.COLORMAP_AUTUMN)
        if sum(self.frame_processor.roi) > 0:
            x, y, w, h = self.frame_processor.roi
            frame = cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                color=(0, 0, 0),
                thickness=2
            )
        if self.frame_processor.line_coords is not None:
            start, end = self.frame_processor.line_coords
            frame = cv2.arrowedLine(
                frame,
                start[::-1],
                end[::-1],
                color=(0, 0, 0),
                thickness=2
            )

        cv2.imshow(self.stream_window, frame)
        cv2.waitKey(1)

    def __update_field_measurement(self):
        """
        Updates the data used in the field plots ready for plotting. Is called by a continuously running timer:
        self.magnetic_field_timer. This updates more often than the plot is updated to improve performance
        :return None:
        """
        field, voltage = self.magnet_controller.get_current_amplitude()
        self.line_measured_field.setText("{:0.4f}".format(field))
        self.line_measured_voltage.setText("{:0.4f}".format(voltage))
        self.mag_y.append(field)
        self.mag_t.append(time.time() - self.start_time)

    def __on_reset_plots(self):
        """
        Resets all the data used to plot graphs that have a time/frame number axis.
        :return :
        """
        self.mutex.lock()
        self.frame_processor.frame_times = deque(maxlen=self.spin_number_of_points.value())
        self.frame_processor.intensities_y = deque(maxlen=self.spin_number_of_points.value())
        self.frame_processor.roi_int_y = deque(maxlen=self.spin_number_of_points.value())
        self.mag_y = deque(self.mag_y, maxlen=self.spin_mag_point_count.value())
        self.mag_t = deque(self.mag_t, maxlen=self.spin_mag_point_count.value())
        self.mutex.unlock()

    def __on_change_plot_count(self):
        """
        Changes the maxmimum length of the data used to plot the data on the right hand panel
        :param value: The new number of points
        :return:
        """
        value = self.spin_number_of_points.value()
        self.mutex.lock()
        self.frame_processor.frame_times = deque(self.frame_processor.frame_times, maxlen=value)
        self.frame_processor.intensities_y = deque(self.frame_processor.intensities_y, maxlen=value)
        self.frame_processor.roi_int_y = deque(self.frame_processor.roi_int_y, maxlen=value)
        self.mutex.unlock()

    def __on_change_mag_plot_count(self):
        """
        Changes the maxmimum length of the data used to plot the magnetic field vs time.
        :param value: The new number of points
        :return None:
        """
        value = self.spin_mag_point_count.value()
        self.mag_y = deque(self.mag_y, maxlen=value)
        self.mag_t = deque(self.mag_t, maxlen=value)

    def __reset_pairs(self):
        """
        Reset the local store of all enabled pairs of LEDs to False
        :return:
        """
        self.enabled_led_pairs.update(
            {"left": False,
             "right": False,
             "up": False,
             "down": False})

    def __reset_led_spis(self):
        """
        Reset the local store of all enabled individual LEDs to False
        :return:
        """
        self.enabled_leds_spi.update(
            {"left1": False,
             "left2": False,
             "right1": False,
             "right2": False,
             "up1": False,
             "up2": False,
             "down1": False,
             "down2": False}
        )

    def __reset_brightness(self):
        """
        Sets all the LED brightnesses to maximum
        :return:
        """
        self.LED_brightnesses.update(
            {"left1": 180,
             "left2": 180,
             "right1": 180,
             "right2": 180,
             "up1": 180,
             "up2": 180,
             "down1": 180,
             "down2": 180}
        )
        self.lamp_controller.set_all_brightness(180)

    def get_lighting_configuration(self):
        """
        Finds the current lighting state, basically which mode is enabled. If no mode is selected then it returns
        all enabled LEDs as a boolean.
        :return str/list: str of currently selected lighting mode or list of bools for each LED's enabled state.
        """
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

    def __on_image_processing_spin_box_change(self):
        """
        Updates the frame processor with all variables for the various image processing modes.
        :return None:
        """
        if self.spin_percentile_lower.value() < self.frame_processor.p_high:
            self.frame_processor.p_low = self.spin_percentile_lower.value()
        if self.spin_percentile_upper.value() > self.frame_processor.p_low:
            self.frame_processor.p_high = self.spin_percentile_upper.value()
        self.frame_processor.clip = self.spin_clip.value()

    def __on_image_processing_mode_change(self, mode):
        """
        Changes the currently used image processing mode based on the user selection.
        :param mode: 0 - none, 1 - basic (just divides by max), 2 - contrast stretching (percentile based stretching of
        histogram), 3 - whole image histogram equalisation to linearise the cumulative distribution 4 - local version
        of 3, very computationally demanding.
        :return None:
        """

        self.frame_processor.mode = mode
        match mode:
            case 0:  # None
                self.spin_percentile_lower.setEnabled(False)
                self.spin_percentile_upper.setEnabled(False)
                self.spin_clip.setEnabled(False)
            case 1:  # Basic
                self.spin_percentile_lower.setEnabled(False)
                self.spin_percentile_upper.setEnabled(False)
                self.spin_clip.setEnabled(False)
            case 2:  # Contrast stretching
                self.spin_percentile_lower.setEnabled(True)
                self.spin_percentile_upper.setEnabled(True)
                self.spin_clip.setEnabled(False)
                if self.spin_percentile_lower.value() < self.frame_processor.p_high:
                    self.frame_processor.p_low = self.spin_percentile_lower.value()
                if self.spin_percentile_upper.value() > self.frame_processor.p_low:
                    self.frame_processor.p_high = self.spin_percentile_upper.value()
                # This is contrast stretching and needs min and max percentiles
            case 3:  # Histrogram eq
                self.spin_percentile_lower.setEnabled(False)
                self.spin_percentile_upper.setEnabled(False)
                self.spin_clip.setEnabled(False)
                # this is auto hist and so no other settings are needed
            case 4:  # Adaptive eq
                self.spin_percentile_lower.setEnabled(False)
                self.spin_percentile_upper.setEnabled(False)
                self.spin_clip.setEnabled(True)
                self.frame_processor.clip = self.spin_clip.value()
                # this is Adaptive EQ and needs a clip limit
            case _:
                logging.error("Unsupported image processing mode")

    def __select_roi(self):
        """
        Asks the user to select a region of interest and then, if one is selected, updates the frame processor and plots
        such that the ROI based information is accessible.
        :return None:
        """
        logging.log(
            ATTENTION_LEVEL,
            "Select a ROI and then press SPACE or ENTER button! \n" +
            "   Cancel the selection process by pressing c button")
        self.image_timer.stop()
        # Seleting using the raw frame means that the scaling is handled automatically.
        roi = cv2.selectROI(self.stream_window, self.frame_processor.latest_processed_frame.astype(np.uint16),
                            showCrosshair=True, printNotice=False)
        if sum(roi) > 0:
            # self.frame_processor.roi = tuple([int(value * (2 / self.binning)) for value in roi])
            self.frame_processor.roi = roi
            self.roi_plot.show()
            logging.info("ROI set to " + str(roi))
            self.button_clear_roi.setEnabled(True)
            logging.info(f'Binning mode: {self.binning}, roi: {self.frame_processor.roi}')
        else:
            logging.info('Failed to set ROI')
            self.__on_clear_roi()

        self.image_timer.start(self.image_timer_rate)

    def __draw_line(self):
        """
        Asks the user to draw a rectangle containing the two ends of a line and then, if one is selected, updates the
        frame processor and plots such that the line profile is plotted for each frame.
        :return None:
        """
        logging.log(
            ATTENTION_LEVEL,
            "Select a bounding box and then press SPACE or ENTER button! \n" +
            "   Cancel the selection process by pressing c button")
        self.image_timer.stop()

        roi = cv2.selectROI(self.stream_window, self.frame_processor.latest_processed_frame.astype(np.uint16),
                            showCrosshair=True, printNotice=False)

        if sum(roi) > 0:
            x, y, w, h = roi
            self.frame_processor.line_coords = ((y, x), (y + h, x + w))
            self.line_profile_plot.show()
            self.button_clear_line.setEnabled(True)
            self.button_flip_line.setEnabled(True)
            logging.info(
                f'Binning mode: {self.binning}, line between: {self.frame_processor.line_coords[0]}' +
                f' and {self.frame_processor.line_coords[1]}')
        else:
            logging.warning('Failed to set line profile')
            self.__on_clear_line()
        self.image_timer.start(self.image_timer_rate)
        self.button_clear_line.setEnabled(True)
        # cv2.line

    def __on_flip_line(self):
        """
        Because the drawn line is taken from the corners of an ROI box, the line can be flipped such that the other
        pair of corners is used instead. This is that.
        :return None:
        """
        (x1, y1), (x2, y2) = self.frame_processor.line_coords
        self.frame_processor.line_coords = ((x1, y2), (x2, y1))
        logging.info(
            f'Flipped line. Line now between: {self.frame_processor.line_coords[0]}' +
            f' and {self.frame_processor.line_coords[1]}')

    def __on_clear_roi(self):
        """
        Clear the ROI and disable now-irrelevant plots buttons.
        :return None:
        """
        self.button_clear_roi.setEnabled(False)
        self.frame_processor.roi = (0, 0, 0, 0)
        self.frame_processor.roi_int_y = deque(maxlen=self.spin_number_of_points.value())
        self.roi_plot.hide()
        logging.info("Cleared ROI")

    def __on_clear_line(self):
        """
        Clear the points used for line profiling and disable now-irrelevant plots buttons.
        :return None:
        """
        self.button_clear_line.setEnabled(False)
        self.button_flip_line.setEnabled(False)
        self.line_profile_plot.hide()
        self.frame_processor.line_coords = None
        logging.info("Cleared Line")

    def __disable_all_leds(self):
        """
        Called when the user clicks the red cross button to disable all LEDs. Disables an enabled LED modes and turns
        all the lights off
        :return None:
        """
        logging.info("Disabling all LEDs")
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

    def __on_individual_led(self):
        """
        This is called whenever the user clicked to enable or disable an individual LED. It disables all active modes
        and enables the enabled LEDs.
        :return None:
        """
        logging.info("Individual LED being called")
        if not self.flickering:
            if self.check_for_any_active_LED_mode():
                self.button_long_pol.setChecked(False)
                self.button_trans_pol.setChecked(False)
                self.button_polar.setChecked(False)
                self.button_long_trans.setChecked(False)
                self.button_pure_long.setChecked(False)
                self.button_pure_trans.setChecked(False)
            self.__populate_spis()
            self.__update_controller_spi()

    def __populate_spis(self):
        self.enabled_leds_spi["up1"] = self.button_up_led1.isChecked()
        self.enabled_leds_spi["up2"] = self.button_up_led2.isChecked()
        self.enabled_leds_spi["down1"] = self.button_down_led1.isChecked()
        self.enabled_leds_spi["down2"] = self.button_down_led2.isChecked()
        self.enabled_leds_spi["left1"] = self.button_left_led1.isChecked()
        self.enabled_leds_spi["left2"] = self.button_left_led2.isChecked()
        self.enabled_leds_spi["right1"] = self.button_right_led1.isChecked()
        self.enabled_leds_spi["right2"] = self.button_right_led2.isChecked()

    def __on_long_pol(self, checked):
        """
        Called when the user clicks the long and pol button. Enables top pair.
        :param bool checked: The state of button_long_pol after clicking.
        :return None:
        """
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
            self.__populate_spis()
            self.__update_controller_pairs()
        else:
            if not self.check_for_any_active_LED_mode():
                self.__disable_all_leds()

    def __on_trans_pol(self, checked):
        """
        Called when the user clicks the trans and pol button. Enables left pair.
        :param bool checked: The state of button_trans_pol after clicking.
        :return None:
        """
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
            self.__populate_spis()
            self.__update_controller_pairs()
        else:
            if not self.check_for_any_active_LED_mode():
                self.__disable_all_leds()

    def __on_polar(self, checked):
        """
        Called when the user clicks the polar button. Enables top middle and bottom middle.
        Cancels longitudinal component.
        :param bool checked: The state of button_pol after clicking.
        :return None:
        """
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
            self.__populate_spis()
            self.__update_controller_spi()
        else:
            if not self.check_for_any_active_LED_mode():
                self.__disable_all_leds()

    def __on_long_trans(self, checked):
        """
        Called when the user clicks the long and trans and pol button. Flickers between the left and top pairs,
        taking a difference image.
        :param bool checked: The state of button_long_trans after clicking.
        :return None:
        """
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
            self.__populate_spis()
            self.lamp_controller.continuous_flicker(0, )
        else:
            if not self.check_for_any_active_LED_mode():
                self.__disable_all_leds()

    def __on_pure_long(self, checked):
        """
        Called when the user clicks the long and trans and pol button. Flickers between the top and bottom pairs,
        taking a difference image. This shows contrast in the longitudinal axis.
        :param bool checked: The state of button_pure_long after clicking.
        :return None:
        """
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
            self.__populate_spis()
        else:
            if not self.check_for_any_active_LED_mode():
                self.__disable_all_leds()

    def __on_pure_trans(self, checked):
        """
        Called when the user clicks the long and trans and pol button. Flickers between the left and right pairs,
        taking a difference image.
        :param bool checked: The state of button_pure_trans after clicking.
        :return None:
        """
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

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(True)
            self.button_right_led1.setChecked(True)
            self.button_right_led2.setChecked(True)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
            self.__populate_spis()
        else:
            if not self.check_for_any_active_LED_mode():
                self.__disable_all_leds()

    def __prepare_for_flicker_mode(self):
        """
        Is called whenever enabling long and trans and pol, pure long or pure trans measurements. It simply updates the
        GUI and some program flow parameters. It pauses the camera which will resume itself in a new mode in
        self.__on_camera_ready. The flicker lights and trigger setup is handled by
        self.lamp_controller.continuous_flicker(mode) in the button callbacks.
        :return None:
        """
        self.frame_processor.subtracting = False
        self.button_measure_background.setEnabled(False)
        self.button_display_subtraction.setEnabled(False)

        self.flickering = True
        self.camera_grabber.running = False
        QtCore.QMetaObject.invokeMethod(
            self.camera_grabber,
            "set_exposure_time",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(float, 0.05)
        )

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
        This allows for the collection of a background image and for the swapping between two camera operating modes.
        :return:
        """
        logging.debug("Ready received")
        if self.get_background:
            logging.info("Attempting to get background")
            self.get_background = False
            # Can't invoke method because of
            frames = self.camera_grabber.grab_n_frames(self.spin_background_averages.value())
            self.frame_processor.background_raw_stack = frames
            self.frame_processor.background = int_mean(frames, axis=0)
        if not self.paused:
            if self.flickering:
                QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_difference_mode",
                                                QtCore.Qt.ConnectionType.QueuedConnection)
                logging.debug("Camera grabber starting difference mode")
            else:
                QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_single_frame",
                                                QtCore.Qt.ConnectionType.QueuedConnection)
                logging.debug("Camera grabber starting normal mode")

    def __on_record_button(self):
        if self.button_record.isChecked():
            self.button_record.setText("Stop")
            logging.info("Preparing to record")
            pg.QtGui.QGuiApplication.processEvents()
            meta_data = {
                'description': "Video acquired using B204 MOKE owned by the Spintronics Group and University of "
                               "Nottingham using ArtieLab V0-2024.04.05.",
                'camera': 'Hamamatsu C11440',
                'sample': self.line_prefix.text(),
                'lighting configuration': [self.get_lighting_configuration()],
                'binning': self.combo_binning.currentText(),
                'lens': self.combo_lens.currentText(),
                'magnification': self.combo_magnification.currentText(),
                'exposure_time': self.spin_exposure_time.value(),
                'correction': self.line_correction.text(),
                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'analyser_postion': self.analyser_controller.position_in_degrees
            }
            match self.get_magnet_mode():
                case 0:
                    meta_data['magnet_mode'] = None
                case 1:  # DC
                    meta_data['magnet_mode'] = 'DC'
                    meta_data['mag_field'] = self.mag_y[-1]
                    meta_data['coil_calib'] = self.combo_calib_file.currentText()
                case 2:  # AC
                    meta_data['magnet_mode'] = 'AC'
                    meta_data['mag_field_amp'] = self.spin_mag_amplitude.value()
                    meta_data['mag_field_freq'] = self.spin_mag_freq.value()
                    meta_data['mag_field_offset'] = self.spin_mag_offset.value()
                    meta_data['coil_calib'] = self.combo_calib_file.currentText()
            if sum(self.frame_processor.roi) > 0:
                meta_data['roi'] = [self.frame_processor.roi]
            if self.frame_processor.line_coords is not None:
                meta_data['line_coords'] = [self.frame_processor.line_coords]
            file_path = Path(self.line_directory.text()).joinpath(
                datetime.now().strftime("%Y-%m-%d--%H-%M-%S") + '_' + self.line_prefix.text().strip().replace(' ',
                                                                                                              '_') + '_movie.h5')
            logging.info("Using " + str(file_path) + ' to store video')
            try:
                self.recording_store = pd.HDFStore(str(file_path))
            except:
                logging.info(
                    "Cannot save to this file/location: " + file_path + '. Does it exist? Do you have write permissions?')
                return
            self.recording_meta_data = meta_data
            if self.frame_processor.background is not None:
                key = 'background_avg'
                self.recording_contents.append(key)
                self.recording_store[key] = pd.DataFrame(self.frame_processor.background.astype(np.uint16))
            self.recording = True
            pass
        else:

            self.recording = False
            logging.info("Stopping recording and closing store.")
            self.button_record.setText("Record")
            self.recording_meta_data['contents'] = [self.recording_contents]
            self.recording_meta_data['fields'] = [self.recording_fields]
            self.recording_meta_data['angles'] = [self.recording_angles]
            self.recording_store['meta_data'] = pd.DataFrame(self.recording_meta_data)
            if "background_avg" in self.recording_contents:
                logging.info(f"Recording Stopped. Saved {len(self.recording_contents)} frames and background avg.")
            else:
                logging.info(f"Recording Stopped. Saved {len(self.recording_contents)} frames.")
            self.recording_store.close()
            self.recording_store = None
            self.recording_meta_data = None
            self.recording_contents = []
            self.recording_fields = []
            self.recording_angles = []
            self.spin_number_of_recorded_frames.setValue(0)

    def __on_frame_processor_new_raw_frame(self, frame):
        if self.recording:
            frame = frame.astype(np.uint16)
            frame_index = self.spin_number_of_recorded_frames.value()
            key = f"frame_{frame_index}"
            self.recording_fields.append(self.magnet_controller.get_current_amplitude()[0])
            self.recording_angles.append(self.analyser_controller.position_in_degrees)
            self.recording_contents.append(key)
            self.recording_store[key] = pd.DataFrame(frame)
            self.spin_number_of_recorded_frames.setValue(frame_index + 1)

    def __on_frame_processor_new_processed_frame(self, frame):
        self.latest_processed_frame = frame.astype(np.uint16)

    def __on_frame_processor_ready(self):
        """
        The frame processor gets paused in order to change the binning mode etc. This allows for the frame processor to
         get restarted with the correct shape empty arrays.
        :return None:
        """
        logging.debug("Frame processor ready received")
        self.mutex.lock()
        self.frame_processor.frame_counter = 0
        self.frame_processor.raw_frame_stack = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.frame_processor.diff_frame_stack_a = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.frame_processor.diff_frame_stack_b = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.frame_processor.background = None
        self.frame_processor.background_raw_stack = None
        self.mutex.unlock()
        QtCore.QMetaObject.invokeMethod(self.frame_processor, "start_processing",
                                        QtCore.Qt.ConnectionType.QueuedConnection)

    def __reset_after_flicker_mode(self):
        """
        This handles all the changes necessary to reset the GUI to running without the difference imaging modes.
        Is called whenever the GUI is changed from a difference mode into normal running mode.
        :return:
        """
        logging.info("Resetting after flicker mode")
        self.item_semaphore = QtCore.QSemaphore(0)
        self.spaces_semaphore = QtCore.QSemaphore(self.BUFFER_SIZE)
        self.frame_buffer = deque(maxlen=self.BUFFER_SIZE)

        self.mutex.lock()
        self.flickering = False
        self.camera_grabber.running = False
        self.mutex.unlock()
        self.button_measure_background.setEnabled(True)
        self.button_display_subtraction.setEnabled(True)
        self.frame_processor.subtracting = self.button_display_subtraction.isChecked()
        QtCore.QMetaObject.invokeMethod(
            self.camera_grabber,
            "set_exposure_time",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(float, self.exposure_time)
        )

        self.button_up_led1.setEnabled(True)
        self.button_up_led2.setEnabled(True)
        self.button_down_led1.setEnabled(True)
        self.button_down_led2.setEnabled(True)
        self.button_left_led1.setEnabled(True)
        self.button_left_led2.setEnabled(True)
        self.button_right_led1.setEnabled(True)
        self.button_right_led2.setEnabled(True)
        self.lamp_controller.stop_flicker()

    def check_for_any_active_LED_mode(self):
        """
        Checks if any of the LED mode buttons are active. Is used when the active LED mode is disabled to check whether
        all the other buttons are disabled.
        :return bool: True when any mode is active, False when all modes are disabled.
        """
        return bool(
            self.button_long_pol.isChecked() +
            self.button_trans_pol.isChecked() +
            self.button_polar.isChecked() +
            self.button_long_trans.isChecked() +
            self.button_pure_long.isChecked() +
            self.button_pure_trans.isChecked()
        )

    def get_magnet_mode(self):
        """
        Returns enum of magnet modes. Only used in saving at the moment.
        :return int: Sum of modes 1, 2, 4 corresponding to DC, AC, Decay respectively.
        """
        return (self.button_DC_field.isChecked() * 1 +
                self.button_AC_field.isChecked() * 2 +
                self.button_decay_field.isChecked() * 4)

    def __update_controller_pairs(self):
        """
        Sends the currently active pairs to the lamp controller to enable the correct LEDs in the non-SPI mode.
        :return None:
        """
        self.lamp_controller.enable_assortment_pairs(self.enabled_led_pairs)

    def __update_controller_spi(self):
        """
        Sends the currently active LEDs to the lamp controller to enable the correct LEDs in SPI mode.
        :return None:
        """
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

    def __on_control_change(self, control_all):
        """
        Called when button_LED_control_all is clicked to handle whether the brightness slider controls active LEDs or
        all LEDs
        :param control_all:
        :return None:
        """
        self.LED_control_all = control_all
        if self.LED_control_all:
            self.button_LED_control_all.setText("Control\nSelected")
        else:
            self.button_LED_control_all.setText("Control\nAll")
        self.__update_brightness(180 - self.scroll_LED_brightness.value())

    def __on_brightness_slider(self, value):
        """
        Updates the LED brightness when the slider is changed. Which LEDs are controlled is handled in __update_brightness
        :param int value: The new brightness value
        :return None:
        """
        value = 180 - value
        logging.info(f"Slider Value Changed to: {value}")
        self.__update_brightness(value)

    def __update_brightness_slider(self):
        """
        When selecting a new more or new LEDs, the brightness slider is moved to display the brightness LED value of the current selection.
        Does not currently update the values of the LEDs until the brightness slider is moved again.
        :return
        """
        if self.LED_control_all:
            keys = self.LED_brightnesses.keys()
        else:
            keys = [key for key, value in self.enabled_leds_spi.items() if value is True]
        if keys:
            logging.debug("active LED keys: " + str(keys))
            brightest_val = max([self.LED_brightnesses[key] for key in keys])
            logging.debug(f"Brightest val: {brightest_val}")
            self.scroll_blocker.reblock()
            self.scroll_LED_brightness.setValue(180 - brightest_val)
            self.scroll_blocker.unblock()
            # self.__update_brightness(brightest_val)

    def __update_brightness(self, value):
        """
        Sets the brightness of the appropriate LEDs based on the state of button_LED_control_all and the currently
        enabled LEDs.
        :param int value: New brightness value
        :return:
        """

        if self.LED_control_all:
            keys = self.LED_brightnesses.keys()
        else:
            keys = [key for key, value in self.enabled_leds_spi.items() if value is True]
        if self.LED_control_all:
            self.LED_brightnesses = {key: value for key in self.LED_brightnesses}
            self.lamp_controller.set_all_brightness(value)
        else:
            for key in keys:
                self.LED_brightnesses[key] = value
            self.lamp_controller.set_some_brightness([value] * len(keys), [self.led_id_enum[key] for key in keys])

    def __on_get_new_background(self):
        """
        Stops the camera and prepares the GUI to measure the background once the camera is ready. This is handled in
        self.__on_camera_ready
        :return None:
        """
        logging.info("Getting background")
        self.get_background = True
        self.mutex.lock()
        self.camera_grabber.running = False
        self.mutex.unlock()

    def __on_exposure_time_changed(self):
        """
        Stops the camera and stops the camera from emitting the ready signal at the end of the collection loop.
        The camera then emits ready after it processes the set_exposure_time call. And this leads to a
        self.__on_camera_ready call which restarts the camera.
        :return:
        """
        value = self.spin_exposure_time.value()
        if value != self.exposure_time:
            logging.info("Attempting to set exposure time to: %s", value)
            self.mutex.lock()
            self.camera_grabber.waiting = True
            self.camera_grabber.running = False
            self.mutex.unlock()
            QtCore.QMetaObject.invokeMethod(
                self.camera_grabber,
                "set_exposure_time",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(float, value)
            )
            self.exposure_time = value

    def __on_binning_mode_changed(self, binning_idx):
        """
        Stops the camera and stops the camera from emitting the ready signal at the end of the collection loop.
        The camera then emits ready after it processes the set_binning_mode call. And this leads to a
        self.__on_camera_ready call which restarts the camera.
        :return:
        """
        # TODO: this causes a memory issue, probably threading related.
        match binning_idx:
            case 0:
                value = 1
                dim = 2048
            case 1:
                value = 2
                dim = 1024
            case 2:
                value = 4
                dim = 512
            case _:
                logging.warning("Invalid Binning Mode!")
                return
        if value != self.binning:
            old_binning = self.binning
            self.binning = value
            logging.info(f"Attempting to set binning mode to {value}x{value}")
            self.mutex.lock()
            self.frame_processor.running = False
            self.camera_grabber.waiting = True
            self.camera_grabber.running = False
            self.mutex.unlock()
            QtCore.QMetaObject.invokeMethod(
                self.camera_grabber,
                "set_binning_mode",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(int, value)
            )
            self.mutex.lock()
            if sum(self.frame_processor.roi) > 0:
                self.frame_processor.roi = tuple(
                    [int(value * (old_binning / self.binning)) for value in self.frame_processor.roi])
                self.mutex.unlock()
                logging.info(f'Binning mode: {self.binning}, roi: {self.frame_processor.roi}')
            self.frame_processor.background = None
            self.frame_processor.resolution = dim
            self.frame_processor.latest_processed_frame = np.zeros((dim, dim), dtype=np.uint16)
            self.mutex.unlock()
            self.width = dim
            self.height = dim

    def __on_average_changed(self):
        """Is called when the number of averages is changed."""
        value = self.spin_foreground_averages.value()
        self.frame_processor.averages = value

    def __on_averaging(self, enabled):
        """
        Is called when button_toggle_averaging is clicked. This sets everyting up for averaging and gets the frame
        processor to start averaging.
        :param bool enabled: State of button_toggle_averaging after clicking.
        :return None:
        """
        if enabled:
            self.button_toggle_averaging.setText("Disable Averaging (F3)")
            logging.info("Averaging enabled")
            self.mutex.lock()
            self.frame_processor.averaging = self.spin_foreground_averages.value()
            self.frame_processor.averaging = True

            self.frame_processor.frame_counter = 0
            self.frame_processor.raw_frame_stack = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
            self.frame_processor.diff_frame_stack_a = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
            self.frame_processor.diff_frame_stack_b = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
            self.mutex.unlock()
        else:
            self.button_toggle_averaging.setText("Enable Averaging (F3)")
            logging.info("Averaging disabled")
            self.mutex.lock()
            self.frame_processor.averaging = False
            self.mutex.unlock()

    def __on_show_subtraction(self, subtracting):
        """
        Is called when button_display_subtraction is clicked. Toggles the frame processor between subtracting the
        background and not.
        :param bool subtracting: state of button_display_subtraction after clicking.
        :return None:
        """
        if subtracting:
            logging.info("Subtracting background")
            self.button_display_subtraction.setText("Ignore Background (F2)")
            self.frame_processor.subtracting = True
        else:
            logging.info("Ignoring background")
            self.button_display_subtraction.setText("Show Subtraction (F2)")
            self.frame_processor.subtracting = False

    def __on_pause_button(self, paused):
        """
        Called when button_pause_camera is clicked. Pauses/resumes the camera grabber to stop/start updating the frames.
        :param bool paused: state of button_pause_camera after clicking
        :return None:
        """
        self.paused = paused
        if paused:
            logging.info("Pausing camera")
            self.mutex.lock()
            self.camera_grabber.running = False
            self.mutex.unlock()
            self.button_pause_camera.setText("Unpause (F4)")
            if self.flickering:
                self.lamp_controller.pause_flicker(paused)
        else:
            logging.info("Resuming camera")
            self.button_pause_camera.setText("Pause (F4)")
            if self.flickering:
                self.lamp_controller.pause_flicker(paused)
                QtCore.QMetaObject.invokeMethod(
                    self.camera_grabber,
                    "start_live_difference_mode",
                    QtCore.Qt.ConnectionType.QueuedConnection
                )
            else:
                QtCore.QMetaObject.invokeMethod(
                    self.camera_grabber,
                    "start_live_single_frame",
                    QtCore.Qt.ConnectionType.QueuedConnection
                )

    def __on_change_calibration(self, index):
        """
        Is called whenever the user selects a new field coil calibration file in combo_calib_file.
        Updates the magnetic field control values and relevant GUI elements. If None is selected, it defaults to using
        uncalibrated voltage
        :param int index: New index after selection.
        :return None:
        """
        if index > 0:
            file_name = self.calibration_dictionary[index]
            calibration_array = np.loadtxt(os.path.join(self.calib_file_dir, file_name), delimiter=',', skiprows=1)
            logging.info("Setting calibration using file: " + str(file_name))
            self.magnet_controller.set_calibration(
                calibration_array[:, 0],
                calibration_array[:, 1],
                calibration_array[:, 2],
                calibration_array[:, 3]
            )
            max_field = np.amax(calibration_array[:, 1])
            self.label_amplitude.setText("Amplitude (mT)")
            self.label_offset.setText("Offset (mT)")
            self.label_measured_field.setText("Field (mT)")
            self.label_max_field.setText("Max Field (mT)")
            self.line_max_field.setText(str(round(max_field, 5)))
            self.spin_mag_amplitude.setValue(0.0)
            self.spin_mag_amplitude.setRange(-max_field, max_field)
            self.spin_mag_amplitude.setSingleStep(round(max_field / 200, 1))
            self.spin_mag_offset.setValue(0.0)
            self.spin_mag_offset.setRange(-max_field, max_field)
            self.spin_mag_offset.setSingleStep(round(max_field / 200, 1))
        else:
            defaults = np.linspace(-10, 10, 100)
            self.magnet_controller.set_calibration(
                defaults,
                defaults,
                defaults,
                defaults
            )
            self.label_amplitude.setText("Amplitude (V)")
            self.label_offset.setText("Offset (V)")
            self.label_measured_field.setText("Field (V)")
            self.label_max_field.setText("Max Field (V)")
            self.line_max_field.setText(str(10))
            self.spin_mag_amplitude.setValue(0.0)
            self.spin_mag_amplitude.setRange(-10, 10)
            self.spin_mag_amplitude.setSingleStep(0.1)
            self.spin_mag_offset.setValue(0.0)
            self.spin_mag_offset.setRange(-10, 10)
            self.spin_mag_offset.setSingleStep(0.1)

    def __on_change_field_amplitude(self):
        """
        Is called whenever the user selects a new field amplitude value and finished editing.
        Updates the magnetic field controller.
        :return None:
        """

        value = self.spin_mag_amplitude.value()
        if self.button_invert_field.isChecked():
            self.magnet_controller.set_target_field(-value)
        else:
            self.magnet_controller.set_target_field(value)

    def __on_change_field_offset(self):
        """
        Is called whenever the user selects a new field offset value and finished editing.
        Updates the magnetic field controller.
        :return None:
        """
        value = self.spin_mag_offset.value()
        if self.button_invert_field.isChecked():
            self.magnet_controller.set_target_offset(-value)
        else:
            self.magnet_controller.set_target_offset(value)

    def __on_change_mag_freq(self):
        """
        Is called whenever the user selects a new field frequency value and finished editing.
        Updates the magnetic field controller.
        :return None:
        """
        value = self.spin_mag_freq.value()
        self.magnet_controller.set_frequency(value)

    def __set_zero_field(self):
        """
        Is called whenever the user clicks zero field or deselcts all field modes.
        Updates the magnetic field controller to set the output amplitude to zero.
        :return None:
        """
        logging.info("Setting field output to zero")
        self.spin_mag_offset.setValue(0)
        self.spin_mag_amplitude.setValue(0)
        self.magnet_controller.reset_field()

    def __on_DC_field(self, enabled):
        """
        Called whenever the DC button is clicked in the magnetic field control group.
        When enabled, configures the magnetic field controller to supply DC magnetic fields.
        When disabled, does nothing unless there is no mode remaining.
        :param bool enabled: Whether the mode is enabled after the click.
        :return None:
        """
        if enabled:
            # self.button_DC_field.setChecked(True)
            self.button_AC_field.setChecked(False)
            if self.magnet_controller.mode == "AC":
                logging.info("Swapped from AC to DC field mode.")
            else:
                logging.info("Enabling DC field mode.")

            self.magnet_controller.mode = "DC"
            self.magnet_controller.update_output()
        else:
            if not self.button_AC_field.isChecked():
                logging.warning("There is no field mode selected.")
                self.magnet_controller.mode = None
                self.__set_zero_field()

    def __on_AC_field(self, enabled):
        """
        Called whenever the AC button is clicked in the magnetic field control group.
        When enabled, configures the magnetic field controller to supply AC magnetic fields.
        When disabled, does nothing unless there is no mode remaining.
        :param bool enabled: Whether the mode is enabled after the click.
        :return None:
        """
        if enabled:
            self.button_DC_field.setChecked(False)
            if self.magnet_controller.mode == "DC":
                logging.info("Swapped from DC to AC field mode.")
            else:
                logging.info("Enabling AC field mode.")
            self.magnet_controller.mode = "AC"
            self.magnet_controller.set_target_offset(self.spin_mag_offset.value())
            self.magnet_controller.set_frequency(self.spin_mag_freq.value())
            self.magnet_controller.update_output()
        else:
            if not self.button_DC_field.isChecked():
                logging.warning("There is no field mode selected.")
                self.magnet_controller.mode = None
                self.__set_zero_field()

    def __on_invert_field(self, inverted):
        """
        Called whenever the Invert button is clicked in the magnetic field control group.
        When enabled, Flips the sign of the output voltage to the magnet power supply in DC mode.
        :param bool enabled: Whether the mode is enabled after the click.
        :return None:
        """
        if inverted:
            logging.info("Inverting field")
            self.magnet_controller.set_target_field(-self.spin_mag_amplitude.value())
            self.magnet_controller.set_target_offset(-self.spin_mag_offset.value())
        else:
            logging.info("Un-inverting field")
            self.magnet_controller.set_target_field(self.spin_mag_amplitude.value())
            self.magnet_controller.set_target_offset(self.spin_mag_offset.value())

    def __rotate_analyser_forward(self):
        """
        Called whenever the right arrow is clicked in the Analyser Control group.
        Moves the analyser by number of degrees specified in the move (degrees) spinbox.
        :return None:
        """
        amount = self.spin_analyser_move_amount.value()
        self.analyser_controller.move(amount)
        self.line_current_angle.setText(str(round(self.analyser_controller.position_in_degrees, 3)))

    def __rotate_analyser_backward(self):
        """
        Called whenever the left arrow is clicked in the Analyser Control group.
        Moves the analyser by the negative of the number of degrees specified in the move (degrees) spinbox.
        :return None:
        """
        amount = -self.spin_analyser_move_amount.value()
        self.analyser_controller.move(amount)
        self.line_current_angle.setText(str(round(self.analyser_controller.position_in_degrees, 3)))

    def __on_find_minimum(self):
        """
        Called whenever the user clicks the Minimise Analyser button. This begins a subroutine in which the analyser
        controller changes the angle of the analyser and measures the mean intensity of singular raw frames. If an ROI
        is specified, the mean intensity within the ROI is used instead. The angle is adjusted to minimise the mean
        intensity.
        :return None:
        """
        if self.flickering:
            logging.error("Cannot run analyser while using difference mode imaging.")
            return
        if sum(self.enabled_leds_spi.values()) == 0:
            logging.error("Cannot run analyser without lights.")
            return
        logging.info("Pausing main GUI for usage with Analyser")
        self.mutex.lock()
        self.camera_grabber.waiting = True
        self.camera_grabber.running = False
        self.frame_processor.waiting = True
        self.frame_processor.running = False
        self.mutex.unlock()
        self.image_timer.stop()
        self.plot_timer.stop()
        self.magnetic_field_timer.stop()
        if sum(self.roi) > 0:
            self.analyser_controller.find_minimum(self.camera_grabber, roi=self.ROI)
        else:
            self.analyser_controller.find_minimum(self.camera_grabber)
        self.line_current_angle.setText(str(round(self.analyser_controller.position_in_degrees, 3)))

        self.image_timer.start(self.image_timer_rate)
        self.plot_timer.start(self.plot_timer_rate)
        self.magnetic_field_timer.start(self.magnetic_field_timer_rate)
        QtCore.QMetaObject.invokeMethod(
            self.camera_grabber,
            "set_exposure_time",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(float, self.exposure_time)
        )
        QtCore.QMetaObject.invokeMethod(self.frame_processor, "start_processing",
                                        QtCore.Qt.ConnectionType.QueuedConnection)
        # TODO: track the analyser position by saving to file
        # TODO: load last known analyser position on restart.

    def __on_hysteresis_sweep(self):
        """
        Called when the user clicks the hysteresis sweep button. Pauses main GUI function (is blocking) and
        Opens the hysteresis sweep tool window. This tool uses main GUI settings such as processing mode and ROI.
        :return None:
        """
        # TODO: got to here when adding documentation
        if self.flickering:
            logging.error("Cannot run analyser while using difference mode imaging.")
            return
        if sum(self.enabled_leds_spi.values()) == 0:
            logging.error("Cannot run analyser without lights.")
            return
        if self.combo_calib_file.currentIndex() == 0:
            logging.error("No calibration file selected.")
            return

        logging.info("Pausing main GUI for Field sweep dialog")
        self.mutex.lock()
        self.camera_grabber.waiting = True
        self.camera_grabber.running = False
        self.frame_processor.waiting = True
        self.frame_processor.running = False
        self.mutex.unlock()
        self.image_timer.stop()
        self.plot_timer.stop()
        self.magnetic_field_timer.stop()

        dialog = FieldSweepDialog(self)
        dialog.exec()
        logging.info("Resuming main GUI after Field sweep dialog")
        self.image_timer.start(self.image_timer_rate)
        self.plot_timer.start(self.plot_timer_rate)
        self.magnetic_field_timer.start(self.magnetic_field_timer_rate)
        QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_single_frame",
                                        QtCore.Qt.ConnectionType.QueuedConnection)
        QtCore.QMetaObject.invokeMethod(self.frame_processor, "start_processing",
                                        QtCore.Qt.ConnectionType.QueuedConnection)

    def __on_analyser_sweep(self):
        """
        Called when the user clicks the analyser sweep button. Pauses main GUI function (is blocking) and
        Opens the analyser sweep tool window. This tool uses main GUI settings such as processing mode and ROI.
        :return None:
        """
        if self.flickering:
            logging.error("Cannot run analyser while using difference mode imaging.")
            return
        if sum(self.enabled_leds_spi.values()) == 0:
            logging.error("Cannot run analyser without lights.")
            return

        logging.info("Pausing main GUI for analyser sweep dialog")
        self.mutex.lock()
        self.camera_grabber.waiting = True
        self.camera_grabber.running = False
        self.frame_processor.waiting = True
        self.frame_processor.running = False
        self.mutex.unlock()
        self.image_timer.stop()
        self.plot_timer.stop()
        self.magnetic_field_timer.stop()

        dialog = AnalyserSweepDialog(self)
        dialog.exec()
        logging.info("Resuming main GUI after analyser sweep dialog")
        self.image_timer.start(self.image_timer_rate)
        self.plot_timer.start(self.plot_timer_rate)
        self.magnetic_field_timer.start(self.magnetic_field_timer_rate)
        QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_single_frame",
                                        QtCore.Qt.ConnectionType.QueuedConnection)
        QtCore.QMetaObject.invokeMethod(self.frame_processor, "start_processing",
                                        QtCore.Qt.ConnectionType.QueuedConnection)

    def __on_save(self):
        """
        Called when the user clicks Save HDF5 Package. Assembles the metadata page, collects all data to be saved and
        adds each necessary frame to the store. If nothing is selected, it simply saves the latest frame.
        :return None:
        """
        meta_data = {
            'description': "Image acquired using B204 MOKE owned by the Spintronics Group and University of "
                           "Nottingham using ArtieLab V0-2024.04.05.",
            'camera': 'Hamamatsu C11440',
            'sample': self.line_prefix.text(),
            'lighting configuration': [self.get_lighting_configuration()],
            'binning': self.combo_binning.currentText(),
            'lens': self.combo_lens.currentText(),
            'magnification': self.combo_magnification.currentText(),
            'exposure_time': self.spin_exposure_time.value(),
            'correction': self.line_correction.text(),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'analyser_postion': self.analyser_controller.position_in_degrees
        }
        match self.get_magnet_mode():
            case 0:
                meta_data['magnet_mode'] = None
            case 1:  # DC
                meta_data['magnet_mode'] = 'DC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
            case 2:  # AC
                meta_data['magnet_mode'] = 'AC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['mag_field_amp'] = self.spin_mag_amplitude.value()
                meta_data['mag_field_freq'] = self.spin_mag_freq.value()
                meta_data['mag_field_offset'] = self.spin_mag_offset.value()
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
        if sum(self.frame_processor.roi) > 0:
            meta_data['roi'] = [self.frame_processor.roi]
        if self.frame_processor.line_coords is not None:
            meta_data['line_coords'] = [self.frame_processor.line_coords]
        contents = []
        file_path = Path(self.line_directory.text()).joinpath(
            datetime.now().strftime("%Y-%m-%d--%H-%M-%S") + '_' + self.line_prefix.text().strip().replace(' ',
                                                                                                          '_') + '.h5')
        logging.info("Saving to: " + str(file_path) + ' This takes time. Please be patient.')
        try:
            store = pd.HDFStore(str(file_path))
        except:
            logging.error(
                "Cannot save to this file/location: " + file_path + '. Does it exist? Do you have write permissions?')
            return

        if self.flickering:
            if self.button_toggle_averaging.isChecked():
                if self.check_save_avg.isChecked():
                    key = 'mean_diff_frame'
                    contents.append(key)
                    store[key] = pd.DataFrame(self.frame_processor.latest_mean_diff.astype(np.uint16))
                if self.check_save_stack.isChecked():
                    diff_stack_a = self.frame_processor.diff_frame_stack_a.astype(np.uint16)
                    diff_stack_b = self.frame_processor.diff_frame_stack_b.astype(np.uint16)
                    n_frames = diff_stack_a.shape[0]
                    # Due to the way the frames overwrite during averaging, this reorders the frames such that index 0
                    # is the oldest frame
                    last_index = (self.frame_processor.frame_counter + 1) % self.frame_processor.averages
                    indices = list(range(n_frames))
                    new_indices = indices[last_index:] + indices[:last_index]
                    diff_stack_a = diff_stack_a[new_indices]
                    diff_stack_b = diff_stack_b[new_indices]
                    for i in range(n_frames):
                        key_a = 'raw_stack_a_' + str(i)
                        key_b = 'raw_stack_b_' + str(i)
                        contents.append(key_a)
                        contents.append(key_b)
                        store[key_a] = pd.DataFrame(diff_stack_a[i])
                        store[key_b] = pd.DataFrame(diff_stack_b[i])
                    key = "stack_frame_times"
                    contents.append(key)
                    store[key] = pd.DataFrame(np.array(self.frame_processor.frame_times)[-n_frames:])
            else:
                if self.check_save_avg.isChecked():
                    logging.warning("Average not saved: measuring in single frame mode")
                if self.check_save_stack.isChecked():
                    logging.warning("Stack not saved: measuring in single frame mode")
                key = 'raw_diff_frame'
                contents.append(key)
                store[key] = pd.DataFrame(self.frame_processor.latest_diff_frame.astype(np.uint16))
                key = 'raw_frame_a'
                contents.append(key)
                store[key] = pd.DataFrame(self.frame_processor.latest_diff_frame_a.astype(np.uint16))
                key = 'raw_frame_b'
                contents.append(key)
                store[key] = pd.DataFrame(self.frame_processor.latest_diff_frame_b.astype(np.uint16))
        else:
            if self.button_toggle_averaging.isChecked():
                if self.check_save_avg.isChecked():
                    key = 'mean_frame'
                    contents.append(key)
                    store[key] = pd.DataFrame(self.frame_processor.latest_mean_frame.astype(np.uint16))
                if self.check_save_stack.isChecked():
                    raw_stack = self.frame_processor.raw_frame_stack.astype(np.uint16)
                    n_frames = raw_stack.shape[0]
                    # Due to the way the frames overwrite during averaging, this reorders the frames such that index 0
                    # is the oldest frame
                    last_index = (self.frame_processor.frame_counter + 1) % self.frame_processor.averages
                    indices = list(range(n_frames))
                    new_indices = indices[last_index:] + indices[:last_index]
                    raw_stack = raw_stack[new_indices]
                    for i in range(n_frames):
                        key = 'raw_stack_' + str(i)
                        contents.append(key)
                        store[key] = pd.DataFrame(raw_stack[i])
                    key = "stack_frame_times"
                    contents.append(key)
                    store[key] = pd.DataFrame(np.array(self.frame_processor.frame_times)[-n_frames:])
            else:
                if self.check_save_avg.isChecked():
                    logging.warning("Average not saved: measuring in single frame mode")
                if self.check_save_stack.isChecked():
                    logging.warning("Stack not saved: measuring in single frame mode")
                key = 'raw_frame'
                contents.append(key)
                store[key] = pd.DataFrame(self.frame_processor.latest_raw_frame.astype(np.uint16))

        if self.check_save_as_seen.isChecked():
            key = 'as_seen'
            if self.button_toggle_averaging.isChecked():
                key += f'_averaged({self.spin_foreground_averages.value()}) '
            if (self.button_display_subtraction.isChecked()
                    and not self.flickering
                    and self.frame_processor.background is not None):
                key += '_subtracted'
            if self.flickering:
                key += '_difference image'
            if key == 'as seen:':
                key += '_single frame'
            meta_data['normalisation'] = f'type: {self.combo_normalisation_selector.currentText()} ' + \
                                         f'lower: {self.spin_percentile_lower.value()} ' + \
                                         f'upper: {self.spin_percentile_upper.value()} ' + \
                                         f'clip: {self.spin_clip.value()}'
            contents.append(key)
            store[key] = pd.DataFrame(self.frame_processor.latest_processed_frame.astype(np.uint16))

        if self.check_save_background.isChecked():
            if self.frame_processor.background is not None:
                key = 'background_avg'
                contents.append(key)
                store[key] = pd.DataFrame(self.frame_processor.background.astype(np.uint16))
            else:
                logging.warning("Background not saved: no background measured")
        if self.check_save_bkg_stack.isChecked():
            if self.frame_processor.background is not None:
                for i in range(len(self.frame_processor.background_raw_stack)):
                    key = 'bkg_stack_' + str(i)
                    contents.append(key)
                    store[key] = pd.DataFrame(self.frame_processor.background_raw_stack[i].astype(np.uint16))
            else:
                logging.warning("Background stack not saved: no background measured")
        meta_data['contents'] = [contents]
        store['meta_data'] = pd.DataFrame(meta_data)
        store.close()
        logging.info("Saving done. Contents: " + str(contents))

    def __on_save_single(self):
        """
        Called when the user clicks Save as Seen. Saves the latest processed frame as a tiff tile with metadata.
        The file name sums up what processing was used to achieve this image.
        :return None:
        """
        # Assemble metadata
        meta_data = {
            'description': "Image acquired using B204 MOKE owned by the Spintronics Group and University of Nottingham using ArtieLab V0-2024.04.05.",
            'camera': 'Hamamatsu C11440',
            'sample': self.line_prefix.text(),
            'lighting configuration': self.get_lighting_configuration(),
            'binning': self.combo_binning.currentText(),
            'lens': self.combo_lens.currentText(),
            'magnification': self.combo_magnification.currentText(),
            'exposure_time': self.spin_exposure_time.value(),
            'correction': self.line_correction.text(),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'normalisation': f'type: {self.combo_normalisation_selector.currentText()} ' +
                             f'lower: {self.spin_percentile_lower.value()} ' +
                             f'upper: {self.spin_percentile_upper.value()} ' +
                             f'clip: {self.spin_clip.value()}',
            'contents': 'frame_as_seen',
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
        match self.get_magnet_mode():
            case 0:
                meta_data['magnet_mode'] = None
            case 1:  # DC
                meta_data['magnet_mode'] = 'DC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
            case 2:  # AC
                meta_data['magnet_mode'] = 'AC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['mag_field_amp'] = self.spin_mag_amplitude.value()
                meta_data['mag_field_freq'] = self.spin_mag_freq.value()
                meta_data['mag_field_offset'] = self.spin_mag_offset.value()
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
        if sum(self.frame_processor.roi) > 0:
            meta_data['roi'] = [self.frame_processor.roi]
        if self.frame_processor.line_coords is not None:
            meta_data['line_coords'] = [self.frame_processor.line_coords]

        file_path = Path(
            self.line_directory.text()).joinpath(
            datetime.now().strftime("%Y-%m-%d--%H-%M-%S") +
            '_' +
            self.line_prefix.text().strip().replace(' ', '_') +
            '.tiff')
        # file_path.mkdir(parents=True, exist_ok=True)
        try:
            tifffile.imwrite(
                str(file_path),
                self.frame_processor.latest_processed_frame.astype(np.uint16),
                photometric='minisblack',
                metadata=meta_data)
        except:
            logging.error(
                "Cannot save to this file/location: " + str(
                    file_path) + '. Does the folder exist? Do you have write permissions?')
            return
        logging.info("Saved file as " + str(file_path))

    def __on_browse(self):
        """
        Called when the user clicks the browse button in the saving control block.
        Allows the user to select a folder to save everything into.
        :return None:
        """
        starting_dir = str(Path(r'C:\Users\User\Desktop\USERS'))
        dest_dir = QtWidgets.QFileDialog.getExistingDirectory(
            None,
            'Choose Save Directory',
            starting_dir,
            QtWidgets.QFileDialog.ShowDirsOnly)
        if dest_dir:
            self.line_directory.setText(str(Path(dest_dir)))

    def closeEvent(self, event):
        """
        Called whenever the user clicks the red close button. postpones the close event so that it can be called when
        all threads/running processes are stopped.
        :param event:
        :return:
        """
        self.close_event = event
        event.ignore()
        self.image_timer.stop()
        self.plot_timer.stop()
        self.magnetic_field_timer.stop()
        # time.sleep(0.1)
        self.lamp_controller.close(reset=False)
        self.magnet_controller.close(reset=False)
        self.analyser_controller.close(reset=True)
        self.mutex.lock()
        self.camera_grabber.closing = True
        self.camera_grabber.running = False
        self.frame_processor.closing = True
        self.frame_processor.running = False
        self.mutex.unlock()


    def __on_quit_ready(self):
        """
        Is activated by the camera_grabber once it is finished closing. This finishes closing things and then incites
        the postponed close event.
        :return None:
        """
        cv2.destroyAllWindows()
        time.sleep(0.1)
        logging.info("Closing threads and exiting")
        self.camera_thread.quit()
        self.frame_processor_thread.quit()
        super(ArtieLabUI, self).closeEvent(self.close_event)
        sys.exit()


if __name__ == '__main__':
    """
    Runs the GUI and sets up error catching so that errors caused by other threads can sometimes be printed instead of 
    just giving an OS error.
    """
    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook


    def my_exception_hook(exctype, value, traceback):
        # Print the error and traceback
        print("__main__:", exctype, value, traceback)
        # Call the normal Exception hook after
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)


    # Set the exception hook to our wrapping function
    sys.excepthook = my_exception_hook

    app = QtWidgets.QApplication(sys.argv)

    app.setStyle('plastique')
    window = ArtieLabUI()
    try:
        sys.exit(app.exec_())
    except:
        print("__main__: Exiting")
    print(app.exit())
