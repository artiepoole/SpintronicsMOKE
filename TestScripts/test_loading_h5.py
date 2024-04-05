import pandas as pd
from tkinter import filedialog
import cv2
from skimage import exposure
import numpy as np

file = filedialog.askopenfilename()
meta_data = pd.read_hdf(file, 'meta_data')
contents = meta_data.contents[0]
frames = {}
for item in contents:
    frames[item] = pd.read_hdf(file, item)
myavg = frames["frame_avg"].values
mybkg = frames["background"].values
cv2.imshow('averaged', (exposure.equalize_hist(myavg) * 65535).astype(np.uint16))
cv2.imshow('subtracted', (exposure.equalize_hist(myavg - mybkg) * 65535).astype(np.uint16))
cv2.waitKey(0)


