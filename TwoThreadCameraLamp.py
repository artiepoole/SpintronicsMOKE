from pylablib.devices import DCAM
import cv2
from PyQt5 import QtCore, QtWidgets, uic
import sys
import time
import threading
import queue

from WrapperClasses.LampController import LampController
from LEDDriverUI import LEDDriverUI

class DualView:

    def __init__(self):
        self.frame_queue = queue.Queue()
        self._is_running = True
        threading.Thread(target=self.start_GUI, daemon=True).start()
        self.connect_camera()
        threading.Thread(target=self.live_camera_wizard, daemon=True).start()
        self.update_view()


    def start_GUI(self):
        app = QtWidgets.QApplication(sys.argv)
        window = LEDDriverUI()
        app.exec_()

    def connect_camera(self):
        self.cam = DCAM.DCAMCamera(idx=0)
        self.cam.set_attribute_value("EXPOSURE TIME", 0.05)
        height, width = self.cam.get_detector_size()
        self.cam.set_roi(hbin=2, vbin=2)

        self.stream_window_name = 'HamamatsuView'
        window_width = width // 2
        window_height = height // 2
        cv2.namedWindow(
            self.stream_window_name,
            flags=(cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_FREERATIO))
        cv2.setWindowProperty(self.stream_window_name, cv2.WND_PROP_TOPMOST, 1.0)
        cv2.setWindowProperty(self.stream_window_name, cv2.WND_PROP_FULLSCREEN, 1.0)
        cv2.resizeWindow(
            self.stream_window_name,
            window_width,
            window_height)
        cv2.moveWindow(
            self.stream_window_name,
            0,
            0)

    def live_camera_wizard(self):
        while self._is_running:
            self.frame_queue.put(self.cam.snap())

    def closeEvent(self, event):
        self.LED_driver.close()

    def update_view(self):
        new_frame_time = 0
        prev_frame_time = 0
        fps = 1 / (new_frame_time - prev_frame_time)
        while self._is_running:
            while not self.frame_queue.empty():
                frame = self.frame_queue.get()
                cv2.imshow(self.stream_window_name, frame)
                k = cv2.waitKey(10)
                if k == 27:
                    self._is_running = False


if __name__ == '__main__':
    DualView()