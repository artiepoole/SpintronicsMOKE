import time

from pylablib.devices import DCAM
from PyQt5 import QtCore, QtWidgets, uic
import numpy as np


class CameraGrabber(QtCore.QObject):
    EXPOSURE_TWENTY_FPS = 0
    EXPOSURE_THIRTY_FPS = 1
    frame_ready_signal = QtCore.pyqtSignal(np.ndarray)
    difference_frame_ready = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    # difference_frame_stack_ready = QtCore.pyqtSignal(tuple, int)
    # frame_stack_from_camera_ready_signal = QtCore.pyqtSignal(np.ndarray, int)
    quit_ready = QtCore.pyqtSignal()
    camera_ready = QtCore.pyqtSignal()
    cam = DCAM.DCAMCamera(idx=0)
    exposure_time = 0.05
    cam.set_trigger_mode('int')
    cam.set_attribute_value("EXPOSURE TIME", exposure_time)
    # self.print_to_queue(self.cam.info)
    binning = 2
    cam.set_roi(hbin=binning, vbin=binning)
    running = False
    closing = False
    difference_mode = False
    mutex = QtCore.QMutex()

    def set_exposure_time(self, exposure_time_idx):
        '''
        Resumes because is usually set via GUI
        :param exposure_time_idx:
        :return:
        '''
        self.cam.stop_acquisition()
        match exposure_time_idx:
            case self.EXPOSURE_TWENTY_FPS:
                self.cam.set_attribute_value("EXPOSURE TIME", 1 / 20)
                print(f"setting exposure time to {1 / 20}")
            case self.EXPOSURE_THIRTY_FPS:
                self.cam.set_attribute_value("EXPOSURE TIME", 1 / 30)
                print(f"setting exposure time to {1 / 30}")
            case _:
                print(f"Unexpected exposure time setting")
        if self.difference_mode:
            self.start_live_difference_mode()
        else:
            self.start_live_single_frame()

    def __prepare_camera(self):
        '''
        Does not resume because is only used internally.
        :return:
        '''
        if self.difference_mode:
            print("Setting camera trigger mode to external")
            self.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
            self.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
            self.cam.set_attribute_value('TRIGGER ACTIVE', 1)  # Edge
            self.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
            self.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
        else:
            print("Setting camera trigger mode to internal")
            self.cam.set_trigger_mode('int')

    def get_detector_size(self):
        return self.cam.get_detector_size()

    def get_data_dims(self):
        return self.cam.get_data_dimensions()

    def snap(self):
        self.frame_ready_signal.emit(self.cam.snap())

    def grab_n_frames(self, n_frames):
        frames = self.cam.grab(n_frames)
        return frames

    def start_live_single_frame(self):

        self.mutex.lock()
        self.running = True
        self.difference_mode = False
        self.mutex.unlock()

        self.__prepare_camera()
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
        print("Camera started in normal mode")
        while self.running:
            frame = self.cam.read_newest_image()
            if frame is not None:
                self.frame_ready_signal.emit(frame)
        self.cam.stop_acquisition()
        print("Camera stopped")
        if self.closing:
            print("Camera closing")
            self.cam.close()
            self.quit_ready.emit()
        print("Camera ready")
        self.camera_ready.emit()

    def start_live_difference_mode(self):

        self.mutex.lock()
        self.running = True
        self.difference_mode = True
        self.mutex.unlock()

        self.__prepare_camera()
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
        print("Camera started in live difference mode")
        while self.running:
            frame_a = None
            frame_b = None
            while frame_a is None:
                frame_a = self.cam.read_newest_image()
            while frame_b is None:
                frame_b = self.cam.read_newest_image()
            self.difference_frame_ready.emit(frame_a, frame_b)

        self.cam.stop_acquisition()
        print("Camera stopped")
        if self.closing:
            print("Camera closing")
            self.cam.close()
            self.quit_ready.emit()
        print("Camera ready")
        self.camera_ready.emit()

    # def start_averaging(self):
    #     self.mutex.lock()
    #     self.running = True
    #     self.averaging = True
    #     self.difference_mode = False
    #     self.mutex.unlock()
    #     self.set_trigger_mode()
    #     self.cam.setup_acquisition()
    #     self.cam.start_acquisition()
    #     frames = []
    #     i = 0
    #     while self.running:
    #         frame = self.cam.read_newest_image()
    #         if frame is not None:
    #             if i % self.averages < len(frames):
    #                 start_time = time.time()
    #                 frames[i % self.averages] = frame
    #                 print("assigning frame to index took: ", time.time() - start_time)
    #             else:
    #                 frames.append(frame)
    #                 print("appending frame")
    #             if len(frames) > self.averages:
    #                 frames = frames[0:self.averages]
    #                 print("Trimming frames")
    #             start_time = time.time()
    #             self.frame_stack_from_camera_ready_signal.emit(np.array(frames), i % self.averages)
    #             print("emitting array took: ", time.time() - start_time)
    #             i = i + 1
    #
    #     self.cam.stop_acquisition()
    #     print("Camera stopped")
    #     if self.closing:
    #         print("Camera closing")
    #         self.cam.close()
    #         self.quit_ready.emit()


if __name__ == "__main__":
    import cv2
    import skimage
    import numpy as np

    camera_grabber = CameraGrabber(None)

    # camera_grabber.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
    # camera_grabber.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
    # camera_grabber.cam.set_attribute_value('TRIGGER ACTIVE', 1)  # Edge
    # camera_grabber.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
    # camera_grabber.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
    print(camera_grabber.cam.get_data_dimensions())
