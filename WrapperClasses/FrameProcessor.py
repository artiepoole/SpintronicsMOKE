import numpy as np
import cv2
from PyQt5 import QtCore, QtWidgets, uic
from skimage import exposure


class FrameProcessor(QtCore.QObject):
    IMAGE_PROCESSING_NONE = 0
    IMAGE_PROCESSING_PERCENTILE = 1
    IMAGE_PROCESSING_HISTEQ = 2
    IMAGE_PROCESSING_ADAPTEQ = 3
    frame_processed_signal = QtCore.pyqtSignal(np.ndarray)
    frame_stack_processed_signal = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    diff_processed_signal = QtCore.pyqtSignal(np.ndarray, np.ndarray)
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
            print("Invalid mode")

    def set_percentile_lower(self, new_percentile):
        if new_percentile < self.p_high:
            self.p_low = new_percentile
        else:
            print("Please raise % max to avoid overlap")

    def set_percentile_upper(self, new_percentile):
        if new_percentile > self.p_low:
            self.p_high = new_percentile
        else:
            print("Please reduce lower % min to avoid overlap")

    def set_clip_limit(self, new_clip_limit):
        self.clip = new_clip_limit

    def __process_frame(self, frame_in):
        if self.subtracting and self.background is not None:
            frame_in = frame_in.astype(np.int16) - self.background.astype(np.int16)
            frame_in[frame_in < 0] = 0
        match self.mode:
            case self.IMAGE_PROCESSING_NONE:
                return frame_in
            case self.IMAGE_PROCESSING_PERCENTILE:
                px_low, px_high = np.percentile(frame_in, (self.p_low, self.p_high))
                return exposure.rescale_intensity(frame_in, in_range=(px_low, px_high))
            case self.IMAGE_PROCESSING_HISTEQ:
                return (exposure.equalize_hist(frame_in) * 65535).astype(np.uint16)
            case self.IMAGE_PROCESSING_ADAPTEQ:
                return (exposure.equalize_adapthist(frame_in, clip_limit=self.clip) * 65535).astype(
                    np.uint16)
            case _:
                print("Unrecognized image processing mode")
                return frame_in

    def process_frame(self, raw_frame):
        self.frame_processed_signal.emit(self.__process_frame(raw_frame).astype(np.uint16))

    def process_stack(self, raw_stack):
        mean_frame = np.mean(np.array(raw_stack), axis=0)
        self.frame_stack_processed_signal.emit(mean_frame, self.__process_frame(mean_frame))

    def process_single_diff(self, frames):
        frame_a = frames[0]
        frame_b = frames[1]
        diff_frame = np.abs(frame_a.astype(np.int16) - frame_b.astype(np.int16)).astype(np.uint16)
        self.diff_processed_signal.emit(diff_frame, self.__process_frame(diff_frame))

    def process_diff_stack(self, frames):
        frames_a = frames[0]
        frames_b = frames[1]

        mean_a = np.mean(np.array(frames_a), axis=0)
        mean_b = np.mean(np.array(frames_b), axis=0)

        meaned_diff = np.abs(mean_a.astype(np.int16) - mean_b.astype(np.int16)).astype(np.uint16)
        self.diff_processed_signal.emit(meaned_diff, self.__process_frame(meaned_diff))

