import os.path
import sys
from os import listdir
from os.path import isfile, join

import numpy as np
from PyQt5 import QtCore, QtWidgets, uic

from WrapperClasses.MagnetController import MagnetController


class MagnetDriverUI(QtWidgets.QMainWindow):
    """
    Standalone GUI for magnet control.
    """
    def __init__(self):
        super(MagnetDriverUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(r'res\Magnet_driver_UI.ui', self)  # Load the .ui file
        self.show()
        print("MagnetDriverUI: Finding calibration files")

        self.timer_update_vals = QtCore.QTimer(self)
        self.timer_update_vals.timeout.connect(self.update_measured_vals)

        if os.path.isfile('res/last_calibration_location.txt'):
            with open('res/last_calibration_location.txt', 'r') as file:
                self.calib_file_dir = file.readline()
        elif os.path.isdir("Coil Calibrations\\"):
            self.calib_file_dir = "Coil Calibrations\\"
            print('MagnetDriverUI:No calibration location found, trying: ', self.calib_file_dir)
        else:
            print("MagnetDriverUI:Default calib file location not found. Asking for user input.")
            self.calib_file_dir = QtWidgets.QFileDialog.getExistingDirectory(
                None,
                'Choose Calibration File Directory',
                QtWidgets.QFileDialog.ShowDirsOnly
            )

        self.magnet_controller = MagnetController(reset=True)
        self.__populate_calibration_combobox(self.calib_file_dir)

        self.combo_calib_file.currentIndexChanged.connect(self.__on_change_calibration)

        self.spin_mag_amplitude.valueChanged.connect(self.__on_change_amplitude)
        self.spin_mag_offset.valueChanged.connect(self.__on_change_offset)
        self.spin_mag_freq.valueChanged.connect(self.__on_change_freq)

        self.button_zero_field.clicked.connect(self.__set_zero_field)
        self.button_DC.clicked.connect(self.__on_DC)
        self.button_AC.clicked.connect(self.__on_AC)
        # self.button_calibration_directory.clicked.connect(self._on_calibration_directory)
        self.timer_update_vals.start(1000)

    def __populate_calibration_combobox(self, dir):
        file_names = [f for f in listdir(dir) if isfile(join(dir, f)) and ".txt" in f]
        if file_names:
            self.calibration_dictionary = {i + 1: name for i, name in enumerate(file_names)}
            # +1 because 0 is "None"

            strings = [name.replace('.txt', '') for name in file_names]
            strings = [name.replace('_fit', '') for name in strings]
            self.combo_calib_file.clear()
            self.combo_calib_file.addItem("None")
            self.combo_calib_file.addItems(strings)
        else:
            print("MagnetDriverUI: No calibration files found.")

    def __on_change_calibration(self, index):
        file_name = self.calibration_dictionary[index]
        calibration_array = np.loadtxt(os.path.join(self.calib_file_dir, file_name), delimiter=',', skiprows=1)
        print("MagnetDriverUI: Setting calibration using file: ", file_name)
        self.magnet_controller.set_calibration(
            calibration_array[:, 0],
            calibration_array[:, 1],
            calibration_array[:, 2],
            calibration_array[:, 3]
        )
        max_field = np.amax(calibration_array[:, 1])
        self.label_amplitude.setText("Amplitude (mT)")
        self.label_offset.setText("Offset (mT)")
        self.label_measured_field.setText("Field (mT)")
        self.spin_mag_amplitude.setValue(0.0)
        self.spin_mag_amplitude.setRange(-max_field, max_field)
        self.spin_mag_amplitude.setSingleStep(round(max_field / 50, 1))
        self.spin_mag_offset.setValue(0.0)
        self.spin_mag_offset.setRange(-max_field, max_field)
        self.spin_mag_offset.setSingleStep(round(max_field / 50, 1))

    def update_measured_vals(self):
        field, current = self.magnet_controller.get_current_amplitude()
        self.line_measured_field.setText("{:0.4f}".format(field))
        self.line_measured_current.setText("{:0.4f}".format(current))

    def __on_change_amplitude(self, value):
        self.magnet_controller.set_target_field(value)

    def __on_change_offset(self, value):
        self.magnet_controller.set_target_offset(value)

    def __set_zero_field(self):
        self.spin_mag_offset.setEnabled(False)
        self.spin_mag_offset.setValue(0)
        self.spin_mag_freq.setEnabled(False)
        self.spin_mag_freq.setValue(0)
        self.magnet_controller.reset_field()

    def __on_change_freq(self, value):
        self.magnet_controller.set_frequency(value)

    def __on_DC(self, enabled):
        if enabled:
            # self.button_DC.setChecked(True)
            self.button_AC.setChecked(False)
            if self.magnet_controller.mode == "AC":
                print("Disabled AC mode")
                self.spin_mag_offset.setEnabled(False)
                self.spin_mag_offset.setValue(0)
                self.spin_mag_freq.setEnabled(False)
                self.spin_mag_freq.setValue(0)
            self.magnet_controller.mode = "DC"
            self.magnet_controller.update_output()
        else:
            if not self.button_AC.isChecked():
                print("MagnetDriverUI: There is no mode selected.")
                self.__set_zero_field()
                self.magnet_controller.mode = None

    def __on_AC(self, enabled):
        if enabled:
            # self.button_AC.setChecked(True)
            self.button_DC.setChecked(False)
            if self.magnet_controller.mode == "DC":
                print("Enabling AC mode")
                self.spin_mag_offset.setEnabled(True)
                self.spin_mag_freq.setEnabled(True)
            self.magnet_controller.mode = "AC"
            self.magnet_controller.set_target_offset(self.spin_mag_offset.value())
            self.magnet_controller.set_frequency(self.spin_mag_freq.value())
            self.magnet_controller.update_output()

        else:
            if not self.button_DC.isChecked():
                print("MagnetDriverUI: There is no mode selected.")
                self.__set_zero_field()
                self.magnet_controller.mode = None

    def closeEvent(self, event):
        self.magnet_controller.close()
        print("MagnetDriverUI: Closed DAQ tasks")
        super(MagnetDriverUI, self).closeEvent(event)
        sys.exit()


if __name__ == '__main__':
    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook


    def my_exception_hook(exctype, value, traceback):
        # Print the error and traceback
        print(exctype, value, traceback)
        # Call the normal Exception hook after
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)


    # Set the exception hook to our wrapping function
    sys.excepthook = my_exception_hook

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('fusion')
    window = MagnetDriverUI()

    try:
        sys.exit(app.exec_())
    except:
        print("Exiting")
