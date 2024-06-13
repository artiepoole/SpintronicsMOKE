import os

os.add_dll_directory(r"C:\Program Files\JetBrains\CLion 2024.1.1\bin\mingw\bin")
os.chdir('./')
from CImageProcessing import equalizeHistogram
import cv2
import numpy as np

frame = np.ascontiguousarray(np.loadtxt("test_frame.dat").astype(np.int32))
# out_frame = np.ascontiguousarray(np.empty(frame.shape, dtype=np.uint16))

out_frame = equalizeHistogram(frame)

adapter = cv2.createCLAHE(tileGridSize=(1, 1))

cv2.imshow('frame_in', frame.astype(np.uint16))
cv2.imshow("frame_out", out_frame.astype(np.uint16))
cv2.imshow("frame_clahe", adapter.apply(frame.astype(np.uint16)))
cv2.waitKey(0)
cv2.destroyAllWindows()
