# -*- coding: utf-8 -*- #
""" Manage i2c Light Sensors """

# Update i2c attached devices
import time

from python_tsl2591 import tsl2591
import adafruit_veml7700
import traceback
import random

# from pytz.exceptions import NonExistentTimeError

import debugging


class LightSensor:
    """Class to manage Light Sensors"""

    # This started with support for the TSL2591 only.
    # It now supports either the TSL2591 or the VEML7700
    # It also assumes that these are directly on the I2C bus rather than being behind an I2C mux

    # TSL2591 Light Sensor - i2c device id (0x29)
    # VEML7700 Light Sensor - i2c device id (0x10)

    # Operations interacting with devices on the i2c bus should not assume that the bus
    # configuration is unchanged - and should also ensure that access does not lock out other
    # users of the bus

    found_device = False
    led_mgmt = None
    conf = None

    # Hardware Info
    sensor_device = False
    hardware_tsl2591 = False
    hardware_veml7700 = False

    # devices
    tsl = None
    dev_veml7700 = None

    def __init__(self, conf, i2cbus, led_mgmt):
        self.conf = conf
        self.found_device = False
        self.i2cbus = i2cbus
        self.led_mgmt = led_mgmt
        self.i2c_scan()
        # self.enable_i2c_device()

    def i2c_scan(self):
        self.sensor_device = False
        if self.i2cbus.i2c_exists(0x29):
            # Looks like TSL2591 device
            debugging.info("lightsensor: i2c scan sees TSL2591 type device")
            self.hardware_tsl2591 = True
            self.sensor_device = True
            self.activate_tsl2591()
        if self.i2cbus.i2c_exists(0x10):
            debugging.info("lightsensor: i2c scan sees VEML7700 type device")
            self.hardware_veml7700 = True
            self.sensor_device = True
            self.activate_veml7700()
        return

    def activate_veml7700(self):
        """VEML7700 Device Setup"""
        self.dev_veml7700 = adafruit_veml7700.VEML7700(self.i2cbus.i2cdevice())
        # Setting Gain to 2 and Integration time to 400ms
        self.dev_veml7700.light_gain = self.dev_veml7700.ALS_GAIN_2
        self.dev_veml7700.light_integration_time = self.dev_veml7700.ALS_400MS

    def activate_tsl2591(self):
        """TSL2591 Device Enable"""
        # FIXME: Remove assumption about device behind i2c mux once test lab hardware updated
        self.i2cbus.set_always_on(7)  # Enable Channel 7
        if self.i2cbus.i2c_exists(0x29):
            # Look for device ID hex(29)
            # Datasheet suggests this device also occupies addr 0x28
            self.found_device = True
            if self.i2cbus.bus_lock("enable_i2c_device"):
                self.tsl = tsl2591(self.i2cbus.i2cdevice())  # initialize
                self.tsl.set_timing(1)
                self.i2cbus.bus_unlock()
        else:
            self.found_device = False

    def read_tsl2591(self):
        """Read LUX value from tsl2591"""
        lux = 0
        if self.i2cbus.bus_lock("light sensor update loop : tsl2591"):
            try:
                lux = self.tsl.get_current()
            except OSError as err:
                debugging.info(f"tsl2591 light sensor read failure: {err}")
                self.i2c_scan()
                lux = 100
            except Exception as e:
                debugging.error(e)
                debugging.error(traceback.format_exc())
            finally:
                self.i2cbus.bus_unlock()
        lux = max(lux, 10)
        lux = min(lux, 255)
        return lux

    def read_veml7700(self):
        """Read LUX value from veml7700"""
        lux = 0
        if self.i2cbus.bus_lock("light sensor update loop : veml7700"):
            try:
                lux = self.dev_veml7700.lux
            except OSError as err:
                debugging.info(f"veml7700 light sensor read failure: {err}")
                self.i2c_scan()
                lux = 100
            except Exception as e:
                debugging.error(e)
                debugging.error(traceback.format_exc())
            finally:
                self.i2cbus.bus_unlock()
        debugging.debug(f"veml7700:raw {lux} lux")
        lux = max(lux, 10)
        lux = min(lux, 255)
        return lux

    def update_loop(self, conf):
        """Thread Main Loop"""
        self.conf = conf
        outerloop = True  # Set to TRUE for infinite outerloop
        lux = 250
        while outerloop:
            if (self.hardware_tsl2591 is False) and (self.hardware_veml7700 is False):
                debugging.info(
                    "No light sensor hardware found for tsl2591 and veml7700"
                )
            old_lux = lux
            old_lux_min = int(lux * 0.9)
            old_lux_max = int(lux * 1.1)
            if self.hardware_tsl2591:
                lux = self.read_tsl2591()
                debugging.debug(f"tsl2591 lux [{lux}]")
            if self.hardware_veml7700:
                lux = self.read_veml7700()
                debugging.debug(f"veml7700 lux [{lux}]")
            lux = round(lux, 0)
            if (lux < old_lux_min) or (lux > old_lux_max):
                debugging.info(f"Light sensor LUX change > 10%: {old_lux} -> {lux}")
            debugging.debug(f"Setting light levels: {lux}")
            self.led_mgmt.set_brightness(lux)
            sleep_interval = 5 + random.randint(0, 5)
            time.sleep(sleep_interval)
