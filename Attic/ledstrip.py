# -*- coding: utf-8 -*- #
"""
Created on Jan 01 2021

@author: Chris Higgins
"""
import time
import datetime
import math

# from rpi_ws281x import ws, Color, Adafruit_NeoPixel
# import neopixel

from enum import Enum

import board
from rpi_ws281x import (
    Color,
    PixelStrip,
    ws,
)  # works with python 3.7. sudo pip3 install rpi_ws281x

import random
import debugging


class LedStrip:
    """
    Class to manage a NeoPixel Strip
    """

    # Colors ( GREEN, RED, BLUE )
    BLACK = (0, 0, 0)  # Black
    GRAY = (128, 128, 128)  # Gray
    BROWN = (42, 165, 42)  # Brown
    RED = (0, 255, 0)  # Red
    ROSE = (0, 255, 128)  # Rose (Red)
    MAGENTA = (0, 255, 255)  # Magenta
    PURPLE = (0, 128, 128)  # Purple
    VIOLET = (0, 128, 255)  # Violet
    PINK = (192, 255, 203)  # Pink
    HOTPINK = (105, 255, 180)  # Hotpink
    BLUE = (0, 0, 255)  # Blue
    NAVY = (0, 0, 128)  # Navy
    AZURE = (128, 0, 255)  # Azure
    CYAN = (255, 0, 255)  # Cyan
    DKCYAN = (139, 0, 139)  # Dark Cyan
    SPGREEN = (255, 0, 127)  # Spring Green
    DKGREEN = (100, 0, 0)  # Dark Green
    GREEN = (255, 0, 0)  # Green
    CHUSE = (255, 128, 0)  # Chartreuse
    YELLOW = (255, 255, 0)  # Yellow
    ORANGE = (165, 255, 0)  # Orange
    GOLD = (215, 255, 0)  # Gold
    WHITE = (255, 255, 255)  # White

    # Airport Color Codes
    WX_VFR = 1
    WX_MVFR = 2
    WX_IFR = 3
    WX_LIFR = 4
    WX_UNKN = 5
    WX_OLD = 6

    def __init__(self, conf, pixelcount):
        """Init object and set initial values for internals"""
        self.conf = conf
        self._leds = None
        self._pixelcount = pixelcount
        #        self.pin = board.D18
        self.nullpins = {}
        self.pin = 18
        self.freq = 800000
        self.dma = 10
        self._brightness = 255
        self.channel = 0
        self.update_counter = 0
        self._enabled = True
        self._strip = None
        self.gamma = None
        # Airport LED Weather Data
        self.airport_weathercode = {}
        self.airport_basecolor = {}
        self.airport_ledstate = {}
        self.airport_index = {}

        # LED Wait Interval
        self.wait = self.conf.get_string("rotaryswitch", "wait")

        # Wipe number of times to execute a particular wipe
        self.num_radar = self.conf.get_string("rotaryswitch", "num_radar")
        self.num_allsame = self.conf.get_string("rotaryswitch", "num_allsame")
        self.num_circle = self.conf.get_string("rotaryswitch", "num_circle")
        self.num_square = self.conf.get_string("rotaryswitch", "num_square")
        self.num_updn = self.conf.get_string("rotaryswitch", "num_updn")
        self.num_rainbow = self.conf.get_string("rotaryswitch", "num_rainbow")
        self.num_fade = self.conf.get_string("rotaryswitch", "num_fade")
        self.num_shuffle = self.conf.get_string("rotaryswitch", "num_shuffle")
        self.num_morse = self.conf.get_string("rotaryswitch", "num_morse")
        self.num_rabbit = self.conf.get_string("rotaryswitch", "num_rabbit")
        self.num_checker = self.conf.get_string("rotaryswitch", "num_checker")

        # Wipe Colors - either random colors or specify an on and off color for each wipe.
        self.rand = self.conf.get_string(
            "rotaryswitch", "rand"
        )  # 0 = No, 1 = Yes, Randomize the colors used in wipes
        self.black_color = (0, 0, 0)
        self.radar_color1 = self.conf.get_string("colors", "radar_color1")
        self.radar_color2 = self.conf.get_string("colors", "radar_color2")
        self.allsame_color1 = self.conf.get_string("colors", "allsame_color1")
        self.allsame_color2 = self.conf.get_string("colors", "allsame_color2")
        self.circle_color1 = self.conf.get_string("colors", "circle_color1")
        self.circle_color2 = self.conf.get_string("colors", "circle_color2")
        self.square_color1 = self.conf.get_string("colors", "square_color1")
        self.square_color2 = self.conf.get_string("colors", "square_color2")
        self.updn_color1 = self.conf.get_string("colors", "updn_color1")
        self.updn_color2 = self.conf.get_string("colors", "updn_color2")
        self.fade_color1 = self.conf.get_string("colors", "fade_color1")
        self.shuffle_color1 = self.conf.get_string("colors", "shuffle_color1")
        self.shuffle_color2 = self.conf.get_string("colors", "shuffle_color2")
        self.morse_color1 = self.conf.get_string("colors", "morse_color1")
        self.morse_color2 = self.conf.get_string("colors", "morse_color2")
        self.rabbit_color1 = self.conf.get_string("colors", "rabbit_color1")
        self.rabbit_color2 = self.conf.get_string("colors", "rabbit_color2")
        self.checker_color1 = self.conf.get_string("colors", "checker_color1")
        self.checker_color2 = self.conf.get_string("colors", "checker_color2")

        # List definitions
        self.ap_id = []  # Airport ID List. Used for screen wipes
        self.latlist = []  # Latitude of airport. Used for screen wipes
        self.lonlist = []  # Longitude of airport. Used for screen wipes

        # Dictionary definitions.
        self.stationiddict = {}
        self.latdict = {}  # airport id and its latitude
        self.londict = {}  # airport id and its longitude
        self.pindict = {}  # Stores airport id and led pin number
        self.apinfodict = (
            {}
        )  # Holds pin num as key and a list to include [airport id, lat, lon]

        self.rev_rgb_grb = {}
        self.rgb_grb = 0
        self.sizelat = 0

        # Morse Code Dictionary
        self.CODE = {
            "A": ".-",
            "B": "-...",
            "C": "-.-.",
            "D": "-..",
            "E": ".",
            "F": "..-.",
            "G": "--.",
            "H": "....",
            "I": "..",
            "J": ".---",
            "K": "-.-",
            "L": ".-..",
            "M": "--",
            "N": "-.",
            "O": "---",
            "P": ".--.",
            "Q": "--.-",
            "R": ".-.",
            "S": "...",
            "T": "-",
            "U": "..-",
            "V": "...-",
            "W": ".--",
            "X": "-..-",
            "Y": "-.--",
            "Z": "--..",
            "1": ".----",
            "2": "..---",
            "3": "...--",
            "4": "....-",
            "5": ".....",
            "6": "-....",
            "7": "--...",
            "8": "---..",
            "9": "----.",
            "0": "-----",
            ", ": "--..--",
            ".": ".-.-.-",
            "?": "..--..",
            "/": "-..-.",
            "-": "-....-",
            "(": "-.--.",
            ")": "-.--.-",
        }

        # Create an instance of NeoPixel
        # strip = Adafruit_NeoPixel(LED_COUNT, self.led_pin, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, LED_STRIP)
        # self._leds.begin()

        # Bright light will provide a low state (0) on GPIO. Dark light will provide a high state (1).
        # Full brightness will be used if no light sensor is installed.
        # if GPIO.input(4) == 1:
        #    LED_BRIGHTNESS = self.conf.get_string("lights", "dimmed_value")
        # else:
        #    LED_BRIGHTNESS = self.conf.get_string("lights", "bright_value")
        # self._leds.setBrightness(LED_BRIGHTNESS)

    def start(self):
        """Initialize LED string"""
        self._leds = PixelStrip(
            self._pixelcount,
            self.pin,
            freq_hz=self.freq,
            dma=self.dma,
            invert=False,
            brightness=self._brightness,
            channel=self.channel,
            strip_type=self._strip,
            gamma=self.gamma,
        )
        self._leds.begin()

    def colorcode(self, color):
        """Convert (RGB) color code to Color datatype"""
        return Color(color[0], color[1], color[2])

    def brightness(self):
        """Current Brightness"""
        return self._brightness

    def setbrightness(self, brightness):
        """Current Brightness"""
        self._brightness = brightness
        self._leds.setBrightness(self._brightness)

    def count(self):
        """Get Current METAR"""
        return self._pixelcount

    def fill(self, color):
        """Iterate across all pixels and set to single color"""
        for i in range(0, self._pixelcount):
            self.setpixcolor(i, color)
        return

    def setpixcolor(self, index, color):
        """Set color of individual pixel"""
        self._leds.setPixelColor(index, self.colorcode(color))

    def blackout(self):
        """Set color to Black (0,0,0)"""
        self.fill((0, 0, 0))
        self._leds.show()

    def setLedState(self, ledindex, status, color):
        """Setup individual LED status"""
        if status is True:
            self._enabled = True
            self.setpixcolor(ledindex, color)
            self._leds.show()
        else:
            self._enabled = False
            self.setpixcolor(ledindex, self.BLACK)
            self._leds.show()
