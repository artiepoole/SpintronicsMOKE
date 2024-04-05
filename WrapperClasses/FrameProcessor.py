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

    def process_frame(self, raw_frame):
        if self.subtracting and self.background is not None:
            raw_frame = raw_frame.astype(np.int16) - self.background.astype(np.int16)
            raw_frame[raw_frame < 0] = 0
        match self.mode:
            case self.IMAGE_PROCESSING_NONE:
                processed_frame = raw_frame
            case self.IMAGE_PROCESSING_PERCENTILE:
                px_low, px_high = np.percentile(raw_frame, (self.p_low, self.p_high))
                processed_frame = exposure.rescale_intensity(raw_frame, in_range=(px_low, px_high))
            case self.IMAGE_PROCESSING_HISTEQ:
                processed_frame = (exposure.equalize_hist(raw_frame) * 65535).astype(np.uint16)
            case self.IMAGE_PROCESSING_ADAPTEQ:
                processed_frame = (exposure.equalize_adapthist(raw_frame, clip_limit=self.clip) * 65535).astype(
                    np.uint16)
            case _:
                print("Unrecognized image processing mode")
                processed_frame = raw_frame
        self.frame_processed_signal.emit(processed_frame.astype(np.uint16))

    def process_stack(self, raw_stack):
        mean_frame = np.mean(np.array(raw_stack), axis=0)
        if self.subtracting and self.background is not None:
            sub = mean_frame - self.background
            sub[sub < 0] = 0
        else:
            sub = mean_frame
        match self.mode:
            case self.IMAGE_PROCESSING_NONE:
                processed_frame = sub
            case self.IMAGE_PROCESSING_PERCENTILE:
                px_low, px_high = np.percentile(sub, (self.p_low, self.p_high))
                processed_frame = exposure.rescale_intensity(sub, in_range=(px_low, px_high))
            case self.IMAGE_PROCESSING_HISTEQ:
                processed_frame = (exposure.equalize_hist(sub) * 65535).astype(np.uint16)
            case self.IMAGE_PROCESSING_ADAPTEQ:
                processed_frame = (exposure.equalize_adapthist(sub.astype(np.uint16), clip_limit=self.clip)*65535)
            case _:
                print("Unrecognized image processing mode")
                processed_frame = sub
        self.frame_stack_processed_signal.emit(mean_frame, processed_frame)
