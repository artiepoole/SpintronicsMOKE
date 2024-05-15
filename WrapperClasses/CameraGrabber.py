import time

import numpy as np
from PyQt5 import QtCore
from pylablib.devices import DCAM
import logging


class CameraGrabber(QtCore.QObject):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        logging.info("CameraGrabber: Initializing CameraGrabber...")
        self.frame_ready_signal = QtCore.pyqtSignal(np.ndarray)
        self.difference_frame_ready = QtCore.pyqtSignal(np.ndarray, np.ndarray)
        self.quit_ready = QtCore.pyqtSignal()
        self.camera_ready = QtCore.pyqtSignal()
        self.cam = DCAM.DCAMCamera(idx=0)
        exposure_time = 0.05
        self.cam.set_trigger_mode('int')
        self.cam.set_attribute_value("EXPOSURE TIME", exposure_time)
        binning = 2
        self.cam.set_roi(hbin=binning, vbin=binning)
        self.running = False
        self.waiting = False
        self.closing = False
        self.difference_mode = False
        self.mutex = QtCore.QMutex()

    @QtCore.pyqtSlot(int)
    def set_exposure_time(self, exposure_time):
        '''
        Resumes because is usually set via GUI
        :param float exposure_time:
        :return:
        '''
        logging.info("Received exposure time:  %s", exposure_time)
        self.cam.set_attribute_value("EXPOSURE TIME", exposure_time)
        logging.info(f"setting exposure time to {exposure_time}")
        logging.info(f"Camera exposure time read as {self.cam.get_exposure()}")
        logging.info("Camera ready")
        self.camera_ready.emit()

    @QtCore.pyqtSlot(int)
    def set_binning_mode(self, binning=2):
        '''
        Resumes because is usually set via GUI
        :param float binning: binning x binning mode.
        :return:
        '''
        logging.info(f"Received binning mode:  {binning}x{binning}")
        self.cam.set_roi(hbin=binning, vbin=binning)
        logging.info(f"Set binning mode binning mode:  {binning}x{binning}")
        logging.info("Camera ready")
        self.camera_ready.emit()

    def _prepare_camera(self):
        '''
        Does not resume because is only used internally.
        :return:
        '''
        if self.difference_mode:
            logging.info("CameraGrabber: Setting camera trigger mode to external")
            self.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
            self.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
            self.cam.set_attribute_value('TRIGGER ACTIVE', 3)  # SyncReadOut - Apparently this works but edge doesn't
            self.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
            self.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
        else:
            logging.info("CameraGrabber: Setting camera trigger mode to internal")
            self.cam.set_trigger_mode('int')
        self.cam.setup_acquisition()
        self.cam.start_acquisition()

    def get_detector_size(self):
        return self.cam.get_detector_size()

    def get_data_dims(self):
        return self.cam.get_data_dimensions()

    def snap(self):
        return self.cam.snap()

    def grab_n_frames(self, n_frames):
        prev_mode = self.difference_mode
        self.difference_mode = False
        self._prepare_camera()
        frames = np.array(self.cam.grab(n_frames), dtype='int32')
        self.difference_mode = prev_mode
        return frames

    @QtCore.pyqtSlot()
    def start_live_single_frame(self):

        self.mutex.lock()
        self.running = True
        self.waiting = False
        self.difference_mode = False
        self.mutex.unlock()
        self._prepare_camera()
        logging.info("Camera started in normal mode")
        while self.running:
            got_space = self.parent.spaces_semaphore.tryAcquire(1, 1)
            if got_space:
                frame = None
                while frame is None:
                    frame = self.cam.read_newest_image(return_info=True)
                    if frame is not None:
                        self.parent.frame_buffer.append((frame[0].astype(np.int32), frame[1]))
                        self.parent.item_semaphore.release()
                        logging.debug("Got frame")
        self.cam.stop_acquisition()
        logging.info("Camera stopped")
        if self.closing:
            logging.info("Camera closing")
            self.cam.close()
            self.quit_ready.emit()
        if not self.waiting:
            logging.info("Camera ready")
            self.camera_ready.emit()

    @QtCore.pyqtSlot()
    def start_live_difference_mode(self):
        self.mutex.lock()
        self.running = True
        self.waiting = False
        self.difference_mode = True
        self.mutex.unlock()

        self._prepare_camera()
        logging.info("Camera started in live difference mode")
        self.diff_mode_acq_loop()
        self.cam.stop_acquisition()
        logging.info("Camera stopped")
        if self.closing:
            logging.info("Camera closing")
            self.cam.close()
            self.quit_ready.emit()
        if not self.waiting:
            self.camera_ready.emit()

    def diff_mode_acq_loop(self):
        """
        Acquisition loop necessary in order to return to break out of the loop and not emit bad data,
        while also exiting when the trigger mode is external. Gets stuck waiting for frames otherwise and never sees
        the "while running"
        :return:
        """
        while self.running:
            got_space = self.parent.spaces_semaphore.tryAcquire(1, 50)
            if got_space:
                frame_a = None
                frame_b = None
                while frame_a is None:
                    frame_data = self.cam.read_newest_image(return_info=True)
                    if frame_data is not None:
                        if frame_data[1].frame_index % 2 == 0:
                            frame_a = (frame_data[0].astype(np.int32), frame_data[1])
                            logging.debug("Got frame_a")
                    if not self.running:
                        logging.warning("stopping without frame_a")
                        self.parent.frame_buffer.append([])
                        self.parent.item_semaphore.release()
                        return
                while frame_b is None:
                    frame_data = self.cam.read_newest_image(return_info=True)
                    if frame_data is not None:
                        if frame_data[1].frame_index % 2 == 1:
                            frame_b = (frame_data[0].astype(np.int32), frame_data[1])
                            logging.debug("Got frame_b")
                    if not self.running:
                        logging.warning("stopping without frame_b")
                        self.parent.frame_buffer.append([])
                        self.parent.item_semaphore.release()
                        return
                self.parent.frame_buffer.append(frame_a + frame_b)
                self.parent.item_semaphore.release()
                logging.debug("Got difference frames")


if __name__ == "__main__":
    import numpy as np
    import cv2
    import skimage.exposure as exposure

    camera_grabber = CameraGrabber(None)

    # camera_grabber.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
    # camera_grabber.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
    # camera_grabber.cam.set_attribute_value('TRIGGER ACTIVE', 1)  # Edge
    # camera_grabber.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
    # camera_grabber.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
    camera_grabber._prepare_camera()
    while True:
        frame = camera_grabber.snap()
        cv2.imshow(
            '',
            cv2.putText(
                exposure.equalize_hist(frame),
                f'{np.mean(frame, axis=(0, 1))}',
                (50, 50),
                0,
                1,
                (255, 255, 255)
            )
        )
        key = cv2.waitKey(50)
        if key == 27:
            print('esc is pressed closing all windows')
            cv2.destroyAllWindows()
            break
