import sys
from collections import deque
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import tifffile
from PyQt5 import uic
import cv2
from matplotlib.backends.backend_qt5agg import *
from matplotlib.figure import Figure

from WrapperClasses import *

import logging

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

        self.BUFFER_SIZE = 2
        self.frame_buffer = deque(maxlen=self.BUFFER_SIZE)
        self.item_semaphore = QtCore.QSemaphore(0)
        self.spaces_semaphore = QtCore.QSemaphore(self.BUFFER_SIZE)

        self.plot_timer = QtCore.QTimer(self)
        self.close_event = None
        self.get_background = False
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

        self.frame_processor = FrameProcessor(self)
        self.frame_processor_thread = QtCore.QThread()
        self.frame_processor.moveToThread(self.frame_processor_thread)
        self.frame_processor_thread.start()

        self.camera_grabber = CameraGrabber(self)
        self.camera_thread = QtCore.QThread()
        self.camera_grabber.moveToThread(self.camera_thread)
        self.camera_thread.start()

        self.height, self.width = self.camera_grabber.get_data_dims()

        self.flickering = False
        self.averaging = False
        self.paused = False

        self.__connect_signals()
        self.__prepare_views()
        self.__prepare_logging()

        self.frame_counter = 0
        self.latest_raw_frame = None
        self.latest_diff_frame_a = None
        self.latest_diff_frame_b = None
        self.latest_processed_frame = None

        self.raw_frame_stack = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.diff_frame_stack_a = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.diff_frame_stack_b = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        self.background_raw_stack = np.array([], dtype=np.uint16).reshape(0, self.height, self.width)
        QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_single_frame",
                                        QtCore.Qt.ConnectionType.QueuedConnection)
        QtCore.QMetaObject.invokeMethod(self.frame_processor, "start_processing",
                                        QtCore.Qt.ConnectionType.QueuedConnection)
        self.plot_timer.start(50)

    def __connect_signals(self):
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

        self.button_long_pol.clicked.connect(self.__on_long_pol)
        self.button_trans_pol.clicked.connect(self.__on_trans_pol)
        self.button_polar.clicked.connect(self.__on_polar)
        self.button_long_trans.clicked.connect(self.__on_long_trans)
        self.button_pure_long.clicked.connect(self.__on_pure_long)
        self.button_pure_trans.clicked.connect(self.__on_pure_trans)

        # Image Processing Controls
        self.combo_normalisation_selector.currentIndexChanged.connect(self.__on_image_processing_mode_change)
        self.spin_percentile_lower.valueChanged.connect(self.__on_image_processing_spin_box_change)
        self.spin_percentile_upper.valueChanged.connect(self.__on_image_processing_spin_box_change)
        self.spin_clip.valueChanged.connect(self.__on_image_processing_spin_box_change)

        # Averaging controls
        self.button_measure_background.clicked.connect(self.__on_get_new_background)
        self.button_toggle_averaging.clicked.connect(self.__on_averaging)
        self.spin_foreground_averages.valueChanged.connect(self.__on_average_changed)

        # Camera Controls
        self.combo_targetfps.currentIndexChanged.connect(self.__on_exposure_time_changed)
        self.combo_binning.currentIndexChanged.connect(self.__on_binning_mode_changed)
        self.button_pause_camera.clicked.connect(self.__on_pause_button)
        self.button_display_subtraction.clicked.connect(self.__on_show_subtraction)

        # Data Streams and Signals
        self.camera_grabber.camera_ready.connect(self.__on_camera_ready)
        self.camera_grabber.quit_ready.connect(self.__on_quit_ready)

        # saving GUI
        self.button_save_package.clicked.connect(self.__on_save)
        self.button_save_single.clicked.connect(self.__on_save_single)
        self.button_dir_browse.clicked.connect(self.__on_browse)

        self.plot_timer.timeout.connect(self.__update_plots)
        self.plot_timer.start(10)

        # TODO: Add planar subtraction
        # TODO: Add ROI
        # TODO: Add Draw Line feature
        # TODO: Add brightness normalisation
        # TODO: binning mode change handling#
        # TODO: Add plot of intensity
        # TODO: Add change the number of frames
        # TODO: Add histogram plot

    def __prepare_logging(self):
        self.log_text_box = QTextEditLogger(self)
        self.log_text_box.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s %(module)s - %(message)s', "%H:%M:%S"))
        logging.getLogger().addHandler(self.log_text_box)
        logging.getLogger().setLevel(logging.INFO)
        # TODO: this layout_logging might be under FRAME_LOGGING.layout or similar because I morphed the layout into a frame.
        self.layout_logging.addWidget(self.log_text_box.widget)

        fh = logging.FileHandler('ArtieLabUI.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                '%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'))
        logging.getLogger().addHandler(fh)

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
        self.hist_bins = []
        self.hist_data = []
        self.hist_line, = self.hist_ax.plot(self.hist_bins, self.hist_data, 'b-')
        self.hist_ax.set(title="Histogram as Seen", xlabel="Brightness", ylabel="Counts")

        self.blank_ax = self.plots_canvas.figure.add_subplot(313)
        self.frame_times = []
        self.old_frame_time = time.time()
        self.blank_line, = self.blank_ax.plot(self.frame_times, 'r-')
        self.blank_ax.set(title="Unused Plot", xlabel="", ylabel="")
        self.plots_canvas.figure.tight_layout(pad=0.1)
        self.layout_plot1.addWidget(self.plots_canvas)

    def __update_plots(self):
        length = len(self.frame_processor.intensities_y)
        self.intensity_line.set_xdata(list(range(min(length, 100))))
        self.intensity_line.set_ydata(self.frame_processor.intensities_y[-min(100, length):])
        self.intensity_ax.relim()
        self.intensity_ax.autoscale_view()

        self.hist_line.set_xdata(self.frame_processor.latest_hist_bins)
        self.hist_line.set_ydata(self.frame_processor.latest_hist_data)
        self.hist_ax.relim()
        self.hist_ax.autoscale_view()

        length = len(self.frame_times)
        self.blank_line.set_xdata(list(range(min(length, 100))))
        self.blank_line.set_ydata(self.frame_times[-min(100, length):])
        self.blank_ax.relim()
        self.blank_ax.autoscale_view()

        if self.frame_processor.latest_processed_frame.shape[0] != 1024:
            print("Resizing")
            cv2.imshow(
                self.stream_window,
                cv2.resize(
                    self.frame_processor.latest_processed_frame,
                    (1024, 1024)
                )
            )
        else:
            cv2.imshow(
                self.stream_window,
                self.frame_processor.latest_processed_frame,
            )

        cv2.waitKey(1)
        self.plots_canvas.draw()
        self.plots_canvas.flush_events()

    def __reset_pairs(self):
        self.enabled_led_pairs.update(
            {"left": False,
             "right": False,
             "up": False,
             "down": False})

    def __reset_led_spis(self):
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

    def __on_individual_led(self, state):
        logging.info("Individual LED being called")
        if not self.flickering:
            if self.__check_for_any_active_mode():
                self.button_long_pol.setChecked(False)
                self.button_trans_pol.setChecked(False)
                self.button_polar.setChecked(False)
                self.button_long_trans.setChecked(False)
                self.button_pure_long.setChecked(False)
                self.button_pure_trans.setChecked(False)
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
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

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
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

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
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

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
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

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
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

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

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(True)
            self.button_right_led1.setChecked(True)
            self.button_right_led2.setChecked(True)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
        else:
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

    def __prepare_for_flicker_mode(self):

        self.frame_processor.subtracting = False
        self.button_display_subtraction.setEnabled(False)
        # TODO: Add cv2 windows for raw frames

        self.flickering = True
        self.camera_grabber.running = False

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
        logging.info("ready received")
        if self.get_background:
            self.get_background = False
            frames = self.camera_grabber.grab_n_frames(self.spin_background_averages.value())
            self.frame_processor.background_raw_stack = frames
            self.frame_processor.background = np.mean(frames, axis=0).astype(np.uint16)
        if not self.paused:
            if self.flickering:
                QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_difference_mode",
                                                QtCore.Qt.ConnectionType.QueuedConnection)
                logging.info("Camera grabber starting difference mode")
            else:
                QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_single_frame",
                                                QtCore.Qt.ConnectionType.QueuedConnection)
                logging.info("Camera grabber starting normal mode")

    def __reset_after_flicker_mode(self):
        logging.info("Resetting after flicker mode")
        self.lamp_controller.stop_flicker()
        self.flickering = False
        self.camera_grabber.running = False

        self.button_display_subtraction.setEnabled(True)
        self.frame_processor.subtracting = self.button_display_subtraction.isChecked()
        # TODO: hide the CV2 windows for the raw pos/neg

        self.button_up_led1.setEnabled(True)
        self.button_up_led2.setEnabled(True)
        self.button_down_led1.setEnabled(True)
        self.button_down_led2.setEnabled(True)
        self.button_left_led1.setEnabled(True)
        self.button_left_led2.setEnabled(True)
        self.button_right_led1.setEnabled(True)
        self.button_right_led2.setEnabled(True)
        QtCore.QMetaObject.invokeMethod(self.camera_grabber, "start_live_single_frame",
                                        QtCore.Qt.ConnectionType.QueuedConnection)

    def __check_for_any_active_mode(self):
        return bool(
            self.button_long_pol.isChecked() +
            self.button_trans_pol.isChecked() +
            self.button_polar.isChecked() +
            self.button_long_trans.isChecked() +
            self.button_pure_long.isChecked() +
            self.button_pure_trans.isChecked()
        )

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

    # def __on_new_raw_frame(self, raw_frame):
    #
    #     self.latest_raw_frame = raw_frame
    #
    #     if self.averaging:
    #         if self.frame_counter % self.averages < len(self.raw_frame_stack):
    #             self.raw_frame_stack[self.frame_counter % self.averages] = raw_frame
    #         else:
    #             self.raw_frame_stack = np.append(self.raw_frame_stack, np.expand_dims(raw_frame, 0), axis=0)
    #         if len(self.raw_frame_stack) > self.averages:
    #             self.raw_frame_stack = self.raw_frame_stack[-self.averages:]
    #
    #         QtCore.QMetaObject.invokeMethod(self.frame_processor, "process_stack",
    #                                         QtCore.Qt.ConnectionType.QueuedConnection,
    #                                         QtCore.Q_ARG(np.ndarray, self.raw_frame_stack),
    #                                         QtCore.Q_ARG(int,
    #                                                      min(
    #                                                          self.frame_counter % self.averages,
    #                                                          self.raw_frame_stack.shape[0] - 1
    #                                                      )
    #                                                      )
    #                                         )
    #         self.frame_counter += 1
    #     else:
    #         QtCore.QMetaObject.invokeMethod(self.frame_processor, "process_frame",
    #                                         QtCore.Qt.ConnectionType.QueuedConnection,
    #                                         QtCore.Q_ARG(np.ndarray, raw_frame),
    #                                         )

    #
    # def __on_new_diff_frame(self, frame_a, frame_b):
    #
    #     if self.averaging:
    #         if self.frame_counter % self.averages < len(self.diff_frame_stack_a):
    #             self.diff_frame_stack_a[self.frame_counter % self.averages] = frame_a
    #             self.diff_frame_stack_b[self.frame_counter % self.averages] = frame_b
    #         else:
    #             self.diff_frame_stack_a = np.append(self.diff_frame_stack_a, np.expand_dims(frame_a, 0), axis=0)
    #             self.diff_frame_stack_b = np.append(self.diff_frame_stack_b, np.expand_dims(frame_b, 0), axis=0)
    #         if len(self.diff_frame_stack_a) > self.averages:
    #             self.diff_frame_stack_a = self.diff_frame_stack_a[-self.averages:]
    #             self.diff_frame_stack_b = self.diff_frame_stack_b[-self.averages:]
    #         self.frame_counter += 1
    #         QtCore.QMetaObject.invokeMethod(
    #             self.frame_processor, "process_diff_stack",
    #             QtCore.Qt.ConnectionType.QueuedConnection,
    #             QtCore.Q_ARG(np.ndarray, self.diff_frame_stack_a),
    #             QtCore.Q_ARG(np.ndarray, self.diff_frame_stack_b),
    #             QtCore.Q_ARG(int,
    #                          min(
    #                              self.frame_counter % self.averages,
    #                              self.diff_frame_stack_a.shape[0] - 1
    #                          )
    #                          )
    #         )
    #     else:
    #         self.latest_diff_frame_a = frame_a
    #         self.latest_diff_frame_b = frame_b
    #         QtCore.QMetaObject.invokeMethod(
    #             self.frame_processor,
    #             "process_single_diff",
    #             QtCore.Qt.ConnectionType.QueuedConnection,
    #             QtCore.Q_ARG(np.ndarray, frame_a),
    #             QtCore.Q_ARG(np.ndarray, frame_b)
    #         )
    #
    # def __on_processed_frame(self, processed_frame, intensity, hist):
    #     new_frame_time = time.time()
    #     self.frame_times.append(new_frame_time - self.old_frame_time)
    #     self.old_frame_time = new_frame_time
    #
    #     self.intensity_y.append(intensity)
    #     self.hist_data, self.hist_bins = hist
    #     self.latest_processed_frame = processed_frame
    #
    #     if not self.paused:
    #         if not self.mode_changed:
    #             QtCore.QMetaObject.invokeMethod(
    #                 self.camera_grabber,
    #                 "get_latest_single_frame",
    #                 QtCore.Qt.ConnectionType.QueuedConnection
    #             )
    #         else:
    #             if self.flickering:
    #                 self.lamp_controller.stop_flicker()
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "stop_acquisition",
    #                     QtCore.Qt.ConnectionType.QueuedConnection,
    #                     QtCore.Q_ARG(bool, False)
    #                 )
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "start_live_difference_mode",
    #                     QtCore.Qt.ConnectionType.QueuedConnection
    #                 )
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "get_latest_diff_frame",
    #                     QtCore.Qt.ConnectionType.QueuedConnection
    #                 )
    #             else:
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "get_latest_single_frame",
    #                     QtCore.Qt.ConnectionType.QueuedConnection
    #                 )
    #             self.mode_changed = False
    #
    # def __on_processed_diff(self, diff, diff_processed, intensity_a, intensity_b, hist):
    #
    #     new_frame_time = time.time()
    #     self.frame_times.append(new_frame_time - self.old_frame_time)
    #     self.old_frame_time = new_frame_time
    #
    #     self.intensity_y.append(intensity_a)
    #     self.intensity_y.append(intensity_b)
    #
    #     self.hist_data, self.hist_bins = hist
    #
    #     self.latest_diff_frame = diff
    #     self.latest_processed_frame = diff_processed
    #
    #     if not self.paused:
    #         if not self.mode_changed:
    #             QtCore.QMetaObject.invokeMethod(
    #                 self.camera_grabber,
    #                 "get_latest_diff_frame",
    #                 QtCore.Qt.ConnectionType.QueuedConnection
    #             )
    #         else:
    #             if not self.flickering:
    #                 self.__reset_after_flicker_mode()
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "stop_acquisition",
    #                     QtCore.Qt.ConnectionType.QueuedConnection,
    #                     QtCore.Q_ARG(bool, False)
    #                 )
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "start_live_single_frame",
    #                     QtCore.Qt.ConnectionType.QueuedConnection
    #                 )
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "get_latest_single_frame",
    #                     QtCore.Qt.ConnectionType.QueuedConnection
    #                 )
    #             else:
    #                 QtCore.QMetaObject.invokeMethod(
    #                     self.camera_grabber,
    #                     "get_latest_diff_frame",
    #                     QtCore.Qt.ConnectionType.QueuedConnection
    #                 )
    #             self.mode_changed = False

    def __on_get_new_background(self, ignored_event):
        # TODO: This doesn't call invokeMethod, nor does it wait for ready/closed from the camera.
        logging.info("Getting background")
        self.get_background = True
        self.mutex.lock()
        self.camera_grabber.running = False
        self.mutex.unlock()

    def __on_exposure_time_changed(self, exposure_time_idx):
        logging.info("Attempting to set exposure time to")
        self.mutex.lock()
        self.camera_grabber.waiting = True
        self.camera_grabber.running = False
        self.mutex.unlock()
        QtCore.QMetaObject.invokeMethod(
            self.camera_grabber, "set_exposure_time",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(int, self.camera_grabber.set_exposure_time(exposure_time_idx))
        )
        self.__on_camera_ready()

    def __on_binning_mode_changed(self, binning_idx):
        logging.info("Binning mode changes not implemented yet.")
        # TODO: Need to change the scale of the processed image to be super/subsampled to be 1024 square on screen
        pass

    def __on_average_changed(self, value):
        self.frame_processor.averages = value

    def __on_averaging(self, enabled):
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
            self.frame_processor.raw_frame_stack = None
            self.frame_processor.diff_frame_stack_a = None
            self.frame_processor.diff_frame_stack_b = None
            self.mutex.unlock()

    def __on_show_subtraction(self, subtracting):
        if subtracting:
            self.button_display_subtraction.setText("Ignore Background (F2)")
            self.frame_processor.subtracting = True
        else:
            self.button_display_subtraction.setText("Show Subtraction (F2)")
            self.frame_processor.subtracting = False

    def __on_pause_button(self, paused):
        self.paused = paused
        if paused:
            self.mutex.lock()
            self.camera_grabber.running = False
            self.mutex.unlock()
            self.button_pause_camera.setText("Unpause (F4)")
            if self.flickering:
                self.lamp_controller.pause_flicker(paused)
        else:
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
        logging.info("Saving to: " + str(file_path) + ' This takes time. Please be patient.')
        try:
            store = pd.HDFStore(str(file_path))
        except:
            logging.info(
                "Cannot save to this file/location: " + file_path + '. Does it exist? Do you have write permissions?')
            return

        if self.button_toggle_averaging.isChecked():
            if self.check_save_avg.isChecked():
                key = 'frame_avg'
                contents.append(key)
                store[key] = pd.DataFrame(self.frame_processor.latest_raw_frame)
            if self.check_save_stack.isChecked():
                for i in range(self.frame_processor.raw_frame_stack.shape[0]):
                    key = 'stack_' + str(i)
                    contents.append(key)
                    store[key] = pd.DataFrame(self.frame_processor.raw_frame_stack[i])
        else:
            if self.check_save_avg.isChecked():
                logging.info("Average not saved: measuring in single frame mode")
            if self.check_save_stack.isChecked():
                logging.info("Stack not saved: measuring in single frame mode")
            key = 'frame'
            contents.append(key)
            store[key] = pd.DataFrame(self.frame_processor.latest_raw_frame)
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
            store[key] = pd.DataFrame(self.frame_processor.latest_processed_frame)
        if self.check_save_background.isChecked():
            if self.frame_processor.background is not None:
                key = 'background_avg'
                contents.append(key)
                store[key] = pd.DataFrame(self.frame_processor.background)
            else:
                logging.info("Background not saved: no background measured")
        if self.check_save_bkg_stack.isChecked():
            if self.frame_processor.background is not None:
                for i in range(len(self.frame_processor.background_raw_stack)):
                    key = 'bkg_stack_' + str(i)
                    contents.append(key)
                    store[key] = pd.DataFrame(self.frame_processor.background_raw_stack[i])
            else:
                logging.info("Background stack not saved: no background measured")
        meta_data['contents'] = [contents]
        store['meta_data'] = pd.DataFrame(meta_data)
        store.close()
        logging.info("Saving done.")

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
        logging.info("Saved file as " + str(file_path))

    def __on_browse(self, event):
        starting_dir = str(Path(r'C:\Users\User\Desktop\USERS'))
        dest_dir = QtWidgets.QFileDialog.getExistingDirectory(
            None,
            'Choose Save Directory',
            starting_dir,
            QtWidgets.QFileDialog.ShowDirsOnly)
        self.line_directory.setText(str(Path(dest_dir)))

    def closeEvent(self, event):
        self.close_event = event
        # time.sleep(0.1)
        self.lamp_controller.close()
        self.mutex.lock()
        self.camera_grabber.closing = True
        self.camera_grabber.running = False
        self.frame_processor.running = False
        self.mutex.unlock()
        cv2.destroyAllWindows()

    def __on_quit_ready(self):
        logging.info("Closing threads and exiting")
        self.camera_thread.quit()
        self.frame_processor_thread.quit()
        super(ArtieLabUI, self).closeEvent(self.close_event)
        sys.exit()


if __name__ == '__main__':
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
    app.setStyle('fusion')
    window = ArtieLabUI()
    try:
        sys.exit(app.exec_())
    except:
        print("__main__: Exiting")
    print(app.exit())
