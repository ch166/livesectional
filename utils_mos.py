#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  7 20:25:48 2023

"""

import collections
import re
import utils

import debugging

# Moved this here from other places ..
# This needs to be restructured before it can be used in the new code layout.


def mos_decode_routine(
    conf,
    stationiddict,
    categories,
    hour_to_display,
    hour_dict,
    airport_database,
    obv_wx,
    typ_wx,
    windsdict,
    wxstringdict,
):
    # FIXME: This still uses the old fields - needs lots of cleanup
    """
    # MOS decode routine
    # MOS data is downloaded daily from; https://www.weather.gov/mdl/mos_gfsmos_mav to the local drive by crontab scheduling.
    # Then this routine reads through the entire file looking for those airports that are in the airports file. If airport is
    # found, the data needed to display the weather for the next 24 hours is captured into mos_dict, which is nested with
    # hour_dict, which holds the airport's MOS data by 3 hour chunks. See; https://www.weather.gov/mdl/mos_gfsmos_mavcard for
    # a breakdown of what the MOS data looks like and what each line represents.
    """
    mos_dict = []
    debugging.info("Starting MOS Data Display")
    mos_filepath = conf.get_string("filenames", "mos_filepath")
    # Read current MOS text file
    try:
        file = open(mos_filepath, "r", encoding="utf8")
        lines = file.readlines()
    except IOError as err:
        debugging.error("MOS data file could not be loaded.")
        debugging.error(err)
        return err

    for line in lines:  # read the MOS data file line by line0
        line = str(line)
        # Ignore blank lines of MOS airport
        if line.startswith("     "):
            ap_flag = 0
            continue
        # Check for and grab date of MOS
        if "DT /" in line:
            # Don't do anything if we're just going to the next line..
            # unused1, dt_cat, month, unused2, unused3, day, unused4 = line.split(" ", 6)
            continue
        # Check for and grab the Airport ID of the current MOS
        if "MOS" in line:
            unused, loc_apid, mos_date = line.split(" ", 2)
            # If this Airport ID is in the airports file then grab all the info needed from this MOS
            if loc_apid in stationiddict:
                ap_flag = 1
                # used to determine if a category is being reported in MOS or not. If not, need to inject it.
                cat_counter = 0
                (dat0, dat1, dat2, dat3, dat4, dat5, dat6, dat7,) = (
                    [] for i in range(8)
                )  # Clear lists
            continue
        # If we just found an airport that is in our airports file, then grab the appropriate weather data from it's MOS
        last_cat = ""
        if ap_flag:
            # capture the category the line read represents
            xtra, cat, value = line.split(" ", 2)
            # Check if the needed categories are being read and if so, grab its data
            if cat in categories:
                cat_counter += (
                    1  # used to check if a category is not in mos report for airport
                )
                if cat == "HR":  # hour designation
                    # grab all the hours from line read
                    temp = re.findall(r"\s?(\s*\S+)", value.rstrip())
                    for j in range(8):
                        tmp = temp[j].strip()
                        # create hour dictionary based on mos data
                        hour_dict[tmp] = ""
                    # Get the hours which are the keys in this dict, so they can be properly poplulated
                    keys = list(hour_dict.keys())
                else:
                    # Checking for missing lines of data and x out if necessary.
                    if (
                        (cat_counter == 5 and cat != "P06")
                        or (cat_counter == 6 and cat != "T06")
                        or (cat_counter == 7 and cat != "POZ")
                        or (cat_counter == 8 and cat != "POS")
                        or (cat_counter == 9 and cat != "TYP")
                    ):
                        # calculate the number of consecutive missing cats and inject 9's into those positions
                        a = categories.index(last_cat) + 1
                        b = categories.index(cat) + 1
                        c = b - a - 1
                        for j in range(c):
                            temp = [
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                                "9",
                            ]
                            set_data(temp, keys, hour_dict, mos_dict, loc_apid)
                            cat_counter += 1
                        # Now write the orignal cat data read from the line in the mos file
                        cat_counter += 1
                        # clear out hour_dict for next airport
                        hour_dict = collections.OrderedDict()
                        last_cat = cat
                        # add the actual line of data read
                        temp = re.findall(r"\s?(\s*\S+)", value.rstrip())
                        set_data(temp, keys, hour_dict, mos_dict, loc_apid)
                        # clear out hour_dict for next airport
                        hour_dict = collections.OrderedDict()
                    else:
                        # continue to decode the next category data that was read.
                        # store what the last read cat was.
                        last_cat = cat
                        temp = re.findall(r"\s?(\s*\S+)", value.rstrip())
                        set_data(temp, keys, hour_dict, mos_dict, loc_apid)
                        # clear out hour_dict for next airport
                        hour_dict = collections.OrderedDict()

    # Now grab the data needed to display on map. Key: [airport][hr][j] - using nested dictionaries
    # airport = from airport file, 4 character ID. hr = 1 of 8 three-hour periods of time, 00 03 06 09 12 15 18 21
    # j = index to weather categories, in this order; 'CLD','WDR','WSP','P06', 'T06', 'POZ', 'POS', 'TYP','CIG','VIS','OBV'.
    # See; https://www.weather.gov/mdl/mos_gfsmos_mavcard for description of available data.
    airport_list = airport_database.get_airport_dict_led()
    for icao, airport in airport_list:
        if airport in mos_dict:
            debugging.debug("\n" + airport)
            debugging.debug(categories)

            mos_time = utils.current_time_hr_utc(conf) + hour_to_display
            if mos_time >= 24:  # check for reset at 00z
                mos_time = mos_time - 24

            for hr in keys:
                if int(hr) <= mos_time <= int(hr) + 2.99:
                    cld = mos_dict[airport][hr][0]
                    # make wind direction end in zero
                    wdr = (mos_dict[airport][hr][1]) + "0"
                    wsp = mos_dict[airport][hr][2]
                    p06 = mos_dict[airport][hr][3]
                    t06 = mos_dict[airport][hr][4]
                    poz = mos_dict[airport][hr][5]
                    pos = mos_dict[airport][hr][6]
                    typ = mos_dict[airport][hr][7]
                    cig = mos_dict[airport][hr][8]
                    vis = mos_dict[airport][hr][9]
                    obv = mos_dict[airport][hr][10]

                    # decode the weather for each airport to display on the livesectional map
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

                    # Check visability too.
                    if (
                        flightcategory != "LIFR"
                    ):  # if it's LIFR due to cloud layer, no reason to check any other things that can set fl$
                        if vis <= "2":  # vis < 1.0 mile:
                            flightcategory = "LIFR"

                        elif "3" <= vis < "4":  # 1.0 <= vis < 3.0 miles:
                            flightcategory = "IFR"

                        elif (
                            vis == "5" and flightcategory != "IFR"
                        ):  # 3.0 <= vis <= 5.0 miles
                            flightcategory = "MVFR"

                    debugging.debug(flightcategory + " |")
                    debugging.debug(f"Windspeed = {wsp} | Wind dir = {wdr} |")

                    # decode reported weather using probabilities provided.
                    if (
                        typ == "9"
                    ):  # check to see if rain, freezing rain or snow is reported. If not use obv weather
                        # Get proper representation for obv designator
                        wx_info = obv_wx[obv]
                    else:
                        # Get proper representation for typ designator
                        wx_info = typ_wx[typ]

                        if wx_info == "RA" and int(p06) < conf.get_int(
                            "rotaryswitch", "prob"
                        ):
                            if obv != "N":
                                wx_info = obv_wx[obv]
                            else:
                                wx_info = "NONE"

                        if wx_info == "SN" and int(pos) < conf.get_int(
                            "rotaryswitch", "prob"
                        ):
                            wx_info = "NONE"

                        if wx_info == "FZRA" and int(poz) < conf.get_int(
                            "rotaryswitch", "prob"
                        ):
                            wx_info = "NONE"

                        # print (t06,apid) # debug
                        if t06 == "" or t06 is None:
                            t06 = "0"

                        # check for thunderstorms
                        if int(t06) > conf.get_int("rotaryswitch", "prob"):
                            wx_info = "TSRA"
                        else:
                            wx_info = "NONE"

                    debugging.debug(f"Reported Weather = {wx_info}")

            # Connect the information from MOS to the board
            stationId = airport

            # grab wind speeds from returned MOS data
            if wsp is None:  # if wind speed is blank, then bypass
                windspeedkt = 0
            elif (
                wsp == "99"
            ):  # Check to see if MOS data is not reporting windspeed for this airport
                windspeedkt = 0
            else:
                windspeedkt = int(wsp)

            # grab Weather info from returned FAA data
            if wx_info is None:  # if weather string is blank, then bypass
                wxstring = "NONE"
            else:
                wxstring = wx_info

            debugging.debug(f"{stationId}, {windspeedkt},  {wxstring}")  # debug

            # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
            if stationId in stationiddict:
                debugging.info(
                    f"{stationId} Duplicate, only saved first metar category"
                )
            else:
                # build category dictionary
                stationiddict[stationId] = flightcategory

            if stationId in windsdict:
                debugging.info(f"{stationId} Duplicate, only saved the first winds")
            else:
                # build windspeed dictionary
                windsdict[stationId] = windspeedkt

            if stationId in wxstringdict:
                debugging.info(f"{stationId} Duplicate, only saved the first weather")
            else:
                # build weather dictionary
                wxstringdict[stationId] = wxstring
    debugging.info("Decoded MOS Data for Display")
    return True


# Used by MOS decode routine. This routine builds mos_dict nested with hours_dict
# FIXME: Move to update_airports.py
def set_data(temp, keys, hour_dict, mos_dict, apid):
    # FIXME: Needs reworking for MOS data
    mos_dict = []
    dat0 = dat1 = dat2 = dat3 = dat4 = dat5 = dat6 = dat7 = []

    # Clean up line of MOS data.
    # this check is unneeded. Put here to vary length of list to clean up.
    if len(temp) >= 0:
        temp1 = []
        tmp_sw = 0

        for val in temp:  # Check each item in the list
            val = val.lstrip()  # remove leading white space
            val = val.rstrip("/")  # remove trailing /

            if len(val) == 6:  # this is for T06 to build appropriate length list
                # add a '0' to the front of the list. T06 doesn't report data in first 3 hours.
                temp1.append("0")
                # add back the original value taken from T06
                temp1.append(val)
                # Turn on switch so we don't go through it again.
                tmp_sw = 1

            # and tmp_sw == 0: # if item is 1 or 2 chars long, then bypass. Otherwise fix.
            elif len(val) > 2 and tmp_sw == 0:
                pos = val.find("100")  # locate first 100
                # capture the first value which is not a 100
                tmp = val[0:pos]
                temp1.append(tmp)  # and store it in temp list.

                k = 0
                for j in range(pos, len(val), 3):  # now iterate through remainder
                    temp1.append(val[j : j + 3])  # and capture all the 100's
                    k += 1
            else:
                temp1.append(val)  # Store the normal values too.

        temp = temp1

    # load data into appropriate lists by hours designated by current MOS file
    # clean up data by removing '/' and spaces
    temp0 = [x.strip() for x in temp[0].split("/")]
    temp1 = [x.strip() for x in temp[1].split("/")]
    temp2 = [x.strip() for x in temp[2].split("/")]
    temp3 = [x.strip() for x in temp[3].split("/")]
    temp4 = [x.strip() for x in temp[4].split("/")]
    temp5 = [x.strip() for x in temp[5].split("/")]
    temp6 = [x.strip() for x in temp[6].split("/")]
    temp7 = [x.strip() for x in temp[7].split("/")]

    # build a list for each data group. grab 1st element [0] in list to store.
    dat0.append(temp0[0])
    dat1.append(temp1[0])
    dat2.append(temp2[0])
    dat3.append(temp3[0])
    dat4.append(temp4[0])
    dat5.append(temp5[0])
    dat6.append(temp6[0])
    dat7.append(temp7[0])

    j = 0
    for key in keys:  # add cat data to the hour_dict by hour
        if j == 0:
            hour_dict[key] = dat0
        elif j == 1:
            hour_dict[key] = dat1
        elif j == 2:
            hour_dict[key] = dat2
        elif j == 3:
            hour_dict[key] = dat3
        elif j == 4:
            hour_dict[key] = dat4
        elif j == 5:
            hour_dict[key] = dat5
        elif j == 6:
            hour_dict[key] = dat6
        elif j == 7:
            hour_dict[key] = dat7
        j += 1

        # marry the hour_dict to the proper key in mos_dict
        mos_dict[apid] = hour_dict
    return mos_dict
