import time

import numpy as np
from PyQt5 import QtCore
from pylablib.devices import DCAM
import logging
import sys


class CameraGrabber(QtCore.QObject):
    frame_ready_signal = QtCore.pyqtSignal(np.ndarray)
    difference_frame_ready = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    quit_ready = QtCore.pyqtSignal()
    camera_ready = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        logging.info("Initializing CameraGrabber...")
        try:
            self.cam = DCAM.DCAMCamera(idx=0)
        except DCAM.DCAMError:
            logging.error("Failed to connect to camera. Is it on or in use?")
            sys.exit(-1)

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

    @QtCore.pyqtSlot(float)
    def set_exposure_time(self, exposure_time):
        '''
        Resumes because is usually set via GUI
        :param float exposure_time:
        :return:
        '''
        logging.debug("Received exposure time:  %s", exposure_time)
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
        logging.debug(f"Received binning mode:  {binning}x{binning}")
        self.cam.set_roi(hbin=binning, vbin=binning)
        logging.info(f"Set binning mode binning mode:  {binning}x{binning}")
        logging.info("Camera ready")
        self.camera_ready.emit()

    def prepare_camera(self):
        '''
        Does not resume because is only used internally.
        :return:
        '''
        if self.difference_mode:
            logging.info("Setting camera trigger mode to external")
            self.cam.set_attribute_value('TRIGGER SOURCE', 2)  # External
            self.cam.set_attribute_value('TRIGGER MODE', 1)  # Normal (as opposed to "start")
            self.cam.set_attribute_value('TRIGGER ACTIVE', 3)  # SyncReadOut - Apparently this works but edge doesn't
            self.cam.set_attribute_value('TRIGGER POLARITY', 1)  # Falling
            self.cam.set_attribute_value('TRIGGER TIMES', 1)  # One frame per trigger signal
        else:
            logging.info("Setting camera trigger mode to internal")
            self.cam.set_trigger_mode('int')
        self.cam.setup_acquisition()
        self.cam.start_acquisition()

    def get_detector_size(self):
        """
        Get camera detector size (in pixels) as a tuple (width, height)
        :return size: size of detector in pixels (2048x2048 in our camera)
        :rtype: tuple[int,int]
        """
        return self.cam.get_detector_size()

    def get_data_dims(self):
        """
        Get camera frame size (in pixels) as a tuple (width, height)
        :return size: size of detector divided by binning amount.
        :rtype: tuple[int,int]|None
        """
        return self.cam.get_data_dimensions()

    def snap(self, info=False):
        """
        Grabs a single frame from the camera without needing to prepare the camera.
        :return frame: frame
        :rtype: np.ndarray[np.uint16, np.uint16] | None
        """
        if info:
            return self.cam.snap(return_info=True)
        else:
            return self.cam.snap()

    def snap_n(self, n_frames, info=False):
        """
        Grabs a stack of frames from the camera without needing to prepare the camera.
        :return frame: frame
        :rtype: np.ndarray[np.int32, np.int32, np.int32] | tuple[np.ndarray[np.int32, np.int32, np.int32], info] | None
        """
        if info:
            frames, info = self.cam.grab(n_frames, return_info=True)
            return np.array(frames), info
        else:
            return np.array(self.cam.grab(n_frames))


    def grab_n_frames(self, n_frames):
        """
        Grabs a stack of frames from the camera but requires preparing the camera.
        :return frame: frame
        :rtype: np.ndarray[np.int32, np.int32, np.int32] | None
        """
        prev_mode = self.difference_mode
        self.difference_mode = False
        self.prepare_camera()
        frames = np.array(self.cam.grab(n_frames))
        self.difference_mode = prev_mode
        return frames

    @QtCore.pyqtSlot()
    def start_live_single_frame(self):
        """
        Starts a continuous measurement loop of single frames, for use with constant lighting modes.
        Appends data to a buffer when the buffer has space. Buffer is held by the parent object, typically ArtieLab.
        :return:
        """
        self.mutex.lock()
        self.running = True
        self.waiting = False
        self.difference_mode = False
        self.mutex.unlock()
        self.prepare_camera()
        logging.info("Camera started in normal mode")
        while self.running:
            got_space = self.parent.spaces_semaphore.tryAcquire(1, 1)
            if got_space:
                frame = None
                while frame is None:
                    if self.cam.get_status() != "busy":
                        logging.error("Camera not busy")
                        self.parent.spaces_semaphore.release()
                        break
                    frame = self.cam.read_newest_image(return_info=True)
                    if frame is not None:
                        self.parent.frame_buffer.append((frame[0], frame[1]))
                        self.parent.item_semaphore.release()
        self.cam.stop_acquisition()
        logging.info("Camera stopped")
        if self.closing:
            logging.info("Camera closing")
            self.cam.close()
            self.quit_ready.emit()
            return
        if not self.waiting:
            logging.info("Camera ready")
            self.camera_ready.emit()

    @QtCore.pyqtSlot()
    def start_live_difference_mode(self):
        """
        Starts a continuous measurement loop of difference frames, for use with flickering lighting modes.
        Appends data to a buffer when the buffer has space. Buffer is held by the parent object, typically ArtieLab.
        :return:
        """
        self.mutex.lock()
        self.running = True
        self.waiting = False
        self.difference_mode = True
        self.mutex.unlock()

        self.prepare_camera()
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
                    if self.cam.get_status() != "busy":
                        logging.error("Camera not busy")
                        self.parent.spaces_semaphore.release()
                        continue
                    frame_data = self.cam.read_newest_image(return_info=True)
                    if frame_data is not None:
                        if self.cam.get_status() != "busy":
                            logging.error("Camera not busy")
                            continue
                        if frame_data[1].frame_index % 2 == 0:
                            frame_a = (frame_data[0], frame_data[1])
                    if not self.running:
                        logging.warning("stopping without frame_a")
                        self.parent.frame_buffer.append([])
                        self.parent.item_semaphore.release()
                        return
                while frame_b is None:
                    if self.cam.get_status() != "busy":
                        logging.error("Camera not busy")
                        self.parent.spaces_semaphore.release()
                        continue
                    frame_data = self.cam.read_newest_image(return_info=True)
                    if frame_data is not None:
                        if frame_data[1].frame_index % 2 == 1:
                            frame_b = (frame_data[0], frame_data[1])
                    if not self.running:
                        logging.warning("stopping without frame_b")
                        self.parent.frame_buffer.append([])
                        self.parent.item_semaphore.release()
                        return
                self.parent.frame_buffer.append(frame_a + frame_b)
                self.parent.item_semaphore.release()


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

    camera_grabber.prepare_camera()
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
    # camera_grabber.prepare_camera()
    # frame = camera_grabber.snap()
    # camera_grabber.cam.close()
    # cv2.imshow(
    #     '',
    #     cv2.putText(
    #         exposure.equalize_hist(frame),
    #         f'{np.mean(frame, axis=(0, 1))}',
    #         (50, 50),
    #         0,
    #         1,
    #         (255, 255, 255)
    #     )
    # )
    # cv2.waitKey(1)
    # rois = cv2.selectROIs('', cv2.putText(
    #     exposure.equalize_hist(frame),
    #     f'{np.mean(frame, axis=(0, 1))}',
    #     (50, 50),
    #     0,
    #     1,
    #     (255, 255, 255)
    #     ),
    #     showCrosshair=True,
    #     printNotice=True
    # )
    # print(rois)
