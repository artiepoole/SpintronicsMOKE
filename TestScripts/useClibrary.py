import os

os.add_dll_directory(r"C:\Program Files\JetBrains\CLion 2024.1.1\bin\mingw\bin")
os.chdir('./')
from CImageProcessing import equalizeHistogram, integer_mean, basic_exposure
import cv2
import numpy as np
import time

frame = np.ascontiguousarray(np.loadtxt("test_frame.dat").astype(np.int32))
# out_frame = np.ascontiguousarray(np.empty(frame.shape, dtype=np.uint16))

out_frame = equalizeHistogram(frame)

adapter = cv2.createCLAHE(tileGridSize=(1, 1))

cv2.imshow('frame_in', frame.astype(np.uint16))
cv2.imshow("frame_out", out_frame.astype(np.uint16))
cv2.imshow("frame_clahe", adapter.apply(frame.astype(np.uint16)))
cv2.waitKey(0)
cv2.destroyAllWindows()

UINT16_MAX = 65535


def py_int_mean(image_stack, axis=0):
    """
    integer math version of mean to speed up averaging of stacks.
    :param np.ndarray[int, int, int] image_stack: stack of integer frames to be meaned along specified axis.
    :param int axis: axis along which the stack will be meaned. default 0.
    :return mean: 2D mean of the 3D array.
    :rtype: np.ndarray[int, int]
    """
    return np.sum(image_stack, axis=axis) // image_stack.shape[0]


def py_numpy_rescale(image, low, high, roi=None):
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
    px_low = np.int32(px_low)
    px_high = np.int32(px_high)
    image[image < px_low] = px_low
    image[image > px_high] = px_high
    return (image - px_low) * UINT16_MAX // (px_high - px_low)


def py_basic_exposure(image):
    """
    Rescales an image between 0 and max brightness.
    :param np.ndarray[int, int] image: Input frame.
    :return: Image with rescaled brightness.
    :rtype: np.ndarray[int, int]
    """
    return (image * (UINT16_MAX // np.amax(image)))


stack = np.loadtxt("test_stack.dat").astype(np.int32).reshape(16, 1024, 1024)

start_time = time.time()
for i in range(25):
    py_int_mean(stack)
print("cpp: ", time.time() - start_time)
start_time = time.time()
for i in range(25):
    py_int_mean(stack)
print("py: ", time.time() - start_time)

start_time = time.time()
for i in range(25):
    basic_exposure(stack[0], np.amax(stack[0]))
print("cpp: ", time.time() - start_time)
start_time = time.time()
for i in range(25):
    py_basic_exposure(stack[0])
print("py: ", time.time() - start_time)
