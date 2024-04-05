import numpy as np

from datetime import datetime
import pandas as pd


n_images = 16
stack = np.loadtxt('../test_stack.dat').reshape((n_images, 1024, 1024))
frame_avg = np.mean(stack, axis=0)

name = 'testimage.h5'

contents = []


store = pd.HDFStore(name)

key = 'frame_avg'
contents.append(key)
store[key] = pd.DataFrame(frame_avg)

for i in range(n_images):
    key = 'frame_' + str(i)
    contents.append(key)
    store[key] = pd.DataFrame(stack[i])

meta_df = pd.DataFrame(data={
    'description': "Image acquired using B204 MOKE owned by the Spintronics Group and University of Nottingham using ArtieLab V0-2024.04.05.",
    'camera': 'hamamatsu C11440',
    'sample': 'None',
    'lighting configuration': 'None',
    'binnning': '2x2',
    'lens': '20x / 0.22',
    'magnification': '',
    'target fps': '20',
    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    'contents': [contents]
})
store['meta_data'] = meta_df
store.close()

#
# import numpy as np
#
# from datetime import datetime
# import tifffile
#
# n_images = 16
# stack = np.loadtxt('../test_stack.dat').reshape((n_images, 1024, 1024))
# frame_avg = np.mean(stack, axis=0)
#
# name = 'testimage.tif'
#
# contents = []
# contents.append('frame_avg')
# for i in range(n_images):
#     key = 'frame_' + str(i)
#     contents.append(key)
#
# data = np.append(frame_avg.reshape(1, 1024, 1024), stack, axis=0)
# meta_df = {
#     'description': "Image acquired using B204 MOKE owned by the Spintronics Group and University of Nottingham using ArtieLab V0-2024.04.05.",
#     'camera': 'hamamatsu C11440',
#     'sample': 'None',
#     'lighting configuration': 'None',
#     'binnning': '2x2',
#     'lens': '20x / 0.22',
#     'magnification': '',
#     'target fps': '20',
#     'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#     'contents': contents
# }
# tifffile.imwrite(name, data, metadata=meta_df)
#
#
# file = r'testimage.tif'
#
# with tifffile.TiffFile(file) as tif:
#     print(tif.shaped_metadata)
