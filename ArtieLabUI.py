from WrapperClasses.CameraGrabber import CameraGrabber
from WrapperClasses.LampController import LampController
from WrapperClasses.FrameProcessor import FrameProcessor

import cv2
from PyQt5 import QtCore, QtWidgets, uic
import sys
import numpy as np
import time


class ArtieLabUI(QtWidgets.QMainWindow):
    def __init__(self):

        super(ArtieLabUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('res/ArtieLab.ui', self)  # Load the .ui file
        right_monitor = QtWidgets.QDesktopWidget().screenGeometry(1)
        self.move(right_monitor.left(), right_monitor.top())
        self.showMaximized()
        self.show()
        self.activateWindow()

        self.lamp_controller = LampController()
        self.lamp_controller.disable_all()

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

        self.camera_thread = QtCore.QThread()
        self.camera_grabber = CameraGrabber()
        self.height, self.width = self.camera_grabber.get_detector_size()

        self.camera_grabber.moveToThread(self.camera_thread)

        self.frame_processor_thread = QtCore.QThread()
        self.frame_processor = FrameProcessor()
        self.frame_processor.moveToThread(self.frame_processor_thread)

        self.frame_processor.background = np.zeros((self.height, self.width))

        self.__connect_signals()
        self.__prepare_view()

        # TODO: IMPLEMENT SETTING EXPOSURE TIME TO THE SETTING FROM GUI ON START
        self.camera_grabber.start_live_single_frame()

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

    def __prepare_view(self):
        self.stream_window = 'HamamatsuView'
        window_width = self.width // 2
        window_height = self.height // 2
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
        self.button_toggle_averaging.toggled.connect(self.__on_averaging)
        self.spin_foreground_averages.valueChanged.connect(self.__on_average_changed)

        # Camera Controls
        self.combo_targetfps.currentIndexChanged.connect(self.__on_exposure_time_changed)

        # Data Streams and Signals
        self.frame_processor.frame_processed_signal.connect(self.__on_processed_frame)
        self.frame_processor.frame_stack_processed_signal.connect(self.__on_processed_stack)
        self.camera_grabber.frame_from_camera_ready_signal.connect(self.__on_new_raw_frame)
        self.camera_grabber.frame_stack_from_camera_ready_signal.connect(self.__on_new_raw_frame_stack)

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
        self.__reset_led_spis()
        self.__reset_pairs()

        self.button_up_led1.setChecked(False)
        self.button_up_led2.setChecked(False)
        self.button_down_led1.setChecked(False)
        self.button_down_led2.setChecked(False)
        self.button_left_led1.setChecked(False)
        self.button_left_led2.setChecked(False)
        self.button_right_led1.setChecked(False)
        self.button_right_led2.setChecked(False)

        self.button_long_pol.setChecked(False)
        self.button_trans_pol.setChecked(False)
        self.button_polar.setChecked(False)
        self.button_long_trans.setChecked(False)
        self.button_pure_long.setChecked(False)
        self.button_pure_trans.setChecked(False)

        self.__update_controller_pairs()

    def __on_individual_led(self, state):
        self.enabled_leds_spi["up1"] = self.button_up_led1.isChecked()
        self.enabled_leds_spi["up2"] = self.button_up_led2.isChecked()
        self.enabled_leds_spi["down1"] = self.button_down_led1.isChecked()
        self.enabled_leds_spi["down2"] = self.button_down_led2.isChecked()
        self.enabled_leds_spi["left1"] = self.button_left_led1.isChecked()
        self.enabled_leds_spi["left2"] = self.button_left_led2.isChecked()
        self.enabled_leds_spi["right1"] = self.button_right_led1.isChecked()
        self.enabled_leds_spi["right2"] = self.button_right_led2.isChecked()
        self.__update_controller_spi()

    def __on_long_pol(self):
        if self.button_long_pol.isChecked():
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
            self.__disable_all_leds()

    def __on_trans_pol(self):
        if self.button_trans_pol.isChecked():
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
            self.__disable_all_leds()

    def __on_polar(self):
        if self.button_polar.isChecked():
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
            self.__disable_all_leds()

    def __on_long_trans(self):
        print("Flashing Feature Not Implemented Yet....")
        if self.button_long_trans.isChecked():
            self.__disable_all_leds()
            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_pure_long.setChecked(False)
            self.button_pure_trans.setChecked(False)
        else:
            self.__disable_all_leds()

    def __on_pure_long(self):
        if self.button_pure_long.isChecked():
            print("Flashing Feature Not Implemented Yet....")
            self.__disable_all_leds()
            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_long_trans.setChecked(False)
            self.button_pure_trans.setChecked(False)
        else:
            self.__disable_all_leds()

    def __on_pure_trans(self):
        if self.button_pure_trans.isChecked():
            self.__disable_all_leds()
            print("Flashing Feature Not Implemented Yet....")
            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.button_long_trans.setChecked(False)
            self.button_pure_long.setChecked(False)
        else:
            self.__disable_all_leds()

    def __update_controller_pairs(self):
        self.lamp_controller.enable_assortment_pairs(self.enabled_led_pairs)

    def __update_controller_spi(self):
        # I assumed the numbering would go outside then inside but it goes inside then outside
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
        start_time = time.time()
        self.frame_processor.process_frame(raw_frame)
        print("time to send single frame to processor = ", time.time() - start_time)
        # self.latest_raw_frame = raw_frame.copy()

    def __on_new_raw_frame_stack(self, raw_frames):
        self.frame_processor.process_stack(raw_frames)
        self.latest_frame_stack = raw_frames.copy()

    def __on_processed_frame(self, processed_frame):

        self.latest_processed_frame = processed_frame
        cv2.imshow(self.stream_window, processed_frame)
        cv2.waitKey(1)


    def __on_processed_stack(self, averaged, processed):
        self.latest_raw_frame = averaged
        self.latest_processed_frame = processed
        cv2.imshow(self.stream_window, processed)
        cv2.waitKey(1)

    def __on_get_new_background(self, ignored_event):
        self.camera_grabber.running = False
        frames = self.camera_grabber.grab_n_frames(self.spin_background_averages.value())
        self.background_raw_Stack = frames.copy()
        self.background_averaged = np.mean(np.array(frames), axis=0)
        self.frame_processor.background = self.background_averaged
        if self.camera_grabber.averaging:
            self.camera_grabber.averaging = self.spin_foreground_averages.value()
            self.camera_grabber.start_averaging()
        else:
            self.camera_grabber.start_live_single_frame()

    def __on_exposure_time_changed(self, exposure_time_idx):
        self.camera_grabber.running = False
        self.camera_grabber.set_exposure_time(exposure_time_idx)

    def __on_average_changed(self, value):
        self.camera_grabber.averages = value

    def __on_averaging(self, enabled):
        if enabled:
            print("averaging enabled")
            self.averaging = True
            self.camera_grabber.running = False
            self.camera_grabber.averaging = self.spin_foreground_averages.value()
            self.camera_grabber.start_averaging()
        else:
            self.averaging = False
            print("averaging disabled")
            self.camera_grabber.start_live_single_frame()

    def closeEvent(self, event):
        self.close()
        super(ArtieLabUI, self).closeEvent(event)

    def close(self):

        self.lamp_controller.disable_all()
        # time.sleep(0.1)
        self.lamp_controller.close()

        self.camera_grabber.running = False
        self.camera_thread.exit()
        self.frame_processor_thread.exit()
        cv2.destroyAllWindows()


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
