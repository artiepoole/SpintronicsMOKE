import pandas as pd
from tkinter import filedialog
import cv2
from skimage import exposure
import numpy as np
from WrapperClasses.FrameProcessor import numpy_rescale
import matplotlib.pyplot as plt

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
cv2.resizeWindow(
    stream_window,
    1024,
    1024)

sweep_1_frames = []
for item in contents:
    if "sweep_frame_" in item:
        frame = pd.read_hdf(file, item).values
        sweep_1_frames.append(frame)
    data = pd.read_hdf(file, 'sweep_data').values.transpose()
    sweep_1_xdata = data[0, :]
    sweep_1_ydata = data[1, :]
try:
    sweep_1_field = meta_data.mag_field
except AttributeError:
    sweep_1_field = 0

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
cv2.resizeWindow(
    stream_window,
    1024,
    1024)

sweep_2_frames = []
for item in contents:
    if "sweep_frame_" in item:
        frame = pd.read_hdf(file, item).values
        sweep_2_frames.append(frame)
    data = pd.read_hdf(file, 'sweep_data').values.transpose()
    sweep_2_xdata = data[0, :]
    sweep_2_ydata = data[1, :]
try:
    sweep_2_field = meta_data.mag_field
except AttributeError:
    sweep_2_field = 0

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
cv2.resizeWindow(
    stream_window,
    1024,
    1024)

sweep_3_frames = []
for item in contents:
    if "sweep_frame_" in item:
        frame = pd.read_hdf(file, item).values
        sweep_3_frames.append(frame)
    data = pd.read_hdf(file, 'sweep_data').values.transpose()
    sweep_3_xdata = data[0, :]
    sweep_3_ydata = data[1, :]
try:
    sweep_3_field = meta_data.mag_field
except AttributeError:
    sweep_3_field = 0

for i in range(len(sweep_2_frames)):
    diff_frame = ((sweep_3_frames[i] - sweep_2_frames[i]) / (sweep_3_frames[i] + sweep_2_frames[i]))
    cv2.imshow(str(sweep_2_xdata[i]), (diff_frame - diff_frame.min()) / (diff_frame.max() - diff_frame.min()))

plt.plot(sweep_2_xdata, sweep_1_ydata - sweep_2_ydata)
plt.show()
cv2.waitKey(0)
print("paused")
