# -*- coding: utf-8 -*- #
"""
Created on Sat Jun 15 08:01:44 2019

@author: Chris Higgins

"""

# This is the collection and aggregation of all functions that manage Airports and airport weather
# products. It's initially focused on processing METARs, but will end up including all the functions
# related to TAFs and MOS data.
#
# This file is the management of the Airport object
# The airport object stores all the interesting data for an airport
# - Airport ICAO code
# - Weather Source ( adds , metar URL, future options)
# - Airport Code to use for WX data (future - for airports without active ASOS/AWOSporting)
# - Current conditions
# - etc.

from datetime import datetime
from datetime import timedelta

# from distutils import util
from enum import Enum, auto

import debugging
import utils_wx
import utils_mos


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
        self._icao = icao
        self._iata = None
        self._latitude = 0
        self._longitude = 0
        self._coordinates = False

        # Airport Configuration
        self._wxsrc = None
        self._metar = metar
        self._metar_prev = None
        self._metar_date = datetime.now() - timedelta(
            days=1
        )  # Make initial date "old"
        self._observation = None
        self._observation_time = None
        self._runway_dataset = None

        # Application Status for Airport
        self._enabled = True
        self._purpose = "off"
        self._active_led = None
        self._led_active_state = None
        self._led_index = None
        self._updated_time = datetime.now()

        # XML Data
        self._flight_category = None
        self._sky_condition = None

        # Airport Weather Data
        self._metar_type = None
        self._wx_conditions = ()
        self._wx_visibility = None
        self._visibility_statute_mi = None
        self._wx_ceiling = None
        self._wind_dir_degrees = None
        self._wind_speed_kt = None
        self._wx_windgust = None
        self._wind_gust_kt = None
        self._wx_category = None
        self._wx_category_str = "UNSET"
        self._ceiling = None

        self._mos_forecast = None

        # HeatMap
        self._hm_index = 0

        # Airport came from Config file
        self._loaded_from_config = False

        # Global Data
        self._metar_returncode = ""

    def last_updated(self):
        """Get last updated time."""
        return self._updated_time

    def loaded_from_config(self):
        """Airport was loaded from config file."""
        self._loaded_from_config = True

    def save_in_config(self):
        """Airport to be saved in config file."""
        # FIXME: What is this trying to do ?
        self._loaded_from_config

    def purpose(self):
        """Return Airport Purpose."""
        return self._purpose

    def set_purpose(self, purpose):
        """Return Airport Purpose."""
        self._purpose = purpose

    def flightcategory(self):
        """Return flight category data."""
        return self._flight_category

    def flight_category(self):
        """Return string form of airport weather category."""
        return self._wx_category_str

    def latitude(self):
        """Return Airport Latitude."""
        return float(self._latitude)

    def longitude(self):
        """Return Airport longitude."""
        return float(self._longitude)

    def valid_coordinates(self):
        """Are lat/lon coordinates set to something other than Missing."""
        return self._coordinates

    def icao_code(self):
        """Airport ICAO (4 letter) code."""
        return self._icao

    def iata_code(self):
        """Airport IATA (3 letter) Code."""
        return self._iata

    def update_metar(self, metartext):
        """Get Current METAR."""
        # debugging.info(f"Metar set for {self._icao} to :{metartext}")
        self._metar_prev = self._metar
        self._metar = metartext
        self._metar_date = datetime.now()
        self._updated_time = datetime.now()

    def set_mos_forecast(self, mos_forecast):
        """Update MOS forecast."""
        self._mos_forecast = mos_forecast

    def get_full_mos_forecast(self):
        """Update MOS forecast."""
        return self._mos_forecast

    def get_mos_forecast(self, app_conf, hour_offset):
        """Get MOS data for future time."""
        flightcategory = utils_mos.get_mos_weather(
            self._mos_forecast, app_conf, hour_offset
        )
        return flightcategory

    def raw_metar(self):
        """Return raw METAR data."""
        return self._metar

    def metar_age(self):
        """Return Timestamp of METAR."""
        return self._metar_date

    def wxconditions(self):
        """Return list of weather conditions at Airport."""
        return self._wx_conditions

    def get_ca_metar(self):
        """Try to get Fresh METAR data for Canadian Airports."""
        # TODO:
        # The ADDS data source appears to have all the data for all the locations.
        # May be able to delete this entirely
        return False

    def get_airport_wx_xml(self):
        """Pull Airport XML data from ADDS XML."""
        # TODO: Stub

    def set_led_index(self, led_index):
        """Update LED ID."""
        self._led_index = led_index

    def get_led_index(self):
        """Return LED ID."""
        return self._led_index

    def wxsrc(self):
        """Get Weather source."""
        return self._wxsrc

    def set_wxsrc(self, wxsrc):
        """Set Weather source."""
        self._wxsrc = wxsrc

    def heatmap_index(self):
        """Heatmap Count."""
        return self._hm_index

    def set_heatmap_index(self, hmcount):
        """Set Heatmap."""
        self._hm_index = hmcount

    def active(self):
        """Active."""
        return self._active_led

    def set_active(self):
        """Mark Airport as Active."""
        self._active_led = True

    def set_inactive(self):
        """Mark Airport as Inactive."""
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
            # debugging.info(runway)
            runway_closed = runway["closed"]
            if runway_closed == '1':
                continue
            runway_direction_le = int(runway["le_heading_degT"])
            runway_wind_delta_le = abs(runway_direction_le - self._wind_dir_degrees)
            runway_direction_he = int(runway["he_heading_degT"])
            runway_wind_delta_he = abs(runway_direction_he - self._wind_dir_degrees)
            better_delta = min(runway_wind_delta_le, runway_wind_delta_he)
            if runway_wind_delta_le < runway_direction_he:
                better_runway = runway_direction_le
            else:
                better_runway = runway_direction_he
            if (best_runway is None) or (better_delta < best_delta):
                best_runway = better_runway
                best_delta = better_delta
        return best_runway

    def set_wx_category(self, wx_category_str):
        """Set WX Category to ENUM based on current wx_category_str."""
        # Calculate Flight Category
        if wx_category_str == "UNKN":
            self._wx_category = AirportFlightCategory.UNKN
        elif wx_category_str == "LIFR":
            self._wx_category = AirportFlightCategory.LIFR
        elif wx_category_str == "IFR":
            self._wx_category = AirportFlightCategory.IFR
        elif wx_category_str == "VFR":
            self._wx_category = AirportFlightCategory.VFR
        elif wx_category_str == "MVFR":
            self._wx_category = AirportFlightCategory.MVFR

    def winddir_degrees(self):
        """Return reported windspeed."""
        return self._wind_dir_degrees

    def runway_data(self):
        """Update Runway Data."""
        return self._runway_dataset

    def set_runway_data(self, runway_dataset):
        """Update Runway Data."""
        self._runway_dataset = runway_dataset

    def wx_windspeed(self):
        """Return reported windspeed."""
        return self._wind_speed_kt

    def get_adds_metar(self, metar_airport_dict):
        """Try to get Fresh METAR data from local Aviation Digital Data Service (ADDS) download."""
        debugging.info("get_adds_metar WX from adds for " + self._icao)
        if self._icao in ["ksea", "kbfi", "k11s", "cwsp"]:
            debugging.info(f"{self._icao}\n****\n{metar_airport_dict}\n****\n")

        raw_metar = metar_airport_dict["raw_text"]
        self.update_metar(raw_metar)
        self._wx_visibility = metar_airport_dict["visibility"]
        self._wx_ceiling = metar_airport_dict["ceiling"]
        self._wind_speed_kt = metar_airport_dict["wind_speed_kt"]
        self._wind_dir_degrees = metar_airport_dict["wind_dir_degrees"]
        self._wx_windgust = metar_airport_dict["wind_gust_kt"]
        self._wx_category_str = metar_airport_dict["flight_category"]
        self._latitude = float(metar_airport_dict["latitude"])
        self._longitude = float(metar_airport_dict["longitude"])
        if self._latitude == "Missing" or self._longitude == "Missing":
            self._coordinates = False
            debugging.info(f"Coordinates missing for {self._icao}")
        else:
            self._coordinates = True
        self.set_wx_category(self._wx_category_str)
        try:
            utils_wx.calculate_wx_from_metar(self)
            return True
        except Exception as err:
            debug_string = f"Error: get_adds_metar processing {self._icao} metar:{self.raw_metar()}:"
            debugging.debug(debug_string)
            debugging.debug(err)
        return False

    def update_raw_metar(self, raw_metar_text):
        """Roll over the metar data."""
        self._metar_prev = self._metar
        self._metar_date = datetime.now()
        self._metar = raw_metar_text

    def update_from_adds_xml(self, station_id, metar_data):
        """Update Airport METAR data from XML record."""

        next_object = metar_data.find("raw_text")
        if next_object is not None:
            self.update_raw_metar(next_object.text)
        else:
            self.update_raw_metar("Missing")

        next_object = metar_data.find("observation_time")
        if next_object is not None:
            self._observation_time = next_object.text
        else:
            self._observation_time = "Missing"

        next_object = metar_data.find("wind_dir_degrees")
        next_val = None
        if next_object is not None:
            try:
                next_val = int(next_object.text)
            except (TypeError, ValueError):
                next_val_int = False
            else:
                next_val_int = True
            if next_val_int:
                self._wind_dir_degrees = next_val
            else:
                # FIXME: Hack to handle complex wind definitions (eg: VRB)
                debugging.debug(
                    f"GRR: wind_dir_degrees parse mismatch - setting to zero; actual:{next_object.text}:"
                )
                self._wind_dir_degrees = 0
        else:
            self._wind_dir_degrees = 0

        next_object = metar_data.find("wind_speed_kt")
        if next_object is not None:
            try:
                next_val = int(next_object.text)
            except (TypeError, ValueError):
                next_val_int = False
            else:
                next_val_int = True
            if next_val_int:
                self._wind_speed_kt = int(next_object.text)
            else:
                # FIXME: Hack to handle complex wind definitions (eg: VRB)
                debugging.debug(
                    f"GRR: wind_speed_kt parse mismatch - setting to zero; actual:{next_object.text}:"
                )
                self._wind_speed_kt = 0
        else:
            self._wind_speed_kt = 0

        next_object = metar_data.find("metar_type")
        if next_object is not None:
            self._metar_type = next_object.text
        else:
            self._metar_type = "Missing"

        next_object = metar_data.find("wind_gust_kt")
        if next_object is not None:
            try:
                next_val = int(next_object.text)
            except (TypeError, ValueError):
                next_val_int = False
            else:
                next_val_int = True
            if next_val_int:
                self._wind_gust_kt = int(next_object.text)
            else:
                # FIXME: Hack to handle complex wind definitions (eg: VRB)
                debugging.debug(
                    f"GRR: wind_gust_kt parse mismatch - setting to zero; actual:{next_object.text}:"
                )
                self._wind_gust_kt = 0
        else:
            self._wind_gust_kt = 0

        next_object = metar_data.find("sky_condition")
        if next_object is not None:
            self._sky_condition = next_object.text
        else:
            self._sky_condition = "Missing"

        next_object = metar_data.find("flight_category")
        if next_object is not None:
            self._flight_category = next_object.text
        else:
            # This may be legitimately empty; if the metar has incomplete data.
            # No visibility information is a case where flight_category is not set
            self._flight_category = "Missing"

        next_object = metar_data.find("ceiling")
        if next_object is not None:
            self._ceiling = next_object.text
        else:
            self._ceiling = "Missing"

        next_object = metar_data.find("visibility_statute_mi")
        if next_object is not None:
            self._visibility_statute_mi = next_object.text
        else:
            self._visibility_statute_mi = "Missing"

        found_latitude = False
        next_object = metar_data.find("latitude")
        if next_object is not None:
            self._latitude = next_object.text
            found_latitude = True
        else:
            self._latitude = "Missing"

        found_longitude = False
        next_object = metar_data.find("longitude")
        if next_object is not None:
            self._longitude = next_object.text
            found_longitude = True
        else:
            self._longitude = "Missing"

        if found_latitude and found_longitude:
            self._coordinates = True
        else:
            self._coordinates = False

    def update_wx(self, airport_master_dict):
        """Update Weather Data - Get fresh METAR."""
        freshness = False
        if self._wxsrc == "adds":
            # WX Updated in main loop
            return True
        elif self._wxsrc.startswith("neigh"):
            # Get METAR data from alternative Airport
            strparts = self._wxsrc.split(":")
            alt_aprt = strparts[1]
            debugging.info(f"{self._icao} needs metar for {alt_aprt}")
            try:
                debugging.info(
                    f"Update USA Metar(neighbor): ADDS {self._icao} ({alt_aprt})"
                )
                if alt_aprt not in airport_master_dict:
                    debugging.info(f"metar_airport_dict WX for Neighbor Airport {alt_aprt} missing")
                    debugging.info(f"len: {len(airport_master_dict)}")
                    self._wx_category = AirportFlightCategory.UNKN
                    self._wx_category_str = "UNKN"
                    self.update_metar(None)
                    return False
                self.update_metar(airport_master_dict[alt_aprt]["raw_text"])
                # freshness = True
            except Exception as err:
                debugging.error(err)
        elif self._wxsrc == "usa-metar":
            # This is the scenario where we want to query an individual METAR record
            # directly. This is unused for now - we may want to use it if the
            # adds data is missing.
            # If the adds data is missing, then we need to find stable reliable and free sources of metar data for all geographies
            debugging.info(
                f"Update USA Metar: {self._icao} - {self._wx_category_str}"
            )
            freshness = utils_wx.get_usa_metar(self)
            if freshness:
                # get_*_metar() returned true, so weather is still fresh
                return
            utils_wx.calculate_wx_from_metar(self)
        return freshness
