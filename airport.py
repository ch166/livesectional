# -*- coding: utf-8 -*- #
"""
Created on Sat Jun 15 08:01:44 2019

@author: Chris Higgins
"""

# This is the collection and aggregation of all functions that manage Airports and airport weather
# products. It's initially focused on processing METARs, but will end up including all of the functions
# related to TAFs and MOS data.
#
# This file is the management of the Airport object
# The airport object stores all of the interesting data for an airport
# - Airport ICAO code
# - Weather Source ( adds , metar URL, future options)
# - Airport Code to use for WX data (future - for airports without active ASOS/AWOS reporting)
# - Current conditions
# - etc.

from datetime import datetime
from datetime import timedelta
from distutils import util
from enum import Enum

# from urllib.request import urlopen
# import urllib.error
# import socket


# XML Handling
# import json
# import xml.etree.ElementTree as ET
# from metar import Metar

import debugging
import ledstrip

# import utils
import wx_utils


class AirportFlightCategory(Enum):
    """
    ENUM Flight Categories
    """

    VFR = ledstrip.LedStrip.GREEN
    MVFR = ledstrip.LedStrip.BLUE
    IFR = ledstrip.LedStrip.RED
    LIFR = ledstrip.LedStrip.MAGENTA
    OLD = ledstrip.LedStrip.YELLOW
    UNKNOWN = ledstrip.LedStrip.WHITE


class Airport:
    """Class to identify Airports that are known to livemap
    Initially it's all location data - but as livemap gets smarter
    we should be able to include more sources like
    - runway information
    - weather information
    """

    def __init__(self, icao, iata, wxsrc, active_led, led_index, conf):
        """Init object and set initial values for internals"""
        # Airport Identity
        self.icao = icao
        self.iata = iata
        self.latitude = 0
        self.longitude = 0

        # Airport Configuration
        self.wxsrc = wxsrc
        self.metar = None
        self.metar_prev = None
        self.metar_date = datetime.now() - timedelta(days=1)  # Make initial date "old"
        self.observation = None

        # Application Status for Airport
        self.enabled = True
        self.active_led = util.strtobool(active_led)
        self.led_active_state = None
        self.led_index = led_index
        self.updated_time = datetime.now()

        # Airport Weather Data
        self.wx_conditions = ()
        self.wx_visibility = None
        self.wx_ceiling = None
        self.wx_dir_degrees = None
        self.wx_windspeed = None
        self.wx_windgust = None
        self.wx_category = None
        self.wx_category_str = "UNSET"

        # Global Data
        self.conf = conf
        self.metar_returncode = ""

    def last_updated(self):
        """Get last updated time"""
        return self.updated_time

    def get_latitude(self):
        """Return Airport Latitude"""
        return self.latitude

    def get_longitude(self):
        """Return Airport longitude"""
        return self.longitude

    def icaocode(self):
        """airport ICAO (4 letter) code"""
        return self.icao

    def iatacode(self):
        """airport IATA (3 letter) Code"""
        return self.iata

    def set_metar(self, metartext):
        """Get Current METAR"""
        self.metar_prev = self.metar
        self.metar = metartext
        self.metar_date = datetime.now()
        self.updated_time = datetime.now()

    def get_raw_metar(self):
        """Return raw METAR data"""
        return self.metar

    def get_metarage(self):
        """Return Timestamp of METAR"""
        return self.metar_date

    def get_ca_metar(self):
        """Try get Fresh METAR data for Canadian Airports"""
        # TODO:
        # The ADDS data source appears to have all the data for all the locations.
        # May be able to delete this entirely
        return False

    def get_airport_wx_xml(self):
        """Pull Airport XML data from ADDS XML"""
        # TODO: Stub

    def set_led_index(self, led_index):
        """Update LED ID"""
        self.led_index = led_index

    def get_led_index(self):
        """Return LED ID"""
        return self.led_index

    def get_wxsrc(self):
        """Set Weather source"""
        return self.wxsrc

    def set_wxsrc(self, wxsrc):
        """Set Weather source"""
        self.wxsrc = wxsrc

    def set_active(self):
        """Mark Airport as Active"""
        self.active_led = True

    def active(self):
        """Active"""
        return self.active_led

    def set_inactive(self):
        """Mark Airport as Inactive"""
        self.active_led = False

    def set_wx_category(self, wx_category_str):
        """Set WX Category to ENUM based on current wx_category_str"""
        # Calculate Flight Category
        if wx_category_str == "UNK":
            self.wx_category = AirportFlightCategory.UNKNOWN
        elif wx_category_str == "LIFR":
            self.wx_category = AirportFlightCategory.LIFR
        elif wx_category_str == "IFR":
            self.wx_category = AirportFlightCategory.IFR
        elif wx_category_str == "VFR":
            self.wx_category = AirportFlightCategory.VFR
        elif wx_category_str == "MVFR":
            self.wx_category = AirportFlightCategory.MVFR

    def get_wx_category_str(self):
        """Return string form of airport weather category"""
        return self.wx_category_str

    def get_wx_dir_degrees(self):
        """Return reported windspeed"""
        return self.wx_dir_degrees

    def get_wx_windspeed(self):
        """Return reported windspeed"""
        return self.wx_windspeed

    def get_adds_metar(self, metar_dict):
        """Try get Fresh METAR data from local Aviation Digital Data Service (ADDS) download"""
        debugging.info("Updating WX from adds for " + self.icao)
        self.metar_date = datetime.now()

        if self.icao not in metar_dict:
            # TODO: If METAR data is missing from the ADDS dataset, then it hasn't been updated
            # We have the option to try a direct query for the data ; but don't have any hint
            # on which alternative source to use.
            # We also need to wonder if we want to copy over data from the previous record
            # to this record... so we have some persistance of data rather than losing the airport completely.
            debugging.debug("metar_dict WX for " + self.icao + " missing")
            self.wx_category = AirportFlightCategory.UNKNOWN
            self.wx_category_str = "UNK"
            self.set_metar(None)
            return

        # Don't need to worry about these entries existing
        # We check for valid data when we create the Airport data
        self.set_metar(metar_dict[self.icao]["raw_text"])
        self.wx_visibility = metar_dict[self.icao]["visibility"]
        self.wx_ceiling = metar_dict[self.icao]["ceiling"]
        self.wx_windspeed = metar_dict[self.icao]["wind_speed_kt"]
        self.wx_dir_degrees = metar_dict[self.icao]["wind_dir_degrees"]
        self.wx_windgust = metar_dict[self.icao]["wind_gust_kt"]
        self.wx_category_str = metar_dict[self.icao]["flight_category"]
        self.latitude = float(metar_dict[self.icao]["latitude"])
        self.longitude = float(metar_dict[self.icao]["longitude"])
        self.set_wx_category(self.wx_category_str)

        try:
            wx_utils.calculate_wx_from_metar(self)
        except Exception as e:
            debug_string = (
                "Error: get_adds_metar processing "
                + self.icao
                + " metar:"
                + self.get_raw_metar()
                + ":"
            )
            debugging.debug(debug_string)
            debugging.debug(e)
        return False

    def update_wx(self, metar_xml_dict):
        """Update Weather Data - Get fresh METAR"""
        freshness = False
        if self.wxsrc == "adds":
            try:
                debugging.info("Update USA Metar: ADDS " + self.icao)
                freshness = self.get_adds_metar(metar_xml_dict)
            except Exception as e:
                debugging.error(e)
        elif self.wxsrc.startswith("neigh"):
            """Get METAR data from alternative Airport"""
            strparts = self.wxsrc.split(":")
            debugging.info(f"{self.icao} needs metar for {strparts[1]}")
        elif self.wxsrc == "usa-metar":
            # This is the scenario where we want to query an individual METAR record
            # directly. This is unused for now - we may want to use it if the
            # adds data is missing.
            # If the adds data is missing, then we need to find stable reliable and free sources of metar data for all geogrpahies
            debugging.info(
                "Update USA Metar: " + self.icao + " - " + self.wx_category_str
            )
            freshness = wx_utils.get_usa_metar(self)
            if freshness:
                # get_*_metar() returned true, so weather is still fresh
                return
            wx_utils.calculate_wx_from_metar(self)
        return
