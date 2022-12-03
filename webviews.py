# -*- coding: utf-8 -*- #

# import os
import datetime
import time

# import subprocess

from rpi_ws281x import (
    Color,
    PixelStrip,
    ws,
)


import secrets
import pytz

import folium
import folium.plugins
from folium.features import CustomIcon
from folium.features import DivIcon
from folium.vector_layers import Circle, CircleMarker, PolyLine, Polygon, Rectangle

from flask import (
    Flask,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    send_file,
    Response,
)
from werkzeug.utils import secure_filename

from pyqrcode import QRCode

import json

import utils
import conf
import debugging
import sysinfo


class WebViews:
    """Class to contain all the Flask WEB functionality."""

    def __init__(self, config, sysdata, airport_database, appinfo):
        self.conf = config
        self.sysdata = sysdata
        self.airport_database = airport_database
        self.appinfo = appinfo
        self.app = Flask(__name__)
        # self.app.jinja_env.auto_reload = True
        # This needs to happen really early in the process to take effect
        self.app.config["TEMPLATES_AUTO_RELOAD"] = True

        self.app.secret_key = secrets.token_hex(16)
        self.app.add_url_rule("/", view_func=self.yindex, methods=["GET"])
        self.app.add_url_rule("/qrcode", view_func=self.qrcode, methods=["GET"])
        self.app.add_url_rule("/metar/<airport>", view_func=self.getmetar, methods=["GET"])
        self.app.add_url_rule("/taf/<airport>", view_func=self.gettaf, methods=["GET"])
        self.app.add_url_rule("/tzset", view_func=self.tzset, methods=["GET", "POST"])
        self.app.add_url_rule("/led_map", view_func=self.led_map, methods=["GET", "POST"])
        self.app.add_url_rule("/map1", view_func=self.map1, methods=["GET", "POST"])
        self.app.add_url_rule("/touchscr", view_func=self.touchscr, methods=["GET", "POST"])
        self.app.add_url_rule("/open_console", view_func=self.open_console, methods=["GET", "POST"])
        self.app.add_url_rule("/stream_log", view_func=self.stream_log, methods=["GET", "POST"])
        self.app.add_url_rule("/stream_log1", view_func=self.stream_log1, methods=["GET", "POST"])
        self.app.add_url_rule("/download_ap", view_func=self.downloadairports, methods=["GET", "POST"])
        self.app.add_url_rule("/download_cf", view_func=self.downloadconfig, methods=["GET", "POST"])
        self.app.add_url_rule("/download_log", view_func=self.downloadlog, methods=["GET", "POST"])
        self.app.add_url_rule("/confedit", view_func=self.confedit, methods=["GET", "POST"])
        self.app.add_url_rule("/apedit", view_func=self.apedit, methods=["GET", "POST"])
        self.app.add_url_rule("/post", view_func=self.handle_post_request, methods=["GET", "POST"])

        self.max_lat = 0
        self.min_lat = 0
        self.max_lon = 0
        self.min_lon = 0

        # Replace These with real data
        self.airports = []
        self.hmdata = None
        self.update_vers = None
        self.machines = []
        self.num = None
        self.update_available = None
        self.ap_info = None
        self.settings = None
        self.strip = None
        self.led_map_dict = {}

    def run(self):
        """Run Flask Application.

        If debug is True, we need to make sure that auto-reload is disabled in threads
        """
        self.app.run(debug=False, host="0.0.0.0")

    def standardtemplate_data(self):
        """Generate a standardized template_data."""
        airport_dict_data = {}
        for (
            airport_icao,
            airportdb_row,
        ) in self.airport_database.get_airport_dict_led().items():
            airport_object = airportdb_row["airport"]
            airport_record = {}
            airport_record["active"] = airport_object.active()
            airport_record["icaocode"] = airport_icao
            airport_record["metarsrc"] = airport_object.get_wxsrc()
            airport_record["ledindex"] = airport_object.get_led_index()
            airport_record["rawmetar"] = airport_object.get_raw_metar()
            airport_dict_data[airport_icao] = airport_record

        template_data = {
            "title": "NOT SET - " + self.appinfo.current_version(),
            "hmdata": self.hmdata,
            "airports": airport_dict_data,
            "settings": self.conf.gen_settings_dict(),
            "ipadd": self.sysdata.local_ip(),
            "strip": self.strip,
            "timestr": utils.time_format(utils.current_time(self.conf)),
            "timestrutc": utils.time_format(utils.current_time_utc(self.conf)),
            "timemetarage": utils.time_format(self.airport_database.get_metar_update_time()),
            "current_timezone": self.conf.get_string("default", "timezone"),
            "num": self.num,
            "version": self.appinfo.current_version(),
            "update_available": self.update_available,
            "update_vers": self.update_vers,
            "machines": self.machines,
            "sysinfo": self.sysdata.query_system_information(),
        }
        return template_data

    def yindex(self):
        """Flask Route: /yield - Display System Info."""
        template_data = self.standardtemplate_data()
        template_data["title"] = "SysInfo"

        debugging.info("Opening System Information page")
        return render_template("sysinfo.html", **template_data)
        # text/html is required for most browsers to show this info.

    def tzset(self):
        """Flask Route: /tzset - Display and Set Timezone Information."""
        if request.method == "POST":
            timezone = request.form["tzselected"]

            flash("Timezone set to " + timezone)
            debugging.info("Request to update timezone to: " + timezone)
            self.conf.set_string("default", "timezone", timezone)
            self.conf.save_config()
            return redirect("tzset")

        tzlist = pytz.common_timezones
        current_timezone = self.conf.get_string("default", "timezone")

        template_data = self.standardtemplate_data()
        template_data["title"] = "TZset"
        template_data["tzoptionlist"] = tzlist
        template_data["current_timezone"] = current_timezone

        debugging.info("Opening Time Zone Set page")
        return render_template("tzset.html", **template_data)

    # Routes for Map Display - Testing
    def map1(self):
        """Flask Route: /map1 ."""
        start_coords = (35.1738, -111.6541)
        folium_map = folium.Map(
            location=start_coords,
            zoom_start=6,
            height="80%",
            width="100%",
            control_scale=True,
            zoom_control=True,
            tiles="OpenStreetMap",
        )

        folium_map.add_child(folium.LatLngPopup())
        folium_map.add_child(folium.ClickForMarker(popup="Marker"))
        folium.plugins.Geocoder().add_to(folium_map)

        # FIXME: Move URL to configuration
        folium_url = "http://wms.chartbundle.com/tms/1.0.0/sec/{z}/{x}/{y}.png?origin=nw"
        folium.TileLayer(folium_url, attr="chartbundle.com", name="ChartBundle Sectional").add_to(folium_map)
        folium.TileLayer("Stamen Terrain", name="Stamen Terrain").add_to(folium_map)
        folium.TileLayer("CartoDB positron", name="CartoDB Positron").add_to(folium_map)
        # other mapping code (e.g. lines, markers etc.)
        folium.LayerControl().add_to(folium_map)

        folium_map.save("/NeoSectional/templates/map.html")
        # TODO: Need a mapedit.html - doesn't exist..
        return render_template("mapedit.html", title="Map", num=5)
        # return folium_map._repr_html_()

    # FIXME: Integrate into Class
    # @app.route('/touchscr', methods=["GET", "POST"])
    def touchscr(self):
        """Flask Route: /touchscr - Touch Screen template."""
        ipadd = self.sysdata.local_ip()
        return render_template(
            "touchscr.html",
            title="Touch Screen",
            num=5,
            machines=self.machines,
            ipadd=ipadd,
        )

    # This streams off to seashells.io ..
    # This works except that we're not currently pumping things to seashells.io
    # @app.route('/open_console', methods=["GET", "POST"])
    def open_console(self):
        """Flask Route: /open_console - Launching Console in discrete window."""
        console_ips = []
        loc_timestr = utils.time_format(utils.current_time(self.conf))
        loc_timestr_utc = utils.time_format(utils.current_time_utc(self.conf))
        with open("/NeoSectional/data/console_ip.txt", "r", encoding="utf8") as file:
            for line in file.readlines()[-1:]:
                line = line.rstrip()
                console_ips.append(line)
        ipadd = self.sysdata.local_ip()
        console_ips.append(ipadd)
        debugging.info("Opening open_console in separate window")
        return render_template(
            "open_console.html",
            urls=console_ips,
            title="Display Console Output-" + self.appinfo.current_version(),
            num=5,
            machines=self.machines,
            ipadd=ipadd,
            timestrutc=loc_timestr_utc,
            timestr=loc_timestr,
        )

    # Routes to display logfile live, and hopefully for a dashboard
    # @app.route('/stream_log', methods=["GET", "POST"])
    # Works with stream_log1
    def stream_log(self):
        """Flask Route: /stream_log - Watch logs live."""
        loc_timestr = utils.time_format(utils.current_time(self.conf))
        loc_timestr_utc = utils.time_format(utils.current_time_utc(self.conf))
        ipadd = self.sysdata.local_ip()
        debugging.info("Opening stream_log in separate window")
        return render_template(
            "stream_log.html",
            title="Display Logfile-" + self.appinfo.current_version(),
            num=5,
            machines=self.machines,
            ipadd=ipadd,
            timestrutc=loc_timestr_utc,
            timestr=loc_timestr,
        )

    # @app.route('/stream_log1', methods=["GET", "POST"])
    def stream_log1(self):
        """Flask Route: /stream_log1 - UNUSED ALTERNATE LOGS ROUTE."""

        def generate():
            with open("/NeoSectional/logs/logfile.log", encoding="utf8") as f:
                while True:
                    yield "{}\n".format(f.read())
                    time.sleep(1)

        return self.app.response_class(generate(), mimetype="text/plain")

    def airport_boundary_calc(self):
        """Scan airport lat/lon data and work out Airport Map boundaries."""
        lat_list = []
        lon_list = []
        airports = self.airport_database.get_airport_dict_led()
        for icao, airportdb_row in airports.items():
            arpt = airportdb_row["airport"]

            if not arpt.active():
                continue
            lat = float(arpt.get_latitude())
            lat_list.append(lat)
            lon = float(arpt.get_longitude())
            lon_list.append(lon)
        self.max_lat = max(lat_list)
        self.min_lat = min(lat_list)
        self.max_lon = max(lon_list)
        self.min_lon = min(lon_list)
        return

    # Route to display map's airports on a digital map.
    # @app.route('/led_map', methods=["GET", "POST"])
    def led_map(self):
        """Flask Route: /led_map - Display LED Map with existing airports."""
        # Update Airport Boundary data based on set of airports
        self.airport_boundary_calc()

        points = []
        title_coords = (self.max_lat, (float(self.max_lon) + float(self.min_lon)) / 2)
        start_coords = (
            (float(self.max_lat) + float(self.min_lat)) / 2,
            (float(self.max_lon) + float(self.min_lon)) / 2,
        )

        # Initialize Map
        folium_map = folium.Map(
            location=start_coords,
            zoom_start=5,
            height="100%",
            width="100%",
            control_scale=True,
            zoom_control=True,
            tiles="OpenStreetMap",
        )

        # Place map within bounds of screen
        folium_map.fit_bounds([[self.min_lat, self.min_lon], [self.max_lat, self.max_lon]])

        # Set Marker Color by Flight Category
        airports = self.airport_database.get_airport_dict_led()
        for icao, arptdb_row in airports.items():
            arpt = arptdb_row["airport"]
            if not arpt.active():
                continue
            if arpt.get_wx_category_str() == "VFR":
                loc_color = "green"
            elif arpt.get_wx_category_str() == "MVFR":
                loc_color = "blue"
            elif arpt.get_wx_category_str() == "IFR":
                loc_color = "red"
            elif arpt.get_wx_category_str() == "LIFR":
                loc_color = "violet"
            else:
                loc_color = "black"

            # Get Pin Number to display in popup
            pin_num = arpt.get_led_index()

            # FIXME - Move URL to config file
            pop_url = f'<a href="https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId={icao}target="_blank">'
            popup = f"{pop_url}{icao}</a><b>{icao}</b><br>[{arpt.get_latitude()},{arpt.get_longitude()}]<br>Pin&nbsp; Number&nbsp;=&nbsp;{arpt.get_led_index()}<br><b><font size=+2 color={loc_color}>{loc_color}</font></b>"

            # Add airport markers with proper color to denote flight category
            folium.CircleMarker(
                radius=7,
                fill=True,
                color=loc_color,
                location=[arpt.get_latitude(), arpt.get_longitude()],
                popup=popup,
                tooltip=f"{str(icao)}<br>Pin {str(arpt.get_led_index())}",
                weight=6,
            ).add_to(folium_map)

        #    Custom Icon Code - Here for possible future use
        #    url = "../../NeoSectional/static/{}".format
        #    icon_image = url("dot1.gif")

        #    icon = CustomIcon(
        #        icon_image,
        #        icon_size=(48, 48),
        #    )

        #    marker = folium.Marker(
        #        location=[45.3288, -121.6625], icon=icon, popup="Mt. Hood Meadows"
        #    )

        #    folium_map.add_child(marker)

        airports = self.airport_database.get_airport_dict_led()
        for icao, arptdb_row in airports.items():
            arpt = arptdb_row["airport"]
            if not arpt.active():
                # Inactive airports likely don't have valid lat/lon data
                continue
            # Add lines between airports. Must make lat/lons
            # floats otherwise recursion error occurs.
            pin_index = int(arpt.get_led_index())
            points.insert(pin_index, [arpt.get_latitude(), arpt.get_longitude()])

        debugging.debug(points)
        folium.PolyLine(points, color="grey", weight=2.5, opacity=1, dash_array="10").add_to(folium_map)

        # Add Title to the top of the map
        folium.map.Marker(
            title_coords,
            icon=DivIcon(
                icon_size=(500, 36),
                icon_anchor=(150, 64),
                html='<div style="font-size: 24pt"><b>LiveSectional Map Layout</b></div>',
            ),
        ).add_to(folium_map)

        # Extra features to add if desired
        folium_map.add_child(folium.LatLngPopup())
        #    folium.plugins.Terminator().add_to(folium_map)
        #    folium_map.add_child(folium.ClickForMarker(popup='Marker'))
        folium.plugins.Geocoder().add_to(folium_map)

        folium.plugins.Fullscreen(
            position="topright",
            title="Full Screen",
            title_cancel="Exit Full Screen",
            force_separate_button=True,
        ).add_to(folium_map)

        # FIXME: Move URL to configuration
        folium.TileLayer(
            "http://wms.chartbundle.com/tms/1.0.0/sec/{z}/{x}/{y}.png?origin=nw",
            attr="chartbundle.com",
            name="ChartBundle Sectional",
        ).add_to(folium_map)
        folium.TileLayer("Stamen Terrain", name="Stamen Terrain").add_to(folium_map)
        folium.TileLayer("CartoDB positron", name="CartoDB Positron").add_to(folium_map)

        folium.LayerControl().add_to(folium_map)

        # FIXME: Move filename to config.ini
        folium_map.save("/NeoSectional/templates/map.html")
        debugging.info("Opening led_map in separate window")

        template_data = self.standardtemplate_data()
        template_data["title"] = "LEDmap"
        template_data["led_map_dict"] = self.led_map_dict
        template_data["max_lat"] = self.max_lat
        template_data["min_lat"] = self.min_lat
        template_data["max_lon"] = self.max_lon
        template_data["min_lon"] = self.min_lon

        return render_template("led_map.html", **template_data)

    def qrcode(self):
        """Flask Route: /qrcode - Generate QRcode for site URL."""
        # Generates qrcode that maps to the mobileconfedit version of
        # the configuration generator
        template_data = self.standardtemplate_data()

        ipadd = self.sysdata.local_ip()
        qraddress = "http://" + ipadd.strip() + ":5000/lsremote"
        debugging.info("Opening qrcode in separate window")
        qrcode_file = self.conf.get_string("filenames", "qrcode")
        qrcode_url = self.conf.get_string("filenames", "qrcode_url")

        myQR = QRCode(qraddress)
        myQR.png(qrcode_file, scale=8)

        return render_template("qrcode.html", qraddress=qraddress, qrimage=qrcode_url)

    def getmetar(self, airport):
        """Flask Route: /metar - Get METAR for Airport."""
        template_data = self.standardtemplate_data()

        debugging.info(f"getmetar: airport = {airport}")
        template_data["airport"] = airport

        airport = airport.lower()

        if airport == "debug":
            """Debug request - dumping DB info"""
            with open("logs/airport_database.txt", "w") as outfile:
                airportdb = self.airport_database.get_airportxmldb()
                counter = 0
                for icao, airport in airportdb.items():
                    outfile.write(f"{icao}: {airport} :\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
        try:
            airport_entry = self.airport_database.get_airportxml(airport)
            debugging.info(airport_entry)
            template_data["metar"] = airport_entry["raw_text"]
        except Exception as e:
            debugging.error(f"Attempt to get metar for failed for :{airport}: ERR:{e}")
            template_data["metar"] = "ERR - Not found"

        return render_template("metar.html", **template_data)

    def gettaf(self, airport):
        """Flask Route: /taf - Get TAF for Airport."""
        template_data = self.standardtemplate_data()

        debugging.info(f"getmetar: airport = {airport}")
        template_data["airport"] = airport

        airport = airport.lower()

        if airport == "debug":
            """Debug request - dumping DB info"""
            with open("logs/airport_database.txt", "w") as outfile:
                airportdb = self.airport_database.get_airportxmldb()
                counter = 0
                for icao, airport in airportdb.items():
                    outfile.write(f"{icao}: {airport} :\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
        try:
            airport_entry = self.airport_database.get_airport_taf(airport)
            debugging.info(airport_entry)
            template_data["taf"] = airport_entry["raw_text"]
        except Exception as e:
            debugging.error(f"Attempt to get metar for failed for :{airport}: ERR:{e}")
            template_data["taf"] = "ERR - Not found"

        return render_template("taf.html", **template_data)

    # FIXME: Figure out what the home page will look like.
    # @app.route('/', methods=["GET", "POST"])
    # @app.route('/index', methods=["GET", "POST"])
    def index(self):
        """Flask Route: / and /index - Homepage."""
        template_data = self.standardtemplate_data()
        template_data["title"] = "ConfEdit"

        # flash(machines) # Debug
        debugging.info("Opening Home Page/Index")
        return render_template("index.html", **template_data)

    # Routes to download airports, logfile.log and config.py to local computer
    # @app.route('/download_ap', methods=["GET", "POST"])
    def downloadairports(self):
        """Flask Route: /download_ap - Export airports file."""
        debugging.info("Downloaded Airport File")
        path = self.conf.get_string("filenames", "airports_json")
        return send_file(path, as_attachment=True)

    # @app.route('/download_cf', methods=["GET", "POST"])
    def downloadconfig(self):
        """Flask Route: /download_cf - Export configuration file."""
        debugging.info("Downloaded Config File")
        path = self.conf.get_string("filenames", "config_file")
        return send_file(path, as_attachment=True)

    # @app.route('/download_log', methods=["GET", "POST"])
    def downloadlog(self):
        """Flask Route: /download_log - Export log file."""
        debugging.info("Downloaded Logfile")
        path = self.conf.get_string("filenames", "config_file")
        return send_file(path, as_attachment=True)

    # FIXME: Integrate into Class
    # @app.route('/download_hm', methods=["GET", "POST"])
    def downloadhm(self):
        """Flask Route: /download_hm - Export heatmap data file."""
        debugging.info("Downloaded Heat Map data file")
        path = "data/hmdata"
        return send_file(path, as_attachment=True)

    # FIXME: Integrate into Class
    # Routes for Heat Map Editor
    # @app.route("/hmedit", methods=["GET", "POST"])
    def hmedit(self):
        """Flask Route: /hmedit - Heat Map Editor."""
        debugging.info("Opening hmedit.html")

        self.readhmdata(self.conf.get_string("filenames", "heatmap_file"))

        template_data = self.standardtemplate_data()
        template_data["title"] = "HeatMap Editor"

        return render_template("hmedit.html", **template_data)

    # FIXME: Integrate into Class
    # @app.route("/hmpost", methods=["GET", "POST"])
    def handle_hmpost_request(self):
        """Flask Route: /hmpost - Upload HeatMap Data."""
        debugging.info("Saving Heat Map Data File")

        loc_newlist = []

        if request.method == "POST":
            data = request.form.to_dict()
            debugging.dprint(data)  # debug

            j = 0
            for key in data:
                value = data.get(key)

                if value == "":
                    value = "0"

                # FIXME: self.airports doesn't exist any more.
                # loc_newlist.append(self.airports[j] + " " + value)
                j += 1

            self.writehmdata(loc_newlist, self.conf.get_string("filenames", "heatmap_file"))

        flash("Heat Map Data Successfully Saved")
        return redirect("hmedit")

    # FIXME: Integrate into Class
    # Import a file to populate Heat Map Data. Must Save airports to keep
    # @app.route("/importhm", methods=["GET", "POST"])
    def importhm(self):
        """Flask Route: /importhm - Importing Heat Map."""
        debugging.info("Importing Heat Map File")
        hmdata = []

        if "file" not in request.files:
            flash("No File Selected")
            return redirect("./hmedit")

        file = request.files["file"]

        if file.filename == "":
            flash("No File Selected")
            return redirect("./hmedit")

        filedata = file.read()
        tmphmdata = bytes.decode(filedata)
        debugging.dprint(tmphmdata)
        hmdata = tmphmdata.split("\n")
        hmdata.pop()
        debugging.dprint(hmdata)

        template_data = self.standardtemplate_data()
        template_data["title"] = "Import HeatMap"
        flash('Heat Map Imported - Click "Save Heat Map File" to save')
        return render_template("hmedit.html", **template_data)

    # FIXME: Integrate into Class
    # Routes for Airport Editor
    # @app.route("/apedit", methods=["GET", "POST"])
    def apedit(self):
        """Flask Route: /apedit - Airport Editor."""
        debugging.info("Opening apedit.html")

        # self.readairports(self.conf.get_string("filenames", "airports_file"))
        template_data = self.standardtemplate_data()
        template_data["title"] = "Airports Editor"
        return render_template("apedit.html", **template_data)

    # FIXME: Integrate into Class
    # @app.route("/numap", methods=["GET", "POST"])
    def numap(self):
        """Flask Route: /numap."""
        debugging.info("Updating Number of airports in airport file")

        if request.method == "POST":
            loc_numap = int(request.form["numofap"])
            debugging.dprint(loc_numap)

        # self.readairports(self.conf.get_string("filenames", "airports_file"))

        # FIXME: self.airports is retired
        newnum = loc_numap - int(len(self.airports))
        if newnum < 0:
            self.airports = self.airports[:newnum]
        else:
            for n in range(len(self.airports), loc_numap):
                self.airports.append("NULL")

        template_data = self.standardtemplate_data()
        template_data["title"] = "Airports Editor"

        flash('Number of LEDs Updated - Click "Save airports" to save.')
        return render_template("apedit.html", **template_data)

    # FIXME: Integrate into Class
    # @app.route("/appost", methods=["GET", "POST"])
    def handle_appost_request(self):
        """Flask Route: /appost."""
        debugging.info("Saving Airport File")

        if request.method == "POST":
            data = request.form.to_dict()
            debugging.debug(data)  # debug
            self.writeairports(data, self.conf.get_string("filenames", "airports_file"))

            # self.readairports(self.conf.get_string("filenames", "airports_file"))

            # update size and data of hmdata based on saved airports file.
            self.readhmdata(self.conf.get_string("filenames", "heatmap_file"))
            # get heat map data to update with newly edited airports file
            # FIXME: self.airports retired
            if len(self.hmdata) > len(self.airports):
                # adjust size of hmdata list if length is larger than airports
                num = len(self.hmdata) - len(self.airports)
                hmdata = hmdata[:-num]

            elif len(hmdata) < len(self.airports):
                # adjust size of hmdata list if length is smaller than airports
                for n in range(len(hmdata), len(self.airports)):
                    hmdata.append("NULL 0")

            for loc_index, airport in enumerate(self.airports):
                # now that both lists are same length, be sure the data matches
                ap, *_ = hmdata[loc_index].split()
                if ap != airport:
                    hmdata[loc_index] = airport + " 0"
                    # save changed airport and set zero landings to it in hmdata
            self.writehmdata(hmdata, self.conf.get_string("filenames", "heatmap_file"))

        flash("Airports Successfully Saved")
        return redirect("apedit")

    # FIXME: Integrate into Class
    # @app.route("/ledonoff", methods=["GET", "POST"])
    def ledonoff(self):
        """Flask Route: /ledonoff."""
        debugging.info("Controlling LED's on/off")

        if request.method == "POST":

            # self.readairports(self.conf.get_string("filenames", "airports_file"))

            if "buton" in request.form:
                num = int(request.form["lednum"])
                debugging.info("LED " + str(num) + " On")
                self.strip.setPixelColor(num, Color(155, 155, 155))
                self.strip.show()
                flash("LED " + str(num) + " On")

            elif "butoff" in request.form:
                num = int(request.form["lednum"])
                debugging.info("LED " + str(num) + " Off")
                self.strip.setPixelColor(num, Color(0, 0, 0))
                self.strip.show()
                flash("LED " + str(num) + " Off")

            elif "butup" in request.form:
                debugging.info("LED UP")
                num = int(request.form["lednum"])
                self.strip.setPixelColor(num, Color(0, 0, 0))
                num = num + 1

                # FIXME: self.airports retired
                if num > len(self.airports):
                    num = len(self.airports)

                self.strip.setPixelColor(num, Color(155, 155, 155))
                self.strip.show()
                flash("LED " + str(num) + " should be On")

            elif "butdown" in request.form:
                debugging.info("LED DOWN")
                num = int(request.form["lednum"])
                self.strip.setPixelColor(num, Color(0, 0, 0))

                num = num - 1
                num = max(num, 0)

                self.strip.setPixelColor(num, Color(155, 155, 155))
                self.strip.show()
                flash("LED " + str(num) + " should be On")

            elif "butall" in request.form:
                debugging.info("LED All ON")
                num = int(request.form["lednum"])

                # FIXME: self.airports retired
                for num in range(len(self.airports)):
                    self.strip.setPixelColor(num, Color(155, 155, 155))
                self.strip.show()
                flash("All LEDs should be On")
                num = 0

            elif "butnone" in request.form:
                debugging.info("LED All OFF")
                num = int(request.form["lednum"])

                # FIXME: self.airports retired
                for num in range(len(self.airports)):
                    self.strip.setPixelColor(num, Color(0, 0, 0))
                self.strip.show()
                flash("All LEDs should be Off")
                num = 0

            else:  # if tab is pressed
                debugging.info("LED Edited")
                num = int(request.form["lednum"])
                flash("LED " + str(num) + " Edited")

        template_data = self.standardtemplate_data()
        template_data["title"] = "Airports File Editor"

        return render_template("apedit.html", **template_data)

    # FIXME: Integrate into Class
    # Import a file to populate airports. Must Save self.airports to keep
    # @app.route("/importap", methods=["GET", "POST"])
    def importap(self):
        """Flask Route: /importap - Import airports File."""
        debugging.info("Importing airports File")

        if "file" not in request.files:
            flash("No File Selected")
            return redirect("./apedit")

        file = request.files["file"]

        if file.filename == "":
            flash("No File Selected")
            return redirect("./apedit")

        filedata = file.read()
        fdata = bytes.decode(filedata)
        debugging.dprint(fdata)
        self.airports = fdata.split("\n")
        self.airports.pop()
        debugging.dprint(self.airports)

        template_data = self.standardtemplate_data()
        template_data["title"] = "Airports Editor"

        flash('Airports Imported - Click "Save self.airports" to save')
        return render_template("apedit.html", **template_data)

    # FIXME: Integrate into Class
    # Routes for Config Editor
    # @app.route("/confedit", methods=["GET", "POST"])
    def confedit(self):
        """Flask Route: /confedit - Configuration Editor."""
        debugging.info("Opening confedit.html")

        # debugging.dprint(ipadd)  # debug
        # debugging.dprint(settings)

        # change rgb code to hex for html color picker
        # color_vfr_hex = utils.rgb2hex(self.conf.get_color("colors","color_vfr"))
        # color_mvfr_hex = utils.rgb2hex(self.conf.get_color("colors","color_mvfr"))
        # color_ifr_hex = utils.rgb2hex(self.conf.get_color("colors","color_ifr"))
        # color_lifr_hex = utils.rgb2hex(self.conf.get_color("colors","color_lifr"))
        # color_nowx_hex = utils.rgb2hex(self.conf.get_color("colors","color_nowx"))
        # color_black_hex = utils.rgb2hex(self.conf.get_color("colors","color_black"))
        # color_lghtn_hex = utils.rgb2hex(self.conf.get_color("colors","color_lghtn"))
        # color_snow1_hex = utils.rgb2hex(self.conf.get_color("colors","color_snow1"))
        # color_snow2_hex = utils.rgb2hex(self.conf.get_color("colors","color_snow2"))
        # color_rain1_hex = utils.rgb2hex(self.conf.get_color("colors","color_rain1"))
        # color_rain2_hex = utils.rgb2hex(self.conf.get_color("colors","color_rain2"))
        # color_frrain1_hex = utils.rgb2hex(self.conf.get_color("colors","color_frrain1"))
        # color_frrain2_hex = utils.rgb2hex(self.conf.get_color("colors","color_frrain2"))
        # color_dustsandash1_hex = utils.rgb2hex(self.conf.get_color("colors","color_dustsandash1"))
        # color_dustsandash2_hex = utils.rgb2hex(self.conf.get_color("colors","color_dustsandash2"))
        # color_fog1_hex = utils.rgb2hex(self.conf.get_color("colors","color_fog1"))
        # color_fog2_hex = utils.rgb2hex(self.conf.get_color("colors","color_fog2"))
        # color_homeport_hex = utils.rgb2hex(self.conf.get_color("colors","color_homeport"))

        # color picker for transitional wipes
        # fade_color1_hex = utils.rgb2hex(self.conf.get_color("colors","fade_color1"))
        # allsame_color1_hex = utils.rgb2hex(self.conf.get_color("colors","allsame_color1"))
        # allsame_color2_hex = utils.rgb2hex(self.conf.get_color("colors","allsame_color2"))
        # shuffle_color1_hex = utils.rgb2hex(self.conf.get_color("colors","shuffle_color1"))
        # shuffle_color2_hex = utils.rgb2hex(self.conf.get_color("colors","shuffle_color2"))
        # radar_color1_hex = utils.rgb2hex(self.conf.get_color("colors","radar_color1"))
        # radar_color2_hex = utils.rgb2hex(self.conf.get_color("colors","radar_color2"))
        # circle_color1_hex = utils.rgb2hex(self.conf.get_color("colors","circle_color1"))
        # circle_color2_hex = utils.rgb2hex(self.conf.get_color("colors","circle_color2"))
        # square_color1_hex = utils.rgb2hex(self.conf.get_color("colors","square_color1"))
        # square_color2_hex = utils.rgb2hex(self.conf.get_color("colors","square_color2"))
        # updn_color1_hex = utils.rgb2hex(self.conf.get_color("colors","updn_color1"))
        # updn_color2_hex = utils.rgb2hex(self.conf.get_color("colors","updn_color2"))
        # morse_color1_hex = utils.rgb2hex(self.conf.get_color("colors","morse_color1"))
        # morse_color2_hex = utils.rgb2hex(self.conf.get_color("colors","morse_color2"))
        # rabbit_color1_hex = utils.rgb2hex(self.conf.get_color("colors","rabbit_color1"))
        # rabbit_color2_hex = utils.rgb2hex(self.conf.get_color("colors","rabbit_color2"))
        # checker_color1_hex = utils.rgb2hex(self.conf.get_color("colors","checker_color1"))
        # checker_color2_hex = utils.rgb2hex(self.conf.get_color("colors","checker_color2"))

        # Pass data to html document
        template_data = self.standardtemplate_data()
        template_data["title"] = "Settings Editor"

        # FIXME: Needs a better way
        template_data["color_vfr_hex"] = self.conf.get_color("colors", "color_vfr")
        template_data["color_mvfr_hex"] = self.conf.get_color("colors", "color_mvfr")
        template_data["color_ifr_hex"] = self.conf.get_color("colors", "color_ifr")
        template_data["color_lifr_hex"] = self.conf.get_color("colors", "color_lifr")
        template_data["color_nowx_hex"] = self.conf.get_color("colors", "color_nowx")
        template_data["color_black_hex"] = self.conf.get_color("colors", "color_black")
        template_data["color_lghtn_hex"] = self.conf.get_color("colors", "color_lghtn")
        template_data["color_snow1_hex"] = self.conf.get_color("colors", "color_snow1")
        template_data["color_snow2_hex"] = self.conf.get_color("colors", "color_snow2")
        template_data["color_rain1_hex"] = self.conf.get_color("colors", "color_rain1")
        template_data["color_rain2_hex"] = self.conf.get_color("colors", "color_rain2")
        template_data["color_frrain1_hex"] = self.conf.get_color("colors", "color_frrain1")
        template_data["color_frrain2_hex"] = self.conf.get_color("colors", "color_frrain2")
        template_data["color_dustsandash1_hex"] = self.conf.get_color("colors", "color_dustsandash1")
        template_data["color_dustsandash2_hex"] = self.conf.get_color("colors", "color_dustsandash2")
        template_data["color_fog1_hex"] = self.conf.get_color("colors", "color_fog1")
        template_data["color_fog2_hex"] = self.conf.get_color("colors", "color_fog2")
        template_data["color_homeport_hex"] = self.conf.get_color("colors", "color_homeport")

        template_data["fade_color1_hex"] = self.conf.get_color("colors", "fade_color1")
        template_data["allsame_color1_hex"] = self.conf.get_color("colors", "allsame_color1")
        template_data["allsame_color2_hex"] = self.conf.get_color("colors", "allsame_color2")
        template_data["shuffle_color1_hex"] = self.conf.get_color("colors", "shuffle_color1")
        template_data["shuffle_color2_hex"] = self.conf.get_color("colors", "shuffle_color2")
        template_data["radar_color1_hex"] = self.conf.get_color("colors", "radar_color1")
        template_data["radar_color2_hex"] = self.conf.get_color("colors", "radar_color2")
        template_data["circle_color1_hex"] = self.conf.get_color("colors", "circle_color1")
        template_data["circle_color2_hex"] = self.conf.get_color("colors", "circle_color2")
        template_data["square_color1_hex"] = self.conf.get_color("colors", "square_color1")
        template_data["square_color2_hex"] = self.conf.get_color("colors", "square_color2")
        template_data["updn_color1_hex"] = self.conf.get_color("colors", "updn_color1")
        template_data["updn_color2_hex"] = self.conf.get_color("colors", "updn_color2")
        template_data["morse_color1_hex"] = self.conf.get_color("colors", "morse_color1")
        template_data["morse_color2_hex"] = self.conf.get_color("colors", "morse_color2")
        template_data["rabbit_color1_hex"] = self.conf.get_color("colors", "rabbit_color1")
        template_data["rabbit_color2_hex"] = self.conf.get_color("colors", "rabbit_color2")
        template_data["checker_color1_hex"] = self.conf.get_color("colors", "checker_color1")
        template_data["checker_color2_hex"] = self.conf.get_color("colors", "checker_color2")
        return render_template("confedit.html", **template_data)

    # FIXME: Integrate into Class
    # @app.route("/post", methods=["GET", "POST"])
    def handle_post_request(self):
        """Flask Route: /post ."""
        debugging.info("Saving Config File")

        ipadd = self.sysdata.local_ip()

        if request.method == "POST":
            data = request.form.to_dict()

            # convert hex value back to rgb string value for storage
            # data["color_vfr"] = str(utils.hex2rgb(data["color_vfr"]))
            # data["color_mvfr"] = str(utils.hex2rgb(data["color_mvfr"]))
            # data["color_ifr"] = str(utils.hex2rgb(data["color_ifr"]))
            # data["color_lifr"] = str(utils.hex2rgb(data["color_lifr"]))
            # data["color_nowx"] = str(utils.hex2rgb(data["color_nowx"]))
            # data["color_black"] = str(utils.hex2rgb(data["color_black"]))
            # data["color_lghtn"] = str(utils.hex2rgb(data["color_lghtn"]))
            # data["color_snow1"] = str(utils.hex2rgb(data["color_snow1"]))
            # data["color_snow2"] = str(utils.hex2rgb(data["color_snow2"]))
            # data["color_rain1"] = str(utils.hex2rgb(data["color_rain1"]))
            # data["color_rain2"] = str(utils.hex2rgb(data["color_rain2"]))
            # data["color_frrain1"] = str(utils.hex2rgb(data["color_frrain1"]))
            # data["color_frrain2"] = str(utils.hex2rgb(data["color_frrain2"]))
            # data["color_dustsandash1"] = str(utils.hex2rgb(data["color_dustsandash1"]))
            # data["color_dustsandash2"] = str(utils.hex2rgb(data["color_dustsandash2"]))
            # data["color_fog1"] = str(utils.hex2rgb(data["color_fog1"]))
            # data["color_fog2"] = str(utils.hex2rgb(data["color_fog2"]))
            # data["color_homeport"] = str(utils.hex2rgb(data["color_homeport"]))

            # convert hex value back to rgb string
            # value for storage for Transitional wipes
            # data["fade_color1"] = str(utils.hex2rgb(data["fade_color1"]))
            # data["allsame_color1"] = str(utils.hex2rgb(data["allsame_color1"]))
            # data["allsame_color2"] = str(utils.hex2rgb(data["allsame_color2"]))
            # data["shuffle_color1"] = str(utils.hex2rgb(data["shuffle_color1"]))
            # data["shuffle_color2"] = str(utils.hex2rgb(data["shuffle_color2"]))
            # data["radar_color1"] = str(utils.hex2rgb(data["radar_color1"]))
            # data["radar_color2"] = str(utils.hex2rgb(data["radar_color2"]))
            # data["circle_color1"] = str(utils.hex2rgb(data["circle_color1"]))
            # data["circle_color2"] = str(utils.hex2rgb(data["circle_color2"]))
            # data["square_color1"] = str(utils.hex2rgb(data["square_color1"]))
            # data["square_color2"] = str(utils.hex2rgb(data["square_color2"]))
            # data["updn_color1"] = str(utils.hex2rgb(data["updn_color1"]))
            # data["updn_color2"] = str(utils.hex2rgb(data["updn_color2"]))
            # data["morse_color1"] = str(utils.hex2rgb(data["morse_color1"]))
            # data["morse_color2"] = str(utils.hex2rgb(data["morse_color2"]))
            # data["rabbit_color1"] = str(utils.hex2rgb(data["rabbit_color1"]))
            # data["rabbit_color2"] = str(utils.hex2rgb(data["rabbit_color2"]))
            # data["checker_color1"] = str(utils.hex2rgb(data["checker_color1"]))
            # data["checker_color2"] = str(utils.hex2rgb(data["checker_color2"]))

            # check and fix data with leading zeros.
            for key in data:
                if data[key] == "0" or data[key] == "00":
                    data[key] = "0"
                elif data[key][:1] == "0":
                    # Check if first character is a 0. i.e. 01, 02 etc.
                    data[key] = data[key].lstrip("0")
                    # if so, then self.strip the leading zero before writing to file.

            self.conf.parse_config_input(data)
            self.conf.save_config()
            # writeconf(data, settings_file)
            # readconf(settings_file)
            flash("Settings Successfully Saved")

            url = request.referrer
            if url is None:
                url = "http://" + ipadd + ":5000/index"
                # Use index if called from URL and not page.

            temp = url.split("/")
            return redirect("/")
            # temp[3] holds name of page that called this route.

    # FIXME: Integrate into Class
    # Routes for LSREMOTE - Allow Mobile Device Remote. Thank Lance
    # # @app.route('/', methods=["GET", "POST"])
    # @app.route('/lsremote', methods=["GET", "POST"])
    def confeditmobile(self):
        """Flask Route: /lsremote - Mobile Device API"""
        debugging.info("Opening lsremote.html")

        ipadd = self.sysdata.local_ip()
        current_timezone = self.conf.get_string("default", "timezone")
        settings = self.conf.gen_settings_dict()
        loc_timestr = utils.time_format(utils.current_time(self.conf))
        loc_timestr_utc = utils.time_format(utils.current_time_utc(self.conf))

        debugging.dprint(ipadd)  # debug

        # change rgb code to hex for html color picker
        color_vfr_hex = utils.rgb2hex(self.conf.get_color("colors", "color_vfr"))
        color_mvfr_hex = utils.rgb2hex(self.conf.get_color("colors", "color_mvfr"))
        color_ifr_hex = utils.rgb2hex(self.conf.get_color("colors", "color_ifr"))
        color_lifr_hex = utils.rgb2hex(self.conf.get_color("colors", "color_lifr"))
        color_nowx_hex = utils.rgb2hex(self.conf.get_color("colors", "color_nowx"))
        color_black_hex = utils.rgb2hex(self.conf.get_color("colors", "color_black"))
        color_lghtn_hex = utils.rgb2hex(self.conf.get_color("colors", "color_lghtn"))
        color_snow1_hex = utils.rgb2hex(self.conf.get_color("colors", "color_snow1"))
        color_snow2_hex = utils.rgb2hex(self.conf.get_color("colors", "color_snow2"))
        color_rain1_hex = utils.rgb2hex(self.conf.get_color("colors", "color_rain1"))
        color_rain2_hex = utils.rgb2hex(self.conf.get_color("colors", "color_rain2"))
        color_frrain1_hex = utils.rgb2hex(self.conf.get_color("colors", "color_frrain1"))
        color_frrain2_hex = utils.rgb2hex(self.conf.get_color("colors", "color_frrain2"))
        color_dustsandash1_hex = utils.rgb2hex(self.conf.get_color("colors", "color_dustsandash1"))
        color_dustsandash2_hex = utils.rgb2hex(self.conf.get_color("colors", "color_dustsandash2"))
        color_fog1_hex = utils.rgb2hex(self.conf.get_color("colors", "color_fog1"))
        color_fog2_hex = utils.rgb2hex(self.conf.get_color("colors", "color_fog2"))
        color_homeport_hex = utils.rgb2hex(self.conf.get_color("colors", "color_homeport"))

        # color picker for transitional wipes
        fade_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "fade_color1"))
        allsame_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "allsame_color1"))
        allsame_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "allsame_color2"))
        shuffle_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "shuffle_color1"))
        shuffle_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "shuffle_color2"))
        radar_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "radar_color1"))
        radar_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "radar_color2"))
        circle_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "circle_color1"))
        circle_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "circle_color2"))
        square_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "square_color1"))
        square_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "square_color2"))
        updn_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "updn_color1"))
        updn_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "updn_color2"))
        morse_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "morse_color1"))
        morse_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "morse_color2"))
        rabbit_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "rabbit_color1"))
        rabbit_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "rabbit_color2"))
        checker_color1_hex = utils.rgb2hex(self.conf.get_color("colors", "checker_color1"))
        checker_color2_hex = utils.rgb2hex(self.conf.get_color("colors", "checker_color2"))

        # Pass data to html document
        template_data = self.standardtemplate_data()
        template_data["title"] = "Settings Editor"
        # TODO: Needs cleanup
        template_data = {
            "title": "Settings Editor-" + self.appinfo.current_version(),
            "settings": settings,
            "ipadd": ipadd,
            # 'num': num,
            "timestr": loc_timestr,
            "timestrutc": loc_timestr_utc,
            "current_timezone": current_timezone,
            # 'update_available': update_available,
            # 'update_vers': update_vers,
            # 'machines': machines,
            # Color Picker Variables to pass
            "color_vfr_hex": color_vfr_hex,
            "color_mvfr_hex": color_mvfr_hex,
            "color_ifr_hex": color_ifr_hex,
            "color_lifr_hex": color_lifr_hex,
            "color_nowx_hex": color_nowx_hex,
            "color_black_hex": color_black_hex,
            "color_lghtn_hex": color_lghtn_hex,
            "color_snow1_hex": color_snow1_hex,
            "color_snow2_hex": color_snow2_hex,
            "color_rain1_hex": color_rain1_hex,
            "color_rain2_hex": color_rain2_hex,
            "color_frrain1_hex": color_frrain1_hex,
            "color_frrain2_hex": color_frrain2_hex,
            "color_dustsandash1_hex": color_dustsandash1_hex,
            "color_dustsandash2_hex": color_dustsandash2_hex,
            "color_fog1_hex": color_fog1_hex,
            "color_fog2_hex": color_fog2_hex,
            "color_homeport_hex": color_homeport_hex,
            # Color Picker Variables to pass
            "fade_color1_hex": fade_color1_hex,
            "allsame_color1_hex": allsame_color1_hex,
            "allsame_color2_hex": allsame_color2_hex,
            "shuffle_color1_hex": shuffle_color1_hex,
            "shuffle_color2_hex": shuffle_color2_hex,
            "radar_color1_hex": radar_color1_hex,
            "radar_color2_hex": radar_color2_hex,
            "circle_color1_hex": circle_color1_hex,
            "circle_color2_hex": circle_color2_hex,
            "square_color1_hex": square_color1_hex,
            "square_color2_hex": square_color2_hex,
            "updn_color1_hex": updn_color1_hex,
            "updn_color2_hex": updn_color2_hex,
            "morse_color1_hex": morse_color1_hex,
            "morse_color2_hex": morse_color2_hex,
            "rabbit_color1_hex": rabbit_color1_hex,
            "rabbit_color2_hex": rabbit_color2_hex,
            "checker_color1_hex": checker_color1_hex,
            "checker_color2_hex": checker_color2_hex,
        }
        return render_template("lsremote.html", **template_data)

    # FIXME: Integrate into Class
    # Import Config file. Must Save Config File to make permenant
    # @app.route("/importconf", methods=["GET", "POST"])
    def importconf(self):
        """Flask Route: /importconf - Flask Config Uploader"""
        debugging.info("Importing Config File")
        tmp_settings = []

        if "file" not in request.files:
            flash("No File Selected")
            return redirect("./confedit")

        file = request.files["file"]

        if file.filename == "":
            flash("No File Selected")
            return redirect("./confedit")

        filedata = file.read()
        fdata = bytes.decode(filedata)
        debugging.dprint(fdata)
        tmp_settings = fdata.split("\n")

        for set_line in tmp_settings:
            if set_line[0:1] in ("#", "\n", ""):
                pass
            else:
                (key, val) = set_line.split("=", 1)
                val = val.split("#", 1)
                val = val[0]
                key = key.strip()
                val = str(val.strip())
                settings[(key)] = val

        debugging.dprint(settings)
        flash('Config File Imported - Click "Save Config File" to save')
        return redirect("./confedit")

    # FIXME: Integrate into Class
    # Restore config.py settings
    # @app.route("/restoreconf", methods=["GET", "POST"])
    def restoreconf(self):
        """Flask Route: /restoreconf"""
        debugging.info("Restoring Config Settings")
        return redirect("./confedit")

    # FIXME: Integrate into Class
    # Loads the profile into the Settings Editor, but does not save it.
    # @app.route("/profiles", methods=["GET", "POST"])
    def profiles(self):
        """Flask Route: /profiles - Load from Multiple Config Profiles"""
        config_profiles = {
            "b1": "config-basic.py",
            "b2": "config-basic2.py",
            "b3": "config-basic3.py",
            "a1": "config-advanced-1oled.py",
            "a2": "config-advanced-lcd.py",
            "a3": "config-advanced-8oledsrs.py",
            "a4": "config-advanced-lcdrs.py",
        }

        req_profile = request.form["profile"]
        debugging.dprint(req_profile)
        debugging.dprint(self.config_profiles)
        tmp_profile = config_profiles[req_profile]
        stored_profile = "/NeoSectional/profiles/" + tmp_profile

        flash(tmp_profile + "Profile Loaded. Review And Tweak The Settings As Desired. Must Be Saved!")
        self.readconf(stored_profile)  # read profile config file
        debugging.info("Loading a Profile into Settings Editor")
        return redirect("confedit")

    # FIXME: Integrate into Class
    # Route for Reboot of RPI
    # @app.route("/reboot1", methods=["GET", "POST"])
    def reboot1(self):
        """Flask Route: /reboot1 - Request host reboot"""
        ipadd = self.sysdata.local_ip()
        url = request.referrer
        if url is None:
            url = "http://" + ipadd + ":5000/index"
            # Use index if called from URL and not page.

        temp = url.split("/")
        # flash("Rebooting Map ")
        debugging.info("Rebooting Map from " + url)
        # FIXME:
        # os.system('sudo shutdown -r now')
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # FIXME: Integrate into Class
    # Route to startup map and displays
    # @app.route("/startup1", methods=["GET", "POST"])
    def startup1(self):
        """Flask Route: /startup1 - Trigger process startup"""
        url = request.referrer
        ipadd = self.sysdata.local_ip()
        if url is None:
            url = "http://" + ipadd + ":5000/index"
            # Use index if called from URL and not page.

        temp = url.split("/")
        debugging.info("Startup Map from " + url)
        # FIXME:
        # os.system('sudo python3 /NeoSectional/startup.py run &')
        flash("Map Turned On ")
        time.sleep(1)
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # FIXME: Integrate into Class
    # Route to turn off the map and displays
    # @app.route("/shutdown1", methods=["GET", "POST"])
    def shutdown1(self):
        """Flask Route: /shutdown1 - Trigger process shutdown"""
        url = request.referrer
        ipadd = self.sysdata.local_ip()
        if url is None:
            url = "http://" + ipadd + ":5000/index"
            # Use index if called from URL and not page.

        temp = url.split("/")
        debugging.info("Shutoff Map from " + url)
        # FIXME:
        # os.system("ps -ef | grep '/NeoSectional/metar-display-v4.py' | awk '{print $2}' | xargs sudo kill")
        # os.system("ps -ef | grep '/NeoSectional/metar-v4.py' | awk '{print $2}' | xargs sudo kill")
        # os.system("ps -ef | grep '/NeoSectional/check-display.py' | awk '{print $2}' | xargs sudo kill")
        # os.system('sudo python3 /NeoSectional/shutoff.py &')
        flash("Map Turned Off ")
        time.sleep(1)
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # FIXME: Integrate into Class
    # Route to power down the RPI
    # @app.route("/shutoffnow1", methods=["GET", "POST"])
    def shutoffnow1(self):
        """Flask Route: /shutoffnow1 - Turn Off RPI"""
        url = request.referrer
        ipadd = self.sysdata.local_ip()
        if url is None:
            url = "http://" + ipadd + ":5000/index"
            # Use index if called from URL and not page.

        temp = url.split("/")
        # flash("RPI is Shutting Down ")
        debugging.info("Shutdown RPI from " + url)
        # FIXME: Security Fixup
        # os.system('sudo shutdown -h now')
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # FIXME: Integrate into Class
    # Route to run LED test
    # @app.route("/testled", methods=["GET", "POST"])
    def testled(self):
        """Flask Route: /testled - Run LED Test scripts"""
        url = request.referrer
        ipadd = self.sysdata.local_ip()

        if url is None:
            url = "http://" + ipadd + ":5000/index"
            # Use index if called from URL and not page.

        temp = url.split("/")

        # flash("Testing LED's")
        debugging.info("Running testled.py from " + url)
        # os.system('sudo python3 /NeoSectional/testled.py')
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # FIXME: Integrate into Class
    # Route to run OLED test
    # @app.route("/testoled", methods=["GET", "POST"])
    def testoled(self):
        """Flask Route: /testoled - Run OLED Test sequence"""
        url = request.referrer
        ipadd = self.sysdata.local_ip()
        if url is None:
            url = "http://" + ipadd + ":5000/index"
            # Use index if called from URL and not page.

        temp = url.split("/")
        if (self.conf.get_int("oled", "displayused") != 1) or (self.conf.get_int("oled", "oledused") != 1):
            return redirect("/")
            # temp[3] holds name of page that called this route.

        # flash("Testing OLEDs ")
        debugging.info("Running testoled.py from " + url)
        # FIXME: Call update_oled equivalent functions
        # os.system('sudo python3 /NeoSectional/testoled.py')
        return redirect("/")
