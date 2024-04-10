import time

from pylablib.devices import DCAM
from PyQt5 import QtCore, QtWidgets, uic
import numpy as np


class CameraGrabber(QtCore.QObject):
    EXPOSURE_TWENTY_FPS = 0
    EXPOSURE_THIRTY_FPS = 1
    frame_from_camera_ready_signal = QtCore.pyqtSignal(np.ndarray)
    difference_frame_ready = QtCore.pyqtSignal(tuple)
    difference_frame_stack_ready = QtCore.pyqtSignal(tuple, int)
    frame_stack_from_camera_ready_signal = QtCore.pyqtSignal(np.ndarray, int)
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

        self.mutex.lock()
        self.running = True
        self.averaging = False
        self.difference_mode = False
        self.mutex.unlock()
        self.set_trigger_mode()
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
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
        self.set_trigger_mode()
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
        frames = []
        i = 0
        while self.running:
            frame = self.cam.read_newest_image()
            if frame is not None:
                if i % self.averages < len(frames):
                    start_time = time.time()
                    frames[i % self.averages] = frame
                    print("assigning frame to index took: ", time.time() - start_time)
                else:
                    frames.append(frame)
                    print("appending frame")
                if len(frames) > self.averages:
                    frames = frames[0:self.averages]
                    print("Trimming frames")
                start_time = time.time()
                self.frame_stack_from_camera_ready_signal.emit(np.array(frames), i % self.averages)
                print("emitting array took: ", time.time() - start_time)
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
        self.set_trigger_mode()
        self.cam.setup_acquisition()
        self.cam.start_acquisition()

        while self.running:
            frame_a = None
            frame_b = None
            while frame_a is None:
                frame_a = self.cam.read_newest_image()
            while frame_b is None:
                frame_b = self.cam.read_newest_image()
            self.difference_frame_ready.emit((frame_a, frame_b))

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
        self.set_trigger_mode()
        self.cam.setup_acquisition()
        self.cam.start_acquisition()

        frames_a = []
        frames_b = []
        i = 0

        while self.running:
            frame_a = None
            frame_b = None
            while frame_a is None:
                frame_a = self.cam.read_newest_image()
            while frame_b is None:
                frame_b = self.cam.read_newest_image()

            if i % self.averages < len(frames_a):
                frames_a[i % self.averages] = frame_a
                frames_b[i % self.averages] = frame_b
            else:
                frames_a.append(frame_a)
                frames_b.append(frame_b)
            if len(frames_a) > self.averages:
                frames_a = frames_a[0:self.averages]
                frames_b = frames_b[0:self.averages]
            self.difference_frame_stack_ready.emit((np.array(frames_a), np.array(frames_b)), i % self.averages)
            i = i + 1

        self.cam.stop_acquisition()
        print("Camera stopped")
        if self.closing:
            print("Camera closing")
            self.cam.close()
            self.quit_ready.emit()

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
        self.cam.close()
        self.cam.open()
        if self.difference_mode:
            self.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
            self.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
            self.cam.set_attribute_value('TRIGGER ACTIVE', 1)  # Edge
            self.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
            self.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
            print("setting trigger mode to ext")
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

    # camera_grabber.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
    # camera_grabber.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
    # camera_grabber.cam.set_attribute_value('TRIGGER ACTIVE', 1)  # Edge
    # camera_grabber.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
    # camera_grabber.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
    print(camera_grabber.cam.get_data_dimensions())
