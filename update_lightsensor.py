# -*- coding: utf-8 -*- #

# Update i2c attached devices


# RPI GPIO Pinouts reference
###########################
#    3V3  (1) (2)  5V     #
#  GPIO2  (3) (4)  5V     #
#  GPIO3  (5) (6)  GND    #
#  GPIO4  (7) (8)  GPIO14 #
#    GND  (9) (10) GPIO15 #
# GPIO17 (11) (12) GPIO18 #
# GPIO27 (13) (14) GND    #
# GPIO22 (15) (16) GPIO23 #
#    3V3 (17) (18) GPIO24 #
# GPIO10 (19) (20) GND    #
#  GPIO9 (21) (22) GPIO25 #
# GPIO11 (23) (24) GPIO8  #
#    GND (25) (26) GPIO7  #
#  GPIO0 (27) (28) GPIO1  #
#  GPIO5 (29) (30) GND    #
#  GPIO6 (31) (32) GPIO12 #
# GPIO13 (33) (34) GND    #
# GPIO19 (35) (36) GPIO16 #
# GPIO26 (37) (38) GPIO20 #
#    GND (39) (40) GPIO21 #
###########################


import time
import datetime


import debugging
import utils
import utils_i2c

from python_tsl2591 import tsl2591


class LightSensor:
    """Class to manage TSL2591 Light Sensors"""

    # Broad option 1 - TSL2591 Light Sensor
    # It will exist on a single i2c device id

    # Broad option 2 - TSL25xx family of sensors that may have a different i2c address

    # The i2c bus may be used to handle other devices ( oled / temp sensor etc. )
    # so operations on the i2c bus should be moved to a common i2c module.
    # Operations interacting with devices on the i2c bus should not assume that the bus
    # configuration is unchanged - and should also ensure that access does not lock out other
    # users of the bus

    tsl = None
    found_device = False
    LEDMgmt = None
    conf = None

    def __init__(self, conf, i2cbus, LEDMgmt):
        self.conf = conf
        self.found_device = False

        # FIXME: Very fragile - assumes existance of hardware

        # TODO: Get Light Sensor data from config
        i2cbus.set_always_on(7)  # Enable Channel 7
        if i2cbus.i2c_exists(0x29):  # Look for device ID hex(29)
            self.found_device = True
            self.tsl = tsl2591()  # initialize
            self.LEDMgmt = LEDMgmt
        else:
            self.found_device = False

    def update_loop(self, conf):
        outerloop = True  # Set to TRUE for infinite outerloop
        while outerloop:
            if not self.found_device:
                current_light = self.tsl.get_current()
                lux = current_light["lux"]
                if lux < 20:
                    lux = 20
                    if lux > 240:
                        lux = 240
                msg = "Setting light levels: " + str(lux)
                debugging.info(msg)
                self.LEDMgmt.set_brightness(lux)
                time.sleep(5)
            else:
                # No device found - longer sleeping
                debugging.info("No light sensor found - sleeping 10m")
                time.sleep(10 * 60)
