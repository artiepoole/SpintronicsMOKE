import pandas as pd
from tkinter import filedialog
import cv2
from skimage import exposure
import numpy as np
import matplotlib.pyplot as plt


file = filedialog.askopenfilename()
meta_data = pd.read_hdf(file, 'meta_data')
print(meta_data)
contents = meta_data.contents[0]
print(contents)
data = pd.read_hdf(file, 'sweep_data').values.transpose()

plt.plot(data[0,:], data[1,:])
plt.show()