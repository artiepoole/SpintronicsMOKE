from WrapperClasses.LampController import LampController
from PyQt5 import QtCore, QtWidgets, uic
import sys
import time


class LEDDriverUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(LEDDriverUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(r'C:\Users\User\PycharmProjects\SpintronicsMOKE\res\LED_driver_UI.ui', self)  # Load the .ui file
        self.show()

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
        self.enabled_brightness.update(
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
        self.enabled_leds_spi["up1"] = self.button_up_led1.isChecked()
        self.enabled_leds_spi["up2"] = self.button_up_led2.isChecked()
        self.enabled_leds_spi["down1"] = self.button_down_led1.isChecked()
        self.enabled_leds_spi["down2"] = self.button_down_led2.isChecked()
        self.enabled_leds_spi["left1"] = self.button_left_led1.isChecked()
        self.enabled_leds_spi["left2"] = self.button_left_led2.isChecked()
        self.enabled_leds_spi["right1"] = self.button_right_led1.isChecked()
        self.enabled_leds_spi["right2"] = self.button_right_led2.isChecked()
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
            self.__update_active_LEDs()

            self.button_trans_pol.setChecked(False)
            self.button_polar.setChecked(False)

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

            self.__update_active_LEDs()

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

            self.__update_controller_pairs()
        else:
            if not self.__check_for_any_active_mode():
                self.__disable_all_leds()

    def __on_polar(self, checked):
        if checked:
            self.enabled_leds_spi.update(
                {"left1": False,
                 "left2": False,
                 "right1": False,
                 "right2": False,
                 "up1": True,
                 "up2": False,
                 "down1": True,
                 "down2": False})

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

    def __get_active_LEDs(self):
        self.__update_active_LEDs()
        return [key for key, value in self.enabled_leds_spi if value is True]

    def __update_controller_pairs(self):
        self.lamp_controller.enable_assortment_pairs(self.enabled_led_pairs)

    def __update_controller_spi(self):
        # I assumed the numbering would go outside then inside, but it goes inside then outside
        value = self.enabled_leds_spi["left1"] * 2 \
                + self.enabled_leds_spi["left2"] * 1 \
                + self.enabled_leds_spi["right1"] * 8 \
                + self.enabled_leds_spi["right2"] * 4 \
                + self.enabled_leds_spi["up1"] * 32 \
                + self.enabled_leds_spi["up2"] * 16 \
                + self.enabled_leds_spi["down1"] * 128 \
                + self.enabled_leds_spi["down2"] * 64
        self.lamp_controller.enable_leds(value)

    def __on_control_change(self, control_all):
        self.control_all = control_all
        if self.control_all:
            self.button_control_all.setText("Control\nSelected")
        else:
            self.button_control_all.setText("Control\nAll")
        self.__update_brightness()

    def __on_brightness_slider(self, value):
        self.__update_brightness(value)

    def __update_brightness(self, value=None):
        if value is None:
            value = self.scroll_LED_brightness.value()
        if self.control_all:
            brightest_val = max(self.LED_brightnesses.values())
            if value != brightest_val:
                print("Changing slider")
                self.scroll_LED_brightness.setValue(brightest_val)
            self.LED_brightnesses = {key: value for key in self.LED_brightnesses}
            self.lamp_controller.set_all_brightness(brightest_val)


    def closeEvent(self, event):
        self.close_event = event
        # time.sleep(0.1)
        self.lamp_controller.close()
        print("LEDDriverUI: Closing threads and exiting")
        super(LEDDriverUI, self).closeEvent(self.close_event)
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
