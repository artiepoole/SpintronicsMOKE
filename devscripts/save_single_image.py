from pylablib.devices import DCAM
import time
import cv2
from WrapperClasses.LampController import LampController
import numpy as np
from tkinter import filedialog as dialog

cam = DCAM.DCAMCamera(idx=0)
cam.set_attribute_value("EXPOSURE TIME", 0.05)
height, width = cam.get_detector_size()
cam.set_roi(hbin=2, vbin=2)

fullscreen = True

stream_window = 'HamamatsuView'
if fullscreen:
    window_width = width // 2
    window_height = height // 2
    cv2.namedWindow(
        stream_window,
        flags=(cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_FREERATIO))
    cv2.setWindowProperty(stream_window, cv2.WND_PROP_TOPMOST, 1.0)
    cv2.setWindowProperty(stream_window, cv2.WND_PROP_FULLSCREEN, 1.0)
    cv2.resizeWindow(
        stream_window,
        window_width,
        window_height)
    cv2.moveWindow(
        stream_window,
        0,
        0)

lampController = LampController()
lampController.enable_left_pair()

time.sleep(1)

frame = cam.snap()
cv2.imshow(stream_window, frame)


name = dialog.asksaveasfilename(title='Save data')
if name:  # if a name was entered, don't save otherwise
    if name[-4:] != '.txt':  # add .txt if not already there
        name = f'{name}.txt'
    np.savetxt(name, frame, newline='\r\n', delimiter='\t')  # save
    print(f'Data saved as {name}')
else:
    print('Data not saved')

cam.close()
lampController.disable_all()
time.sleep(0.2)
lampController.close()
cv2.destroyAllWindows()
