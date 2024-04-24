import logging
import time

import numpy as np
from PyQt5 import QtCore


class Producer(QtCore.QObject):
    is_running = False

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    @QtCore.pyqtSlot()
    def start(self):
        self.is_running = True
        logging.info("Producer: Starting.")
        while self.is_running:
            got = self.parent.spaces_semaphore.tryAcquire(1, 50)
            if got:
                frame = np.random.rand(100, 100)
                self.parent.frame_buffer.append(frame)
                logging.info(f"Producer: Frame produced with mean of : {np.mean(frame, axis=(0, 1))}", )
                self.parent.counter += 1
                self.parent.item_semaphore.release()
                time.sleep(50e-3)
        logging.info("Producer: Stopping.")


class Consumer(QtCore.QObject):
    frame_ready_signal = QtCore.pyqtSignal(np.ndarray)
    is_running = False

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    @QtCore.pyqtSlot()
    def start(self):
        self.is_running = True
        logging.info("Consumer: Starting.")
        while self.is_running:
            got = self.parent.item_semaphore.tryAcquire(1, 50)
            if got:
                frame = self.parent.frame_buffer.popleft()
                self.parent.counter -= 1
                self.parent.spaces_semaphore.release()
                time.sleep(55e-3)
                self.frame_ready_signal.emit(frame)
                logging.info(f"Consumer: Frame consumed with mean of : {np.mean(frame, axis=(0, 1))}")

        logging.info("Consumer: Stopping.")
