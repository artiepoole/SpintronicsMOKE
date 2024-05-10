from ctypes import *
import numpy as np
from numpy.ctypeslib import ndpointer

processors = cdll.LoadLibrary("../CFrameProcessors/cmake-build-debug/libCImageProcessing.dll")


class c_range(Structure):
    _fields_ = [('minimum', c_long),
                ('maximum', c_long)]


# class c_hist(Structure):
#     _fields_ = [('hist_data', c_long * 65536),
#                 ('hist_bins', c_long * 65536)]


frame = np.loadtxt("test_frame.dat").astype(np.int32)
out_frame = np.empty(frame.shape, dtype=np.int32)

percentile = processors.percentile
percentile.restype = c_range
percentile.argtypes = [ndpointer(c_long, flags="C_CONTIGUOUS"), c_size_t, c_size_t]

my_range = percentile(frame, frame.shape[0], frame.shape[1])
print(my_range.minimum, my_range.maximum)
print(frame.min(), frame.max())


# rescale_percentile = processors.rescale_percentile
# rescale_percentile.restype = c_hist
# rescale_percentile.argtypes = [ndpointer(c_long, flags="C_CONTIGUOUS"), c_size_t, c_size_t,
#                                ndpointer(c_long, flags="C_CONTIGUOUS")]
#
# my_hist = rescale_percentile(frame, frame.shape[0], frame.shape[1], out_frame)
# print(my_hist.hist_data)
