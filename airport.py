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
# - Airport Code to use for WX data (future - for airports without active ASOS/AWOSporting)
# - Current conditions
# - etc.

from datetime import datetime
from datetime import timedelta

# from distutils import util
from enum import Enum, auto

# from urllib.request import urlopen
# import urllib.error
# import socket


# XML Handling
# import json
# import xml.etree.ElementTree as ET
# from metar import Metar

import debugging

import utils
import utils_wx

from lxml import etree


class AirportFlightCategory(Enum):
    """ENUM Flight Categories."""

    VFR = auto()
    MVFR = auto()
    IFR = auto()
    LIFR = auto()
    OLD = auto()
    UNKN = auto()
    OFF = auto()


class Airport:
    """Class to identify Airports that are known to livemap.

    Initially it's all location data - but as livemap gets smarter
    we should be able to include more sources like
    - runway information
    - weather information
    """

    def __init__(self, icao, metar):
        """Initialize object and set initial values for internals."""
        # Airport Identity
        self.__icao = icao
        self.__iata = None
        self.__latitude = 0
        self.__longitude = 0
        self.__coordinates = False

        # Airport Configuration
        self.__wxsrc = None
        self.__metar = metar
        self.__metar_prev = None
        self.__metar_date = datetime.now() - timedelta(
            days=1
        )  # Make initial date "old"
        self.__observation = None
        self.__observation_time = None
        self.__runway_dataset = None

        # Application Status for Airport
        self.__enabled = True
        self.__purpose = "off"
        self.__active_led = None
        self.led_active_state = None
        self.led_index = None
        self.updated_time = datetime.now()

        # XML Data
        self.__flight_category = None
        self.__sky_condition = None

        # Airport Weather Data
        self.__metar_type = None
        self.__wx_conditions = ()
        self.wx_visibility = None
        self.__visibility_statute_mi = None
        self.wx_ceiling = None
        self.__wind_dir_degrees = None
        self.__wind_speed_kt = None
        self.wx_windgust = None
        self.__wind_gust_kt = None
        self.wx_category = None
        self.__wx_category_str = "UNSET"
        self.__ceiling = None

        # HeatMap
        self.hm_index = 0

        # Airport came from Config file
        self.__loaded_from_config = False

        # Global Data
        self.__metar_returncode = ""

    def last_updated(self):
        """Get last updated time."""
        return self.updated_time

    def loaded_from_config(self):
        """Airport was loaded from config file."""
        self.__loaded_from_config = True

    def save_in_config(self):
        """Airport to be saved in config file."""
        # FIXME: What is this trying to do ?
        self.__loaded_from_config

    def purpose(self):
        """Return Airport Purpose."""
        return self.__purpose

    def set_purpose(self, purpose):
        """Return Airport Purpose."""
        self.__purpose = purpose

    def flightcategory(self):
        """Return flight category data."""
        return self.__flight_category

    def latitude(self):
        """Return Airport Latitude."""
        return self.__latitude

    def longitude(self):
        """Return Airport longitude."""
        return self.__longitude

    def valid_coordinates(self):
        """Are lat/lon coordinates set to something other than Missing."""
        return self.__coordinates

    def icaocode(self):
        """Airport ICAO (4 letter) code."""
        return self.__icao

    def iatacode(self):
        """Airport IATA (3 letter) Code."""
        return self.__iata

    def set_metar(self, metartext):
        """Get Current METAR."""
        # debugging.info(f"Metar set for {self.__icao} to :{metartext}")
        self.__metar_prev = self.__metar
        self.__metar = metartext
        self.__metar_date = datetime.now()
        self.updated_time = datetime.now()

    def get_raw_metar(self):
        """Return raw METAR data."""
        return self.__metar

    def get_metarage(self):
        """Return Timestamp of METAR."""
        return self.__metar_date

    def wxconditions(self):
        """Return list of weather conditions at Airport."""
        return self.__wx_conditions

    def get_ca_metar(self):
        """Try get Fresh METAR data for Canadian Airports."""
        # TODO:
        # The ADDS data source appears to have all the data for all the locations.
        # May be able to delete this entirely
        return False

    def get_airport_wx_xml(self):
        """Pull Airport XML data from ADDS XML."""
        # TODO: Stub

    def set_led_index(self, led_index):
        """Update LED ID."""
        self.led_index = led_index

    def set_runway_data(self, runway_dataset):
        """Update Runway Data."""
        self.__runway_dataset = runway_dataset

    def get_led_index(self):
        """Return LED ID."""
        return self.led_index

    def wxsrc(self):
        """Get Weather source."""
        return self.__wxsrc

    def set_wxsrc(self, wxsrc):
        """Set Weather source."""
        self.__wxsrc = wxsrc

    def set_active(self):
        """Mark Airport as Active."""
        self.__active_led = True

    def heatmap_index(self):
        """Heatmap Count."""
        return self.hm_index

    def set_heatmap_index(self, hmcount):
        """Set Heatmap."""
        self.hm_index = hmcount

    def active(self):
        """Active."""
        return self.__active_led

    def set_inactive(self):
        """Mark Airport as Inactive."""
        self.__active_led = False

    def best_runway(self):
        """Examine the list of known runways to find the best alignment to the wind."""
        if self.__runway_dataset is None:
            return None
        best_runway = None
        best_delta = None
        if self.__runway_dataset is None:
            return best_runway
        for runway in self.__runway_dataset:
            # debugging.info(runway)
            runway_closed = runway["closed"]
            if runway_closed:
                continue
            runway_direction_le = runway["le_heading_degT"]
            runway_wind_delta_le = abs(runway_direction_le - self.__wind_dir_degrees)
            runway_direction_he = runway["he_heading_degT"]
            runway_wind_delta_he = abs(runway_direction_he - self.__wind_dir_degrees)
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
        """Set WX Category to ENUM based on current wx_category_str."""
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

    def wx_category_str(self):
        """Return string form of airport weather category."""
        return self.__wx_category_str

    def winddir_degrees(self):
        """Return reported windspeed."""
        return self.__wind_dir_degrees

    def get_wx_windspeed(self):
        """Return reported windspeed."""
        return self.__wind_speed_kt

    def get_adds_metar(self, metar_dict):
        """Try get Fresh METAR data from local Aviation Digital Data Service (ADDS) download."""
        debugging.info("get_adds_metar WX from adds for " + self.__icao)
        if self.__icao in ("ksea", "kbfi"):
            debugging.info(f"{self.__icao}\n****\n{metar_dict}\n****\n")
        if self.__icao not in metar_dict:
            # TODO: If METAR data is missing from the ADDS dataset, then it hasn't been updated
            # We have the option to try a direct query for the data ; but don't have any hint
            # on which alternative source to use.
            # We also need to wonder if we want to copy over data from the previous record
            # to this record... so we have some persistance of data rather than losing the airport completely.
            debugging.info("metar_dict WX for " + self.__icao + " missing")
            self.wx_category = AirportFlightCategory.UNKN
            self.__wx_category_str = "UNKN"
            self.set_metar(None)
            return False
        debugging.info("get_adds_metar WX from adds for (1) " + self.__icao)
        debugging.info(metar_dict[self.__icao])
        # Don't need to worry about these entries existing
        # We check for valid data when we create the Airport data
        raw_metar = metar_dict[self.__icao]["raw_text"]
        debugging.info("get_adds_metar WX from adds for (1b) " + self.__icao)
        self.set_metar(raw_metar)
        debugging.info("get_adds_metar WX from adds for (1c) " + self.__icao)
        self.wx_visibility = metar_dict[self.__icao]["visibility"]
        self.wx_ceiling = metar_dict[self.__icao]["ceiling"]
        self.__wind_speed_kt = metar_dict[self.__icao]["wind_speed_kt"]
        self.__wind_dir_degrees = metar_dict[self.__icao]["wind_dir_degrees"]
        self.wx_windgust = metar_dict[self.__icao]["wind_gust_kt"]
        self.__wx_category_str = metar_dict[self.__icao]["flight_category"]
        self.__latitude = float(metar_dict[self.__icao]["latitude"])
        self.__longitude = float(metar_dict[self.__icao]["longitude"])
        if self.__latitude == "Missing" or self.__longitude == "Missing":
            self.__coordinates = False
            debugging.info(f"Coordinates missing for {self.__icao}")
        else:
            self.__coordinates = True
        debugging.info("get_adds_metar WX from adds for (2) " + self.__icao)
        self.set_wx_category(self.__wx_category_str)
        debugging.info("get_adds_metar WX from adds for (3) " + self.__icao)
        try:
            debugging.info("get_adds_metar WX from adds for (4) " + self.__icao)
            utils_wx.calculate_wx_from_metar(self)
            return True
        except Exception as err:
            debug_string = f"Error: get_adds_metar processing {self.__icao} metar:{self.get_raw_metar()}:"
            debugging.debug(debug_string)
            debugging.debug(err)
        return False

    def update_raw_metar(self, raw_metar_text):
        """Roll over the metar data."""
        self.__metar_prev = self.__metar
        self.__metar_date = datetime.now()
        self.__metar = raw_metar_text

    def update_airport_xml(self, station_id, metar_data):
        """Update Airport METAR data from XML record."""
        # Pulling this processing out of the update loop ; it needs to move to airport.py

        next_object = metar_data.find("raw_text")
        if next_object is not None:
            self.update_raw_metar(next_object.text)
        else:
            self.update_raw_metar("Missing")

        next_object = metar_data.find("observation_time")
        if next_object is not None:
            self.__observation_time = next_object.text
        else:
            self.__observation_time = "Missing"

        next_object = metar_data.find("wind_dir_degrees")
        if next_object is not None:
            try:
                next_val = int(next_object.text)
            except (TypeError, ValueError):
                next_val_int = False
            else:
                next_val_int = True
            if next_val_int:
                self.__wind_dir_degrees = next_val
            else:
                # FIXME: Hack to handle complex wind definitions (eg: VRB)
                debugging.debug(
                    f"GRR: wind_dir_degrees parse mismatch - setting to zero; actual:{next_object.text}:"
                )
                self.__wind_dir_degrees = 0
        else:
            self.__wind_dir_degrees = 0

        next_object = metar_data.find("wind_speed_kt")
        if next_object is not None:
            try:
                next_val = int(next_object.text)
            except (TypeError, ValueError):
                next_val_int = False
            else:
                next_val_int = True
            if next_val_int:
                self.__wind_speed_kt = int(next_object.text)
            else:
                # FIXME: Hack to handle complex wind definitions (eg: VRB)
                debugging.debug(
                    f"GRR: wind_speed_kt parse mismatch - setting to zero; actual:{next_object.text}:"
                )
                self.__wind_speed_kt = 0
        else:
            self.__wind_speed_kt = 0

        next_object = metar_data.find("metar_type")
        if next_object is not None:
            self.__metar_type = next_object.text
        else:
            self.__metar_type = "Missing"

        next_object = metar_data.find("wind_gust_kt")
        if next_object is not None:
            try:
                next_val = int(next_object.text)
            except (TypeError, ValueError):
                next_val_int = False
            else:
                next_val_int = True
            if next_val_int:
                self.__wind_gust_kt = int(next_object.text)
            else:
                # FIXME: Hack to handle complex wind definitions (eg: VRB)
                debugging.debug(
                    f"GRR: wind_gust_kt parse mismatch - setting to zero; actual:{next_object.text}:"
                )
                self.__wind_gust_kt = 0
        else:
            self.__wind_gust_kt = 0

        next_object = metar_data.find("sky_condition")
        if next_object is not None:
            self.__sky_condition = next_object.text
        else:
            self.__sky_condition = "Missing"

        next_object = metar_data.find("flight_category")
        if next_object is not None:
            self.__flight_category = next_object.text
        else:
            # This may be legitimately empty; if the metar has incomplete data.
            # No visibility information is a case where flight_category is not set
            self.__flight_category = "Missing"

        next_object = metar_data.find("ceiling")
        if next_object is not None:
            self.__ceiling = next_object.text
        else:
            self.__ceiling = "Missing"

        next_object = metar_data.find("visibility_statute_mi")
        if next_object is not None:
            self.__visibility_statute_mi = next_object.text
        else:
            self.__visibility_statute_mi = "Missing"

        found_latitude = False
        next_object = metar_data.find("latitude")
        if next_object is not None:
            self.__latitude = next_object.text
            found_latitude = True
        else:
            self.__latitude = "Missing"

        found_longitude = False
        next_object = metar_data.find("longitude")
        if next_object is not None:
            self.__longitude = next_object.text
            found_longitude = True
        else:
            self.__longitude = "Missing"

        if found_latitude and found_longitude:
            self.__coordinates = True
        else:
            self.__coordinates = False

    def update_wx(self, metar_xml_dict):
        """Update Weather Data - Get fresh METAR."""
        freshness = False
        if self.__wxsrc == "adds":
            try:
                debugging.info("Update USA Metar: ADDS " + self.__icao)
                freshness = self.get_adds_metar(metar_xml_dict)
                # freshness = True
            except Exception as err:
                debugging.error(err)
        elif self.__wxsrc.startswith("neigh"):
            # Get METAR data from alternative Airport
            strparts = self.__wxsrc.split(":")
            alt_aprt = strparts[1]
            debugging.info(f"{self.__icao} needs metar for {alt_aprt}")
            try:
                debugging.info(
                    f"Update USA Metar(neighbor): ADDS {self.__icao} ({alt_aprt})"
                )
                freshness = self.get_adds_metar(alt_aprt)
                # freshness = True
            except Exception as err:
                debugging.error(err)
        elif self.__wxsrc == "usa-metar":
            # This is the scenario where we want to query an individual METAR record
            # directly. This is unused for now - we may want to use it if the
            # adds data is missing.
            # If the adds data is missing, then we need to find stable reliable and free sources of metar data for all geographies
            debugging.info(
                f"Update USA Metar: {self.__icao} - {self.__wx_category_str}"
            )
            freshness = utils_wx.get_usa_metar(self)
            if freshness:
                # get_*_metar() returned true, so weather is still fresh
                return
            utils_wx.calculate_wx_from_metar(self)
        return
