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
                return (exposure.equalize_adapthist(frame_in/65535, clip_limit=self.clip))
            case _:
                print("FrameProcessor: Unrecognized image processing mode")
                return frame_in

    @QtCore.pyqtSlot(np.ndarray)
    def process_frame(self, raw_frame):
        print("FrameProcessor: Processing Frame...")
        self.frame_processed_signal.emit(self.__process_frame(raw_frame))
        print("FrameProcessor: Done")

    @QtCore.pyqtSlot(np.ndarray, np.ndarray)
    def process_diff(self, frame_a, frame_b):
        diff_frame = np.abs(frame_a.astype(np.int32) - frame_b.astype(np.int32)).astype(np.uint16)
        self.diff_processed_signal.emit(diff_frame, self.__process_frame(diff_frame))


