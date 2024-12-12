# -*- coding: utf-8 -*- #
"""
Created on Tue Feb  7 20:25:48 2023

"""

# import collections
import re
import utils
import debugging

# https://vlab.noaa.gov/web/mdl/mav-card

# Active Dec 2024
# https://www.weather.gov/media/mdl/mdltpb05-03.pdf
# https://www.weather.gov/media/mdl/mdltpb05-04.pdf

# Moved this here from other places
# This needs to be restructured before it can be used in the new code layout.

# TODO:
#  Open question on the appropriateness of using MOS data formats, or switching
#  to the newer NBM data sets - https://vlab.noaa.gov/web/mdl/nbm
#

#
# Visibility Categories
# 1 = visibility of < 1/2 mi;
# 2 = visibility of 1/2 - < 1 mi;
# 3 = visibility of 1 to < 2 mi;
# 4 = visibility of 2 to < 3 mi;
# 5 = visibility of 3 to 5 mi;
# 6 = visibility of 6 mi;
# 7 = visibility of > 6 mi.

#
# Ceiling Height Categories
# 1 = ceiling height of < 200 feet;
# 2 = ceiling height of 200 - 400 feet;
# 3 = ceiling height of 500 - 900 feet;
# 4 = ceiling height of 1000 - 1900 feet;
# 5 = ceiling height of 2000 - 3000 feet;
# 6 = ceiling height of 3100 - 6500 feet;
# 7 = ceiling height of 6600 - 12,000 feet;
# 8 = ceiling height of > 12,000 feet or unlimited ceiling.


# MOS Flight Categories
# These lines represent the possible set of individual rows in a MOS site record
categories = [
    "DT",
    "HR",
    "CIG",
    "CLD",
    "DPT",
    "N/X",
    "OBV",
    "P06",
    "P12",
    "POS",
    "POZ",
    "Q06",
    "Q12",
    "SNW",
    "T06",
    "T12",
    "TMP",
    "TYP",
    "VIS",
    "WDR",
    "WSP",
    "X/N",
]

# Start positions of columns in MOS data
mos_columns = [
    # 0, Ignoring label column
    4,
    8,
    11,
    14,
    17,
    20,
    23,
    26,
    29,
    32,
    35,
    38,
    41,
    44,
    47,
    50,
    53,
    56,
    59,
    62,
    65,
]

# Decode from MOS to TAF/METAR
typ_wx = {
    "S": "SN",  # Snow, Snow Grains, Snow Pellets or Snow Showers
    "Z": "FZRA",  # Freezing Precipitation,  (freezing rain, freezing drizzle, ice pellets (sleet), or any report of these elements mixed with other precipitation types)
    "R": "RA",  # Liquid Precipitation, (rain, drizzle, or a mixture of rain or drizzle with snow)
    "X": "UNKN",  # Missing
    "999": "UNKN",
}

# Obstruction to Vision Categories
# N = none of the following;
# HZ = haze, smoke, dust;
# BR = mist (fog with visibility > 5/8 mi);
# FG = fog or ground fog (visibility < 5/8 mi);
# BL = blowing dust, sand, snow.
# X = Missing
obv_wx = {
    "N": "None",
    "HZ": "HZ",
    "BR": "RA",
    "FG": "FG",
    "BL": "HZ",
    "X": "UNKN",
    "999": "UNKN",
}


def mos_analyze_datafile(
    app_conf,
):
    """
    # MOS decode routine
    # MOS data is downloaded daily from; https://www.weather.gov/mdl/mos_gfsmos_mav to the local drive by crontab scheduling.
    # Then this routine reads through the entire file parsing the data and working out the weather conditions at each airport for each hour.
    #
    """
    debugging.info("Starting MOS Data Analysis")
    mos_filepath = app_conf.get_string("filenames", "mos_filepath")
    # Read current MOS text file
    try:
        file = open(mos_filepath, "r", encoding="utf8")
        lines = file.readlines()
    except IOError as err:
        debugging.error("MOS data file could not be loaded.")
        debugging.error(err)
        return False, None

    mos_dict = parse_mos_data(lines)

    result_dict = {}
    mos_forecast = {}
    for icao in mos_dict:
        airport_code = icao.upper()
        result_dict[airport_code] = {}
        # Process HR line to get the hour values
        # Then for each of the collections ; process that line if it exists ; or fill in blanks if it doesn't.
        if "HR" not in mos_dict[airport_code]:
            debugging.debug(f"HR line missing for {airport_code}")
            continue
        hour_keys_array = parse_hr_row(mos_dict[airport_code]["HR"])

        # This code currently processes all the categories ;
        # TODO: Optimize the set of categories to be only the ones required to make a weather determination
        for category in categories:
            if category == "DT":
                dt_dates = parse_dt_row(mos_dict[airport_code]["DT"])
                result_dict[airport_code][category] = ["DT", dt_dates]
                result_dict[airport_code]["MTH"] = generate_month_row(dt_dates)
                result_dict[airport_code]["DAY"] = generate_day_row(dt_dates)
                continue
            if category in mos_dict[airport_code]:
                result_dict[airport_code][category] = parse_mos_row(
                    category, mos_dict[airport_code]
                )
            else:
                result_dict[airport_code][category] = new_empty_array(
                    # 999 is used to signify missing data
                    "999",
                    len(hour_keys_array),
                )

        if airport_code == "KBFI":
            debugging.debug(
                f"MOS DICT {airport_code}\n{debugging.prettify_dict(result_dict[airport_code])}"
            )

        mos_forecast[airport_code] = {}
        for index in range(0, len(result_dict[airport_code]["HR"])):
            cld = result_dict[airport_code]["CLD"][index]
            # make wind direction end in zero
            wdr = result_dict[airport_code]["WDR"][index] + "0"
            wsp = result_dict[airport_code]["WSP"][index]
            p06 = result_dict[airport_code]["P06"][index]
            t06 = result_dict[airport_code]["T06"][index]
            poz = result_dict[airport_code]["POZ"][index]
            pos = result_dict[airport_code]["POS"][index]
            typ = result_dict[airport_code]["TYP"][index]
            cig = result_dict[airport_code]["CIG"][index]
            vis = result_dict[airport_code]["VIS"][index]
            obv = result_dict[airport_code]["OBV"][index]

            # decode the weather for each airport
            flightcategory = "VFR"  # start with VFR as the assumption
            # If the layer is OVC, BKN, set Flight category based on height of layer
            if cld in ("OV", "BK"):
                if cig <= "2":  # AGL is less than 500:
                    flightcategory = "LIFR"
                elif cig == "3":  # AGL is between 500 and 1000
                    flightcategory = "IFR"
                elif "4" <= cig <= "5":  # AGL is between 1000 and 3000:
                    flightcategory = "MVFR"
                elif cig >= "6":  # AGL is above 3000
                    flightcategory = "VFR"

            # Check visibility too.
            if (
                flightcategory != "LIFR"
            ):  # if it's LIFR due to cloud layer, no reason to check any other things that can set fl$
                if vis <= "2":  # vis < 1.0 mile:
                    flightcategory = "LIFR"
                elif "3" <= vis < "4":  # 1.0 <= vis < 3.0 miles:
                    flightcategory = "IFR"
                elif vis == "5" and flightcategory != "IFR":  # 3.0 <= vis <= 5.0 miles
                    flightcategory = "MVFR"

            # decode reported weather using probabilities provided.
            if (
                typ == "999"
            ):  # check to see if rain, freezing rain or snow is reported. If not use obv weather
                # Get proper representation for obv designator
                wx_info = obv_wx[obv]
            else:
                # Get proper representation for typ designator
                wx_info = typ_wx[typ]

                if p06 == "" or p06 is None:
                    p06 = "0"
                if wx_info == "RA" and int(p06) < app_conf.get_int(
                    "metar", "mos_probability"
                ):
                    if obv != "N":
                        wx_info = obv_wx[obv]
                    else:
                        wx_info = "NONE"

                if pos == "" or pos is None:
                    pos = "0"

                if wx_info == "SN" and int(pos) < app_conf.get_int(
                    "metar", "mos_probability"
                ):
                    wx_info = "NONE"

                if poz == "" or poz is None:
                    poz = "0"
                if wx_info == "FZRA" and int(poz) < app_conf.get_int(
                    "metar", "mos_probability"
                ):
                    wx_info = "NONE"

                # TODO: Need to properly parse the T06 line
                # The T06 line represents forecasts for the probability of thunderstorms (to the left of the diagonal)
                # and the conditional probability of severe thunderstorms (to the right of the diagonal) occurring
                # during a 6-h period. The 6-h probability forecasts are valid for intervals of 6-12, 12-18, 18-24,
                # 24-30, 30-36, 36-42, 42-48, 48-54, 54-60, and 66-72 hours after
                # the initial data times (0000 and 1200 UTC).

                # if t06 == '' or t06 is None:
                #     t06 = '0'
                #
                # check for thunderstorms
                # if int(t06) > app_conf.get_int( "metar", "mos_probability"):
                #     wx_info = "TSRA"
                # else:
                #    wx_info = "NONE"

            # grab wind speeds from returned MOS data
            if wsp is None:  # if wind speed is blank, then bypass
                windspeedkt = 0
            elif (
                wsp == "999"
            ):  # Check to see if MOS data is not reporting windspeed for this airport
                windspeedkt = 0
            else:
                windspeedkt = int(wsp)

            # grab Weather info from returned FAA data
            if wx_info is None:  # if weather string is blank, then bypass
                wxstring = "NONE"
            else:
                wxstring = wx_info

            mos_forecast[airport_code][index] = {}
            mos_forecast[airport_code][index]["month"] = result_dict[airport_code][
                "MTH"
            ][index]
            mos_forecast[airport_code][index]["day"] = result_dict[airport_code]["DAY"][
                index
            ]
            mos_forecast[airport_code][index]["hour"] = result_dict[airport_code]["HR"][
                index
            ]
            mos_forecast[airport_code][index]["flightcategory"] = flightcategory

    debugging.info("Decoded MOS Data for Display")
    debugging.debug(debugging.prettify_dict(mos_forecast))
    return True, mos_forecast


def parse_mos_data(lines):
    """Parse MOS data lines."""
    # Process through a sequence of text lines; and extract all the lines
    # associated with a single airport.

    ap_flag = 0
    mos_line_dict = {}
    loc_apid = ""

    for line in lines:  # read the MOS data file line by line0
        line = line.rstrip("\n")
        line = str(line)

        # Blank line signals that we're starting over with a new block.
        # Clear the active airport flag and go back to the top.
        if line.startswith("     "):
            ap_flag = 0
            continue
        # Check for and grab the Airport ID of the current MOS.
        if "MOS" in line:
            _unused1, loc_apid, mos_date = line.split(" ", 2)
            # debugging.info(f"::{line}")
            mos_line_dict[loc_apid] = {}
            mos_line_dict[loc_apid]["MOS"] = line
            mos_line_dict[loc_apid]["MOSDATE"] = mos_date

            ap_flag = 1
            continue
        # If we just found an airport, grab the appropriate weather data from it's MOS
        if ap_flag:
            # capture the category the line represents
            _unused1, cat, _unused2 = line.split(" ", 2)
            mos_line_dict[loc_apid][cat] = line
    return mos_line_dict


def new_empty_array(value, length):
    """Create new empty array populated with value."""
    new_array = []
    for _index in range(1, length):
        new_array.append(value)
    return new_array


def generate_month_row(dt_dict):
    """Create a Month Row"""
    month_row = []
    for index in range(0, len(mos_columns) - 1):
        for date_index in range(0, len(dt_dict.keys())):
            if (dt_dict[date_index]["start_pos"] <= mos_columns[index]) and (
                dt_dict[date_index]["end_pos"] >= mos_columns[index]
            ):
                month_row.append(dt_dict[date_index]["month"])
    return month_row


def generate_day_row(dt_dict):
    """Create a day Row"""
    day_row = []
    for index in range(0, len(mos_columns) - 1):
        for date_index in range(0, len(dt_dict.keys())):
            if (dt_dict[date_index]["start_pos"] <= mos_columns[index]) and (
                dt_dict[date_index]["end_pos"] >= mos_columns[index]
            ):
                day_row.append(dt_dict[date_index]["day"])
    return day_row


def parse_mos_row(row_key, row_dict):
    """Parse contents from specific MOS row into an array."""
    row_str = row_dict[row_key]
    contents = []

    for index in range(0, len(mos_columns) - 1):
        if index == len(mos_columns) - 1:
            value = row_str[mos_columns[index] : len(row_str)]
        else:
            value = row_str[mos_columns[index] : mos_columns[index + 1]]
        contents.insert(index, value.strip())
    return contents


def parse_dt_row(mos_row):
    """Parse the DT row in a MOS message"""
    # Check for and grab date of MOS.
    dt_dates = {}
    date_pos = []
    for index in re.finditer("/", mos_row):
        date_pos.append(index.start())
    for index in range(0, len(date_pos)):
        # debugging.info(f"parse_dt_row: {index} / {len(date_pos)}")
        if index == len(date_pos) - 1:
            start_pos = date_pos[index]
            end_pos = len(mos_row)
        else:
            start_pos = date_pos[index]
            end_pos = date_pos[index + 1]
        date_string = re.search(r"([A-Z]{3})\s+([0-9]*)", mos_row[start_pos:end_pos])
        if date_string:
            month = date_string.group(1)
            day = date_string.group(2)
            dt_dates[index] = {
                "month": month,
                "day": day,
                "start_pos": start_pos,
                "end_pos": end_pos,
            }
    return dt_dates


def parse_hr_row(mos_row):
    """Parse the HR row in a MOS message"""
    hour_array = []
    contents = re.findall(
        r"\s?(\s*\S+)", mos_row.rstrip()
    )  # grab all the hours from line read
    for index in range(len(contents)):
        tmp_hr = contents[index].strip()
        if tmp_hr == "HR":
            continue
        hour_array.append(tmp_hr)
    return hour_array


def get_mos_weather(mos_forecast, app_conf, hour_offset):
    """Lookup forecast weather at airport_id, at hour_offset from now."""
    mos_time = utils.current_time_utc_plus_hr(app_conf, hour_offset)
    target_month = mos_time.strftime("%b").upper()
    target_day = mos_time.day
    target_hour = mos_time.hour
    for index in range(len(mos_forecast)):
        forecast_day = int(mos_forecast[index]["day"])
        forecast_month = mos_forecast[index]["month"]
        forecast_hour = int(mos_forecast[index]["hour"])
        if (
            (forecast_day == target_day)
            and (forecast_month == target_month)
            and (forecast_hour <= target_hour)
            and (forecast_hour + 3 >= target_hour)
        ):
            return mos_forecast[index]["flightcategory"]
    return "UNKN"
