import time

from pylablib.devices import DCAM
from PyQt5 import QtCore, QtWidgets, uic
import numpy as np


class CameraGrabber(QtCore.QObject):
    EXPOSURE_TWENTY_FPS = 0
    EXPOSURE_THIRTY_FPS = 1
    frame_from_camera_ready_signal = QtCore.pyqtSignal(np.ndarray)
    difference_frame_ready = QtCore.pyqtSignal((np.ndarray, np.ndarray))
    frame_stack_from_camera_ready_signal = QtCore.pyqtSignal(np.ndarray)
    quit_ready = QtCore.pyqtSignal()
    cam = DCAM.DCAMCamera(idx=0)
    exposure_time = 0.05
    cam.set_trigger_mode('int')
    cam.set_attribute_value("EXPOSURE TIME", exposure_time)
    # self.print_to_queue(self.cam.info)
    cam.set_roi(hbin=2, vbin=2)
    running = False
    closing = False
    averages = 16
    averaging = False
    difference_mode = False
    mutex = QtCore.QMutex()

    def start_live_single_frame(self):
        self.set_trigger_mode('int')
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
        self.mutex.lock()
        self.running = True
        self.averaging = False
        self.difference_mode = False
        self.mutex.unlock()
        while self.running:
            frame = self.cam.read_newest_image()
            if frame is not None:
                self.frame_from_camera_ready_signal.emit(frame)
        self.cam.stop_acquisition()
        print("Camera stopped")
        if self.closing:
            print("Camera closing")
            self.cam.close()
            self.quit_ready.emit()

    def start_averaging(self):

        self.mutex.lock()
        self.running = True
        self.averaging = True
        self.difference_mode = False
        self.mutex.unlock()
        self.cam.set_trigger_mode('int')
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
        frames = []
        i = 0
        while self.running:
            frame = self.cam.read_newest_image()
            if frame is not None:
                if i % self.averages < len(frames):
                    frames[i % self.averages] = frame
                else:
                    frames.append(frame)
                if len(frames) > self.averages:
                    frames = frames[0:self.averages]
                self.frame_stack_from_camera_ready_signal.emit(np.array(frames))
                i = i + 1
        self.cam.stop_acquisition()
        print("Camera stopped")
        if self.closing:
            print("Camera closing")
            self.cam.close()
            self.quit_ready.emit()

    def start_difference_mode_single(self):
        self.mutex.lock()
        self.running = True
        self.averaging = False
        self.difference_mode = True
        self.mutex.unlock()
        need_pos = True
        self.set_trigger_mode()
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
        while self.running:
            frame = self.cam.read_newest_image()
            if frame is not None:
                if need_pos:
                    frame_a = frame.copy()
                    need_pos = False
                else:
                    frame_b = frame.copy()
                    need_pos = True
                    self.frame_from_camera_ready_signal.emit((frame_a, frame_b))
        self.cam.stop_acquisition()
        print("Camera stopped")
        if self.closing:
            print("Camera closing")
            self.cam.close()
            self.quit_ready.emit()

    def start_difference_mode_averaging(self):
        self.mutex.lock()
        self.running = True
        self.averaging = False
        self.difference_mode = True
        self.mutex.unlock()
        need_pos = True
        self.set_trigger_mode('ext')

    def set_exposure_time(self, exposure_time_idx):
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
        if self.averaging:
            self.start_averaging(self.averages)
        else:
            self.start_live_single_frame()

    def set_trigger_mode(self):
        if self.difference_mode:
            camera_grabber.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
            camera_grabber.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
            camera_grabber.cam.set_attribute_value('TRIGGER ACTIVE', 1)  # Edge
            camera_grabber.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
            camera_grabber.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
        else:
            self.cam.set_trigger_mode('int')
            print("setting trigger mode to int")

    def snap(self):
        self.frame_from_camera_ready_signal.emit(self.cam.snap())

    def get_detector_size(self):
        return self.cam.get_detector_size()

    def grab_n_frames(self, n_frames):
        frames = self.cam.grab(n_frames)
        return frames


if __name__ == "__main__":
    import cv2
    import skimage
    import numpy as np

    camera_grabber = CameraGrabber(None)


