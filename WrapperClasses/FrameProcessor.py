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
    mode = 0
    p_low = 0
    p_high = 100
    clip = 0.03

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
        match self.mode:
            case self.IMAGE_PROCESSING_NONE:
                processed_frame = raw_frame
            case self.IMAGE_PROCESSING_PERCENTILE:
                px_low, px_high = np.percentile(raw_frame, (self.p_low, self.p_high))
                processed_frame = exposure.rescale_intensity(raw_frame, in_range=(px_low, px_high))
            case self.IMAGE_PROCESSING_HISTEQ:
                processed_frame = exposure.equalize_hist(raw_frame)
            case self.IMAGE_PROCESSING_ADAPTEQ:
                processed_frame = exposure.equalize_adapthist(raw_frame, clip_limit=self.clip)
            case _:
                print("Unrecognized image processing mode")
                processed_frame = raw_frame
        self.frame_processed_signal.emit(processed_frame)
