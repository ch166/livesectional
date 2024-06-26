# testled.py - used as a test script for LiveSectional Map, www.livesectional.com
# NeoPixel library strandtest example
# Inspired by: Tony DiCola (tony@tonydicola.com)
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.
import time
import config
from rpi_ws281x import *  # works with python 3.7. sudo pip3 install rpi_ws281x

# LED strip configuration:
LED_COUNT = config.LED_COUNT  # Number of LED pixels.
LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 5  # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_STRIP = ws.WS2811_STRIP_GRB  # Strip type and colour ordering

iterations = 2
j = 0


def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)


def rainbowCycle(strip, wait_ms=50, iterations=5):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256 * iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()


# 		time.sleep(wait_ms/1000.0)


def turnoff(strip):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


# Main program logic follows:
if __name__ == "__main__":
    # Create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(
        LED_COUNT,
        LED_PIN,
        LED_FREQ_HZ,
        LED_DMA,
        LED_INVERT,
        LED_BRIGHTNESS,
        LED_CHANNEL,
        LED_STRIP,
    )

    # Intialize the library (must be called once before other functions).
    strip.begin()
    print("Rainbow animations.")

    while j < iterations:
        rainbowCycle(strip)
        j += 1

    turnoff(strip)
