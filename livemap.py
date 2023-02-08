#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main livemap program

Takes care of all of the setup needed for each component in the system

Start individual threads
 a) update_airport thread - to keep METAR/TAF/MOS data up to date
 b) update_leds thread - keep the LEDs updated to reflect airport state
 c) update_oleds thread - keep the OLEDs updated to reflect state
 d) Web interface for config and maps
 e) Light Sensor thread

"""

# livemap.py - Main engine ; running threads to keep the data updated

# import os
# import sys
import threading
import time

# import logging
import debugging
import conf  # Config.py holds user settings used by the various scripts

# import admin

# from flask import Flask

import utils
import utils_i2c
import sysinfo

# import appinfo

import update_airports
import update_leds
import update_gpio
import update_oled
import update_lightsensor
import appinfo
import webviews

# import update_oled


if __name__ == "__main__":
    # Startup and run the threads to operate the LEDs, Displays etc.

    # Initialize configuration
    conf = conf.Conf()
    appinfo = appinfo.AppInfo()

    # Setup Logging
    debugging.loginit()

    # Check for working Internet
    if utils.wait_for_internet():
        # Check for working Internet access
        debugging.info("Internet Available")
    else:
        debugging.warn("Internet NOT Available")

    # Generate System Data
    sysdata = sysinfo.SystemData()
    sysdata.refresh()
    ipaddr = sysdata.local_ip()

    i2cbus = utils_i2c.I2CBus(conf)

    # Setup Airport DB
    airport_database = update_airports.AirportDB(conf)
    airport_database.load_airport_db()

    # Setup LED Management
    LEDmgmt = update_leds.UpdateLEDs(conf, airport_database)

    # Setup LightSensor Management
    LuxSensor = update_lightsensor.LightSensor(conf, i2cbus, LEDmgmt)

    # Setup GPIO Monitoring
    GPIOmon = update_gpio.UpdateGPIO(conf, airport_database)

    # Setup OLED Management
    OLEDmgmt = update_oled.UpdateOLEDs(conf, airport_database, i2cbus)

    # Setup Flask APP
    web_app = webviews.WebViews(conf, sysdata, airport_database, appinfo, LEDmgmt)

    # Almost Setup
    debugging.info(f"Livemap Startup - IP: {ipaddr}")
    debugging.info(f'Base Directory : {conf.get_string("filenames", "basedir")}')

    #
    # Setup Threads
    #

    # Load Airports
    debugging.info("Starting Airport data management thread")
    airport_thread = threading.Thread(target=airport_database.update_loop, args=(conf,))

    # Updating LEDs
    debugging.info("Starting LED updating thread")
    led_thread = threading.Thread(target=LEDmgmt.update_loop, args=())

    # Updating LightSensor
    debugging.info("Starting Light Sensor thread")
    lightsensor_thread = threading.Thread(target=LuxSensor.update_loop, args=(conf,))

    # Updating OLEDs
    debugging.info("Starting OLED updating thread")
    oled_thread = threading.Thread(target=OLEDmgmt.update_loop, args=())

    # Monitoring GPIO pins
    debugging.info("Starting GPIO monitoring thread")
    gpio_thread = threading.Thread(target=GPIOmon.update_loop, args=())

    # Flask Thread
    debugging.info("Creating Flask Thread")
    flask_thread = threading.Thread(target=web_app.run, args=())

    #
    # Start Executing Threads
    #
    debugging.info("Starting threads")
    airport_thread.start()
    led_thread.start()
    gpio_thread.start()
    oled_thread.start()
    flask_thread.start()
    lightsensor_thread.start()

    main_loop_sleep = 5

    while True:
        MSG = "In Main Loop - Threadcount ({}), Sleep for {}m"
        active_thread_count = threading.active_count()
        debugging.info(MSG.format(active_thread_count, main_loop_sleep))

        # TODO: We should get around to generating and reporting health
        # metrics in this loop.
        time.sleep(main_loop_sleep * 60)
