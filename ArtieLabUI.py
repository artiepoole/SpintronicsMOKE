from WrapperClasses.CameraGrabber import CameraGrabber
from WrapperClasses.LampController import LampController
from WrapperClasses.FrameProcessor import FrameProcessor

import cv2
from PyQt5 import QtCore, QtWidgets, uic
import sys
import time


class ArtieLabUI(QtWidgets.QMainWindow):
    def __init__(self):

        super(ArtieLabUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('res/ArtieLab.ui', self)  # Load the .ui file
        self.showMaximized()
        self.show()

        self.lamp_controller = LampController()
        self.lamp_controller.disable_all()
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False

        self.camera_thread = QtCore.QThread()
        self.camera_grabber = CameraGrabber()
        self.height, self.width = self.camera_grabber.get_detector_size()
        self.camera_grabber.moveToThread(self.camera_thread)

        self.frame_processor_thread = QtCore.QThread()
        self.frame_processor = FrameProcessor()
        self.frame_processor.moveToThread(self.frame_processor_thread)

        self.__connect_signals()
        self.__prepare_view()

        # TODO: IMPLEMENT SETTING EXPOSURE TIME TO THE SETTING FROM GUI ON START
        self.camera_grabber.start()

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
        self.button_left_led.toggled.connect(self.__on_left)
        self.button_right_led.toggled.connect(self.__on_right)
        self.button_up_led.toggled.connect(self.__on_up)
        self.button_down_led.toggled.connect(self.__on_down)
        self.button_long_pol.clicked.connect(self.__on_long_pol)
        self.button_trans_pol.clicked.connect(self.__on_trans_pol)
        self.button_polar.clicked.connect(self.__on_polar)
        self.button_long_trans.clicked.connect(self.__on_long_trans)
        self.button_pure_long.clicked.connect(self.__on_pure_long)
        self.button_pure_trans.clicked.connect(self.__on_pure_trans)
        self.combo_normalisation_selector.currentIndexChanged.connect(self.__on_image_processing_mode_change)
        self.spin_percentile_lower.valueChanged.connect(self.__on_image_processing_spin_box_change)
        self.spin_percentile_upper.valueChanged.connect(self.__on_image_processing_spin_box_change)
        self.spin_clip.valueChanged.connect(self.__on_image_processing_spin_box_change)
        # self.camera_grabber.frame_signal.connect(self.on_frame_signal)

        self.button_left_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')
        self.button_right_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')
        self.button_up_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')
        self.button_down_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')
        self.combo_targetfps.currentIndexChanged.connect(self.__on_exposure_time_changed)


        self.frame_processor.frame_processed_signal.connect(self.__on_processed_frame)
        self.camera_grabber.frame_from_camera_ready_signal.connect(self.__on_new_raw_frame)

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

    def __on_up(self, state):
        self.__up = state
        self.__update_controller()

    def __on_down(self, state):
        self.__down = state
        self.__update_controller()

    def __on_left(self, state):
        self.__left = state
        self.__update_controller()

    def __on_right(self, state):
        self.__right = state
        self.__update_controller()

    def __on_long_pol(self):
        self.__up = True
        self.__down = False
        self.__left = False
        self.__right = False
        self.button_up_led.setChecked(True)
        self.button_down_led.setChecked(False)
        self.button_left_led.setChecked(False)
        self.button_right_led.setChecked(False)
        self.__update_controller()

    def __on_trans_pol(self):
        self.__up = False
        self.__down = False
        self.__left = True
        self.__right = False
        self.button_up_led.setChecked(False)
        self.button_down_led.setChecked(False)
        self.button_left_led.setChecked(True)
        self.button_right_led.setChecked(False)
        self.__update_controller()

    def __on_polar(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print(
            "Sorry, this feature is not available. Can't select individual channels yet for some reason, only pairs.")
        self.__update_controller()

    def __on_long_trans(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print("Flashing Feature Not Implemented Yet....")
        self.__update_controller()

    def __on_pure_long(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print("Flashing Feature Not Implemented Yet....")
        self.__update_controller()

    def __on_pure_trans(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print("Flashing Feature Not Implemented Yet....")
        self.__update_controller()

    def __update_controller(self):
        self.lamp_controller.enable_assortment_pairs(self.__left, self.__right, self.__up, self.__down)

    def __on_new_raw_frame(self, raw_frame):
        self.frame_processor.process_frame(raw_frame)
        self.latest_raw_frame = raw_frame.copy()

    def __on_processed_frame(self, processed_frame):
        self.latest_processed_frame = processed_frame.copy()
        cv2.imshow(self.stream_window, processed_frame)
        cv2.waitKey(1)

    def __on_exposure_time_changed(self, exposure_time_idx):
        # print(exposure_time)
        self.camera_grabber.running = False
        self.camera_grabber.set_exposure_time(exposure_time_idx)

    def closeEvent(self, event):
        self.close()

    def close(self):

        self.lamp_controller.disable_all()
        # time.sleep(0.1)
        self.lamp_controller.close()

        self.camera_grabber.running = False
        self.camera_thread.exit()
        self.frame_processor_thread.exit()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    # # Back up the reference to the exceptionhook
    # sys._excepthook = sys.excepthook
    #
    #
    # def my_exception_hook(exctype, value, traceback):
    #     # Print the error and traceback
    #     print(exctype, value, traceback)
    #     # Call the normal Exception hook after
    #     sys._excepthook(exctype, value, traceback)
    #     sys.exit(1)
    #
    #
    # # Set the exception hook to our wrapping function
    # sys.excepthook = my_exception_hook

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('fusion')
    window = ArtieLabUI()
    app.exec_()
    app.exit()
