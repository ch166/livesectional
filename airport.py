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

# from distutils import util
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

import utils
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
    UNKN = ledstrip.LedStrip.WHITE
    OFF = ledstrip.LedStrip.BLACK


class Airport:
    """Class to identify Airports that are known to livemap
    Initially it's all location data - but as livemap gets smarter
    we should be able to include more sources like
    - runway information
    - weather information
    """

    def __init__(self, icao, iata, wxsrc, active_led, led_index, purpose, conf):
        """Init object and set initial values for internals"""
        # Airport Identity
        self._icao = icao
        self._iata = iata
        self._latitude = 0
        self._longitude = 0
        self._coordinates = False

        # Airport Configuration
        self._wxsrc = wxsrc
        self._metar = None
        self._metar_prev = None
        self._metar_date = datetime.now() - timedelta(days=1)  # Make initial date "old"
        self._observation = None
        self._runway_dataset = None

        # Application Status for Airport
        self._enabled = True
        self._purpose = purpose
        self._active_led = utils.str2bool(active_led)
        self.led_active_state = None
        self.led_index = led_index
        self.updated_time = datetime.now()

        # Airport Weather Data
        self._wx_conditions = ()
        self.wx_visibility = None
        self.wx_ceiling = None
        self.wx_dir_degrees = None
        self.wx_windspeed = None
        self.wx_windgust = None
        self.wx_category = None
        self.wx_category_str = "UNSET"

        # HeatMap
        self.hm_index = 0

        # Global Data
        self._conf = conf
        self._metar_returncode = ""

    def last_updated(self):
        """Get last updated time"""
        return self.updated_time

    def purpose(self):
        """Return Airport Purpose."""
        return self._purpose

    def latitude(self):
        """Return Airport Latitude."""
        return self._latitude

    def longitude(self):
        """Return Airport longitude."""
        return self._longitude

    def valid_coordinates(self):
        """Are lat/lon coordinates set to something other than Missing."""
        return self._coordinates

    def icaocode(self):
        """airport ICAO (4 letter) code"""
        return self._icao

    def iatacode(self):
        """airport IATA (3 letter) Code"""
        return self._iata

    def set_metar(self, metartext):
        """Get Current METAR"""
        self._metar_prev = self._metar
        self._metar = metartext
        self._metar_date = datetime.now()
        self.updated_time = datetime.now()

    def get_raw_metar(self):
        """Return raw METAR data"""
        return self._metar

    def get_metarage(self):
        """Return Timestamp of METAR"""
        return self._metar_date

    def wxconditions(self):
        """Return list of weather conditions at Airport."""
        return self._wx_conditions

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

    def set_runway_data(self, runway_dataset):
        """Update Runway Data"""
        self._runway_dataset = runway_dataset

    def get_led_index(self):
        """Return LED ID"""
        return self.led_index

    def wxsrc(self):
        """Set Weather source"""
        return self._wxsrc

    def set_wxsrc(self, wxsrc):
        """Set Weather source"""
        self._wxsrc = wxsrc

    def set_active(self):
        """Mark Airport as Active"""
        self._active_led = True

    def heatmap_index(self):
        """Heatmap Count"""
        return self.hm_index

    def set_heatmap_index(self, hmcount):
        """Set Heatmap"""
        self.hm_index = hmcount

    def active(self):
        """Active"""
        return self._active_led

    def set_inactive(self):
        """Mark Airport as Inactive"""
        self._active_led = False

    def best_runway(self):
        """Examine the list of known runways to find the best alignment to the wind."""
        if self._runway_dataset is None:
            return None
        best_runway = None
        best_delta = None
        if self._runway_dataset is None:
            return best_runway
        for runway in self._runway_dataset:
            debugging.info(runway)
            runway_closed = runway["closed"]
            if runway_closed:
                continue
            runway_direction_le = runway["le_heading_degT"]
            runway_wind_delta_le = abs(runway_direction_le - self.wx_dir_degrees)
            runway_direction_he = runway["he_heading_degT"]
            runway_wind_delta_he = abs(runway_direction_he - self.wx_dir_degrees)
            better_delta = min(runway_wind_delta_le, runway_wind_delta_he)
            if runway_wind_delta_le < runway_direction_he:
                better_runway = runway_direction_le
            else:
                better_runway = runway_direction_he
            if (best_runway is None) or (better_delta < best_delta):
                best_runway = better_runway
                best_delta = min(runway_wind_delta_le, runway_direction_he)
        return best_runway

    def set_wx_category(self, wx_category_str):
        """Set WX Category to ENUM based on current wx_category_str"""
        # Calculate Flight Category
        if wx_category_str == "UNKN":
            self.wx_category = AirportFlightCategory.UNKN
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
        debugging.info("Updating WX from adds for " + self._icao)
        self._metar_date = datetime.now()

        if self._icao not in metar_dict:
            # TODO: If METAR data is missing from the ADDS dataset, then it hasn't been updated
            # We have the option to try a direct query for the data ; but don't have any hint
            # on which alternative source to use.
            # We also need to wonder if we want to copy over data from the previous record
            # to this record... so we have some persistance of data rather than losing the airport completely.
            debugging.debug("metar_dict WX for " + self._icao + " missing")
            self.wx_category = AirportFlightCategory.UNKN
            self.wx_category_str = "UNKN"
            self.set_metar(None)
            return

        # Don't need to worry about these entries existing
        # We check for valid data when we create the Airport data
        self.set_metar(metar_dict[self._icao]["raw_text"])
        self.wx_visibility = metar_dict[self._icao]["visibility"]
        self.wx_ceiling = metar_dict[self._icao]["ceiling"]
        self.wx_windspeed = metar_dict[self._icao]["wind_speed_kt"]
        self.wx_dir_degrees = metar_dict[self._icao]["wind_dir_degrees"]
        self.wx_windgust = metar_dict[self._icao]["wind_gust_kt"]
        self.wx_category_str = metar_dict[self._icao]["flight_category"]
        self._latitude = float(metar_dict[self._icao]["latitude"])
        self._longitude = float(metar_dict[self._icao]["longitude"])
        if self._latitude == "Missing" or self._longitude == "Missing":
            self._coordinates = False
            debugging.info(f"Coordinates missing for {self._icao}")
        else:
            self._coordinates = True
        self.set_wx_category(self.wx_category_str)

        try:
            wx_utils.calculate_wx_from_metar(self)
        except Exception as err:
            debug_string = f"Error: get_adds_metar processing {self._icao} metar:{self.get_raw_metar()}:"
            debugging.debug(debug_string)
            debugging.debug(err)
        return False

    def update_wx(self, metar_xml_dict):
        """Update Weather Data - Get fresh METAR"""
        freshness = False
        if self._wxsrc == "adds":
            try:
                debugging.info("Update USA Metar: ADDS " + self._icao)
                freshness = self.get_adds_metar(metar_xml_dict)
            except Exception as err:
                debugging.error(err)
        elif self._wxsrc.startswith("neigh"):
            # Get METAR data from alternative Airport
            strparts = self._wxsrc.split(":")
            debugging.info(f"{self._icao} needs metar for {strparts[1]}")
        elif self._wxsrc == "usa-metar":
            # This is the scenario where we want to query an individual METAR record
            # directly. This is unused for now - we may want to use it if the
            # adds data is missing.
            # If the adds data is missing, then we need to find stable reliable and free sources of metar data for all geographies
            debugging.info(f"Update USA Metar: {self._icao} - {self.wx_category_str}")
            freshness = wx_utils.get_usa_metar(self)
            if freshness:
                # get_*_metar() returned true, so weather is still fresh
                return
            wx_utils.calculate_wx_from_metar(self)
        return
