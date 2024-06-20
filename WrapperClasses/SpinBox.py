from PyQt5 import QtCore, QtWidgets


class SpinBox(QtWidgets.QDoubleSpinBox):
    stepChanged = QtCore.pyqtSignal()

    def __init__(self, min, max, step, val, decimals):
        super(SpinBox, self).__init__()
        self.setStyleSheet("background-color: rgb(255,255,255)")
        self.setMinimum(min)
        self.setMaximum(max)
        self.setSingleStep(step)
        self.setValue(val)
        self.setDecimals(decimals)

    def stepBy(self, step):
        value = self.value()
        super(SpinBox, self).stepBy(step)
        if self.value() != value:
            self.stepChanged.emit()
