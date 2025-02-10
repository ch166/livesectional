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
import utils


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

    UNUSED = "unused"

    _icao = None
    _iata = None
    _latitude = 0
    _longitude = 0
    _coordinates = False

    # Airport Configuration
    _wxsrc = None
    _metar = None
    _metar_date = None
    _observation = None
    _observation_time = None
    _runway_dataset = None
    _processed_metar_object = None

    # Application Status for Airport
    _purpose = UNUSED
    _active_led = None
    _led_index = None
    _updated_time = None

    # XML Data
    _flight_category = None
    _sky_condition = None

    # Airport Weather Data
    _metar_type = None
    _wx_conditions = ()
    _active_wx_conditions = False
    _wx_visibility = None
    _visibility_statute_mi = None
    _wx_ceiling = None
    _wind_dir_degrees = None
    _wind_speed_kt = None
    _wx_wind_gust = None
    _wind_gust_kt = None
    _wx_category = None
    _wx_category_str = "UNSET"
    _ceiling = None

    _mos_forecast = None

    # Runway data
    _best_runway = None
    _best_runway_deg = None
    _best_runway_width = None

    # HeatMap
    _hm_index = 0
    # Airport came from Config file
    _loaded_from_config = False
    # Global Data
    _metar_returncode = ""

    # Stats
    _metar_update_count = 0
    _short_update_cycle = 10000

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
        self._metar_date = datetime.now() - timedelta(days=1)  # Make initial date "old"
        self._observation = None
        self._observation_time = None
        self._runway_dataset = None

        # Application Status for Airport
        self._purpose = self.UNUSED
        self._active_led = None
        self._led_index = None
        self._updated_time = datetime.now()

        # XML Data
        self._flight_category = None
        self._sky_condition = None

        # Airport Weather Data
        self._metar_type = None
        self._wx_conditions = ()
        self._active_wx_conditions = False
        self._wx_visibility = None
        self._visibility_statute_mi = None
        self._wx_ceiling = None
        self._wind_dir_degrees = None
        self._wind_speed_kt = None
        self._wx_wind_gust = None
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

    def min_update_interval(self):
        return self._short_update_cycle

    def update_count(self):
        return self._metar_update_count

    def loaded_from_config(self, save_flag):
        """Airport was loaded from config file."""
        self._loaded_from_config = save_flag

    def save_in_config(self):
        """Airport to be saved in config file."""
        return self._loaded_from_config

    def purpose(self):
        """Return Airport Purpose."""
        return self._purpose

    def set_purpose(self, purpose):
        """Set Airport Purpose."""
        self._purpose = purpose

    def set_purpose_unused(self):
        """Return Airport Purpose."""
        self._purpose = self.UNUSED

    def flightcategory(self) -> str:
        """Return flight category data."""
        return self._flight_category

    def flight_category(self) -> str:
        """Return string form of airport weather category."""
        return self._wx_category_str

    def latitude(self) -> float:
        """Return Airport Latitude."""
        return float(self._latitude)

    def longitude(self) -> float:
        """Return Airport longitude."""
        return float(self._longitude)

    def valid_coordinates(self) -> bool:
        """Are lat/lon coordinates set to something other than Missing."""
        return self._coordinates

    def update_coordinates(self, lon, lat):
        """Update Coordinates"""
        debugging.debug(f"coord update {self._icao} {lon}/{lat}")
        if not self._coordinates:
            self._latitude = lat
            self._longitude = lon
            self._coordinates = True
            return
        if self._coordinates and ((lon != 0) or (lat != 0)):
            if lon == "Missing" or lat == "Missing":
                # If we have existing coordinates, we need a new full set to replace them
                return
            self._latitude = lat
            self._longitude = lon
            self._coordinates = True

    def icao_code(self) -> str:
        """Airport ICAO (4 letter) code."""
        return self._icao

    def iata_code(self) -> str:
        """Airport IATA (3 letter) Code."""
        return self._iata

    def update_metar(self, metartext):
        """Get Current METAR."""
        # debugging.info(f"Metar set for {self._icao} to :{metartext}")
        # Track the shortest update interval
        self._metar_update_count += 1
        time_now = datetime.now()

        if self._metar_date is not None:
            update_timedelta = time_now - self._metar_date
            if (update_timedelta.days == 0) and (update_timedelta.seconds < 10):
                debugging.info(f"short update: {self._icao} {update_timedelta}")
                return
            if update_timedelta.seconds < self._short_update_cycle:
                self._short_update_cycle = update_timedelta.seconds

        self._metar_date = time_now
        self._updated_time = time_now
        if metartext is None or metartext == "Missing":
            self._metar = "Missing"
            self._processed_metar_object = None
            return
        self._metar = metartext
        utils_wx.calculate_wx_from_metar(self)
        return

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

    def raw_metar(self) -> str:
        """Return raw METAR data."""
        return self._metar

    def metar_age(self):
        """Return Timestamp of METAR."""
        return self._metar_date

    def wxconditions(self):
        """Return list of weather conditions at Airport."""
        return self._wx_conditions

    def wxconditions_str(self) -> str:
        """Return list of weather conditions at Airport."""
        if self._wx_conditions is None:
            return ""
        return utils_wx.print_wx_conditions(self._wx_conditions)

    def active_wx_conditions(self) -> bool:
        return self._active_wx_conditions

    def set_wx_conditions(self, wx_conditions):
        """Update tuple of weather conditions at Airport."""
        self._wx_conditions = wx_conditions
        self._active_wx_conditions = False
        if len(wx_conditions) > 0:
            self._active_wx_conditions = True

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

    def get_led_index(self) -> int:
        """Return LED ID."""
        return self._led_index

    def wxsrc(self) -> str:
        """Get Weather source."""
        return self._wxsrc

    def set_wxsrc(self, wxsrc):
        """Set Weather source."""
        self._wxsrc = wxsrc

    def heatmap_index(self) -> int:
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

    def best_runway_deg(self):
        """Return computed runway degree value for best identified runway"""
        if self._best_runway_deg is None:
            return 0
        return self._best_runway_deg

    def best_runway_width(self) -> int:
        if self._best_runway_width is None:
            return 0
        return self._best_runway_width

    def best_runway(self):
        return self._best_runway

    def refresh_best_runway(self):
        """Examine the list of known runways to find the best alignment to the wind."""
        best_runway_deg = None
        best_delta = None
        best_runway_width = 0
        best_runway_ident = "No Runway Found"
        best_runway_length = 0
        if self._runway_dataset is None or self._wind_dir_degrees is None:
            self._best_runway = best_runway_ident
            self._best_runway_deg = best_runway_deg
            self._best_runway_width = best_runway_width
            return

        for runway in self._runway_dataset:
            if runway["closed"] == "1":
                continue

            runway_direction_le_str = runway["le_heading_degT"]
            if runway_direction_le_str.isnumeric():
                runway_direction_le = int(runway_direction_le_str)
            else:
                # TODO: Need an escape here when we can't properly parse one of a set of runways
                runway_direction_le = 0

            runway_direction_he_str = runway["he_heading_degT"]
            if runway_direction_he_str.isnumeric():
                runway_direction_he = int(runway_direction_he_str)
            else:
                runway_direction_he = 0

            runway_wind_delta_le = abs(runway_direction_le - self._wind_dir_degrees)
            runway_wind_delta_he = abs(runway_direction_he - self._wind_dir_degrees)
            better_delta = min(runway_wind_delta_le, runway_wind_delta_he)

            # TODO: Would be nice when an airport has two parallel runways to pick a *better* one.
            # At this stage we have access to runway length information - so perhaps prioritize longer runways
            # Would be fantastic at some magical future time to pick runway based on any knowledge aboutv published IFR approach details.

            if type(runway["length_ft"]) is str:
                result, better_runway_length = utils.str2int(runway["length_ft"])
            else:
                better_runway_length = runway["length_ft"]

            if type(runway["length_ft"]) is str:
                result, better_runway_width = utils.str2int(runway["length_ft"])
            else:
                better_runway_width = runway["length_ft"]

            if runway_wind_delta_le < runway_direction_he:
                better_runway = runway_direction_le
                better_runway_ident = runway["le_ident"]
            else:
                better_runway = runway_direction_he
                better_runway_ident = runway["he_ident"]
            if (
                (best_runway_deg is None)
                or (better_delta < best_delta)
                or (
                    (better_delta <= best_delta)
                    and (better_runway_length > best_runway_length)
                )
            ):
                best_runway_deg = better_runway
                best_delta = better_delta
                best_runway_ident = better_runway_ident
                best_runway_width = better_runway_width
                best_runway_length = better_runway_length
        self._best_runway = best_runway_ident
        self._best_runway_deg = best_runway_deg
        self._best_runway_width = best_runway_width

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
        if self._wind_speed_kt is None:
            return -1
        return self._wind_speed_kt

    def get_adds_metar(self, metar_airport_dict):
        """Try to get Fresh METAR data from local Aviation Digital Data Service (ADDS) download."""
        debugging.debug("get_adds_metar WX from adds for " + self._icao)
        raw_metar = metar_airport_dict["raw_text"]
        self.update_metar(raw_metar)
        self._wx_visibility = metar_airport_dict["visibility"]
        self._wx_ceiling = metar_airport_dict["ceiling"]
        self._wind_speed_kt = metar_airport_dict["wind_speed_kt"]
        self._wind_dir_degrees = metar_airport_dict["wind_dir_degrees"]
        self._wx_wind_gust = metar_airport_dict["wind_gust_kt"]
        self._wx_category_str = metar_airport_dict["flight_category"]
        adds_latitude = float(metar_airport_dict["latitude"])
        adds_longitude = float(metar_airport_dict["longitude"])
        self.update_coordinates(adds_longitude, adds_latitude)
        self.set_wx_category(self._wx_category_str)
        # try:
        #     utils_wx.calculate_wx_from_metar(self)
        #     return True
        # except Exception as err:
        #     debug_string = f"Error: get_adds_metar processing {self._icao} metar:{self.raw_metar()}:"
        #     debugging.debug(debug_string)
        #    debugging.debug(err)
        return True

    def metar_object(self):
        """Return processed metar object."""
        return self._processed_metar_object

    def update_from_adds_xml(self, station_id, metar_data):
        """Update Airport METAR data from XML record."""

        next_object = metar_data.find("raw_text")
        if next_object is not None:
            self.update_metar(next_object.text)
        else:
            self.update_metar("Missing")

        next_object = metar_data.find("observation_time")
        if next_object is not None:
            self._observation_time = next_object.text
        else:
            self._observation_time = "Missing"

        next_object = metar_data.find("wind_dir_degrees")
        next_val = None
        if next_object is not None:
            next_val_int, next_val = utils.str2int(next_object.text)
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
            next_val_int, next_val = utils.str2int(next_object.text)
            if next_val_int:
                self._wind_speed_kt = next_val
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
            next_val_int, next_val = utils.str2int(next_object.text)
            if next_val_int:
                self._wind_gust_kt = next_val
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
            adds_latitude = next_object.text
            found_latitude = True
        else:
            adds_latitude = "Missing"

        found_longitude = False
        next_object = metar_data.find("longitude")
        if next_object is not None:
            adds_longitude = next_object.text
            found_longitude = True
        else:
            adds_longitude = "Missing"

        if found_latitude and found_longitude:
            self.update_coordinates(adds_longitude, adds_latitude)

    def update_wx(self, airport_master_dict):
        """Update Weather Data - Get fresh METAR."""
        if self._wxsrc is None:
            return False
        if self._wxsrc == "adds":
            self.update_metar(self._metar)
            return True
        if self._wxsrc.startswith("neigh"):
            # Get METAR data from alternative Airport
            str_parts = self._wxsrc.split(":")
            alt_aprt_name = str_parts[1]
            debugging.info(f"{self._icao} needs metar for {alt_aprt_name}")
            try:
                debugging.debug(
                    f"Update USA Metar(neighbor): ADDS {self._icao} ({alt_aprt_name})"
                )
                if alt_aprt_name not in airport_master_dict:
                    debugging.info(
                        f"metar_airport_dict WX for Neighbor Airport {alt_aprt_name} missing"
                    )
                    debugging.info(f"len: {len(airport_master_dict)}")
                    self._wx_category = AirportFlightCategory.UNKN
                    self._wx_category_str = "UNKN"
                    self.update_metar(None)
                    return False
                alt_arpt = airport_master_dict[alt_aprt_name]
                self.update_metar(alt_arpt.raw_metar())
                return True
            except Exception as err:
                debugging.error(err)
        elif self._wxsrc == "usa-metar":
            # This is the scenario where we want to query an individual METAR record
            # directly. This is unused for now - we may want to use it if the adds data is missing.
            # If the adds data is missing, then we need to find stable reliable and free sources of metar data for all geographies
            debugging.info(f"Update USA Metar: {self._icao} - {self._wx_category_str}")
            freshness = utils_wx.get_usa_metar(self)
            if freshness:
                # get_*_metar() returned true, so weather is still fresh
                return True
            self.update_metar(self._metar)
        return False
