import pandas as pd
from tkinter import filedialog
import cv2
from skimage import exposure
import numpy as np
from WrapperClasses.FrameProcessor import numpy_rescale
import matplotlib.pyplot as plt

file = filedialog.askopenfilename()
meta_data = pd.read_hdf(file, 'meta_data')
contents = meta_data.contents[0]

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
    if "raw_stack_" in item:
        frame = pd.read_hdf(file, item).values
        sweep_1_frames.append(frame)



file = filedialog.askopenfilename()
meta_data = pd.read_hdf(file, 'meta_data')
contents = meta_data.contents[0]

sweep_2_frames = []
for item in contents:
    if "raw_stack_" in item:
        frame = pd.read_hdf(file, item).values
        sweep_2_frames.append(frame)

diff = np.mean(sweep_1_frames, axis=0) - np.mean(sweep_2_frames, axis=0)
diff_img = adapter.apply((diff+32000).astype(np.uint16))
cv2.imshow(stream_window, diff_img)
cv2.waitKey(0)

print("dummy statement for debug purposes")
