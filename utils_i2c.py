# -*- coding: utf-8 -*-
"""
Created on Sat Oct 15 10:51:49 2022

i2c utils

@author: chris
"""

import time
import board
from board import SCL, SDA
import busio

import smbus2

import utils
import debugging


# the channel for the mux board
# there are 8 available channels, write a single bit
# to the specific channel to switch it

# TODO: - compute this rather than pregenerate it ; it's not exactly the hardest binary math.
I2C_ch = [
    0b00000001,  # Channel 0 active
    0b00000010,  # Channel 1 active
    0b00000100,  # Channel 2 active
    0b00001000,  # Channel 3 active
    0b00010000,  # Channel 4 active
    0b00100000,  # Channel 5 active
    0b01000000,  # Channel 6 active
    0b10000000,  # Channel 7 active
]


class I2CBus:
    # the raspberry pi i2c bus number
    # This code is assuming we're on a raspberry PI ; and that we're using i2c bus 1
    #
    rpi_bus_number = 1

    # This is the default address of the TCA9548A multiplexer
    # The actual i2c address of the TCA9548a is set using the three address lines A0/A1/A2
    # on the chip. In a complex circuit these addresses can be changed dynamically.
    # Hard coding here for the default A0=A1=A2=0=GND
    # Not sure how valuable moving this to a configurable value would be
    multiplexer_address = 0x70

    bus = None
    i2c = None

    # Channels that are always on
    always_enabled = 0x0
    current_enabled = 0x0

    def __init__(self, conf):
        self.bus = smbus2.SMBus(self.rpi_bus_number)
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.i2c_mux_default()
        self.i2c_update()

    def i2c_exists(self, device_id):
        active_devices = self.i2c.scan()
        if device_id in active_devices:
            return True
        return False

    def set_always_on(self, channel_id):
        self.always_enabled = I2C_ch[channel_id]
        self.i2c_update()

    def add_always_on(self, channel_id):
        self.always_enabled = self.always_enabled & I2C_ch[channel_id]
        self.i2c_update()

    def clear_always_on(self):
        self.always_enabled = 0x0
        self.i2c_update()

    def i2c_mux_select(self, channel_id):
        # This switches to channel 1
        self.current_enabled = I2C_ch[channel_id]
        self.i2c_update()

    def i2c_mux_default(self):
        # This switches to channel 1
        # TODO: Need to only do this if we've confirmed a device at 0x70
        if self.i2c_exists(0x70):
            self.bus.write_byte(self.multiplexer_address, self.always_enabled)
            self.i2c_update()

    def i2c_update(self):
        try:
            self.bus.write_byte(self.multiplexer_address, self.always_enabled | self.current_enabled)
        except Exception as e:
            msg = "Error attempting to execute i2c_update"
            debugging.error(msg)
            debugging.error(e)
