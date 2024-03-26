from WrapperClasses.LampController import LampController
from PyQt5 import QtCore, QtWidgets, uic
import sys
import time


class LEDDriverUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(LEDDriverUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(r'C:\Users\User\PycharmProjects\SpintronicsMOKE\res\ArtieLab.ui', self)  # Load the .ui file
        self.show()

        self.button_left_led.toggled.connect(self.__on_left)
        self.button_right_led.toggled.connect(self.__on_right)
        self.button_up_led.toggled.connect(self.__on_up)
        self.button_down_led.toggled.connect(self.__on_down)
        self.button_long_pol.clicked.connect(self.__on_long_pol)
        self.button_trans_pol.clicked.connect(self.__on_trans_pol)
        self.button_polar.clicked.connect(self.__on_polar)
        self.button_long_trans.clicked.connect(self.__on_long_trans)
        self.button_pure_long.clicked.connect(self.__on_pure_long)
        self.button_pure_trans.clicked.connect(self.__on_pure_trans)

        self.button_left_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')
        self.button_right_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')
        self.button_up_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')
        self.button_down_led.setStyleSheet('QRadioButton::indicator { width: 50px; height: 50px;}')



        self.controller = LampController()
        self.controller.disable_all()
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False

    def __on_up(self, state):
        self.__up = state
        self.__update_controller()

    def __on_down(self, state):
        self.__down = state
        self.__update_controller()

    def __on_left(self, state):
        self.__left = state
        self.__update_controller()

    def __on_right(self, state):
        self.__right = state
        self.__update_controller()

    def __on_long_pol(self):
        self.__up = True
        self.__down = False
        self.__left = False
        self.__right = False
        self.button_up_led.setChecked(True)
        self.button_down_led.setChecked(False)
        self.button_left_led.setChecked(False)
        self.button_right_led.setChecked(False)
        self.__update_controller()

    def __on_trans_pol(self):
        self.__up = False
        self.__down = False
        self.__left = True
        self.__right = False
        self.button_up_led.setChecked(False)
        self.button_down_led.setChecked(False)
        self.button_left_led.setChecked(True)
        self.button_right_led.setChecked(False)
        self.__update_controller()

    def __on_polar(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print("Sorry, this feature is not available. Can't select individual channels yet for some reason, only pairs.")
        self.__update_controller()

    def __on_long_trans(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print("Flashing Feature Not Implemented Yet....")
        self.__update_controller()

    def __on_pure_long(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print("Flashing Feature Not Implemented Yet....")
        self.__update_controller()

    def __on_pure_trans(self):
        self.__up = False
        self.__down = False
        self.__left = False
        self.__right = False
        print("Flashing Feature Not Implemented Yet....")
        self.__update_controller()

    def __update_controller(self):
        self.controller.enable_assortment_pairs(self.__left, self.__right, self.__up, self.__down)

    def closeEvent(self, event):
        self.close()

    def close(self):
        self.controller.disable_all()
        time.sleep(0.1)
        self.controller.close()

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
    window = LEDDriverUI()

    try:
        sys.exit(app.exec_())
    except:
        print("Exiting")
