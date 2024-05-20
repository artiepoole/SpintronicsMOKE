import time

from PyQt5.QtWidgets import QDialog
from PyQt5 import uic
import pyqtgraph as pg
from datetime import datetime
from pathlib import Path
import pandas as pd
import logging
import numpy as np


class AnalyserSweepDialog(QDialog):
    def __init__(self, parent):
        super().__init__()
        uic.loadUi('res/AnalyserSweep.ui', self)
        self.steps = int(self.line_steps.text())
        self.start = self.spin_start.value()
        self.stop = self.spin_stop.value()
        self.step_size = self.spin_step.value()

        self.parent = parent
        self.camera_grabber = self.parent.camera_grabber
        self.magnet_controller = self.parent.magnet_controller
        self.analyser_controller = self.parent.analyser_controller
        self.start_angle = self.analyser_controller.position_in_degrees
        self.roi = self.parent.frame_processor.roi
        self.averaging = self.parent.frame_processor.averaging
        if self.averaging:
            self.averages = self.parent.frame_processor.averages
        if sum(self.roi) <= 0:
            self.roi = None

        # Target file destination and other settings.

        self.plot_canvas = pg.GraphicsLayoutWidget()
        self.layout_plot.addWidget(self.plot_canvas)
        # Target file destination and other settings.
        if self.roi is not None:
            left = "Mean ROI Intensity"
            logging.info("Using region of intensity")
        else:
            left = "Mean Intensity"

        self.sweep_plot = self.plot_canvas.addPlot(
            row=0,
            col=0,
            title="Analyser Sweep Plot",
            left=left,
            bottom="Angle (°)"
        )
        self.sweep_line = self.sweep_plot.plot([], [], pen='k')

        self.spin_start.valueChanged.connect(self.spin_start_value_changed)
        self.spin_stop.valueChanged.connect(self.spin_stop_value_changed)
        self.spin_step.valueChanged.connect(self.spin_step_value_changed)
        self.button_run.clicked.connect(self.run)
        self.button_cancel.clicked.connect(self.close)

    def spin_start_value_changed(self, value):
        self.start = value

        self.update_steps()

        pass

    def spin_stop_value_changed(self, value):
        self.stop = value
        self.update_steps()
        pass

    def spin_step_value_changed(self, value):
        self.step_size = value
        self.update_steps()
        pass

    def update_steps(self):
        steps = int(abs(self.start - self.stop) / self.step_size)
        if steps == 0:
            return
        self.steps = steps
        self.line_steps.setText(str(steps))

    def run(self):
        file_path = Path(
            self.parent.line_directory.text()).joinpath(
            datetime.now().strftime("%Y-%m-%d--%H-%M-%S") +
            '_AnalyserSweep_' +
            self.parent.line_prefix.text().strip().replace(' ', '_') +
            '.h5'
        )
        try:
            store = pd.HDFStore(str(file_path))
        except:
            logging.warning(
                "Cannot save to this file/location: " + str(file_path) +
                '. Does it exist? Do you have write permissions?\n' +
                '\t Did not start sweep. Close the window and check the save settings in main GUI.')
            return
        meta_data = {
            'description': "Anaylser sweep data and assosciated frames acquired using B204 MOKE owned by the "
                           "Spintronics Group and University of "
                           "Nottingham using ArtieLab V0-2024.04.05.",
            'camera': 'Hamamatsu C11440',
            'sample': self.parent.line_prefix.text(),
            'lighting configuration': [self.parent.get_lighting_configuration()],
            'binnning': self.parent.combo_binning.currentText(),
            'lens': self.parent.combo_lens.currentText(),
            'magnification': self.parent.combo_magnification.currentText(),
            'exposure_time': self.parent.spin_exposure_time.value(),
            'correction': self.parent.line_correction.text(),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'start': self.spin_start.value(),
            'stop': self.spin_stop.value(),
            'step': self.spin_step.value(),
            'steps': self.steps,
            'roi': [self.roi],
        }
        match self.parent.get_magnet_mode():
            case 0:
                meta_data['magnet_mode'] = None
            case 1:  # DC
                meta_data['magnet_mode'] = 'DC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
            case 2:  # AC
                meta_data['magnet_mode'] = 'AC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['mag_field_amp'] = self.spin_mag_amplitude.value()
                meta_data['mag_field_freq'] = self.spin_mag_freq.value()
                meta_data['mag_field_offset'] = self.spin_mag_offset.value()
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
        if self.averaging:
            meta_data['averages'] = self.parent.spin_foreground_averages.value()

        contents = []
        intensities = []
        angles = []
        self.analyser_controller.move(-self.start_angle)
        angle = self.start

        self.camera_grabber.prepare_camera()
        if abs(self.start) > 0.0001:
            self.analyser_controller.move(self.start)
        for i in range(self.steps):
            time.sleep(self.parent.exposure_time)
            if self.averaging:
                frames = self.camera_grabber.snap_n(self.averages)
                frame = np.mean(frames, axis=0)
            else:
                frame = self.camera_grabber.snap()
            if self.roi:
                x, y, w, h = self.roi
                intensities.append(np.mean(frame[y:y + h, x:x + w], axis=(0, 1)))
                angles.append(angle)
            self.sweep_line.setData(angles, intensities)
            pg.QtGui.QGuiApplication.processEvents()  # draws the updates to screen.

            key = f'sweep_frame_{i}'
            contents.append(key)
            store[key] = pd.DataFrame(frame)
            self.analyser_controller.move(self.step_size)
            angle += self.step_size

        contents.append('sweep_data')
        meta_data['contents'] = [contents]
        store['meta_data'] = pd.DataFrame(meta_data)
        store['sweep_data'] = pd.DataFrame(np.array(list(zip(angles, intensities))))
        contents.append('sweep_data')

        store.close()
        logging.info("Sweep complete. Data saved to: " + str(file_path))
        logging.info("Returning to original analyser position")
        self.analyser_controller.move(-self.stop + self.start_angle)


class FieldSweepDialog(QDialog):
    def __init__(self, parent):
        super().__init__()
        uic.loadUi('res/FieldSweep.ui', self)
        self.amplitude = self.spin_amplitude.value()
        self.offset = self.spin_offset.value()
        self.step_size = self.spin_step_size.value()
        self.repeats = self.spin_repeats.value()
        self.points = int(self.line_points.text())

        self.parent = parent
        self.camera_grabber = self.parent.camera_grabber
        self.magnet_controller = self.parent.magnet_controller
        self.roi = self.parent.frame_processor.roi
        self.averaging = self.parent.frame_processor.averaging
        if self.averaging:
            self.averages = self.parent.frame_processor.averages
        if sum(self.roi) <= 0:
            self.roi = None

        # Target file destination and other settings.

        self.plot_canvas = pg.GraphicsLayoutWidget()
        self.layout_plot.addWidget(self.plot_canvas)
        # Target file destination and other settings.
        if self.roi is not None:
            left = "Mean ROI Intensity"
            logging.info("Using region of intensity")
        else:
            left = "Mean Intensity"

        self.sweep_plot = self.plot_canvas.addPlot(
            row=0,
            col=0,
            title="Field Sweep Plot",
            left=left,
            bottom="Field (mT)"
        )
        self.sweep_line = self.sweep_plot.plot([], [], pen='k')

        self.amplitude.valueChanged.connect(self.spin_amplitude_value_changed)
        self.offset.valueChanged.connect(self.spin_offset_value_changed)
        self.step_size.valueChanged.connect(self.spin_step_size_value_changed)
        self.spin_repeats.valueChanged.connect(self.spin_repeats_value_changed)
        self.button_run.clicked.connect(self.run)
        self.button_cancel.clicked.connect(self.close)

    def spin_amplitude_value_changed(self, value):
        self.amplitude = value

        self.update_steps()

        pass

    def spin_offset_value_changed(self, value):
        self.offset = value
        self.update_steps()
        pass

    def spin_step_size_value_changed(self, value):
        self.step_size = value
        self.update_steps()
        pass

    def spin_repeats_value_changed(self, value):
        self.repeats = value
        self.update_steps()
        pass

    def update_steps(self):
        steps = int(abs(self.amplitude) / self.step_size) * self.repeats * 2
        if steps == 0:
            return
        self.points = steps
        self.line_steps.setText(str(steps))

    def run(self):
        file_path = Path(
            self.parent.line_directory.text()).joinpath(
            datetime.now().strftime("%Y-%m-%d--%H-%M-%S") +
            '_FieldSweep_' +
            self.parent.line_prefix.text().strip().replace(' ', '_') +
            '.h5'
        )
        try:
            store = pd.HDFStore(str(file_path))
        except:
            logging.warning(
                "Cannot save to this file/location: " + str(file_path) +
                '. Does it exist? Do you have write permissions?\n' +
                '\t Did not start sweep. Close the window and check the save settings in main GUI.')
            return
        meta_data = {
            'description': "Field Sweep Data acquired using B204 MOKE owned by the Spintronics Group and University of "
                           "Nottingham using ArtieLab V0-2024.04.05.",
            'camera': 'Hamamatsu C11440',
            'sample': self.parent.line_prefix.text(),
            'lighting configuration': [self.parent.get_lighting_configuration()],
            'binnning': self.parent.combo_binning.currentText(),
            'lens': self.parent.combo_lens.currentText(),
            'magnification': self.parent.combo_magnification.currentText(),
            'exposure_time': self.parent.spin_exposure_time.value(),
            'correction': self.parent.line_correction.text(),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'start': self.spin_start.value(),
            'stop': self.spin_stop.value(),
            'step': self.spin_step.value(),
            'steps': self.points,
            'roi': [self.roi],
        }
        match self.parent.get_magnet_mode():
            case 0:
                meta_data['magnet_mode'] = None
            case 1:  # DC
                meta_data['magnet_mode'] = 'DC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
            case 2:  # AC
                meta_data['magnet_mode'] = 'AC'
                meta_data['mag_field'] = self.mag_y[-1]
                meta_data['mag_field_amp'] = self.spin_mag_amplitude.value()
                meta_data['mag_field_freq'] = self.spin_mag_freq.value()
                meta_data['mag_field_offset'] = self.spin_mag_offset.value()
                meta_data['coil_calib'] = self.combo_calib_file.currentText()
        if self.averaging:
            meta_data['averages'] = self.parent.spin_foreground_averages.value()
        one_side = np.arange(0, self.amplitude + self.step_size, self.step_size)

        target_fields = np.repeat(np.concatenate([one_side, np.flip(one_side), -one_side, -np.flip(one_side)]),
                                  self.repeats) + self.offset

        contents = []
        intensities = []
        fields = []
        voltages = []
        field = 0

        self.camera_grabber.prepare_camera()
        self.magnet_controller.mode = "DC"
        self.magnet_controller.set_target_field(field + self.offset)

        for target_field in target_fields:
            self.magnet_controller.set_target_field(target_field)
            field += self.step_size
            time.sleep(self.parent.exposure_time)
            if self.averaging:
                frames = self.camera_grabber.snap_n(self.averages)
                frame = np.mean(frames, axis=0)
            else:
                frame = self.camera_grabber.snap()
            if self.roi:
                x, y, w, h = self.roi
                intensities.append(np.mean(frame[y:y + h, x:x + w], axis=(0, 1)))
                field, voltage = self.magnet_controller.get_current_amplitude()
                fields.append(field)
                voltages.append(voltage)
            self.sweep_line.setData(fields, intensities)
            pg.QtGui.QGuiApplication.processEvents()  # draws the updates to screen.

        contents.append('sweep_data')
        meta_data['contents'] = [contents]
        store['meta_data'] = pd.DataFrame(meta_data)
        data_dict = {'fields (mT)': fields, 'voltages (V)': voltages, 'intensities': intensities}
        store['sweep_data'] = pd.DataFrame(data_dict)
        contents.append('sweep_data')

        store.close()
        logging.info("Sweep complete. Data saved to: " + str(file_path))
