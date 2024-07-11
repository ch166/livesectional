#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

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

import update_datasets
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
    app_conf = conf.Conf()
    app_info = appinfo.AppInfo()

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

    i2cbus = utils_i2c.I2CBus(app_conf)

    # Download Datasets
    dataset_sync = update_datasets.DataSets(app_conf)

    # Setup Airport DB
    airport_database = update_airports.AirportDB(app_conf, dataset_sync)

    # Setup LED Management
    LEDmgmt = update_leds.UpdateLEDs(app_conf, airport_database)

    # Setup LightSensor Management
    LuxSensor = update_lightsensor.LightSensor(app_conf, i2cbus, LEDmgmt)

    # Setup GPIO Monitoring
    GPIOmon = update_gpio.UpdateGPIO(app_conf, airport_database)

    # Setup OLED Management
    OLEDmgmt = update_oled.UpdateOLEDs(app_conf, sysdata, airport_database, i2cbus)

    # Setup Flask APP
    web_app = webviews.WebViews(app_conf, sysdata, airport_database, app_info, LEDmgmt)

    # Almost Setup
    debugging.info(f"Livemap Startup - IP: {ipaddr}")
    debugging.info(f'Base Directory : {app_conf.get_string("filenames", "basedir")}')

    #
    # Setup Threads
    #

    # Get datasets
    debugging.info("Starting DataSet download thread")
    dataset_thread = threading.Thread(
        target=dataset_sync.update_loop, name="datasetsync", args=(app_conf,)
    )

    # Load Airports
    debugging.info("Starting Airport data management thread")
    airport_thread = threading.Thread(
        target=airport_database.update_loop,
        name="airportdb",
        args=(
            app_conf,
        ),
    )

    # Updating LEDs
    debugging.info("Starting LED updating thread")
    led_thread = threading.Thread(
        target=LEDmgmt.update_loop, name="led management", args=()
    )

    # Updating LightSensor
    debugging.info("Starting Light Sensor thread")
    lightsensor_thread = threading.Thread(
        target=LuxSensor.update_loop, name="lightsensor", args=(app_conf,)
    )

    # Updating OLEDs
    debugging.info("Starting OLED updating thread")
    oled_thread = threading.Thread(
        target=OLEDmgmt.update_loop, name="oled management", args=()
    )

    # Monitoring GPIO pins
    debugging.info("Starting GPIO monitoring thread")
    gpio_thread = threading.Thread(
        target=GPIOmon.update_loop, name="gpio monitoring", args=()
    )

    # Flask Thread
    debugging.info("Creating Flask Thread")
    flask_thread = threading.Thread(
        target=web_app.run, name="flask web server", args=()
    )

    #
    # Start Executing Threads
    #

    debugging.info("Starting threads")
    dataset_thread.start()
    airport_thread.start()
    led_thread.start()
    gpio_thread.start()
    oled_thread.start()
    flask_thread.start()
    lightsensor_thread.start()

    MAIN_LOOP_SLEEP = 5

    while True:
        active_thread_count = threading.active_count()
        info_msg = f"In Main Loop - Threadcount ({active_thread_count}), Sleep for {MAIN_LOOP_SLEEP}m"
        debugging.info(info_msg)

        for thread_obj in threading.enumerate():
            debugging.info(f"ID:{thread_obj.ident}/name:{thread_obj.name}")

        sysdata.refresh()
        # TODO: We should get around to generating and reporting health
        # metrics in this loop.
        debugging.info(airport_database.stats())
        debugging.info(i2cbus.stats())
        debugging.info(dataset_sync.stats())

        time.sleep(MAIN_LOOP_SLEEP * 60)
