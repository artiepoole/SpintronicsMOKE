from WrapperClasses.CameraGrabber import CameraGrabber
import cv2
from PyQt5 import QtCore, QtWidgets, uic
import sys

class MyGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(MyGUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('res/button.ui', self)  # Load the .ui file
        self.show()
        self.thread = QtCore.QThread()
        self.camera_grabber = CameraGrabber()
        self.height, self.width = self.camera_grabber.get_detector_size()
        self.camera_grabber.moveToThread(self.thread)
        # self.camera_grabber.frame_ready.connect(self.on_frame_ready)
        self.button_get_frame.clicked.connect(self.get_frame)
        self.camera_grabber.frame_signal.connect(self.on_frame_signal)
        self.frame = []

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

    def get_frame(self):
        print('asking for frame')
        frame = self.camera_grabber.snap()

    def on_frame_signal(self, frame):
        self.frame = frame
        self.__update_view()

    def __update_view(self):
        cv2.imshow(self.stream_window, self.frame)



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
    window = MyGUI()
    # window.resize(0, 0)
    try:
        sys.exit(app.exec_())
    except:
        print("Exiting")
