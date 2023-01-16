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


# Application local imports
import update_airports
import airport

import random

import debugging

"""
LED Strip Configuration Data
LED_COUNT = settings.get('ledstring', 'count')
self.led_pin = board.D18
LED_FREQ_HZ = 800000
LED_DMA = 5
LED_BRIGHTNESS = 255
LED_INVERT = False
LED_CHANNEL = 0
LED_STRIP = ws.WS2811_STRIP_GRB
"""


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
        self.leds = None
        self.pixelcount = pixelcount
        #        self.pin = board.D18
        self.nullpins = {}
        self.pin = 18
        self.freq = 800000
        self.dma = 10
        self.brightness = 255
        self.channel = 0
        self.update_counter = 0
        self.enabled = True
        self.strip = None
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
        # self.leds.begin()

        # Bright light will provide a low state (0) on GPIO. Dark light will provide a high state (1).
        # Full brightness will be used if no light sensor is installed.
        # if GPIO.input(4) == 1:
        #    LED_BRIGHTNESS = self.conf.get_string("lights", "dimmed_value")
        # else:
        #    LED_BRIGHTNESS = self.conf.get_string("lights", "bright_value")
        # self.leds.setBrightness(LED_BRIGHTNESS)

    def start(self):
        """Initialize LED string"""
        self.leds = PixelStrip(
            self.pixelcount,
            self.pin,
            freq_hz=self.freq,
            dma=self.dma,
            invert=False,
            brightness=self.brightness,
            channel=self.channel,
            strip_type=self.strip,
            gamma=self.gamma,
        )
        self.leds.begin()

    def colorcode(self, color):
        """Convert (RGB) color code to Color datatype"""
        return Color(color[0], color[1], color[2])

    def getbrightness(self):
        """Current Brightness"""
        return self.brightness

    def setbrightness(self, brightness):
        """Current Brightness"""
        self.brightness = brightness
        self.leds.setBrightness(self.brightness)

    def count(self):
        """Get Current METAR"""
        return self.pixelcount

    def fill(self, color):
        """Iterate across all pixels and set to single color"""
        for i in range(0, self.pixelcount):
            self.setpixcolor(i, color)
        return

    def setpixcolor(self, index, color):
        """Set color of individual pixel"""
        self.leds.setPixelColor(index, self.colorcode(color))

    def colorwipe(self):
        """Run a color wipe test"""
        self.fill(self.RED)
        self.leds.show()
        time.sleep(2)
        self.fill(self.GREEN)
        self.leds.show()
        time.sleep(2)
        self.fill(self.BLUE)
        self.leds.show()
        time.sleep(2)

    def blackout(self):
        """Set color to Black (0,0,0)"""
        self.fill((0, 0, 0))
        self.leds.show()

    def selftest(self):
        """Run through self test process to enable all LEDs and
        then turn them off"""
        self.colorwipe()
        time.sleep(1)
        self.blackout()

    def setLedState(self, ledindex, status, color):
        """Setup individual LED status"""
        if status is True:
            self.enabled = True
            self.setpixcolor(ledindex, color)
            self.leds.show()
        else:
            self.enabled = False
            self.setpixcolor(ledindex, self.BLACK)
            self.leds.show()

    def getWxColor(self, weathercode, timeslice):
        """For a specific weather code and timeslice, work out
        the appropriate color"""
        wxcolor = self.HOTPINK
        if weathercode == self.WX_UNKN:
            wxcolor = self.WHITE
        if weathercode == self.WX_MVFR:
            wxcolor = self.BLUE
        if weathercode == self.WX_IFR:
            wxcolor = self.RED
        if weathercode == self.WX_LIFR:
            wxcolor = self.MAGENTA
        if weathercode == self.WX_VFR:
            wxcolor = self.GREEN
        if weathercode == self.WX_OLD:
            wxcolor = self.YELLOW
        if timeslice == 1:
            #
            return wxcolor
        return wxcolor

    def setBaseColor(self):
        for key in self.airport_weathercode:
            debugging.debug("Set base color for Airport : %s" % key)
            self.airport_basecolor[key] = self.getWxColor(self.airport_weathercode, 1)
        return

    def updateLedState(self, led_slice):
        for key in self.airport_weathercode:
            debugging.debug("LED Update for %s" % key)
            self.airport_ledstate[key] = self.getWxColor(
                self.airport_weathercode, led_slice
            )
            self.setpixcolor(self.airport_index[key], self.airport_ledstate[key])
        return

    def setLedAirportWeather(self, airportdb, key):
        """Record the intended color state for the Airport"""
        airportcode = airportdb[key].icaocode()
        self.airport_index[key] = airportdb[key].led_index
        if not airportcode in self.airport_weathercode:
            # Initialize to UNKN if airport doesn't already exist
            self.airport_weathercode[airportcode] = self.WX_UNKN
        if airportdb[key].wx_category == airport.AirportFlightCategory.MVFR:
            self.airport_weathercode[airportcode] = self.WX_MVFR
        if airportdb[key].wx_category == airport.AirportFlightCategory.VFR:
            self.airport_weathercode[airportcode] = self.WX_VFR
        if airportdb[key].wx_category == airport.AirportFlightCategory.IFR:
            self.airport_weathercode[airportcode] = self.WX_IFR
        if airportdb[key].wx_category == airport.AirportFlightCategory.LIFR:
            self.airport_weathercode[airportcode] = self.WX_LIFR
        if airportdb[key].wx_category == airport.AirportFlightCategory.OLD:
            self.airport_weathercode[airportcode] = self.WX_OLD
        if airportdb[key].wx_category == airport.AirportFlightCategory.UNKN:
            self.airport_weathercode[airportcode] = self.WX_UNKN
        debugging.debug(
            "Airport WX Code : %s : " % self.airport_weathercode[airportcode]
        )
        return

    #    Includes the following patterns;
    #       Rainbow
    #       Square
    #       Circle
    #       Radar
    #       Up/Down and Side to Side
    #       All One Color
    #       Fader
    #       Shuffle
    #       Morse Code
    #       Rabbit Chase
    #       Checkerbox
    #
    #    Fixed wipes that turned on NULL and LGND Leds
    #    Fixed dimming feature when a wipe is executed
    #    Fixed bug whereby lat/lon was miscalculated for certain wipes.

    # Functions
    # Rainbow Animation functions - taken from https://github.com/JJSilva/NeoSectional/blob/master/metar.py
    def wheel(self, pos):
        """Generate rainbow colors across 0-255 positions."""
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return Color(0, pos * 3, 255 - pos * 3)

    def rainbowCycle(self, led_indexations, wait=0.1):
        """Draw rainbow that uniformly distributes itself across all pixels."""
        for j in range(256 * led_indexations):
            for led_index in range(self.leds.numPixels()):
                if (
                    str(led_index) in self.nullpins
                ):  # exclude NULL and LGND pins from wipe
                    self.leds.setPixelColor(led_index, Color(0, 0, 0))
                else:
                    self.leds.setPixelColor(
                        led_index,
                        self.wheel(
                            (int(led_index * 256 / self.leds.numPixels()) + j) & 255
                        ),
                    )
            self.leds.show()
            time.sleep(wait / 100)

    # Generate random RGB color
    def randcolor(self):
        r = int(random.randint(0, 255))
        g = int(random.randint(0, 255))
        b = int(random.randint(0, 255))
        return (r, g, b)

    # Change color code to work with various led strips. For instance, WS2812 model strip uses RGB where WS2811 model uses GRB
    # Set the "rgb_grb" user setting above. 1 for RGB LED strip, and 0 for GRB self.leds.
    # If necessary, populate the list rev_rgb_grb with pin numbers of LED's that use the opposite color scheme.
    def rgbtogrb_wipes(self, led_index, data, order=0):
        if (
            str(led_index) in self.rev_rgb_grb
        ):  # This accommodates the use of both models of LED strings on one map.
            order = not order
            debugging.debug(
                "Reversing rgb2grb Routine Output for LED PIN " + str(led_index)
            )

        red = data[0]
        grn = data[1]
        blu = data[2]

        if order:
            data = [red, grn, blu]
        else:
            data = [grn, red, blu]

        xcolor = Color(data[0], data[1], data[2])
        return xcolor

    # range to loop through floats, rather than integers. Used to loop through lat/lons.
    def frange(self, start, stop, step):
        if start != stop:
            i = start
            if i < stop:
                while i < stop:
                    yield round(i, 2)
                    i += step
            else:
                while i > stop:
                    yield round(i, 2)
                    i -= step

    # Wipe routines based on Lat/Lons of airports on map.
    # Need to pass name of dictionary with coordinates, either latdict or londict
    # Also need to pass starting value and ending values to led_indexate through. These are floats for Lat/Lon. ie. 36.23
    # Pass Step value to led_indexate through the values provided in start and end. Typically needs to be .01
    # pass the start color and ending color. Pass a wait time or delay, ie. .01
    def wipe(self, dict_name, start, end, step, color1, color2, wait_mult):
        # Need to find duplicate values (lat/lons) from dictionary using flip technique
        flipped = {}
        for key, value in list(
            dict_name.items()
        ):  # create a dict where keys and values are swapped
            if value not in flipped:
                flipped[value] = [key]
            else:
                flipped[value].append(key)

        for i in self.frange(start, end, step):
            key = str(i)

            if key in flipped:  # Grab latitude from dict
                num_elem = len(flipped[key])  # Determine the number of duplicates

                for j in range(
                    num_elem
                ):  # loop through each duplicate to get led number
                    key_id = flipped[key][j]
                    led_index = self.ap_id.index(
                        key_id
                    )  # Assign the pin number to the led to turn on/off

                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    self.leds.setPixelColor(led_index, color)
                    self.leds.show()
                    time.sleep(self.wait * wait_mult)

                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.leds.setPixelColor(led_index, color)
                    self.leds.show()
                    time.sleep(self.wait * wait_mult)

    # Circle wipe
    def circlewipe(self, minlon, minlat, maxlon, maxlat, color1, color2):
        rad_inc = 4
        rad = rad_inc

        sizelat = round(abs(maxlat - minlat), 2)  # height of box
        sizelon = round(abs(maxlon - minlon), 2)  # width of box

        centerlat = round(sizelat / 2 + minlat, 2)  # center y coord of box
        centerlon = round(sizelon / 2 + minlon, 2)  # center x coord of box

        circle_x = centerlon
        circle_y = centerlat

        led_index = int(
            self.sizelat / rad_inc
        )  # attempt to figure number of led_indexations necessary to cover whole map

        for j in range(led_index):
            for key in self.apinfodict:
                x = float(self.apinfodict[key][2])
                y = float(self.apinfodict[key][1])
                led_index = int(self.apinfodict[key][0])

                if (x - circle_x) * (x - circle_x) + (y - circle_y) * (
                    y - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                else:
                    #               print("Outside")
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                self.leds.setPixelColor(led_index, color)
                self.leds.show()
                time.sleep(self.wait)
            rad = rad + rad_inc

        for j in range(led_index):
            rad = rad - rad_inc
            for key in self.apinfodict:
                x = float(self.apinfodict[key][2])
                y = float(self.apinfodict[key][1])
                led_index = int(self.apinfodict[key][0])

                if (x - circle_x) * (x - circle_x) + (y - circle_y) * (
                    y - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                else:
                    #               print("Outside")
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                self.leds.setPixelColor(led_index, color)
                self.leds.show()
                time.sleep(self.wait)

        self.allonoff_wipes((0, 0, 0), 0.1)

    # radar wipe - Needs area calc routines to determine areas of triangles
    def area(self, x1, y1, x2, y2, x3, y3):
        return abs((x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0)

    def isInside(self, x1, y1, x2, y2, x3, y3, x, y):
        # Calculate area of triangle ABC
        A = self.area(x1, y1, x2, y2, x3, y3)
        # Calculate area of triangle PBC
        A1 = self.area(x, y, x2, y2, x3, y3)
        # Calculate area of triangle PAC
        A2 = self.area(x1, y1, x, y, x3, y3)
        # Calculate area of triangle PAB
        A3 = self.area(x1, y1, x2, y2, x, y)
        # Check if sum of A1, A2 and A3 is same as A

        if ((A1 + A2 + A3) - 1) >= A <= ((A1 + A2 + A3) + 1):
            return True
        else:
            return False

    def radarwipe(
        self,
        centerlat,
        centerlon,
        led_index,
        color1,
        color2,
        sweepwidth=175,
        radius=50,
        angleinc=0.05,
    ):
        PI = 3.141592653
        angle = 0

        for k in range(led_index):
            # Calculate the x1,y1 for the end point of our 'sweep' based on
            # the current angle. Then do the same for x2,y2
            x1 = round(radius * math.sin(angle) + centerlon, 2)
            y1 = round(radius * math.cos(angle) + centerlat, 2)
            x2 = round(radius * math.sin(angle + sweepwidth) + centerlon, 2)
            y2 = round(radius * math.cos(angle + sweepwidth) + centerlat, 2)

            for key in self.apinfodict:
                px1 = float(self.apinfodict[key][2])  # Lon
                py1 = float(self.apinfodict[key][1])  # Lat
                led_index = int(self.apinfodict[key][0])  # LED Pin Num
                #           print (centerlon, centerlat, x1, y1, x2, y2, px1, py1, pin) #debug

                if self.isInside(centerlon, centerlat, x1, y1, x2, y2, px1, py1):
                    #               print('Inside')
                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    self.leds.setPixelColor(led_index, color)
                else:
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.leds.setPixelColor(led_index, color)
            #               print('Not Inside')
            self.leds.show()
            time.sleep(self.wait)

            # Increase the angle by angleinc radians
            angle = angle + angleinc

            # If we have done a full sweep, reset the angle to 0
            if angle > 2 * PI:
                angle = angle - (2 * PI)

    # Square wipe
    # findpoint in a given rectangle or not.   Example -114.87, 37.07, -109.07, 31.42, -114.4, 32.87
    def findpoint(self, x1, y1, x2, y2, x, y):
        if x > x1 and x < x2 and y > y1 and y < y2:
            return True
        else:
            return False

    def center(self, max_a, min_a):
        z = ((max_a - min_a) / 2) + min_a
        return round(z, 2)

    def squarewipe(
        self,
        minlon,
        minlat,
        maxlon,
        maxlat,
        led_index,
        color1,
        color2,
        step=0.5,
        wait_mult=10,
    ):
        declon = minlon
        declat = minlat
        inclon = maxlon
        inclat = maxlat
        centlon = self.center(maxlon, minlon)
        centlat = self.center(maxlat, minlat)

        for j in range(led_index):
            for inclon in self.frange(maxlon, centlon, step):
                # declon, declat = Upper Left of box.
                # inclon, inclat = Lower Right of box
                for key in self.apinfodict:
                    px1 = float(self.apinfodict[key][2])  # Lon
                    py1 = float(self.apinfodict[key][1])  # Lat
                    led_index = int(self.apinfodict[key][0])  # LED Pin Num

                    #                print((declon, declat, inclon, inclat, px1, py1)) #debug
                    if self.findpoint(declon, declat, inclon, inclat, px1, py1):
                        #                    print('Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    else:
                        #                    print('Not Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                    self.leds.setPixelColor(led_index, color)

                inclat = round(inclat - step, 2)
                declon = round(declon + step, 2)
                declat = round(declat + step, 2)

                self.leds.show()
                time.sleep(self.wait * wait_mult)

            for inclon in self.frange(centlon, maxlon, step):
                # declon, declat = Upper Left of box.
                # inclon, inclat = Lower Right of box
                for key in self.apinfodict:
                    px1 = float(self.apinfodict[key][2])  # Lon
                    py1 = float(self.apinfodict[key][1])  # Lat
                    led_index = int(self.apinfodict[key][0])  # LED Pin Num

                    #                print((declon, declat, inclon, inclat, px1, py1)) #debug
                    if self.findpoint(declon, declat, inclon, inclat, px1, py1):
                        #                    print('Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    else:
                        #                   print('Not Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                    self.leds.setPixelColor(led_index, color)

                inclat = round(inclat + step, 2)
                declon = round(declon - step, 2)
                declat = round(declat - step, 2)

                self.leds.show()
                time.sleep(self.wait * wait_mult)

    def checkerwipe(
        self,
        minlon,
        minlat,
        maxlon,
        maxlat,
        led_index,
        color1,
        color2,
        cwccw=0,
        wait_mult=100,
    ):
        centlon = self.center(maxlon, minlon)
        centlat = self.center(maxlat, minlat)

        # Example square: lon1, lat1, lon2, lat2  [x1, y1, x2, y2]  -114.87, 37.07, -109.07, 31.42
        # +-----+-----+
        # |  1  |  2  |
        # |-----+-----|
        # |  3  |  4  |
        # +-----+-----+
        square1 = [minlon, centlat, centlon, maxlat]
        square2 = [centlon, centlat, maxlon, maxlat]
        square3 = [minlon, minlat, centlon, centlat]
        square4 = [centlon, minlat, maxlon, centlat]
        squarelist = [square1, square2, square4, square3]

        if cwccw == 1:  # clockwise = 0, counter-clockwise = 1
            squarelist.reverse()

        for j in range(led_index):
            for box in squarelist:
                for key in self.apinfodict:
                    px1 = float(self.apinfodict[key][2])  # Lon
                    py1 = float(self.apinfodict[key][1])  # Lat
                    led_index = int(self.apinfodict[key][0])  # LED Pin Num

                    if self.findpoint(
                        *box, px1, py1
                    ):  # Asterick allows unpacking of list in function call.
                        color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    else:
                        color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                    self.leds.setPixelColor(led_index, color)
                self.leds.show()
                time.sleep(self.wait * wait_mult)
        self.allonoff_wipes((0, 0, 0), 0.1)

    # Turn on or off all the lights using the same color.
    def allonoff_wipes(self, color1, delay):
        for led_index in range(self.leds.numPixels()):
            if str(led_index) in self.nullpins:  # exclude NULL and LGND pins from wipe
                self.leds.setPixelColor(led_index, Color(0, 0, 0))
            else:
                color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                self.leds.setPixelColor(led_index, color)
        self.leds.show()
        time.sleep(delay)

    # Fade LED's in and out using the same color.
    def fade(self, color1, delay):

        for val in range(0, self.brightness, 1):  # self.leds.numPixels()):
            for led_index in range(self.leds.numPixels()):  # LED_BRIGHTNESS,0,-1):
                if (
                    str(led_index) in self.nullpins
                ):  # exclude NULL and LGND pins from wipe
                    self.leds.setPixelColor(led_index, Color(0, 0, 0))
                else:
                    color2 = self.dimwipe(color1, val)
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.leds.setPixelColor(led_index, color)
            self.leds.show()
            time.sleep(self.wait * 0.5)

        for val in range(self.brightness, 0, -1):  # self.leds.numPixels()):
            for led_index in range(self.leds.numPixels()):  # 0,LED_BRIGHTNESS,1):
                if (
                    str(led_index) in self.nullpins
                ):  # exclude NULL and LGND pins from wipe
                    self.leds.setPixelColor(led_index, Color(0, 0, 0))
                else:
                    color2 = self.dimwipe(color1, val)
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.leds.setPixelColor(led_index, color)
            self.leds.show()
            time.sleep(self.wait * 0.5)
        time.sleep(delay * 1)

    # Dim LED's
    def dimwipe(self, data, value):
        red = int(data[0] - value)
        if red < 0:
            red = 0

        grn = int(data[1] - value)
        if grn < 0:
            grn = 0

        blu = int(data[2] - value)
        if blu < 0:
            blu = 0

        data = [red, grn, blu]
        return data

    # Shuffle LED Wipe
    def shuffle(self, color1, color2, delay):
        l = list(range(self.leds.numPixels()))
        random.shuffle(l)
        for led_index in l:
            if str(led_index) in self.nullpins:  # exclude NULL and LGND pins from wipe
                self.leds.setPixelColor(led_index, Color(0, 0, 0))
            else:
                color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                self.leds.setPixelColor(led_index, color)
            self.leds.show()
            time.sleep(self.wait * 1)

        l = list(range(self.leds.numPixels()))
        random.shuffle(l)
        for led_index in l:
            if str(led_index) in self.nullpins:  # exclude NULL and LGND pins from wipe
                self.leds.setPixelColor(led_index, Color(0, 0, 0))
            else:
                color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                self.leds.setPixelColor(led_index, color)
            self.leds.show()
            time.sleep(self.wait * 1)
        time.sleep(delay)

    # Morse Code Wipe
    # There are rules to help people distinguish dots from dashes in Morse code.
    #   The length of a dot is 1 time unit.
    #   A dash is 3 time units.
    #   The space between symbols (dots and dashes) of the same letter is 1 time unit.
    #   The space between letters is 3 time units.
    #   The space between words is 7 time units.
    def morse(self, color1, color2, msg, delay):
        # define timing of morse display
        dot_leng = self.wait * 1
        dash_leng = self.wait * 3
        bet_symb_leng = self.wait * 1
        bet_let_leng = self.wait * 3
        bet_word_leng = self.wait * 4  # logic will add bet_let_leng + bet_word_leng = 7

        for char in self.conf("rotaryswitch", "morse_msg"):
            letter = []
            if char.upper() in self.CODE:
                letter = list(self.CODE[char.upper()])
                debugging.debug(letter)  # debug

                for val in letter:  # display individual dot/dash with proper timing
                    if val == ".":
                        morse_signal = dot_leng
                    else:
                        morse_signal = dash_leng

                    for led_index in range(self.leds.numPixels()):  # turn LED's on
                        if (
                            str(led_index) in self.nullpins
                        ):  # exclude NULL and LGND pins from wipe
                            self.leds.setPixelColor(led_index, Color(0, 0, 0))
                        else:
                            color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                            self.leds.setPixelColor(led_index, color)
                    self.leds.show()
                    time.sleep(morse_signal)  # time on depending on dot or dash

                    for led_index in range(self.leds.numPixels()):  # turn LED's off
                        if (
                            str(led_index) in self.nullpins
                        ):  # exclude NULL and LGND pins from wipe
                            self.leds.setPixelColor(led_index, Color(0, 0, 0))
                        else:
                            color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                            self.leds.setPixelColor(led_index, color)
                    self.leds.show()
                    time.sleep(bet_symb_leng)  # timing between symbols
                time.sleep(bet_let_leng)  # timing between letters

            else:  # if character in morse_msg is not part of the Morse Code Alphabet, substitute a '/'
                if char == " ":
                    time.sleep(bet_word_leng)

                else:
                    char = "/"
                    letter = list(self.CODE[char.upper()])

                    for val in letter:  # display individual dot/dash with proper timing
                        if val == ".":
                            morse_signal = dot_leng
                        else:
                            morse_signal = dash_leng

                        for led_index in range(self.leds.numPixels()):  # turn LED's on
                            if (
                                str(led_index) in self.nullpins
                            ):  # exclude NULL and LGND pins from wipe
                                self.leds.setPixelColor(led_index, Color(0, 0, 0))
                            else:
                                color = self.rgbtogrb_wipes(
                                    led_index, color1, self.rgb_grb
                                )
                                self.leds.setPixelColor(led_index, color)
                        self.leds.show()
                        time.sleep(morse_signal)  # time on depending on dot or dash

                        for led_index in range(self.leds.numPixels()):  # turn LED's off
                            if (
                                str(led_index) in self.nullpins
                            ):  # exclude NULL and LGND pins from wipe
                                self.leds.setPixelColor(led_index, Color(0, 0, 0))
                            else:
                                color = self.rgbtogrb_wipes(
                                    led_index, color2, self.rgb_grb
                                )
                                self.leds.setPixelColor(led_index, color)
                        self.leds.show()
                        time.sleep(bet_symb_leng)  # timing between symbols

                    time.sleep(bet_let_leng)  # timing between letters

        time.sleep(delay)

    # Rabbit Chase
    # Chase the rabbit through string.
    def rabbit(self, color1, color2, delay):

        for led_index in range(self.leds.numPixels()):  # turn LED's on
            rabbit = led_index + 1

            if (
                str(led_index) in self.nullpins or str(rabbit) in self.nullpins
            ):  # exclude NULL and LGND pins from wipe
                self.leds.setPixelColor(led_index, Color(0, 0, 0))
                self.leds.setPixelColor(rabbit, Color(0, 0, 0))

            else:

                if rabbit < self.leds.numPixels() and rabbit > 0:
                    color = self.rgbtogrb_wipes(rabbit, color2, self.rgb_grb)
                    self.leds.setPixelColor(rabbit, color)
                    self.leds.show()

                color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                self.leds.setPixelColor(led_index, color)
                self.leds.show()
                time.sleep(self.wait)

        for led_index in range(self.leds.numPixels(), -1, -1):  # turn led's off
            rabbit = led_index + 1
            erase_pin = led_index + 2

            if (
                str(rabbit) in self.nullpins or str(erase_pin) in self.nullpins
            ):  # exclude NULL and LGND pins from wipe
                self.leds.setPixelColor(rabbit, Color(0, 0, 0))
                self.leds.setPixelColor(erase_pin, Color(0, 0, 0))
                self.leds.show()
            else:

                if rabbit < self.leds.numPixels() and rabbit > 0:
                    color = self.rgbtogrb_wipes(rabbit, color2, self.rgb_grb)
                    self.leds.setPixelColor(rabbit, color)
                    self.leds.show()

                if erase_pin < self.leds.numPixels() and erase_pin > 0:
                    color = self.rgbtogrb_wipes(
                        erase_pin, self.black_color, self.rgb_grb
                    )
                    self.leds.setPixelColor(erase_pin, color)
                    self.leds.show()
                    time.sleep(self.wait)

        self.allonoff_wipes(self.black_color, 0)


#    def wipes_v4_main(self):
#        #Start of executed code
#        #read airports file - read each time weather is updated in case a change to "airports" file was made while script was running.
#        with open("/NeoSectional/data/airports") as f:
#            airports = f.readlines()
#        airports = [x.strip() for x in airports]
#
#        #Define URL to get weather METARS. This will pull only the latest METAR from the last 2.5 hours. If no METAR reported withing the last 2.5 hours, Airport LED will be white.
#        url = "https://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=metars&requestType=retrieve&format=xml&mostRecentForEachStation=constraint&hoursBeforeNow="+str(metar_age)+"&stationString="
#        #    debugging.debug(url)
#
#        #Build URL to submit to FAA with the proper airports from the airports file and populate the pindict dictionary
#        i = 0
#        self.nullpins = []
#        for airportcode in airports:
#            if airportcode == "NULL" or airportcode == "LGND":
#                self.nullpins.append(str(i))
#                i += 1
#                continue
#            url = url + airportcode + ","
#            pindict[airportcode] = str(i)           #build a dictionary of the LED pins for each airport used
#            i += 1
#        # debugging.debug('Airports = ' + str(airports))
#        # debugging.debug('URL = ' + str(url))
#        # debugging.debug('nullpins = ' + str(nullpins))
#
#        try:                                        #Simple Error trap, in case FAA web site is not responding
#            content = urllib.request.urlopen(url).read()
#        except:                                     #End of Error trap
#            pass
#
#        root = ET.fromstring(content)               #Process XML data returned from FAA
#
#        #grab the airport category, wind speed and various weather from the results given from FAA.
#        for metar in root.led_index('METAR'):
#            stationId = metar.find('station_id').text
#
#            #grab latitude of airport
#            if metar.find('latitude') is None: #if weather string is blank, then bypass
#    #            lat = '0'
#                pass
#            else:
#                lat = metar.find('latitude').text
#
#            #grab longitude of airport
#            if metar.find('longitude') is None:     #if weather string is blank, then bypass
#    #            lon = '0'
#                pass
#            else:
#                lon = metar.find('longitude').text
#
#            if stationId in latdict:
#                print ("Duplicate, only saved the first weather")
#            else:
#                latdict[stationId] = lat            #build latitude dictionary
#
#            if stationId in londict:
#                print ("Duplicate, only saved the first weather")
#            else:
#                londict[stationId] = lon            #build longitude dictionary
#
#            self.apinfodict[stationId]=[pindict[stationId],lat,lon] #Build Dictionary with structure:{airport id[pin num,lat,lon]}
#
#        debugging.debug(apinfodict)
#        debugging.debug(latdict)
#        debugging.debug(londict)
#
#        #build necessary lists to find proper Lat/Lons (Try to eliminate and use apinfodict instead)
#        for key, value in latdict.items():
#            temp = float(value)
#            latlist.append(temp)
#        debugging.debug(latlist)
#
#        for key, value in londict.items():
#            temp = float(value)
#            lonlist.append(temp)
#        debugging.debug(lonlist)
#
#        for airportcode in airports:
#            ap_id.append(airportcode)
#        debugging.debug(ap_id)
#
#        #set the maximum and minimum Lat/Lons to constrain area.
#        maxlat = max(latlist)                       #Upper bounds of box
#        minlat = min(latlist)                       #Lower bounds of box
#
#        maxlon = max(lonlist)                       #Right bounds of box
#        minlon = min(lonlist)                       #Left bounds of box
#
#        sizelat = round(abs(maxlat - minlat),2)     #height of box
#        sizelon = round(abs(maxlon - minlon),2)     #width of box
#
#        centerlat = round(sizelat/2+minlat,2)       #center y coord of box
#        centerlon = round(sizelon/2+minlon,2)       #center x coord of box
#
#        debugging.info('maxlat = ' + str(maxlat) + ' minlat = ' + str(minlat) + ' maxlon = ' + str(maxlon) + ' minlon = ' + str(minlon))
#        debugging.info('sizelat = ' + str(sizelat) + ' sizelon = ' + str(sizelon) + ' centerlat ' + str(centerlat) + ' centerlon = ' + str(centerlon))
#
#
#        #Start the different wipes. Check to see how many led_indexations of each. Zero disables the wipe.
#        time.sleep(1)                               #pause to give the string of lights a chance get catch up. Used so lights won't hang up.
#
#        #Checker wipe
#        if num_checker > 0:
#            debugging.info('Executing checkerbox Wipe')
#
#        for j in range(num_checker):
#            if rand:
#                checkerwipe(minlon, minlat, maxlon, maxlat, 2, randcolor(), randcolor(), 1)
#            else:
#                checkerwipe(minlon, minlat, maxlon, maxlat, 2, checker_color1, checker_color2, 1)
#
#        #square wipe - provide coord of box and size, led_indexations, and colors
#        if num_square > 0:
#            debugging.info('Executing Square Wipe')
#
#        for j in range(num_square):
#            if rand:
#                squarewipe(minlon, minlat, maxlon, maxlat, 1, randcolor(), randcolor())
#            else:
#                squarewipe(minlon, minlat, maxlon, maxlat, 1, square_color1, square_color2)
#
#        #radar wipe - provide center of map and the number of times to cycle through
#        if num_radar > 0:
#            debugging.info('Executing Radar Wipe')
#
#        for j in range(num_radar):
#            if rand:
#                radarwipe(centerlat, centerlon, 130, randcolor(), randcolor())
#            else:
#                radarwipe(centerlat, centerlon, 130, radar_color1, radar_color2)
#
#        #Circle wipe. provide center coordinates, provide inside of circle color then outside of circle.
#        if num_circle > 0:
#            debugging.info('Executing Circle Wipe')
#
#        for j in range(num_circle):
#            if rand:
#                circlewipe(centerlat, centerlon, randcolor(), randcolor())
#            else:
#                circlewipe(centerlat, centerlon, circle_color1, circle_color2)
#
#        #Wipe from bottom to top and back, then side to side
#        if num_updn > 0:
#            debugging.info('Executing Up/Down-Side to Side Wipe')
#
#        for j in range(num_updn):
#            if rand:
#                wipe(latdict, minlat, maxlat, .01, randcolor(), randcolor(), .1)
#                wipe(latdict, maxlat, minlat, .01, randcolor(), randcolor(), .1)
#                wipe(londict, minlon, maxlon, .01, randcolor(), randcolor(), .1)
#                wipe(londict, maxlon, minlon, .01, randcolor(), randcolor(), .1)
#            else:
#                wipe(latdict, minlat, maxlat, .01, updn_color1, updn_color2, .1)
#                wipe(latdict, maxlat, minlat, .01, updn_color1, updn_color2, .1)
#                wipe(londict, minlon, maxlon, .01, updn_color1, updn_color2, .1)
#                wipe(londict, maxlon, minlon, .01, updn_color1, updn_color2, .1)
#
#        #change colors on whole board
#        if num_allsame > 0:
#            debugging.info('Executing Solid Color Wipe')
#
#        for j in range(num_allsame):
#            if rand:
#                allonoff_wipes(randcolor(),wait*1000)
#            else:
#                allonoff_wipes(allsame_color1,wait*1000)
#
#        #Fade colors in and out on whole board
#        if num_fade > 0:
#            debugging.info('Executing Fading Color Wipe')
#
#        for j in range(num_fade):
#            if rand:
#                fade(randcolor(),wait)
#            else:
#                fade(fade_color1,wait)
#
#        #shuffle effect
#        if num_shuffle > 0:
#            debugging.info('Executing Shuffle Wipe')
#
#        for j in range(num_shuffle):
#            if rand:
#                shuffle(randcolor(),randcolor(), wait*10)
#            else:
#                shuffle(shuffle_color1, shuffle_color2, wait*10)
#
#        #Morse code effect
#        if num_morse > 0:
#            debugging.info('Executing Morse Code Wipe')
#
#        for j in range(num_morse):
#            if rand:
#                morse(randcolor(),randcolor(), morse_msg, wait*60)
#            else:
#                morse(morse_color1, morse_color2, morse_msg, wait*60)
#
#        #rainbow effect
#        if num_rainbow > 0:
#            debugging.info('Executing Rainbow Wipe')
##
#        for j in range(num_rainbow):
#            rainbowCycle(strip, 2, wait)
#
#        debugging.info('Turning Off all LEDs')
#    #    allonoff_wipes((0,0,0),.1)
#
#        #Rabbit Chase effect
#        if num_rabbit > 0:
#            debugging.info('Executing Rabbit Chase Wipe')
#
#        for j in range(num_rabbit):
#            if rand:
#                rabbit(randcolor(),randcolor(), wait*10)
#            else:
#                rabbit(rabbit_color1, rabbit_color2, wait*10)
