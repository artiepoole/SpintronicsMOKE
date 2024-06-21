import sys
from collections import deque
from datetime import datetime
from pathlib import Path

import pandas as pd
import tifffile
from PyQt5 import uic
import cv2
import os
import pyqtgraph as pg

from SweeperUIs import AnalyserSweepDialog, FieldSweepDialog

os.add_dll_directory(r"C:\Program Files\JetBrains\CLion 2024.1.1\bin\mingw\bin")
from CImageProcessing import integer_mean
from WrapperClasses import *

import os.path
from os import listdir
from os.path import isfile, join
import sys

import numpy as np
from PyQt5 import QtCore, QtWidgets, uic, QtGui

import logging
from logging.handlers import RotatingFileHandler


class SpinBox(QtWidgets.QSpinBox):
    stepChanged = QtCore.pyqtSignal()

    def stepBy(self, step):
        value = self.value()
        super(SpinBox, self).stepBy(step)
        if self.value() != value:
            self.stepChanged.emit()


class ui(QtWidgets.QMainWindow):
    def __init__(self):
        # Loads the UI file and sets it to full screen
        super(ui, self).__init__()
        uic.loadUi('testing_spin_ui.ui', self)
        self.layout1.removeWidget(self.spin)
        self.spin.close()
        self.spin = SpinBox()
        self.layout1.addWidget(self.spin)
        self.spin.editingFinished.connect(self.myfinished)
        self.spin.stepChanged.connect(self.myfinished)
        self.show()
        self.activateWindow()
    # def eventFilter(self, source, event):
    #     if source is self.spin:
    #         match event.type():
    #             case QtCore.QEvent.MouseButtonRelease:
    #                 self.myfinished()
    #                 print("mouse event")
    #                 super(ui, self).eventFilter(source, event)
    #             case 31:
    #                 if "QWheelEvent" in str(type(event)):
    #                     super(ui, self).eventFilter(source, event)
    #                     self.myfinished()
    #                     # lags by one change
    #
    #                     print("scroll event")
    #
    #     return super(ui, self).eventFilter(source, event)

    @QtCore.pyqtSlot()
    def myfinished(self):
        print(f"value change detected. New Value: {self.spin.value()}")


if __name__ == '__main__':
    """
    Runs the GUI and sets up error catching so that errors caused by other threads can sometimes be printed instead of 
    just giving an OS error.
    """
    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook


    def my_exception_hook(exctype, value, traceback):
        # Print the error and traceback
        print("__main__:", exctype, value, traceback)
        # Call the normal Exception hook after
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)


    # Set the exception hook to our wrapping function
    sys.excepthook = my_exception_hook

    app = QtWidgets.QApplication(sys.argv)

    app.setStyle('plastique')
    window = ui()
    try:
        sys.exit(app.exec_())
    except:
        print("__main__: Exiting")
    print(app.exit())
