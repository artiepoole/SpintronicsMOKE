import numpy as np
from PyQt5 import QtCore
from skimage import exposure
import logging
from collections import deque
import time


def int_mean(image_stack, axis=0):
    return np.sum(image_stack, axis=axis) // image_stack.shape[0]


def numpy_rescale(image, low, high):
    px_low, px_high = np.percentile(image, (low, high))
    px_low = np.int32(px_low)
    px_high = np.int32(px_high)
    image[image < px_low] = px_low
    image[image > px_high] = px_high
    return (image - px_low) * 63355 // (px_high - px_low)


# Cast to int32 is twice as fast as cast to float64

def numpy_equ(image):
    img_cdf, bin_centers = exposure.cumulative_distribution(image, nbins=100)
    return (np.interp(image, bin_centers, img_cdf)*63355).astype(np.int32)


def basic_exposure(image):
    return image * (63355 // np.amax(image))


class FrameProcessor(QtCore.QObject):
    logging.info("FrameProcessor: Initializing FrameProcessor...")
    IMAGE_PROCESSING_NONE = 0
    IMAGE_PROCESSING_BASIC = 1
    IMAGE_PROCESSING_PERCENTILE = 2
    IMAGE_PROCESSING_HISTEQ = 3
    IMAGE_PROCESSING_ADAPTEQ = 4
    frame_processed_signal = QtCore.pyqtSignal(np.ndarray, np.float64, tuple)
    diff_processed_signal = QtCore.pyqtSignal(np.ndarray, np.ndarray, np.float64, np.float64, tuple)
    mode = 1
    p_low = 0
    p_high = 100
    clip = 0.03
    subtracting = True
    background = None
    running = False
    frame_counter = 0
    latest_raw_frame = None
    latest_diff_frame_a = None
    latest_diff_frame_b = None
    latest_processed_frame = np.zeros((1024, 1024), dtype=np.uint16)
    diff_frame_stack_a = None
    diff_frame_stack_b = None
    latest_hist_data = []
    latest_hist_bins = []
    intensities_y = deque(maxlen=100)
    frame_times = deque(maxlen=100)
    averaging = False
    averages = 16
    mutex = QtCore.QMutex()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

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
            logging.info("FrameProcessor: Invalid mode")

    def set_percentile_lower(self, new_percentile):
        if new_percentile < self.p_high:
            self.p_low = new_percentile
        else:
            logging.info("FrameProcessor: Please raise % max to avoid overlap")

    def set_percentile_upper(self, new_percentile):
        if new_percentile > self.p_low:
            self.p_high = new_percentile
        else:
            logging.info("FrameProcessor: Please reduce lower % min to avoid overlap")

    def set_clip_limit(self, new_clip_limit):
        self.clip = new_clip_limit

    def __process_frame(self, frame_in):
        if self.subtracting and self.background is not None:
            frame_in = frame_in - self.background
            frame_in[frame_in < 0] = 0
        match self.mode:
            case self.IMAGE_PROCESSING_NONE:
                return frame_in
            case self.IMAGE_PROCESSING_BASIC:
                return basic_exposure(frame_in)
            case self.IMAGE_PROCESSING_PERCENTILE:
                # Fast
                return numpy_rescale(frame_in, self.p_low, self.p_high)
            case self.IMAGE_PROCESSING_HISTEQ:
                # Okay performance
                return numpy_equ(frame_in)
            case self.IMAGE_PROCESSING_ADAPTEQ:
                # Really slow
                return exposure.equalize_adapthist(frame_in / np.amax(frame_in), clip_limit=self.clip)
            case _:
                logging.info("FrameProcessor: Unrecognized image processing mode")
                return frame_in

    @QtCore.pyqtSlot()
    def start_processing(self):
        self.running = True
        while self.running:
            got = self.parent.item_semaphore.tryAcquire(1, 1)
            if got:
                logging.debug("Processing Frame")
                item = self.parent.frame_buffer.popleft()
                self.parent.spaces_semaphore.release()

                if len(item) == 4:
                    logging.debug("Got difference frames")
                    # Diff mode
                    self.latest_diff_frame_a, latest_diff_frame_data_a, self.latest_diff_frame_b, latest_diff_frame_data_b = item
                    self.intensities_y.append(np.mean(self.latest_diff_frame_a, axis=(0, 1)))
                    self.intensities_y.append(np.mean(self.latest_diff_frame_b, axis=(0, 1)))
                    self.frame_times.append(latest_diff_frame_data_a.timestamp_us * 1e-6)
                    self.frame_times.append(latest_diff_frame_data_b.timestamp_us * 1e-6)
                    if self.averaging:
                        if self.frame_counter % self.averages < len(self.diff_frame_stack_a):
                            self.diff_frame_stack_a[self.frame_counter % self.averages] = self.latest_diff_frame_a
                            self.diff_frame_stack_b[self.frame_counter % self.averages] = self.latest_diff_frame_b
                        else:
                            self.diff_frame_stack_a = np.append(self.diff_frame_stack_a,
                                                                np.expand_dims(self.latest_diff_frame_a, 0),
                                                                axis=0)
                            self.diff_frame_stack_b = np.append(self.diff_frame_stack_b,
                                                                np.expand_dims(self.latest_diff_frame_b, 0),
                                                                axis=0)
                        if len(self.diff_frame_stack_a) > self.averages:
                            self.diff_frame_stack_a = self.diff_frame_stack_a[-self.averages:]
                            self.diff_frame_stack_b = self.diff_frame_stack_b[-self.averages:]
                        self.frame_counter += 1
                        mean_a = int_mean(self.diff_frame_stack_a, axis=0)
                        mean_b = int_mean(self.diff_frame_stack_b, axis=0)
                        meaned_diff = np.abs(mean_a - mean_b)
                        self.latest_processed_frame = self.__process_frame(meaned_diff)
                    else:
                        diff_frame = np.abs(
                            self.latest_diff_frame_a - self.latest_diff_frame_b)
                        self.latest_processed_frame = self.__process_frame(diff_frame)
                elif len(item) == 2:
                    logging.debug("Got single frame")
                    # Single frame mode
                    self.latest_raw_frame, latest_frame_data = item
                    self.mutex.lock()
                    self.intensities_y.append(np.mean(self.latest_raw_frame, axis=(0, 1)))
                    self.frame_times.append(latest_frame_data.timestamp_us * 1e-6)
                    self.mutex.unlock()
                    if self.averaging:
                        if self.frame_counter % self.averages < len(self.raw_frame_stack):
                            self.raw_frame_stack[self.frame_counter % self.averages] = self.latest_raw_frame
                        else:
                            self.raw_frame_stack = np.append(self.raw_frame_stack,
                                                             np.expand_dims(self.latest_raw_frame, 0), axis=0)
                        if len(self.raw_frame_stack) > self.averages:
                            self.raw_frame_stack = self.raw_frame_stack[-self.averages:]
                        self.frame_counter += 1
                        mean_frame = int_mean(self.raw_frame_stack, axis=0)
                        self.latest_processed_frame = self.__process_frame(mean_frame)
                    else:
                        self.latest_processed_frame = self.__process_frame(self.latest_raw_frame)
                self.latest_hist_data, self.latest_hist_bins = exposure.histogram(self.latest_processed_frame)
        logging.info("Stopping Frame Processor")


if __name__ == "__main__":
    import cv2

    frames = np.loadtxt("../TestScripts/test_stack.dat", delimiter="\t").astype(np.int32).reshape(16, 1024, 1024)

    frame = frames[0]
    cv2.imshow('Raw', basic_exposure(frame).astype(np.uint16))
    cv2.imshow('Processed Frame', numpy_equ(frame).astype(np.uint16))
    cv2.waitKey(0)
    print(frame.shape)
