import numpy as np
from PyQt5 import QtCore
from skimage import exposure
import logging
from collections import deque
import time
from skimage.measure import profile_line
import cv2

UINT16_MAX = 65535
INT16_MAX = 65535 // 2
import os

os.add_dll_directory(r"C:\Program Files\JetBrains\CLion 2024.1.1\bin\mingw\bin")
from CImageProcessing import equalizeHistogram, integer_mean


def numpy_rescale(image, low, high, roi=None):
    """
    Rescales the image using percentile values. Must faster than scipy rescaling.
    :param np.ndarray[int,int,int] image: Input frame
    :param int low: lower percentile value
    :param int high: upper percentile value
    :param tuple[int, int, int, int]|None roi: Region of Interest (x,y,w,h) or None
    :return:
    """
    if roi is not None:
        px_low, px_high = np.percentile(roi, (low, high))
    else:
        px_low, px_high = np.percentile(image, (low, high))
    px_low = np.uint16(px_low)
    px_high = np.uint16(px_high)
    image[image < px_low] = px_low
    image[image > px_high] = px_high
    return (image - px_low) * (UINT16_MAX // (px_high - px_low))


def basic_exposure(image):
    """
    Rescales an image between 0 and max brightness.
    :param np.ndarray[int, int] image: Input frame.
    :return: Image with rescaled brightness.
    :rtype: np.ndarray[int, int]
    """
    return image * (UINT16_MAX // np.amax(image))


class FrameProcessor(QtCore.QObject):
    logging.info("FrameProcessor: Initializing FrameProcessor...")
    IMAGE_PROCESSING_NONE = 0
    IMAGE_PROCESSING_BASIC = 1
    IMAGE_PROCESSING_PERCENTILE = 2
    IMAGE_PROCESSING_HISTEQ = 3
    IMAGE_PROCESSING_ADAPTEQ = 4
    frame_processor_ready = QtCore.pyqtSignal()
    new_raw_frame_signal = QtCore.pyqtSignal(np.ndarray)
    new_processed_frame_signal = QtCore.pyqtSignal(np.ndarray)
    mode = 1
    p_low = 0
    p_high = 100
    clip = 0.03
    resolution = 1024
    subtracting = True
    background = None
    background_raw_stack = None
    running = False
    closing = False
    frame_counter = 0
    latest_raw_frame = None
    latest_mean_frame = None
    raw_frame_stack = None
    latest_diff_frame = None
    latest_diff_frame_a = None
    latest_diff_frame_b = None
    latest_mean_diff = None
    latest_processed_frame = np.zeros((1024, 1024), dtype=np.uint16)
    diff_frame_stack_a = None
    diff_frame_stack_b = None
    latest_hist_data = []
    latest_hist_bins = []
    intensities_y = deque(maxlen=100)
    frame_times = deque(maxlen=100)
    roi_int_y = deque(maxlen=100)
    waiting = False
    averaging = False
    averages = 16
    mutex = QtCore.QMutex()
    roi = (0, 0, 0, 0)
    line_coords = None
    latest_profile = np.array([])
    adapter = cv2.createCLAHE()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def update_settings(self, settings):
        '''
        :param dict settings: {mode, percentile_lower, percentile_upper, clip_limit}
        :return: None
        '''
        self.mode, self.p_low, self.p_high, self.clip = settings

    def _process_frame(self, frame):
        if self.subtracting and self.background is not None:
            frame = ((frame.astype(np.int32) - self.background + UINT16_MAX) // 2).astype(np.uint16)
        match self.mode:
            case self.IMAGE_PROCESSING_NONE:
                pass
            case self.IMAGE_PROCESSING_BASIC:
                # Divide by max and rescale.
                frame = basic_exposure(frame)
            case self.IMAGE_PROCESSING_PERCENTILE:
                # Percentile rescaling
                if sum(self.roi) > 0:
                    x, y, w, h = self.roi
                    frame = numpy_rescale(frame, self.p_low, self.p_high, frame[y:y + h, x:x + w])
                else:
                    frame = numpy_rescale(frame, self.p_low, self.p_high)
            case self.IMAGE_PROCESSING_HISTEQ:
                # Uses Artie's own C++ histogram equalisation because openCV HistEq doesn't support uint16 or int32.
                if not frame.flags.c_contiguous:
                    logging.warning('Not contiguous')
                    return equalizeHistogram(np.ascontiguousarray(frame))
                else:
                    return equalizeHistogram(frame)
            case self.IMAGE_PROCESSING_ADAPTEQ:
                # Uses openCV CLAHE algorithm which doesn't support int32.
                frame = self.adapter.apply(frame)
            case _:
                logging.info("FrameProcessor: Unrecognized image processing mode")
        return frame

    @QtCore.pyqtSlot()
    def start_processing(self):
        """
        Constantly acquires frames from buffer and processes them. Handles storing of frames into stacks and difference
        calulations etc.
        :return None:
        """
        # TODO: Figure out how to do everything with uint16 values to save significant memory and processing.
        self.running = True
        self.closing = False
        self.waiting = False
        while self.running:
            got = self.parent.item_semaphore.tryAcquire(1, 1)
            if got:
                try:
                    item = self.parent.frame_buffer.popleft()
                    self.parent.spaces_semaphore.release()
                except IndexError:
                    logging.error("Processing Frame queue is empty after get call. Resetting buffer.")
                    self.parent.frame_buffer = deque(maxlen=self.parent.BUFFER_SIZE)
                    self.parent.item_semaphore = QtCore.QSemaphore(0)
                    self.parent.spaces_semaphore = QtCore.QSemaphore(self.parent.BUFFER_SIZE)
                    continue

                if len(item) == 4:
                    logging.debug("Got difference frames")
                    # Diff mode
                    self.latest_diff_frame_a, latest_diff_frame_data_a, self.latest_diff_frame_b, latest_diff_frame_data_b = item
                    self.intensities_y.append(np.mean(self.latest_diff_frame_a, axis=(0, 1)))
                    self.intensities_y.append(np.mean(self.latest_diff_frame_b, axis=(0, 1)))
                    if sum(self.roi) > 0:
                        x, w, y, h = [int(value * 2 / self.parent.binning) for value in self.roi]
                        self.roi_int_y.append(np.mean(self.latest_diff_frame_a[y:y + h, x:x + w], axis=(0, 1)))
                        self.roi_int_y.append(np.mean(self.latest_diff_frame_b[y:y + h, x:x + w], axis=(0, 1)))
                    self.frame_times.append(latest_diff_frame_data_a.timestamp_us * 1e-6)
                    self.frame_times.append(latest_diff_frame_data_b.timestamp_us * 1e-6)
                    if self.latest_diff_frame_a.shape[0] != self.resolution:
                        # This happens when changing binning mode with frames in the buffer.
                        logging.warning("Latest frame is not correct shape. Discarding frame.")
                        continue
                    if self.averaging:
                        if self.frame_counter % self.averages < len(self.diff_frame_stack_a):
                            # When the stack is full up to the number of averages, this overwrites the frames in memory.
                            # This is more efficient than rolling or extending
                            self.diff_frame_stack_a[self.frame_counter % self.averages] = self.latest_diff_frame_a
                            self.diff_frame_stack_b[self.frame_counter % self.averages] = self.latest_diff_frame_b
                        else:
                            # If the stack is not full, then this appends to the array.
                            self.diff_frame_stack_a = np.append(self.diff_frame_stack_a,
                                                                np.expand_dims(self.latest_diff_frame_a, 0),
                                                                axis=0)
                            self.diff_frame_stack_b = np.append(self.diff_frame_stack_b,
                                                                np.expand_dims(self.latest_diff_frame_b, 0),
                                                                axis=0)
                        if len(self.diff_frame_stack_a) > self.averages:
                            # If the target number of averages is reduced then this code trims the stack to discard
                            # excess frames.
                            self.diff_frame_stack_a = self.diff_frame_stack_a[-self.averages:]
                            self.diff_frame_stack_b = self.diff_frame_stack_b[-self.averages:]
                        self.frame_counter += 1
                        mean_a = integer_mean(self.diff_frame_stack_a)
                        mean_b = integer_mean(self.diff_frame_stack_b)
                        self.latest_mean_diff = (mean_a.astype(np.int32) - mean_b.astype(np.int32))
                        # diff_frame = ((sweep_3_frames[i] - sweep_2_frames[i]) / (sweep_3_frames[i] + sweep_2_frames[i]))
                        # cv2.imshow(str(sweep_2_data[i]),
                        #            (diff_frame - diff_frame.min()) / (diff_frame.max() - diff_frame.min()))
                        self.latest_processed_frame = (self._process_frame(
                            self.latest_mean_diff + UINT16_MAX) // 2
                                                       ).astype(np.uint16)

                    else:
                        self.latest_diff_frame = self.latest_diff_frame_a.astype(np.int32) - self.latest_diff_frame_b.astype(np.int32)
                        # diff_frame = ((sweep_3_frames[i] - sweep_2_frames[i]) / (sweep_3_frames[i] + sweep_2_frames[i]))
                        # cv2.imshow(str(sweep_2_data[i]),
                        #            (diff_frame - diff_frame.min()) / (diff_frame.max() - diff_frame.min()))
                        self.latest_processed_frame = (self._process_frame(
                            self.latest_diff_frame + UINT16_MAX) // 2
                                                       ).astype(np.uint16)
                    self.latest_hist_data, self.latest_hist_bins = exposure.histogram(self.latest_processed_frame)
                    if self.line_coords is not None:
                        start, end = self.line_coords
                        self.latest_profile = profile_line(self.latest_processed_frame, start,
                                                           end, linewidth=5)
                elif len(item) == 2:
                    logging.debug("Got single frame")
                    # Single frame mode
                    self.latest_raw_frame, latest_frame_data = item
                    self.new_raw_frame_signal.emit(self.latest_raw_frame)
                    self.mutex.lock()
                    self.intensities_y.append(np.mean(self.latest_raw_frame, axis=(0, 1)))
                    if sum(self.roi) > 0:
                        x, y, w, h = self.roi
                        self.roi_int_y.append(np.mean(self.latest_raw_frame[y:y + h, x:x + w], axis=(0, 1)))
                    self.frame_times.append(latest_frame_data.timestamp_us * 1e-6)
                    self.mutex.unlock()
                    if self.latest_raw_frame.shape[0] != self.resolution:
                        # This happens when changing binning mode with frames in the buffer.
                        logging.warning("Latest frame is not correct shape. Discarding frame.")
                        continue
                    if self.averaging:
                        # TODO: consider assigning zeros array of length self.averages and only take mean of filled portion of
                        #  array whenever the array is too small.
                        if self.frame_counter % self.averages < len(self.raw_frame_stack):
                            # When the stack is full up to the number of averages, this overwrites the frames in memory.
                            # This is more efficient than rolling or extending
                            self.raw_frame_stack[self.frame_counter % self.averages] = self.latest_raw_frame
                        else:
                            # If the stack is not full, then this appends to the array.
                            self.raw_frame_stack = np.append(self.raw_frame_stack,
                                                             np.expand_dims(self.latest_raw_frame, 0), axis=0)
                        if len(self.raw_frame_stack) > self.averages:
                            # If the target number of averages is reduced then this code trims the stack to discard
                            # excess frames.
                            self.raw_frame_stack = self.raw_frame_stack[-self.averages:]
                        self.frame_counter += 1
                        self.latest_mean_frame = integer_mean(self.raw_frame_stack)
                        self.latest_processed_frame = self._process_frame(self.latest_mean_frame)
                    else:
                        self.latest_processed_frame = self._process_frame(self.latest_raw_frame)
                    self.latest_hist_data, self.latest_hist_bins = exposure.histogram(self.latest_processed_frame)
                    if self.line_coords is not None:
                        start, end = self.line_coords
                        self.latest_profile = profile_line(self.latest_processed_frame, start,
                                                           end, linewidth=5)
                    self.new_processed_frame_signal.emit(self.latest_processed_frame)
                else:
                    logging.warning(
                        'Incorrect length of contents: Frame processor received neither single frame nor difference frame')
        logging.info("Frame Processor stopped")
        if not (self.closing or self.waiting):
            self.frame_processor_ready.emit()  # This restarts the frame processor after binning mode changes.

    def _process_buffer(self):
        """
        A tool which can be used to process a supplied buffer which is used in performance profiling but not in normal
        use.
        :return None:
        """
        self.running = True
        while self.running:
            got = self.parent.item_semaphore.tryAcquire(1, 1)
            if not got:
                # print("stack empty")
                return
            else:
                item = self.parent.frame_buffer.popleft()
                self.parent.spaces_semaphore.release()
                self.latest_raw_frame = item
                self.intensities_y.append(np.mean(self.latest_raw_frame, axis=(0, 1)))
                if sum(self.roi) > 0:
                    x, y, w, h = self.roi
                    self.roi_int_y.append(np.mean(self.latest_raw_frame[y:y + h, x:x + w], axis=(0, 1)))
                if self.averaging:
                    if self.latest_raw_frame.shape[0] != self.raw_frame_stack.shape[1]:
                        # This happens when changing binning mode with frames in the buffer.
                        logging.warning("Latest frame is not correct shape. Discarding frame.")
                        break
                    if self.frame_counter % self.averages < len(self.raw_frame_stack):
                        # When the stack is full up to the number of averages, this overwrites the frames in memory.
                        # This is more efficient than rolling or extending
                        self.raw_frame_stack[self.frame_counter % self.averages] = self.latest_raw_frame
                    else:
                        # If the stack is not full, then this appends to the array.
                        self.raw_frame_stack = np.append(self.raw_frame_stack,
                                                         np.expand_dims(self.latest_raw_frame, 0), axis=0)
                    if len(self.raw_frame_stack) > self.averages:
                        # If the target number of averages is reduced then this code trims the stack to discard
                        # excess frames.
                        self.raw_frame_stack = self.raw_frame_stack[-self.averages:]
                    self.frame_counter += 1
                    self.latest_mean_frame = integer_mean(self.raw_frame_stack)
                    self.latest_processed_frame = self._process_frame(self.latest_mean_frame)
                else:
                    self.latest_processed_frame = self._process_frame(self.latest_raw_frame)
                self.latest_hist_data, self.latest_hist_bins = exposure.histogram(
                    self.latest_processed_frame)
                if self.line_coords is not None:
                    start, end = self.line_coords
                    self.latest_profile = profile_line(self.latest_processed_frame, start,
                                                       end, linewidth=5)
            logging.info("Stack Processed")


if __name__ == "__main__":

    class TestingContainer:
        """
        Used for performance profiling.
        """

        def __init__(self):
            self.BUFFER_SIZE = 1600  # max 100 stacks
            self.binning = 2
            self.frame_buffer = deque(maxlen=self.BUFFER_SIZE)
            self.item_semaphore = QtCore.QSemaphore(0)
            self.spaces_semaphore = QtCore.QSemaphore(self.BUFFER_SIZE)
            self.frame_processor = FrameProcessor(self)

        def benchmarking(self, number_of_stacks):
            modes = [3]
            averaging = [False, True]
            averages = [16]
            frames = np.loadtxt("../devscripts/test_stack.dat", delimiter="\t").astype(np.uint16).reshape(16, 1024,
                                                                                                         1024)
            self.frame_processor.raw_frame_stack = (
                np.array([], dtype=np.uint16).
                reshape(0, frames.shape[1], frames.shape[1]))

            loop_index = list(range(frames.shape[0])) * number_of_stacks
            print("number of frames: ", len(loop_index))
            for avg_enable in averaging:
                print("averaging?: ", avg_enable)
                self.frame_processor.averaging = avg_enable
                if avg_enable:
                    for average in averages:
                        print("averages: ", average)
                        self.frame_processor.averages = average
                for mode in modes:
                    print("Mode: ", mode)
                    self.frame_processor.mode = mode
                    for i in loop_index:
                        got_space = self.spaces_semaphore.tryAcquire(1, 1)
                        if got_space:
                            self.frame_buffer.append(frames[i])
                            self.item_semaphore.release()
                    start = time.time()
                    self.frame_processor._process_buffer()
                    print("Time taken per frame: ", (time.time() - start) / (number_of_stacks * frames.shape[0]))


    testing_container = TestingContainer()
    testing_container.benchmarking(20)  # max 100
