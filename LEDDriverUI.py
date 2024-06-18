from WrapperClasses.LampController import LampController
from PyQt5 import QtCore, QtWidgets, uic
import sys
import time


class LEDDriverUI(QtWidgets.QMainWindow):
    """
    Standalone GUI for lighting control.
    """
    def __init__(self):
        super(LEDDriverUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(r'C:\Users\User\PycharmProjects\SpintronicsMOKE\res\LED_driver_UI.ui', self)  # Load the .ui file
        self.show()

        # Define enums
        self.led_binary_enum = {
            "left1": 2,
            "left2": 1,
            "right1": 8,
            "right2": 4,
            "up1": 32,
            "up2": 16,
            "down1": 128,
            "down2": 64}

        self.led_id_enum = {
            "left1": 2,
            "left2": 1,
            "right1": 4,
            "right2": 3,
            "up1": 6,
            "up2": 5,
            "down1": 8,
            "down2": 7}

        self.enabled_leds_spi = {"left1": False,
                                 "left2": False,
                                 "right1": False,
                                 "right2": False,
                                 "up1": False,
                                 "up2": False,
                                 "down1": False,
                                 "down2": False}

        self.LED_brightnesses = {"left1": 180,
                                 "left2": 180,
                                 "right1": 180,
                                 "right2": 180,
                                 "up1": 180,
                                 "up2": 180,
                                 "down1": 180,
                                 "down2": 180}

        self.enabled_led_pairs = {"left": False,
                                  "right": False,
                                  "up": False,
                                  "down": False}

        self.control_all = False

        # Connect Signals
        self.button_left_led1.clicked.connect(self.__on_individual_led)
        self.button_right_led1.clicked.connect(self.__on_individual_led)
        self.button_up_led1.clicked.connect(self.__on_individual_led)
        self.button_down_led1.clicked.connect(self.__on_individual_led)
        self.button_left_led2.clicked.connect(self.__on_individual_led)
        self.button_right_led2.clicked.connect(self.__on_individual_led)
        self.button_up_led2.clicked.connect(self.__on_individual_led)
        self.button_down_led2.clicked.connect(self.__on_individual_led)

        self.button_leds_off.clicked.connect(self.__disable_all_leds)

        self.button_long_pol.clicked.connect(self.__on_long_pol)
        self.button_trans_pol.clicked.connect(self.__on_trans_pol)
        self.button_polar.clicked.connect(self.__on_polar)

        self.button_control_all.clicked.connect(self.__on_control_change)
        self.button_reset_brightness.clicked.connect(self.__reset_brightness)
        self.scroll_LED_brightness.valueChanged.connect(self.__on_brightness_slider)
        self.scroll_LED_brightness.setSingleStep(-1)
        self.scroll_blocker = QtCore.QSignalBlocker(self.scroll_LED_brightness)
        self.scroll_blocker.unblock()

        # Start the LED control
        self.lamp_controller = LampController()
        self.lamp_controller.disable_all()

    def __reset_pairs(self):
        self.enabled_led_pairs.update(
            {"left": False,
             "right": False,
             "up": False,
             "down": False})

    def __reset_led_spis(self):
        self.enabled_leds_spi.update(
            {"left1": False,
             "left2": False,
             "right1": False,
             "right2": False,
             "up1": False,
             "up2": False,
             "down1": False,
             "down2": False}
        )

    def __reset_brightness(self):
        self.LED_brightnesses.update(
            {"left1": 180,
             "left2": 180,
             "right1": 180,
             "right2": 180,
             "up1": 180,
             "up2": 180,
             "down1": 180,
             "down2": 180}
        )
        self.lamp_controller.set_all_brightness(180)

    def __disable_all_leds(self):
        print("ArtieLabUI: Disabling all LEDs")
        self.__reset_led_spis()
        self.__reset_pairs()

        self.button_long_pol.setChecked(False)
        self.button_trans_pol.setChecked(False)
        self.button_polar.setChecked(False)

        self.button_up_led1.setChecked(False)
        self.button_up_led2.setChecked(False)
        self.button_down_led1.setChecked(False)
        self.button_down_led2.setChecked(False)
        self.button_left_led1.setChecked(False)
        self.button_left_led2.setChecked(False)
        self.button_right_led1.setChecked(False)
        self.button_right_led2.setChecked(False)

        self.__update_controller_pairs()

    def __on_individual_led(self, state):

        if self.__check_for_any_active_mode():
            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)
        self.__update_active_LEDs()
        self.__update_controller_spi()

    def __on_long_pol(self, checked):
        if checked:
            self.enabled_led_pairs.update(
                {"left": False,
                 "right": False,
                 "up": True,
                 "down": False})

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(True)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)

            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)

            self.__update_active_LEDs()
            self.__update_controller_pairs()
        else:
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

    def __on_trans_pol(self, checked):
        if checked:
            self.enabled_led_pairs.update({"left": True,
                                           "right": False,
                                           "up": False,
                                           "down": False})

            self.button_up_led1.setChecked(False)
            self.button_up_led2.setChecked(False)
            self.button_down_led1.setChecked(False)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(True)
            self.button_left_led2.setChecked(True)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)

            self.button_long_pol.setChecked(False)
            self.button_polar.setChecked(False)
            self.__update_active_LEDs()
            self.__update_controller_pairs()
        else:
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

    def __on_polar(self, checked):
        if checked:
            self.__reset_pairs()

            self.button_up_led1.setChecked(True)
            self.button_up_led2.setChecked(False)
            self.button_down_led1.setChecked(True)
            self.button_down_led2.setChecked(False)
            self.button_left_led1.setChecked(False)
            self.button_left_led2.setChecked(False)
            self.button_right_led1.setChecked(False)
            self.button_right_led2.setChecked(False)

            self.button_long_pol.setChecked(False)
            self.button_trans_pol.setChecked(False)
            self.__update_active_LEDs()
            self.__update_controller_spi()
        else:
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

    def __check_for_any_active_mode(self):
        return bool(
            self.button_long_pol.isChecked() +
            self.button_trans_pol.isChecked() +
            self.button_polar.isChecked()
        )

    def __update_active_LEDs(self):
        self.enabled_leds_spi["up1"] = self.button_up_led1.isChecked()
        self.enabled_leds_spi["up2"] = self.button_up_led2.isChecked()
        self.enabled_leds_spi["down1"] = self.button_down_led1.isChecked()
        self.enabled_leds_spi["down2"] = self.button_down_led2.isChecked()
        self.enabled_leds_spi["left1"] = self.button_left_led1.isChecked()
        self.enabled_leds_spi["left2"] = self.button_left_led2.isChecked()
        self.enabled_leds_spi["right1"] = self.button_right_led1.isChecked()
        self.enabled_leds_spi["right2"] = self.button_right_led2.isChecked()
        self.__update_brightness_slider()

    def __update_controller_pairs(self):
        self.lamp_controller.enable_assortment_pairs(self.enabled_led_pairs)

    def __update_controller_spi(self):
        keys = self.led_binary_enum.keys()
        value = 0
        for key in keys:
            value += self.led_binary_enum[key] * self.enabled_leds_spi[key]
        self.lamp_controller.enable_leds_using_SPI(value)

    def __on_control_change(self, control_all):
        self.control_all = control_all
        if self.control_all:
            self.button_control_all.setText("Control\nSelected")
        else:
            self.button_control_all.setText("Control\nAll")
        self.__update_brightness(180 - self.scroll_LED_brightness.value())

    def __on_brightness_slider(self, value):
        value = 180 - value
        print("Slider Value Changed to: ", value)
        self.__update_brightness(value)

    def __update_brightness_slider(self):
        if self.control_all:
            keys = self.LED_brightnesses.keys()
        else:
            keys = [key for key, value in self.enabled_leds_spi.items() if value is True]
        if keys:
            print(keys)
            brightest_val = max([self.LED_brightnesses[key] for key in keys])
            print("Brightest val: ", brightest_val)
            self.scroll_blocker.reblock()
            self.scroll_LED_brightness.setValue(180-brightest_val)
            self.scroll_blocker.unblock()
            self.__update_brightness(brightest_val)

    def __update_brightness(self, value):
        if self.control_all:
            keys = self.LED_brightnesses.keys()
        else:
            keys = [key for key, value in self.enabled_leds_spi.items() if value is True]
        if self.control_all:
            self.LED_brightnesses = {key: value for key in self.LED_brightnesses}
            self.lamp_controller.set_all_brightness(value)
        else:
            for key in keys:
                self.LED_brightnesses[key] = value
            self.lamp_controller.set_some_brightness([value] * len(keys), [self.led_id_enum[key] for key in keys])

    def closeEvent(self, event):
        self.lamp_controller.close(reset=True)
        print("LEDDriverUI: Closing threads and exiting")
        super(LEDDriverUI, self).closeEvent(event)
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
    window = LEDDriverUI()

    try:
        sys.exit(app.exec_())
    except:
        print("Exiting")
