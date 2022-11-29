# -*- coding: utf-8 -*- #
"""
Created on Mon Sept 5 08:01:44 2022.

@author: Chris Higgins
"""

# This is the collection and aggregation of all functions that
# parse METAR, Weather, TAF data

# It includes supporting utility functions

from datetime import datetime
from datetime import timedelta

# from distutils import util
from enum import Enum
from urllib.request import urlopen
import urllib.error
import socket


from metar import Metar
import debugging
import utils


class WxConditions(Enum):
    """
    ENUM Identifying Weather Conditions.
    """

    HIGHWINDS = 1
    GUSTS = 2
    SNOW = 3
    LIGHTNING = 4
    FOG = 5


def get_usa_metar(airport_data):
    """Try get Fresh METAR Data if current data is more than METAREXPIRY minutes old"""
    timenow = datetime.now()
    if not airport_data.enabled:
        return True
    # TODO: Move this to config
    metarexpiry = 5
    expiredtime = timenow - timedelta(minutes=metarexpiry)
    if airport_data.metar_date > expiredtime:
        # Metar Data still fresh
        debugging.debug("METAR is fresh  : " + airport_data.icao + " - " + airport_data.wx_category_str)
        return True
    # TODO: Move this to config
    metar_url_usa = "https://tgftp.nws.noaa.gov/data/observations/metar/stations"
    url = "%s/%s.TXT" % (metar_url_usa, airport_data.icao.upper())
    debugging.info("Retrieving METAR from: " + url)
    urlh = None
    try:
        urlh = urlopen(url)
        report = ""
        for line in urlh:
            if not isinstance(line, str):
                line = line.decode()  # convert Python3 bytes buffer to string
            if line.startswith(airport_data.icao.upper()):
                report = line.strip()
                airport_data.metar_date = timenow
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = report
                debugging.info(report)
        if not report:
            debugging.debug("No data for " + airport_data.icao)
    except urllib.error.HTTPError:
        debugging.debug("HTTPError retrieving " + airport_data.icao + " data")
    except urllib.error.URLError:
        # import traceback
        # debugging.info(traceback.format_exc())
        debugging.debug("URLError retrieving " + airport_data.icao + " data")
        if urlh:
            if urlh.getcode() == 404:
                airport_data.metar_date = timenow
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = "URL 404 Error : Disabling"
                airport_data.enabled = False
                return True
            else:
                # airport_data.metar_date = timenow
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = "Transient Error"
                return True
        else:
            debugging.debug("URLError: urlh not set")
            # airport_data.metar_date = timenow
            airport_data.metar_prev = airport_data.metar
            airport_data.metar = "Transient Error"
            return True
    except (socket.error, socket.gaierror):
        debugging.info("Socket Error retrieving " + airport_data.icao)
        # airport_data.metar_date = timenow
        airport_data.metar_prev = airport_data.metar
        airport_data.metar = "Transient Error"
        return True
    return False


def cloud_height(wx_metar):
    """Calculate Height to Broken Layer
    wx_metar - METAR String"""
    # debugging.info(wx_data.observation.sky)
    wx_data = Metar.Metar(wx_metar)
    lowest_ceiling = 100000
    for cloudlayer in wx_data.sky:
        key = cloudlayer[0]
        if key == "VV":
            debugging.debug("Metar: VV Found")
            # Vertical Visibilty Code
        if key in ("CLR", "SKC", "NSC", "NCD"):
            # python metar codes for clear skies.
            return lowest_ceiling
        if not cloudlayer[1]:
            # Not sure why we are here - should have a cloud layer with altitudes
            debugging.debug("Cloud Layer without altitude values " + cloudlayer[0])
            return -1
        layer_altitude = cloudlayer[1].value()
        debugging.debug("LOC: " + wx_metar + " Layer: " + key + " Alt: " + str(layer_altitude))
        if key in ("OVC", "BKN"):
            # Overcast or Broken are considered ceiling
            if layer_altitude < lowest_ceiling:
                lowest_ceiling = layer_altitude
        if key == "VV":
            # """
            # From the AIM - Vertical Visibility (indefinite ceilingheight).
            # The height into an indefinite ceiling is preceded by “VV” and followed
            # by three digits indicating the vertical visibility in hundreds of feet.
            # This layer indicates total obscuration
            # """
            if layer_altitude < lowest_ceiling:
                lowest_ceiling = layer_altitude
        debugging.debug("Ceiling : " + str(lowest_ceiling))

    return lowest_ceiling


def update_wx(airport_data, metar_xml_dict):
    """Update Weather Data - Get fresh METAR"""
    freshness = False
    if airport_data.wxsrc == "adds":
        try:
            debugging.info("Update USA Metar: ADDS " + airport_data.icao)
            freshness = airport_data.get_adds_metar(metar_xml_dict)
        except Exception as e:
            debugging.error(e)
    elif airport_data.wxsrc == "usa-metar":
        debugging.info("Update USA Metar: " + airport_data.icao + " - " + airport_data.wx_category_str)
        freshness = get_usa_metar(airport_data)
        if freshness:
            # get_*_metar() returned true, so weather is still fresh
            return
        calculate_wx_from_metar(airport_data)
    elif airport_data.wxsrc == "ca-metar":
        debugging.info("Update CA Metar: " + airport_data.icao + " and skip")
        freshness = airport_data.get_ca_metar()
        if freshness:
            # get_*_metar() returned true, so weather is still fresh
            return
        airport_data.wx_category_str = "UNK"
        airport_data.set_wx_category(airport_data.wx_category_str)
    return


def calculate_wx_from_metar(airport_data):
    # Should have Good METAR data in airport_data.metar
    # Need to Figure out Airport State
    try:
        airport_data_observation = Metar.Metar(airport_data.metar)
    except Metar.ParserError as e:
        debugging.info("Parse Error for METAR code: " + airport_data.metar)
        debugging.error(e)
        airport_data.wx_category_str = "UNK"
        airport_data.set_wx_category(airport_data.wx_category_str)
        return

    if not airport_data_observation:
        debugging.warn("Have no observations for " + airport_data.icao)
        return False

    if airport_data_observation.wind_gust:
        airport_data.wx_windgust = airport_data_observation.wind_gust.value()
    else:
        airport_data.wx_windgust = 0
    if airport_data.observation.wind_speed:
        airport_data.wx_windspeed = airport_data_observation.wind_speed.value()
    else:
        airport_data.wx_windspeed = 0
    if airport_data.observation.vis:
        airport_data.wx_visibility = airport_data_observation.vis.value()
    else:
        # Set visiblity to -1 to flag as unknown
        airport_data.wx_visibility = -1
    try:
        airport_data.wx_ceiling = cloud_height(airport_data.metar)
    except Exception as e:
        msg = "airport_data.cloud_height() failed for " + airport_data.icao
        debugging.error(msg)
        debugging.error(e)

    # Calculate Flight Category
    if airport_data.wx_ceiling == -1 or airport_data.wx_visibility == -1:
        airport_data.wx_category_str = "UNK"
    elif airport_data.wx_visibility < 1 or airport_data.wx_ceiling < 500:
        airport_data.wx_category_str = "LIFR"
    elif 1 <= airport_data.wx_visibility < 3 or 500 <= airport_data.wx_ceiling < 1000:
        airport_data.wx_category_str = "IFR"
    elif 3 <= airport_data.wx_visibility <= 5 or 1000 <= airport_data.wx_ceiling <= 3000:
        airport_data.wx_category_str = "MVFR"
    elif airport_data.wx_visibility > 5 and airport_data.wx_ceiling > 3000:
        airport_data.wx_category_str = "VFR"
    else:
        airport_data.wx_category_str = "UNK"

    airport_data.set_wx_category(airport_data.wx_category_str)

    debugging.debug("Airport: Ceiling " + str(airport_data.wx_ceiling) + " Visibility " + str(airport_data.wx_visibility))
    debugging.info("Airport " + airport_data.icao + " - " + airport_data.wx_category_str)
    return


def calc_wx_conditions(wx_metar):
    """
    Compute Wind Conditions
    """
    wx_conditions = ()
    wx_data = Metar.Metar(wx_metar)

    if wx_data.wind_speed > 20:
        wx_conditions = wx_conditions + (WxConditions.HIGHWINDS,)
    if wx_data.wind_gust > 0:
        wx_conditions = wx_conditions + (WxConditions.GUSTS,)
    return wx_conditions


def decode_taf_data(wx_data, stationiddict, windsdict, wxstringdict, metar_taf_mos, root_data):
    # FIXME: Moved from update_leds ; fix references to variables over there, that aren't here.
    # TAF decode routine
    # 0 equals display TAF. This routine will decode the TAF, pick the appropriate time frame to display.
    if metar_taf_mos == 0:
        debugging.info("Starting TAF Data Display")
        # start of TAF decoding routine
        for data in root_data.iter("data"):
            # get number of airports reporting TAFs to be used for diagnosis only
            num_results = data.attrib["num_results"]
            debugging.info("\nNum of Airport TAFs = " + num_results)  # debug

        for taf in root_data.iter("TAF"):  # iterate through each airport's TAF
            stationId = taf.find("station_id").text  # debug
            debugging.info(stationId)  # debug
            # debugging.info('Current+Offset Zulu - ' + wx_data.current_zulu)  # debug
            taf_wx_string = ""
            taf_change_indicator = ""
            taf_wind_dir_degrees = ""
            taf_wind_speed_kt = ""
            taf_wind_gust_kt = ""

            # Now look at the forecasts for the airport
            for forecast in taf.findall("forecast"):

                # Routine inspired by Nick Cirincione.
                flightcategory = "VFR"  # intialize flight category
                taf_time_from = forecast.find("fcst_time_from").text  # get taf's from time
                taf_time_to = forecast.find("fcst_time_to").text  # get taf's to time

                if forecast.find("wx_string") is not None:
                    taf_wx_string = forecast.find("wx_string").text  # get weather conditions

                if forecast.find("change_indicator") is not None:
                    taf_change_indicator = forecast.find("change_indicator").text  # get change indicator

                if forecast.find("wind_dir_degrees") is not None:
                    taf_wind_dir_degrees = forecast.find("wind_dir_degrees").text  # get wind direction

                if forecast.find("wind_speed_kt") is not None:
                    taf_wind_speed_kt = forecast.find("wind_speed_kt").text  # get wind speed

                if forecast.find("wind_gust_kt") is not None:
                    taf_wind_gust_kt = forecast.find("wind_gust_kt").text  # get wind gust speed

                # test if current time plus offset falls within taf's timeframe
                if taf_time_from <= utils.current_time_utc(wx_data.conf) <= taf_time_to:
                    debugging.info("FROM - " + taf_time_from)
                    debugging.info(utils.comp_time(utils.current_time_utc(wx_data.conf), taf_time_from))
                    debugging.info("TO - " + taf_time_to)
                    debugging.info(utils.comp_time(utils.current_time_utc(wx_data.conf), taf_time_to))

                    # There can be multiple layers of clouds in each taf, but they are always listed lowest AGL first.
                    # Check the lowest (first) layer and see if it's overcast, broken, or obscured. If it is, then compare to cloud base height to set $
                    # This algorithm basically sets the flight category based on the lowest OVC, BKN or OVX layer.
                    # for each sky_condition from the XML
                    for sky_condition in forecast.findall("sky_condition"):
                        # get the sky cover (BKN, OVC, SCT, etc)
                        sky_cvr = sky_condition.attrib["sky_cover"]
                        debugging.info(sky_cvr)  # debug

                        # If the layer is OVC, BKN or OVX, set Flight category based on height AGL
                        if sky_cvr in ("OVC", "BKN", "OVX"):

                            try:
                                # get cloud base AGL from XML
                                cld_base_ft_agl = sky_condition.attrib["cloud_base_ft_agl"]
                                debugging.info(cld_base_ft_agl)  # debug
                            except Exception as e:
                                # get cloud base AGL from XML
                                debugging.error(e)
                                cld_base_ft_agl = forecast.find("vert_vis_ft").text

                            #  cld_base_ft_agl = sky_condition.attrib['cloud_base_ft_agl'] #get cloud base AGL from XML
                            #  debugging.info(cld_base_ft_agl) #debug

                            cld_base_ft_agl = int(cld_base_ft_agl)
                            if cld_base_ft_agl < 500:
                                flightcategory = "LIFR"
                                break

                            elif 500 <= cld_base_ft_agl < 1000:
                                flightcategory = "IFR"
                                break

                            elif 1000 <= cld_base_ft_agl <= 3000:
                                flightcategory = "MVFR"
                                break

                            elif cld_base_ft_agl > 3000:
                                flightcategory = "VFR"
                                break

                    # visibilty can also set flight category. If the clouds haven't set the fltcat to LIFR. See if visibility will
                    # if it's LIFR due to cloud layer, no reason to check any other things that can set flight category.
                    if flightcategory != "LIFR":
                        # check XML if visibility value exists
                        if forecast.find("visibility_statute_mi") is not None:
                            visibility_statute_mi = forecast.find("visibility_statute_mi").text  # get visibility number
                            visibility_statute_mi = float(visibility_statute_mi)
                            debugging.info(visibility_statute_mi)

                            if visibility_statute_mi < 1.0:
                                flightcategory = "LIFR"

                            if visibility_statute_mi < 1.0:
                                flightcategory = "LIFR"

                            elif 1.0 <= visibility_statute_mi < 3.0:
                                flightcategory = "IFR"

                            # if Flight Category was already set to IFR $
                            elif 3.0 <= visibility_statute_mi <= 5.0 and flightcategory != "IFR":
                                flightcategory = "MVFR"

                    # Print out TAF data to screen for diagnosis only
                    debugging.info("Airport - " + stationId)
                    debugging.info("Flight Category - " + flightcategory)
                    debugging.info("Wind Speed - " + taf_wind_speed_kt)
                    debugging.info("WX String - " + taf_wx_string)
                    debugging.info("Change Indicator - " + taf_change_indicator)
                    debugging.info("Wind Director Degrees - " + taf_wind_dir_degrees)
                    debugging.info("Wind Gust - " + taf_wind_gust_kt)

                    # grab flightcategory from returned FAA data
                    if flightcategory is None:  # if wind speed is blank, then bypass
                        flightcategory = None

                    # grab wind speeds from returned FAA data
                    if taf_wind_speed_kt is None:  # if wind speed is blank, then bypass
                        windspeedkt = 0
                    else:
                        windspeedkt = taf_wind_speed_kt

                    # grab Weather info from returned FAA data
                    if taf_wx_string is None:  # if weather string is blank, then bypass
                        wxstring = "NONE"
                    else:
                        wxstring = taf_wx_string

            # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
            if stationId in stationiddict:
                debugging.info(stationId + " Duplicate, only saved first metar category")
            else:
                # build category dictionary
                stationiddict[stationId] = flightcategory

            if stationId in windsdict:
                debugging.info(stationId + " Duplicate, only saved the first winds")
            else:
                # build windspeed dictionary
                windsdict[stationId] = windspeedkt

            if stationId in wxstringdict:
                debugging.info(stationId + " Duplicate, only saved the first weather")
            else:
                # build weather dictionary
                wxstringdict[stationId] = wxstring
        debugging.info("Decoded TAF Data for Display")

    # All the following appears to be redundant METAR code.
    # Proposing bulk delete.
    elif metar_taf_mos == 1:
        debugging.info("Starting METAR Data Display")
        # start of METAR decode routine if 'metar_taf_mos' equals 1. Script will default to this routine without a rotary switch installed.
        # grab the airport category, wind speed and various weather from the results given from FAA.
        for metar in root_data.iter("METAR"):
            stationId = metar.find("station_id").text

            # METAR Decode Routine to create flight category via cloud cover and/or visability when flight category is not reported.
            # Routine contributed to project by Nick Cirincione. Thank you for your contribution.
            # if category is blank, then see if there's a sky condition or vis that would dictate flight category
            if metar.find("flight_category") is None or metar.find("flight_category") == "NONE":
                flightcategory = "VFR"  # intialize flight category
                sky_cvr = "SKC"  # Initialize to Sky Clear
                debugging.info(stationId + " Not Reporting Flight Category through the API.")

                # There can be multiple layers of clouds in each METAR, but they are always listed lowest AGL first.
                # Check the lowest (first) layer and see if it's overcast, broken, or obscured. If it is, then compare to cloud base height to set flight category.
                # This algorithm basically sets the flight category based on the lowest OVC, BKN or OVX layer.
                # First check to see if the FAA provided the forecast field, if not get the sky_condition.
                if metar.find("forecast") is None or metar.find("forecast") == "NONE":
                    debugging.info("FAA xml data is NOT providing the forecast field for this airport")
                    # for each sky_condition from the XML
                    for sky_condition in metar.findall("./sky_condition"):
                        # get the sky cover (BKN, OVC, SCT, etc)
                        sky_cvr = sky_condition.attrib["sky_cover"]
                        debugging.info("Sky Cover = " + sky_cvr)

                        # Break out of for loop once we find one of these conditions
                        if sky_cvr in ("OVC", "BKN", "OVX"):
                            break

                else:
                    debugging.info("FAA xml data IS providing the forecast field for this airport")
                    # for each sky_condition from the XML
                    for sky_condition in metar.findall("./forecast/sky_condition"):
                        # get the sky cover (BKN, OVC, SCT, etc)
                        sky_cvr = sky_condition.attrib["sky_cover"]
                        debugging.info("Sky Cover = " + sky_cvr)
                        debugging.info(metar.find("./forecast/fcst_time_from").text)

                        # Break out of for loop once we find one of these conditions
                        if sky_cvr in ("OVC", "BKN", "OVX"):
                            break

                # If the layer is OVC, BKN or OVX, set Flight category based on height AGL
                if sky_cvr in ("OVC", "BKN", "OVX"):
                    try:
                        # get cloud base AGL from XML
                        cld_base_ft_agl = sky_condition.attrib["cloud_base_ft_agl"]
                    except Exception as e:
                        # get cloud base AGL from XML
                        debugging.error(e)
                        cld_base_ft_agl = forecast.find("vert_vis_ft").text

                    debugging.info("Cloud Base = " + cld_base_ft_agl)
                    cld_base_ft_agl = int(cld_base_ft_agl)

                    if cld_base_ft_agl < 500:
                        flightcategory = "LIFR"
                        # break
                    elif 500 <= cld_base_ft_agl < 1000:
                        flightcategory = "IFR"
                        # break
                    elif 1000 <= cld_base_ft_agl <= 3000:
                        flightcategory = "MVFR"
                        # break
                    elif cld_base_ft_agl > 3000:
                        flightcategory = "VFR"
                        # break

                # visibilty can also set flight category. If the clouds haven't set the fltcat to LIFR. See if visibility will
                # if it's LIFR due to cloud layer, no reason to check any other things that can set flight category.
                if flightcategory != "LIFR":
                    # check XML if visibility value exists
                    if metar.find("./forecast/visibility_statute_mi") is not None:
                        visibility_statute_mi = metar.find("./forecast/visibility_statute_mi").text  # get visibility number
                        visibility_statute_mi = float(visibility_statute_mi)

                        if visibility_statute_mi < 1.0:
                            flightcategory = "LIFR"

                        elif 1.0 <= visibility_statute_mi < 3.0:
                            flightcategory = "IFR"

                        # if Flight Category was already set to IFR by clouds, it can't be reduced to MVFR
                        elif 3.0 <= visibility_statute_mi <= 5.0 and flightcategory != "IFR":
                            flightcategory = "MVFR"

                debugging.info(stationId + " flight category is Decode script-determined as " + flightcategory)

            else:
                debugging.info(stationId + ": FAA is reporting " + metar.find("flight_category").text + " through their API")
                # pull flight category if it exists and save all the algoritm above
                flightcategory = metar.find("flight_category").text
            # End of METAR Decode added routine to create flight category via cloud cover and/or visability when flight category is not reported.
            # grab wind speeds from returned FAA data
            # if wind speed is blank, then bypass
            if metar.find("wind_speed_kt") is None:
                windspeedkt = 0
            else:
                windspeedkt = metar.find("wind_speed_kt").text

            # grab Weather info from returned FAA data
            # if weather string is blank, then bypass
            if metar.find("wx_string") is None:
                wxstring = "NONE"
            else:
                wxstring = metar.find("wx_string").text

            # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
            if stationId in stationiddict:
                debugging.info(stationId + " Duplicate, only saved first metar category")
            else:
                # build category dictionary
                stationiddict[stationId] = flightcategory

            if stationId in windsdict:
                debugging.info(stationId + " Duplicate, only saved the first winds")
            else:
                # build windspeed dictionary
                windsdict[stationId] = windspeedkt

            if stationId in wxstringdict:
                debugging.info(stationId + " Duplicate, only saved the first weather")
            else:
                # build weather dictionary
                wxstringdict[stationId] = wxstring
        debugging.info("Decoded METAR Data for Display")
