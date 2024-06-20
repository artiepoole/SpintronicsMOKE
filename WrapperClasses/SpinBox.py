from PyQt5 import QtCore, QtWidgets


class DoubleSpinBox(QtWidgets.QDoubleSpinBox):
    stepChanged = QtCore.pyqtSignal()

    def __init__(self, old):
        super(DoubleSpinBox, self).__init__()
        self.setStyleSheet("background-color: rgb(255,255,255)")
        if old:
            self.setMinimum(old.minimum())
            self.setMaximum(old.maximum())
            self.setSingleStep(old.singleStep())
            self.setValue(old.value())
            self.setDecimals(old.decimals())

    def stepBy(self, step):
        value = self.value()
        super(DoubleSpinBox, self).stepBy(step)
        if self.value() != value:
            self.editingFinished.emit()

        print("name: ", self.objectName())

class SpinBox(QtWidgets.QSpinBox):
    stepChanged = QtCore.pyqtSignal()

    def __init__(self, old):
        super(SpinBox, self).__init__()
        self.setStyleSheet("background-color: rgb(255,255,255)")
        if old:
            self.setMinimum(old.minimum())
            self.setMaximum(old.maximum())
            self.setSingleStep(old.singleStep())
            self.setValue(old.value())

    def stepBy(self, step):
        value = self.value()
        super(SpinBox, self).stepBy(step)
        if self.value() != value:
            self.editingFinished.emit()
        print("name: ", self.objectName())
