import os.path
from WrapperClasses.MagnetController import MagnetController
from PyQt5 import QtCore, QtWidgets, uic
import sys
import time
from os import listdir
from os.path import isfile, join
import numpy as np


class MagnetDriverUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(MagnetDriverUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(r'res\Magnet_driver_UI.ui', self)  # Load the .ui file
        self.show()
        print("MagnetDriverUI: Finding calibration files")
        if os.path.isfile('res/last_calibration_location.txt'):
            with open('res/last_calibration_location.txt', 'r') as file:
                self.calib_file_dir = file.readline()
        elif os.path.isdir("Coil Calibrations\\"):
            self.calib_file_dir = "Coil Calibrations\\"
            print('MagnetDriverUI:No calibration location found, trying: ', calib_file_dir)
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
        # self.button_calibration_directory.clicked.connect(self._on_calibration_directory)

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
