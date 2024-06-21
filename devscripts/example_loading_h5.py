import pandas as pd
from tkinter import filedialog
import cv2
from skimage import exposure
import numpy as np
import os

os.add_dll_directory(r"C:\Program Files\JetBrains\CLion 2024.1.1\bin\mingw\bin")
from CImageProcessing import equalizeHistogram

# store = pd.HDFStore('path/to/your/h5/file.h5', complevel=9, complib='xz')
# data_retrieved = store[some_key]
file = filedialog.askopenfilename()
meta_data = pd.read_hdf(file, 'meta_data')
print(meta_data)
contents = meta_data.contents[0]
print(contents)
frames = {}
adapter = cv2.createCLAHE()
adapter.setClipLimit(100)
stream_window = 'window'
cv2.namedWindow(
    stream_window,
    cv2.WINDOW_NORMAL
)
cv2.setWindowProperty(stream_window, cv2.WND_PROP_TOPMOST, 1.0)
cv2.resizeWindow(
    stream_window,
    1024,
    1024)
background = None
if 'background_avg' in contents:
    background = pd.read_hdf(file, 'background_avg').values
# for i in range(10):
for item in contents:
    if "frame" in item or "stack" in item:
        data = pd.read_hdf(file, item).values
        if background is not None:
            data = data-background
        if len(data.shape) == 2:
            if data.shape[0] == data.shape[1]:
                # cv2.imshow(item, data / np.amax(data))
                cv2.imshow(stream_window, cv2.putText(equalizeHistogram(data), item,
                                                      (50, 50),
                                                      0,
                                                      1,
                                                      (255, 255, 255)))
                cv2.waitKey(20)
        break  # Use to only plot one frame

cv2.waitKey(0)
cv2.destroyAllWindows()
# myavg = frames["frame_avg"].values
# mybkg = frames["background"].values
# cv2.imshow('averaged', (exposure.equalize_hist(myavg) * 65535).astype(np.uint16))
# cv2.imshow('subtracted', (exposure.equalize_hist(myavg - mybkg) * 65535).astype(np.uint16))
# cv2.waitKey(0)
