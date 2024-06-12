# from ctypes import *
# import os
# import cv2
# import numpy as np
# from numpy.ctypeslib import ndpointer
# os.chdir(r'C:\Users\User\PycharmProjects\SpintronicsMOKE')
# processors = cdll.LoadLibrary("CFrameProcessors/playing/cmake-build-debug/libmylib.dll")
#
#
# # class c_range(Structure):
# #     _fields_ = [('minimum', c_long),
# #                 ('maximum', c_long)]
#
#
# # class c_hist(Structure):
# #     _fields_ = [('hist_data', c_long * 65536),
# #                 ('hist_bins', c_long * 65536)]
#
#
# frame = np.loadtxt("test_frame.dat").astype(np.uint16)
# out_frame = np.empty(frame.shape, dtype=np.uint16)
#
# eqHist16 = processors.equalizeHistogram
# eqHist16.restype = None
# eqHist16.argtypes = [ndpointer(c_short, flags="C_CONTIGUOUS"),
#                      ndpointer(c_short, flags="C_CONTIGUOUS"),
#                      c_int,
#                      c_int,
#                      c_int]
#
# eqHist16(frame, out_frame, frame.shape[0], frame.shape[1], 65535)
# cv2.imshow('frame_in', frame)
# cv2.imshow("frame_out", out_frame)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
#
# # percentile = processors.percentile
# # percentile.restype = c_range
# # percentile.argtypes = [ndpointer(c_long, flags="C_CONTIGUOUS"), c_size_t, c_size_t]
# #
# # my_range = percentile(frame, frame.shape[0], frame.shape[1])
# # print(my_range.minimum, my_range.maximum)
# # print(frame.min(), frame.max())
#
#
# # rescale_percentile = processors.rescale_percentile
# # rescale_percentile.restype = c_hist
# # rescale_percentile.argtypes = [ndpointer(c_long, flags="C_CONTIGUOUS"), c_size_t, c_size_t,
# #                                ndpointer(c_long, flags="C_CONTIGUOUS")]
# #
# # my_hist = rescale_percentile(frame, frame.shape[0], frame.shape[1], out_frame)
# # print(my_hist.hist_data)

import os

os.add_dll_directory(r"C:\Program Files\JetBrains\CLion 2024.1.1\bin\mingw\bin")
from CImageProcessing import equalizeHistogram
import cv2
import numpy as np

frame = np.ascontiguousarray(np.loadtxt("test_frame.dat").astype(np.int32))
original_shape = frame.shape
frame = frame.flatten()
# out_frame = np.ascontiguousarray(np.empty(frame.shape, dtype=np.uint16))

out_frame = equalizeHistogram(frame, original_shape[0], original_shape[1], 65535)
out_frame = out_frame.reshape(original_shape)
frame = frame.reshape(original_shape)
cv2.imshow('frame_in', frame.astype(np.uint16))
cv2.imshow("frame_out", out_frame.astype(np.uint16))
cv2.waitKey(0)
cv2.destroyAllWindows()
