import sys
from collections import deque

import cv2
from PyQt5 import QtWidgets, uic

from SemaphoreWorkers import *


class QTextEditLogger(logging.Handler, QtCore.QObject):
    appendPlainText = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        super().__init__()
        QtCore.QObject.__init__(self)
        self.widget = QtWidgets.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)
        self.appendPlainText.connect(self.widget.appendPlainText)

    def emit(self, record):
        msg = self.format(record)
        self.appendPlainText.emit(msg)


class SemaphoreUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(SemaphoreUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('SemaphoreUI.ui', self)  # Load the .ui file
        self.show()
        self.activateWindow()

        self.BUFFER_SIZE = 2
        self.frame_buffer = deque(maxlen=self.BUFFER_SIZE)
        self.item_semaphore = QtCore.QSemaphore(0)
        self.spaces_semaphore = QtCore.QSemaphore(self.BUFFER_SIZE)
        self.counter = 0

        self.__prepare_logging()

        self.stream_window = 'HamamatsuView'
        cv2.namedWindow(
            self.stream_window)
        self.latest_frame = np.zeros((100, 100))

        self.producer_thread = QtCore.QThread()
        self.producer = Producer(self)
        self.producer.moveToThread(self.producer_thread)
        self.producer_thread.start()

        self.consumer_thread = QtCore.QThread()
        self.consumer = Consumer(self)
        self.consumer.moveToThread(self.consumer_thread)
        self.consumer_thread.start()

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.__update_plots)
        self.update_counter_timer = QtCore.QTimer(self)
        self.update_counter_timer.timeout.connect(self.__update_counter)

        self.button_startstop.clicked.connect(self.__on_start)
        self.consumer.frame_ready_signal.connect(self.__on_new_frame)
        self.running = False
        self.update_timer.start(100)
        self.update_counter_timer.start(0)

    def __prepare_logging(self):

        self.log_text_box = QTextEditLogger(self)
        self.log_text_box.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s %(module)s - %(message)s', "%H:%M:%S"))
        logging.getLogger().addHandler(self.log_text_box)
        logging.getLogger().setLevel(logging.INFO)
        self.layout_logger.addWidget(self.log_text_box.widget)

        fh = logging.FileHandler('SemaphoreUI.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                '%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'))
        logging.getLogger().addHandler(fh)

    def __on_start(self, starting):
        if starting:
            logging.info("Resetting Semaphores")
            # Reset semaphores
            self.frame_buffer.clear()
            self.item_semaphore = QtCore.QSemaphore(0)
            self.spaces_semaphore = QtCore.QSemaphore(self.BUFFER_SIZE)
            self.counter = 0
            self.button_startstop.setText("Stop")
            logging.info("Starting workers")
            QtCore.QMetaObject.invokeMethod(self.producer, "start", QtCore.Qt.QueuedConnection)
            QtCore.QMetaObject.invokeMethod(self.consumer, "start", QtCore.Qt.QueuedConnection)
        else:
            self.button_startstop.setText("Start")
            self.producer.is_running = False
            self.consumer.is_running = False

    def __update_plots(self):
        cv2.imshow(self.stream_window, self.latest_frame)

        cv2.waitKey(1)

    def __update_counter(self):
        self.line_counter.setText(str(self.counter))

    def __on_new_frame(self, frame):
        logging.info("SemaphoreUI: New Frame To Display")
        self.latest_frame = frame

    def closeEvent(self, event):
        logging.info("Closing threads and exiting.")
        self.consumer.is_running = False
        self.producer.is_running = False
        self.producer_thread.quit()
        self.consumer_thread.quit()
        super(SemaphoreUI, self).closeEvent(event)
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
    window = SemaphoreUI()
    try:
        sys.exit(app.exec_())
    except:
        print("__main__: Exiting")
    print(app.exit())

# logging.debug('damn, a bug')
# logging.info('something to remember')
# logging.warning('that\'s not right')
# logging.error('foobar')
