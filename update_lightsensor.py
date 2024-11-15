# -*- coding: utf-8 -*- #
""" Manage TSL2591 i2c Light Sensors """

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

from python_tsl2591 import tsl2591

import random
import debugging


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
    led_mgmt = None
    conf = None

    def __init__(self, conf, i2cbus, led_mgmt):
        self.conf = conf
        self.found_device = False
        self.i2cbus = i2cbus
        self.led_mgmt = led_mgmt
        self.enable_i2c_device()

    def enable_i2c_device(self):
        """TSL2591 Device Enable"""
        # FIXME: Very fragile - assumes existance of hardware
        # TODO: Get Light Sensor data from config
        self.i2cbus.set_always_on(7)  # Enable Channel 7
        if self.i2cbus.i2c_exists(0x29):
            # Look for device ID hex(29)
            # Datasheet suggests this device also occupies addr 0x28
            self.found_device = True
            if self.i2cbus.bus_lock("enable_i2c_device"):
                self.tsl = tsl2591(i2c_bus=1)  # initialize
                self.tsl.set_timing(1)
                self.i2cbus.bus_unlock()
            # FIXME: This time interval should align to the thread cycle time
            # The current default interval is 60s
        else:
            self.found_device = False

    def update_loop(self, conf):
        """Thread Main Loop"""
        outerloop = True  # Set to TRUE for infinite outerloop
        current_light = None
        while outerloop:
            if self.found_device:
                if self.i2cbus.bus_lock("light sensor update loop"):
                    try:
                        current_light = self.tsl.get_current()
                    except OSError as err:
                        debugging.info(f"light sensor read failure: {err}")
                        # Try to rediscover the device on the i2c bus
                        # self.i2cbus.bus_unlock()
                        self.enable_i2c_device()
                    except Exception as e:
                        debugging.error(traceback.format_exc())
                    finally:
                        self.i2cbus.bus_unlock()
                if current_light is not None:
                    lux = current_light["lux"] * 2
                else:
                    lux = 250
                lux = max(lux, 20)
                lux = min(lux, 255)
                debugging.debug(f"Setting light levels: {lux}")
                self.led_mgmt.set_brightness(lux)
                sleep_interval = 5 + random.randint(0, 5)
                time.sleep(sleep_interval)
            else:
                # No device found - longer sleeping
                debugging.info(
                    "No light sensor found - trying to activate - then sleeping 10m"
                )
                self.enable_i2c_device()
                time.sleep(10 * 60)
