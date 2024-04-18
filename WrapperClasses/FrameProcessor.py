import numpy as np
import cv2
from PyQt5 import QtCore, QtWidgets, uic
from skimage import exposure


class FrameProcessor(QtCore.QObject):
    print("FrameProcessor: Initializing FrameProcessor...")
    IMAGE_PROCESSING_NONE = 0
    IMAGE_PROCESSING_PERCENTILE = 1
    IMAGE_PROCESSING_HISTEQ = 2
    IMAGE_PROCESSING_ADAPTEQ = 3
    frame_processed_signal = QtCore.pyqtSignal(np.ndarray, np.float64, tuple)
    diff_processed_signal = QtCore.pyqtSignal(np.ndarray, np.ndarray, np.float64, np.float64, tuple)
    mode = 0
    p_low = 0
    p_high = 100
    clip = 0.03
    subtracting = True
    background = None

    def update_settings(self, settings):
        '''
        :param dict settings: {mode, percentile_lower, percentile_upper, clip_limit}
        :return: None
        '''
        self.mode, self.p_low, self.p_high, self.clip = settings

    def set_mode(self, new_mode):
        if new_mode in [0, 1, 2, 3]:
            self.mode = new_mode
        else:
            print("FrameProcessor: Invalid mode")

    def set_percentile_lower(self, new_percentile):
        if new_percentile < self.p_high:
            self.p_low = new_percentile
        else:
            print("FrameProcessor: Please raise % max to avoid overlap")

    def set_percentile_upper(self, new_percentile):
        if new_percentile > self.p_low:
            self.p_high = new_percentile
        else:
            print("FrameProcessor: Please reduce lower % min to avoid overlap")

    def set_clip_limit(self, new_clip_limit):
        self.clip = new_clip_limit

    def __process_frame(self, frame_in):
        if self.subtracting and self.background is not None:
            frame_in = frame_in - self.background
            frame_in[frame_in < 0] = 0
        match self.mode:
            case self.IMAGE_PROCESSING_NONE:
                return frame_in
            case self.IMAGE_PROCESSING_PERCENTILE:
                px_low, px_high = np.percentile(frame_in, (self.p_low, self.p_high))
                return exposure.rescale_intensity(frame_in, in_range=(px_low, px_high))
            case self.IMAGE_PROCESSING_HISTEQ:
                return (exposure.equalize_hist(frame_in))
            case self.IMAGE_PROCESSING_ADAPTEQ:
                return (exposure.equalize_adapthist(frame_in / 65535, clip_limit=self.clip))
            case _:
                print("FrameProcessor: Unrecognized image processing mode")
                return frame_in

    @QtCore.pyqtSlot(np.ndarray)
    def process_frame(self, raw_frame):
        processed_frame = self.__process_frame(raw_frame)
        self.frame_processed_signal.emit(
            processed_frame,
            np.mean(raw_frame, axis=(0, 1)),
            exposure.histogram(processed_frame)
        )

    @QtCore.pyqtSlot(np.ndarray, int)
    def process_stack(self, raw_stack, intensity_index):
        mean_frame = np.mean(np.array(raw_stack), axis=0)
        processed_frame = self.__process_frame(mean_frame)
        self.frame_processed_signal.emit(
            processed_frame,
            np.mean(raw_stack[intensity_index], axis=(0, 1)),
            exposure.histogram(processed_frame)
        )

    @QtCore.pyqtSlot(np.ndarray, np.ndarray)
    def process_single_diff(self, frame_a, frame_b):
        diff_frame = np.abs(frame_a.astype(np.int32) - frame_b.astype(np.int32)).astype(np.uint16)
        processed_frame = self.__process_frame(diff_frame)
        self.diff_processed_signal.emit(
            diff_frame,
            processed_frame,
            np.mean(frame_a, axis=(0, 1)),
            np.mean(frame_b, axis=(0, 1)),
            exposure.histogram(processed_frame)

        )

    @QtCore.pyqtSlot(np.ndarray, np.ndarray, int)
    def process_diff_stack(self, frames_a, frames_b, intensity_index):
        mean_a = np.mean(np.array(frames_a), axis=0)
        mean_b = np.mean(np.array(frames_b), axis=0)
        meaned_diff = np.abs(mean_a.astype(np.int32) - mean_b.astype(np.int32)).astype(np.uint16)
        processed_frame = self.__process_frame(meaned_diff)
        self.diff_processed_signal.emit(
            meaned_diff,
            processed_frame,
            np.mean(frames_a[intensity_index], axis=(0, 1)),
            np.mean(frames_b[intensity_index], axis=(0, 1)),
            exposure.histogram(processed_frame)
        )
