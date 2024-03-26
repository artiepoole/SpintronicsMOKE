from pylablib.devices import DCAM
from PyQt5 import QtCore, QtWidgets, uic
import numpy as np

class CameraGrabber(QtCore.QObject):
    EXPOSURE_TWENTY_FPS = 0
    EXPOSURE_THIRTY_FPS = 1
    frame_from_camera_ready_signal = QtCore.pyqtSignal(np.ndarray)
    cam = DCAM.DCAMCamera(idx=0)
    exposure_time = 0.05
    cam.set_attribute_value("EXPOSURE TIME", exposure_time)
    # self.print_to_queue(self.cam.info)
    cam.set_roi(hbin=2, vbin=2)
    running = False

    def start(self):
        self.cam.setup_acquisition()
        self.cam.start_acquisition()
        self.running = True
        while self.running:
            frame = self.cam.read_newest_image()
            if frame is not None:
                self.frame_from_camera_ready_signal.emit(frame)
        self.cam.stop_acquisition()

    def set_exposure_time(self, exposure_time_idx):
        self.cam.stop_acquisition()
        match exposure_time_idx:
            case self.EXPOSURE_TWENTY_FPS:
                self.cam.set_attribute_value("EXPOSURE TIME", 1/20)
                print(f"setting exposure time to {1/20}")
            case self.EXPOSURE_THIRTY_FPS:
                self.cam.set_attribute_value("EXPOSURE TIME", 1 / 30)
                print(f"setting exposure time to {1 / 30}")
            case _:
                print(f"Unexpected exposure time setting")
        self.start()


    def snap(self):
        self.frame_from_camera_ready_signal.emit(self.cam.snap())

    def get_detector_size(self):
        return self.cam.get_detector_size()


# class CameraLiveFeeder(QtCore.QObject):
#
#     cam = DCAM.DCAMCamera(idx=0)
#     cam.set_attribute_value("EXPOSURE TIME", 0.05)
#     # self.print_to_queue(self.cam.info)
#     cam.set_roi(hbin=2, vbin=2)
#     running = True
#     frame_from_camera_ready_signal = QtCore.pyqtSignal(np.ndarray)
#
#     def get_detector_size(self):
#         return self.cam.get_detector_size()
#
#     def start(self):
#         while self.running:
#             self.frame_from_camera_ready_signal.emit(self.cam.snap())
        