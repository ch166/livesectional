# -*- coding: utf-8 -*- #
"""Flask Module for WEB Interface."""

import os

# import datetime
import time

import json

# import subprocess
import secrets
import pytz

from rpi_ws281x import (
    Color,
)

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

# from werkzeug.utils import secure_filename

from pyqrcode import QRCode

import utils

# import conf
from update_leds import LedMode
import debugging

# import sysinfo


class WebViews:
    """Class to contain all the Flask WEB functionality."""

    max_lat = 0
    min_lat = 0
    max_lon = 0
    min_lon = 0

    airports = []  # type: list[object]
    update_vers = None
    machines = []  # type: list[str]
    update_available = None
    ap_info = None
    settings = None
    led_map_dict = {}  # type: dict

    def __init__(self, config, sysdata, airport_database, appinfo, led_mgmt):
        self.conf = config
        self._sysdata = sysdata
        self._airport_database = airport_database
        self._appinfo = appinfo
        self.app = Flask(__name__)
        # self.app.jinja_env.auto_reload = True
        # This needs to happen really early in the process to take effect
        self.app.config["TEMPLATES_AUTO_RELOAD"] = True

        self.app.secret_key = secrets.token_hex(16)
        self.app.add_url_rule("/", view_func=self.index, methods=["GET"])
        self.app.add_url_rule("/sysinfo", view_func=self.systeminfo, methods=["GET"])
        self.app.add_url_rule("/qrcode", view_func=self.qrcode, methods=["GET"])
        self.app.add_url_rule(
            "/metar/<airport>", view_func=self.getmetar, methods=["GET"]
        )
        self.app.add_url_rule("/taf/<airport>", view_func=self.gettaf, methods=["GET"])
        self.app.add_url_rule("/wx/<airport>", view_func=self.getwx, methods=["GET"])
        self.app.add_url_rule("/tzset", view_func=self.tzset, methods=["GET", "POST"])
        self.app.add_url_rule(
            "/ledmodeset", view_func=self.ledmodeset, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/led_map", view_func=self.led_map, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/heat_map", view_func=self.heat_map, methods=["GET", "POST"]
        )
        # self.app.add_url_rule("/touchscr", view_func=self.touchscr, methods=["GET", "POST"])
        self.app.add_url_rule(
            "/open_console", view_func=self.open_console, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/stream_log", view_func=self.stream_log, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/stream_log1", view_func=self.stream_log1, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/download_ap", view_func=self.downloadairports, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/download_cf", view_func=self.downloadconfig, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/download_log", view_func=self.downloadlog, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/confedit", view_func=self.confedit, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/confmobile", view_func=self.confmobile, methods=["GET", "POST"]
        )
        self.app.add_url_rule("/apedit", view_func=self.apedit, methods=["GET", "POST"])
        self.app.add_url_rule("/hmedit", view_func=self.hmedit, methods=["GET", "POST"])
        self.app.add_url_rule(
            "/hmpost", view_func=self.hmpost_handler, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/cfpost", view_func=self.cfedit_handler, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/system_reboot", view_func=self.system_reboot, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/mapturnon", view_func=self.handle_mapturnon, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/mapturnoff", view_func=self.handle_mapturnoff, methods=["GET", "POST"]
        )

        self._led_strip = led_mgmt

        self.num = self.conf.get_int("default", "led_count")

    def run(self):
        """Run Flask Application.

        If debug is True, we need to make sure that auto-reload is disabled in threads
        """
        self.app.run(debug=False, host="0.0.0.0")

    def standardtemplate_data(self):
        """Generate a standardized template_data."""
        # For performance reasons we should do the minimum of data generation now
        # This gets executed for every page load
        airport_dict_data = {}
        for (
            airport_icao,
            airportdb_row,
        ) in self._airport_database.get_airport_dict_led().items():
            airport_object = airportdb_row["airport"]
            airport_record = {}
            airport_record["active"] = airport_object.active()
            airport_record["icaocode"] = airport_icao
            airport_record["metarsrc"] = airport_object.wxsrc()
            airport_record["ledindex"] = airport_object.get_led_index()
            airport_record["rawmetar"] = airport_object.get_raw_metar()
            airport_record["purpose"] = airport_object.purpose()
            airport_record["hmindex"] = airport_object.heatmap_index()
            airport_dict_data[airport_icao] = airport_record

        current_ledmode = self._led_strip.ledmode()

        template_data = {
            "title": "NOT SET - " + self._appinfo.current_version(),
            "airports": airport_dict_data,
            "settings": self.conf.gen_settings_dict(),
            "ipadd": self._sysdata.local_ip(),
            "strip": self._led_strip,
            "timestr": utils.time_format(utils.current_time(self.conf)),
            "timestrutc": utils.time_format(utils.current_time_utc(self.conf)),
            "timemetarage": utils.time_format(
                self._airport_database.get_metar_update_time()
            ),
            "current_timezone": self.conf.get_string("default", "timezone"),
            "current_ledmode": current_ledmode,
            "num": self.num,
            "version": self._appinfo.current_version(),
            "update_available": self.update_available,
            "update_vers": self.update_vers,
            "machines": self.machines,
            "sysinfo": self._sysdata.query_system_information(),
        }
        return template_data

    def systeminfo(self):
        """Flask Route: /sysinfo - Display System Info."""
        self._sysdata.refresh()
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

    def ledmodeset(self):
        """Flask Route: /ledmodeset - Set LED Display Mode."""
        if request.method == "POST":
            newledmode = request.form["newledmode"]
            newledmode_upper = newledmode.upper()
            if newledmode_upper == "METAR":
                self._led_strip.set_ledmode(LedMode.METAR)
            if newledmode_upper == "OFF":
                self._led_strip.set_ledmode(LedMode.OFF)
            if newledmode_upper == "TEST":
                self._led_strip.set_ledmode(LedMode.TEST)
            if newledmode_upper == "RABBIT":
                self._led_strip.set_ledmode(LedMode.RABBIT)
            if newledmode_upper == "METAR":
                self._led_strip.set_ledmode(LedMode.METAR)
            if newledmode_upper == "SHUFFLE":
                self._led_strip.set_ledmode(LedMode.SHUFFLE)
            if newledmode_upper == "RAINBOW":
                self._led_strip.set_ledmode(LedMode.RAINBOW)

            flash(f"LED Mode set to {newledmode}")
            debugging.info(f"LEDMode set to {newledmode}")
            return redirect("ledmodeset")

        ledmodelist = ["METAR", "Off", "Test", "Rabbit", "Shuffle", "Rainbow"]
        current_ledmode = self._led_strip.ledmode()

        template_data = self.standardtemplate_data()
        template_data["title"] = "LEDModeSet"
        template_data["ledoptionlist"] = ledmodelist
        template_data["current_ledmode"] = current_ledmode

        debugging.info("Opening LEDode Set page")
        return render_template("ledmode.html", **template_data)

    # FIXME: Integrate into Class
    # @app.route('/touchscr', methods=["GET", "POST"])
    def touchscr(self):
        """Flask Route: /touchscr - Touch Screen template."""
        ipadd = self._sysdata.local_ip()
        return render_template(
            "touchscr.html",
            title="Touch Screen",
            num=5,
            machines=self.machines,
            ipadd=ipadd,
        )

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
        ipadd = self._sysdata.local_ip()
        console_ips.append(ipadd)
        debugging.info("Opening open_console in separate window")
        return render_template(
            "open_console.html",
            urls=console_ips,
            title="Display Console Output-" + self._appinfo.current_version(),
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
        ipadd = self._sysdata.local_ip()
        debugging.info("Opening stream_log in separate window")
        return render_template(
            "stream_log.html",
            title="Display Logfile-" + self._appinfo.current_version(),
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
            with open("/NeoSectional/logs/logfile.log", encoding="utf8") as file:
                while True:
                    yield "{}\n".format(file.read())
                    time.sleep(1)

        return self.app.response_class(generate(), mimetype="text/plain")

    def airport_boundary_calc(self):
        """Scan airport lat/lon data and work out Airport Map boundaries."""
        # TODO: Handle boot-up scenario where airport list isn't loaded yet
        lat_list = []
        lon_list = []
        airports = self._airport_database.get_airport_dict_led()
        debugging.debug("Boundary Calc")
        for icao, airportdb_row in airports.items():
            arpt = airportdb_row["airport"]
            if not arpt.active():
                continue
            if not arpt.valid_coordinates():
                continue
            lat = float(arpt.latitude())
            lat_list.append(lat)
            lon = float(arpt.longitude())
            lon_list.append(lon)
            debugging.dprint(f"boundary:{icao}:{lat}:{lon}:")
        if len(lat_list) >= 1:
            self.max_lat = max(lat_list)
        else:
            self.max_lat = 0
        if len(lat_list) >= 1:
            self.min_lat = min(lat_list)
        else:
            self.max_lat = 0
        if len(lat_list) >= 1:
            self.max_lon = max(lon_list)
        else:
            self.max_lat = 0
        if len(lat_list) >= 1:
            self.min_lon = min(lon_list)
        else:
            self.max_lat = 0

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
            attr="OpenStreetMap",
        )
        # Place map within bounds of screen
        folium_map.fit_bounds(
            [[self.min_lat - 1, self.min_lon - 1], [self.max_lat + 1, self.max_lon + 1]]
        )
        # Set Marker Color by Flight Category
        airports = self._airport_database.get_airport_dict_led()
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

            # FIXME - Move URL to config file
            pop_url = f'<a href="https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId={icao}target="_blank">'
            popup = f"{pop_url}{icao}</a><b>{icao}</b><br>[{arpt.latitude()},{arpt.longitude()}]<br>Pin&nbsp; Number&nbsp;=&nbsp;{arpt.get_led_index()}<br><b><font size=+2 color={loc_color}>{loc_color}</font></b>"

            # Add airport markers with proper color to denote flight category
            folium.CircleMarker(
                radius=7,
                fill=True,
                color=loc_color,
                location=[arpt.latitude(), arpt.longitude()],
                popup=popup,
                tooltip=f"{str(icao)}<br>Pin {str(arpt.get_led_index())}",
                weight=6,
            ).add_to(folium_map)

        airports = self._airport_database.get_airport_dict_led()
        for icao, arptdb_row in airports.items():
            arpt = arptdb_row["airport"]
            if not arpt.active():
                # Inactive airports likely don't have valid lat/lon data
                continue
            if not arpt.valid_coordinates():
                continue
            # Add lines between airports. Must make lat/lons
            # floats otherwise recursion error occurs.
            pin_index = int(arpt.get_led_index())
            points.insert(pin_index, [arpt.latitude(), arpt.longitude()])
            folium.PolyLine(
                points, color="grey", weight=2.5, opacity=1, dash_array="10"
            ).add_to(folium_map)

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
            "https://wms.chartbundle.com/tms/1.0.0/sec/{z}/{x}/{y}.png?origin=nw",
            attr="chartbundle.com",
            name="ChartBundle Sectional",
        ).add_to(folium_map)
        folium.TileLayer(
            "Stamen Terrain", name="Stamen Terrain", attr="stamen.com"
        ).add_to(folium_map)
        folium.TileLayer(
            "CartoDB positron", name="CartoDB Positron", attr="carto.com"
        ).add_to(folium_map)

        folium.LayerControl().add_to(folium_map)

        # FIXME: Move filename to config.ini
        folium_map.save("/NeoSectional/static/led_map.html")
        debugging.info("Opening led_map in separate window")

        template_data = self.standardtemplate_data()
        template_data["title"] = "LEDmap"
        template_data["led_map_dict"] = self.led_map_dict
        template_data["max_lat"] = self.max_lat
        template_data["min_lat"] = self.min_lat
        template_data["max_lon"] = self.max_lon
        template_data["min_lon"] = self.min_lon

        return render_template("led_map.html", **template_data)

    # Route to display map's airports on a digital map.
    # @app.route('/led_map', methods=["GET", "POST"])
    def heat_map(self):
        """Flask Route: /heat_map - Display HEAT Map with existing airports."""
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
            height="90%",
            width="90%",
            control_scale=True,
            zoom_control=True,
            tiles="OpenStreetMap",
            attr="OpenStreetMap",
        )

        # Place map within bounds of screen
        folium_map.fit_bounds(
            [[self.min_lat, self.min_lon], [self.max_lat, self.max_lon]]
        )

        # Set Marker Color by Flight Category
        airports = self._airport_database.get_airport_dict_led()
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
            heatmap_scale = arpt.heatmap_index()
            if heatmap_scale == 0:
                heatmap_radius = 10
            else:
                heatmap_radius = 10 + heatmap_scale / 100 * 30

            # FIXME - Move URL to config file
            pop_url = f'<a href="https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId={icao}target="_blank">'
            popup = (
                f"{pop_url}{icao}</a><b>{icao}</b><br>[{arpt.latitude()},{arpt.longitude()}]"
                f"<br>Pin&nbsp; Number&nbsp;=&nbsp;{arpt.get_led_index()}<br><b>"
                f"<font size=+2 color={loc_color}>{loc_color}</font></b>"
            )

            # Add airport markers with proper color to denote flight category
            folium.CircleMarker(
                radius=heatmap_radius,
                fill=True,
                color=loc_color,
                location=[arpt.latitude(), arpt.longitude()],
                popup=popup,
                tooltip=f"{str(icao)}<br>LED {str(arpt.get_led_index())}",
                weight=6,
            ).add_to(folium_map)

        airports = self._airport_database.get_airport_dict_led()
        for icao, arptdb_row in airports.items():
            arpt = arptdb_row["airport"]
            debugging.info(
                f"Heatmap: {arpt.icaocode()} : Active: {arpt.active()} :"
                f" Coords: {arpt.valid_coordinates()}"
            )
            if not arpt.active():
                # Inactive airports likely don't have valid lat/lon data
                continue
            if not arpt.valid_coordinates():
                continue
            # Add lines between airports. Must make lat/lons
            # floats otherwise recursion error occurs.
            pin_index = int(arpt.get_led_index())
            debugging.info(
                f"HeatMap: {arpt.icaocode()} :{arpt.latitude()}:{arpt.longitude()}:{pin_index}:"
            )
            points.insert(pin_index, [arpt.latitude(), arpt.longitude()])

        # debugging.info(points)
        # No polyline on HeatMap
        # folium.PolyLine(points, color="grey", weight=2.5, opacity=1, dash_array="10").add_to(folium_map)

        # Add Title to the top of the map
        folium.map.Marker(
            title_coords,
            icon=DivIcon(
                icon_size=(500, 36),
                icon_anchor=(150, 64),
                html='<div style="font-size: 24pt"><b>LiveSectional HeatMap Layout</b></div>',
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
            "https://wms.chartbundle.com/tms/1.0.0/sec/{z}/{x}/{y}.png?origin=nw",
            attr="chartbundle.com",
            name="ChartBundle Sectional",
        ).add_to(folium_map)
        folium.TileLayer(
            "Stamen Terrain", name="Stamen Terrain", attr="stamen.com"
        ).add_to(folium_map)
        folium.TileLayer(
            "CartoDB positron", name="CartoDB Positron", attr="charto.com"
        ).add_to(folium_map)

        folium.LayerControl().add_to(folium_map)

        # FIXME: Move filename to config.ini
        folium_map.save("/NeoSectional/static/heat_map.html")
        debugging.info("Opening led_map in separate window")

        template_data = self.standardtemplate_data()
        template_data["title"] = "HEATmap"
        template_data["led_map_dict"] = self.led_map_dict
        template_data["max_lat"] = self.max_lat
        template_data["min_lat"] = self.min_lat
        template_data["max_lon"] = self.max_lon
        template_data["min_lon"] = self.min_lon

        return render_template("heat_map.html", **template_data)

    def qrcode(self):
        """Flask Route: /qrcode - Generate QRcode for site URL."""
        # Generates qrcode that maps to the mobileconfedit version of
        # the configuration generator
        template_data = self.standardtemplate_data()

        ipadd = self._sysdata.local_ip()
        qraddress = "http://" + ipadd.strip() + ":5000/confmobile"
        debugging.info("Opening qrcode in separate window")
        qrcode_file = self.conf.get_string("filenames", "qrcode")
        qrcode_url = self.conf.get_string("filenames", "qrcode_url")

        my_qrcode = QRCode(qraddress)
        my_qrcode.png(qrcode_file, scale=8)

        return render_template(
            "qrcode.html", qraddress=qraddress, qrimage=qrcode_url, **template_data
        )

    def getwx(self, airport):
        """Flask Route: /wx - Get WX JSON for Airport."""
        template_data = self.standardtemplate_data()

        # debugging.info(f"getwx: airport = {airport}")
        template_data["airport"] = airport

        airport = airport.lower()

        if airport == "debug":
            # Debug request - dumping DB info
            with open("logs/airport_database.txt", "w") as outfile:
                airportdb = self._airport_database.get_airportxmldb()
                counter = 0
                for icao, airport_id in airportdb.items():
                    outfile.write(f"{icao}: {airport_id} :\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
            wx_data = {
                "airport": "Debugging Request",
                "metar": "",
                "flightcategory": "DB DUMPED",
            }
            return json.dumps(wx_data)
        wx_data = {"airport": "Default Value", "metar": "", "flightcategory": "UNKN"}
        try:
            airport_entry = self._airport_database.get_airportxml(airport)
            debugging.info(airport_entry)
            wx_data["airport"] = airport_entry["stationId"]
            wx_data["metar"] = airport_entry["raw_text"]
            wx_data["flightcategory"] = airport_entry["flight_category"]
            wx_data["latitude"] = airport_entry["latitude"]
            wx_data["longitude"] = airport_entry["longitude"]
        except Exception as err:
            debugging.error(f"Attempt to get wx for failed for :{airport}: ERR:{err}")

        return json.dumps(wx_data)

    def getmetar(self, airport):
        """Flask Route: /metar - Get METAR for Airport."""
        template_data = self.standardtemplate_data()

        debugging.info(f"getmetar: airport = {airport}")
        template_data["airport"] = airport

        airport = airport.lower()

        if airport == "debug":
            # Debug request - dumping DB info
            with open("logs/airport_database.txt", "w") as outfile:
                airportdb = self._airport_database.get_airportxmldb()
                counter = 0
                for icao, airport_id in airportdb.items():
                    outfile.write(f"{icao}: {airport_id} :\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
        try:
            airport_entry = self._airport_database.get_airportxml(airport)
            # debugging.info(airport_entry)
            template_data["metar"] = airport_entry["raw_text"]
        except Exception as err:
            debugging.error(
                f"Attempt to get metar for failed for :{airport}: ERR:{err}"
            )
            template_data["metar"] = "ERR - Not found"

        return render_template("metar.html", **template_data)

    def gettaf(self, airport):
        """Flask Route: /taf - Get TAF for Airport."""
        template_data = self.standardtemplate_data()

        debugging.info(f"getmetar: airport = {airport}")
        template_data["airport"] = airport

        airport = airport.lower()

        if airport == "debug":
            # Debug request - dumping DB info
            with open("logs/airport_database.txt", "w") as outfile:
                airportdb = self._airport_database.get_airportxmldb()
                counter = 0
                for icao, airport_id in airportdb.items():
                    outfile.write(f"{icao}: {airport_id} :\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
        try:
            airport_entry = self._airport_database.get_airport_taf(airport)
            debugging.info(airport_entry)
            template_data["taf"] = airport_entry["raw_text"]
        except Exception as err:
            debugging.error(
                f"Attempt to get metar for failed for :{airport}: ERR:{err}"
            )
            template_data["taf"] = "ERR - Not found"

        return render_template("taf.html", **template_data)

    # @app.route('/', methods=["GET", "POST"])
    # @app.route('/intro', methods=["GET", "POST"])
    def index(self):
        """Flask Route: / and /index - Homepage."""
        template_data = self.standardtemplate_data()
        template_data["title"] = "Intro"

        # flash(machines) # Debug
        debugging.info("Opening Home Page/Intro")
        return render_template("intro.html", **template_data)

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

    # Routes for Heat Map Editor
    # @app.route("/hmedit", methods=["GET", "POST"])
    def hmedit(self):
        """Flask Route: /hmedit - Heat Map Editor."""
        debugging.info("Opening hmedit.html")
        template_data = self.standardtemplate_data()
        template_data["title"] = "HeatMap Editor"
        return render_template("hmedit.html", **template_data)

    # @app.route("/hmpost", methods=["GET", "POST"])
    def hmpost_handler(self):
        """Flask Route: /hmpost - Upload HeatMap Data."""
        debugging.info("Updating airport heatmap data in airport records")

        if request.method == "POST":
            form_data = request.form.to_dict()
            # debugging.dprint(data)  # debug

            # This will update the data for all airports.
            # So we should iterate through the airport data set.
            airports = self._airport_database.get_airport_dict_led()
            for icao, airportdb_row in airports.items():
                arpt = airportdb_row["airport"]
                if not arpt.active():
                    continue
                if icao in form_data:
                    hm_value = int(form_data[icao])
                    arpt.set_heatmap_index(hm_value)
                    debugging.debug(f"hmpost: key {icao} : value {hm_value}")

        self._airport_database.save_airport_db()

        flash("Heat Map Data applied")
        return redirect("hmedit")

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
            for count_index in range(len(self.airports), loc_numap):
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

            debugging.debug("FIXME: NEED TO PROCESS handle_appost_request")
            # self.writeairports(data, self.conf.get_string("filenames", "airports_file"))

            # self.readairports(self.conf.get_string("filenames", "airports_file"))

        # flash("Airports Successfully Saved")
        return redirect("apedit")

    # FIXME: Integrate into Class
    # @app.route("/ledonoff", methods=["GET", "POST"])
    def ledonoff(self):
        """Flask Route: /ledonoff."""
        debugging.info("Controlling LED's on/off")

        if request.method == "POST":
            if "buton" in request.form:
                num = int(request.form["lednum"])
                debugging.info("LED " + str(num) + " On")
                self._led_strip.set_led_color(num, Color(155, 155, 155))
                self._led_strip.show()
                flash("LED " + str(num) + " On")

            elif "butoff" in request.form:
                num = int(request.form["lednum"])
                debugging.info("LED " + str(num) + " Off")
                self._led_strip.set_led_color(num, Color(0, 0, 0))
                self._led_strip.show()
                flash("LED " + str(num) + " Off")

            elif "butup" in request.form:
                debugging.info("LED UP")
                num = int(request.form["lednum"])
                self._led_strip.set_led_color(num, Color(0, 0, 0))
                num = num + 1

                # FIXME: self.airports retired
                if num > len(self.airports):
                    num = len(self.airports)

                self._led_strip.set_led_color(num, Color(155, 155, 155))
                self._led_strip.show()
                flash("LED " + str(num) + " should be On")

            elif "butdown" in request.form:
                debugging.info("LED DOWN")
                num = int(request.form["lednum"])
                self._led_strip.set_led_color(num, Color(0, 0, 0))

                num = num - 1
                num = max(num, 0)

                self._led_strip.set_led_color(num, Color(155, 155, 155))
                self._led_strip.show()
                flash("LED " + str(num) + " should be On")

            elif "butall" in request.form:
                debugging.info("LED All ON")
                num = int(request.form["lednum"])

                # FIXME: self.airports retired
                for num in range(len(self.airports)):
                    self._led_strip.set_led_color(num, Color(155, 155, 155))
                self._led_strip.show()
                flash("All LEDs should be On")
                num = 0

            elif "butnone" in request.form:
                debugging.info("LED All OFF")
                num = int(request.form["lednum"])

                # FIXME: self.airports retired
                for num in range(len(self.airports)):
                    self._led_strip.set_led_color(num, Color(0, 0, 0))
                self._led_strip.show()
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

    # Routes for Config Editor
    # @app.route("/confedit", methods=["GET", "POST"])
    def confedit(self):
        """Flask Route: /confedit - Configuration Editor."""
        debugging.info("Opening confedit.html")

        # Pass data to html document
        template_data = self.standardtemplate_data()
        template_data["title"] = "Settings Editor"

        # FIXME: Needs a better way
        template_data["color_vfr_hex"] = self.conf.color("colors", "color_vfr")
        template_data["color_mvfr_hex"] = self.conf.color("colors", "color_mvfr")
        template_data["color_ifr_hex"] = self.conf.color("colors", "color_ifr")
        template_data["color_lifr_hex"] = self.conf.color("colors", "color_lifr")
        template_data["color_nowx_hex"] = self.conf.color("colors", "color_nowx")
        template_data["color_black_hex"] = self.conf.color("colors", "color_black")
        template_data["color_lghtn_hex"] = self.conf.color("colors", "color_lghtn")
        template_data["color_snow1_hex"] = self.conf.color("colors", "color_snow1")
        template_data["color_snow2_hex"] = self.conf.color("colors", "color_snow2")
        template_data["color_rain1_hex"] = self.conf.color("colors", "color_rain1")
        template_data["color_rain2_hex"] = self.conf.color("colors", "color_rain2")
        template_data["color_frrain1_hex"] = self.conf.color("colors", "color_frrain1")
        template_data["color_frrain2_hex"] = self.conf.color("colors", "color_frrain2")
        template_data["color_dustsandash1_hex"] = self.conf.color(
            "colors", "color_dustsandash1"
        )
        template_data["color_dustsandash2_hex"] = self.conf.color(
            "colors", "color_dustsandash2"
        )
        template_data["color_fog1_hex"] = self.conf.color("colors", "color_fog1")
        template_data["color_fog2_hex"] = self.conf.color("colors", "color_fog2")
        template_data["color_homeport_hex"] = self.conf.color(
            "colors", "color_homeport"
        )

        template_data["fade_color1_hex"] = self.conf.color("colors", "fade_color1")
        template_data["allsame_color1_hex"] = self.conf.color(
            "colors", "allsame_color1"
        )
        template_data["allsame_color2_hex"] = self.conf.color(
            "colors", "allsame_color2"
        )
        template_data["shuffle_color1_hex"] = self.conf.color(
            "colors", "shuffle_color1"
        )
        template_data["shuffle_color2_hex"] = self.conf.color(
            "colors", "shuffle_color2"
        )
        template_data["radar_color1_hex"] = self.conf.color("colors", "radar_color1")
        template_data["radar_color2_hex"] = self.conf.color("colors", "radar_color2")
        template_data["circle_color1_hex"] = self.conf.color("colors", "circle_color1")
        template_data["circle_color2_hex"] = self.conf.color("colors", "circle_color2")
        template_data["square_color1_hex"] = self.conf.color("colors", "square_color1")
        template_data["square_color2_hex"] = self.conf.color("colors", "square_color2")
        template_data["updn_color1_hex"] = self.conf.color("colors", "updn_color1")
        template_data["updn_color2_hex"] = self.conf.color("colors", "updn_color2")
        template_data["morse_color1_hex"] = self.conf.color("colors", "morse_color1")
        template_data["morse_color2_hex"] = self.conf.color("colors", "morse_color2")
        template_data["rabbit_color1_hex"] = self.conf.color("colors", "rabbit_color1")
        template_data["rabbit_color2_hex"] = self.conf.color("colors", "rabbit_color2")
        template_data["checker_color1_hex"] = self.conf.color(
            "colors", "checker_color1"
        )
        template_data["checker_color2_hex"] = self.conf.color(
            "colors", "checker_color2"
        )
        return render_template("confedit.html", **template_data)

    # @app.route("/cfpost", methods=["GET", "POST"])
    def cfedit_handler(self):
        """Flask Route: /cfpost ."""
        debugging.info("Processing Config Form")

        ipadd = self._sysdata.local_ip()

        if request.method == "POST":
            data = request.form.to_dict()
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
            flash("Settings Successfully Saved")

            url = request.referrer
            if url is None:
                url = "http://" + ipadd + ":5000/"
                # Use index if called from URL and not page.

            # temp = url.split("/")
            return redirect("/")
            # temp[3] holds name of page that called this route.
        return redirect("/")

    # FIXME: Integrate into Class
    # Routes for LSREMOTE - Allow Mobile Device Remote. Thank Lance
    # # @app.route('/', methods=["GET", "POST"])
    # @app.route('/confmobile', methods=["GET", "POST"])
    def confmobile(self):
        """Flask Route: /confmobile - Mobile Device API"""
        debugging.info("Opening lsremote.html")

        # ipadd = self._sysdata.local_ip()
        # current_timezone = self.conf.get_string("default", "timezone")
        # settings = self.conf.gen_settings_dict()
        # loc_timestr = utils.time_format(utils.current_time(self.conf))
        # loc_timestr_utc = utils.time_format(utils.current_time_utc(self.conf))

        # Pass data to html document
        template_data = self.standardtemplate_data()
        template_data["title"] = "Mobile Settings Editor"
        template_data["color_vfr_hex"] = self.conf.color("colors", "color_vfr")
        template_data["color_mvfr_hex"] = self.conf.color("colors", "color_mvfr")
        template_data["color_ifr_hex"] = self.conf.color("colors", "color_ifr")
        template_data["color_lifr_hex"] = self.conf.color("colors", "color_lifr")
        template_data["color_nowx_hex"] = self.conf.color("colors", "color_nowx")
        template_data["color_black_hex"] = self.conf.color("colors", "color_black")
        template_data["color_lghtn_hex"] = self.conf.color("colors", "color_lghtn")
        template_data["color_snow1_hex"] = self.conf.color("colors", "color_snow1")
        template_data["color_snow2_hex"] = self.conf.color("colors", "color_snow2")
        template_data["color_rain1_hex"] = self.conf.color("colors", "color_rain1")
        template_data["color_rain2_hex"] = self.conf.color("colors", "color_rain2")
        template_data["color_frrain1_hex"] = self.conf.color("colors", "color_frrain1")
        template_data["color_frrain2_hex"] = self.conf.color("colors", "color_frrain2")
        template_data["color_dustsandash1_hex"] = self.conf.color(
            "colors", "color_dustsandash1"
        )
        template_data["color_dustsandash2_hex"] = self.conf.color(
            "colors", "color_dustsandash2"
        )
        template_data["color_fog1_hex"] = self.conf.color("colors", "color_fog1")
        template_data["color_fog2_hex"] = self.conf.color("colors", "color_fog2")
        template_data["color_homeport_hex"] = self.conf.color(
            "colors", "color_homeport"
        )

        template_data["fade_color1_hex"] = self.conf.color("colors", "fade_color1")
        template_data["allsame_color1_hex"] = self.conf.color(
            "colors", "allsame_color1"
        )
        template_data["allsame_color2_hex"] = self.conf.color(
            "colors", "allsame_color2"
        )
        template_data["shuffle_color1_hex"] = self.conf.color(
            "colors", "shuffle_color1"
        )
        template_data["shuffle_color2_hex"] = self.conf.color(
            "colors", "shuffle_color2"
        )
        template_data["radar_color1_hex"] = self.conf.color("colors", "radar_color1")
        template_data["radar_color2_hex"] = self.conf.color("colors", "radar_color2")
        template_data["circle_color1_hex"] = self.conf.color("colors", "circle_color1")
        template_data["circle_color2_hex"] = self.conf.color("colors", "circle_color2")
        template_data["square_color1_hex"] = self.conf.color("colors", "square_color1")
        template_data["square_color2_hex"] = self.conf.color("colors", "square_color2")
        template_data["updn_color1_hex"] = self.conf.color("colors", "updn_color1")
        template_data["updn_color2_hex"] = self.conf.color("colors", "updn_color2")
        template_data["morse_color1_hex"] = self.conf.color("colors", "morse_color1")
        template_data["morse_color2_hex"] = self.conf.color("colors", "morse_color2")
        template_data["rabbit_color1_hex"] = self.conf.color("colors", "rabbit_color1")
        template_data["rabbit_color2_hex"] = self.conf.color("colors", "rabbit_color2")
        template_data["checker_color1_hex"] = self.conf.color(
            "colors", "checker_color1"
        )
        template_data["checker_color2_hex"] = self.conf.color(
            "colors", "checker_color2"
        )
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
                # settings[(key)] = val

        # debugging.dprint(settings)
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
    # def profiles(self):
    #    """Flask Route: /profiles - Load from Multiple Config Profiles"""
    #    config_profiles = {
    #        "b1": "config-basic.py",
    #        "b2": "config-basic2.py",
    #        "b3": "config-basic3.py",
    #        "a1": "config-advanced-1oled.py",
    #        "a2": "config-advanced-lcd.py",
    #        "a3": "config-advanced-8oledsrs.py",
    #        "a4": "config-advanced-lcdrs.py",
    #    }
    #
    #    req_profile = request.form["profile"]
    #    debugging.dprint(req_profile)
    #    debugging.dprint(self.config_profiles)
    #    tmp_profile = config_profiles[req_profile]
    #    stored_profile = "/NeoSectional/profiles/" + tmp_profile
    #
    #    flash(
    #        tmp_profile
    #        + "Profile Loaded. Review And Tweak The Settings As Desired. Must Be Saved!"
    #    )
    #    self.readconf(stored_profile)  # read profile config file
    #    debugging.info("Loading a Profile into Settings Editor")
    #    return redirect("confedit")

    # Route for Reboot of RPI
    def system_reboot(self):
        """Flask Route: /system_reboot - Request host reboot"""
        ipadd = self._sysdata.local_ip()
        url = request.referrer
        if url is None:
            url = "http://" + ipadd + ":5000/"
            # Use index if called from URL and not page.

        flash("Rebooting System")
        debugging.info("Rebooting Map from " + url)
        os.system("sudo shutdown -r now")
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # Route to turn off the map and displays
    # @app.route("/mapturnoff", methods=["GET", "POST"])
    def handle_mapturnoff(self):
        """Flask Route: /mapturnoff - Trigger process shutdown"""
        url = request.referrer
        debugging.info(f"Shutoff Map from {url}")
        self._led_strip.set_ledmode(LedMode.OFF)
        flash("Map Turned Off")
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # Route to turn off the map and displays
    # @app.route("/mapturnoff", methods=["GET", "POST"])
    def handle_mapturnon(self):
        """Flask Route: /mapturnon - Trigger process shutdown"""
        url = request.referrer
        debugging.info(f"Turn Map ON from {url}")
        self._led_strip.set_ledmode(LedMode.METAR)
        flash("Map Turned On")
        return redirect("/")
        # temp[3] holds name of page that called this route.

    # FIXME: Integrate into Class
    # Route to power down the RPI
    # @app.route("/shutoffnow1", methods=["GET", "POST"])
    def shutoffnow1(self):
        """Flask Route: /shutoffnow1 - Turn Off RPI"""
        url = request.referrer
        ipadd = self._sysdata.local_ip()
        if url is None:
            url = "http://" + ipadd + ":5000/"
            # Use index if called from URL and not page.

        # temp = url.split("/")
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
        ipadd = self._sysdata.local_ip()

        if url is None:
            url = "http://" + ipadd + ":5000/"
            # Use index if called from URL and not page.

        # temp = url.split("/")

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
        ipadd = self._sysdata.local_ip()
        if url is None:
            url = "http://" + ipadd + ":5000/"
            # Use index if called from URL and not page.

        # temp = url.split("/")
        if (self.conf.get_int("oled", "displayused") != 1) or (
            self.conf.get_int("oled", "oledused") != 1
        ):
            return redirect("/")
            # temp[3] holds name of page that called this route.

        # flash("Testing OLEDs ")
        debugging.info("Running testoled.py from " + url)
        # FIXME: Call update_oled equivalent functions
        # os.system('sudo python3 /NeoSectional/testoled.py')
        return redirect("/")
