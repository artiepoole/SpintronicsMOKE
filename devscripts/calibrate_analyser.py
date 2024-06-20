from WrapperClasses import *
import numpy as np
import cv2
import skimage.exposure as exposure
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')

plt.ion()
plt.show(block=False)

controller = AnalyserController()
camera_grabber = CameraGrabber(None)
camera_grabber.cam.set_attribute_value("EXPOSURE TIME", 3e-3)

fig = plt.figure()
ax = fig.add_subplot(111)

intensities = []
positions = []
plot_line, = ax.plot(positions, intensities, 'kx')

position = 0
steps_per_frame = 1000

camera_grabber.prepare_camera()
running = True
while running:
    frame = camera_grabber.snap()
    intensities.append(np.mean(frame, axis=(0, 1)))

    positions.append(position)
    position += steps_per_frame
    controller._step_backward(steps_per_frame, False)
    plot_line.set_xdata(positions)
    plot_line.set_ydata(intensities)
    ax.relim()
    ax.autoscale_view()
    fig.canvas.draw()
    fig.canvas.flush_events()

    cv2.imshow(
        '',
        cv2.putText(
            exposure.equalize_hist(frame),
            f'{np.mean(frame, axis=(0, 1))}',
            (50, 50),
            0,
            1,
            (0, 0, 0)
        )
    )
    key = cv2.waitKey(50)
    if key == 27:
        print('esc is pressed closing all windows')
        cv2.destroyAllWindows()
        running = False
    plt.pause(50e-3)

data = np.transpose(np.array([intensities, positions]))
np.savetxt('intensity vs steps.dat', data, delimiter='\t')

camera_grabber.cam.close()
controller.close()
