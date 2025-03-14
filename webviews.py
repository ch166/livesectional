# -*- coding: utf-8 -*- #
"""Flask Module for WEB Interface."""

import time
import json
import secrets
import pytz

import folium
import folium.plugins
from folium.features import DivIcon

from flask import (
    Flask,
    render_template,
    request,
    Response,
    flash,
    redirect,
    send_file,
    url_for,
)


from werkzeug.utils import secure_filename


# from pyqrcode import QRCode
import qrcode

import utils
import utils_coord
import utils_mos
import utils_colors
import utils_certificates
import utils_system


# import conf
from update_leds import LedMode
import debugging
from utils_colors import wx_fog


# import sysinfo


class WebViews:
    """Class to contain all the Flask WEB functionality."""

    max_lat = 0
    min_lat = 0
    max_lon = 0
    min_lon = 0

    _clean_reboot_request = False

    _app_conf = None
    airports = []  # type: list[object]
    machines = []  # type: list[str]
    _zeroconf = None
    led_map_dict = {}  # type: dict
    _ledmodelist = [
        "METAR",
        "Off",
        "Test",
        "Rabbit",
        "Shuffle",
        "Rainbow",
        "Morse",
        "Radar",
        "TAF 1",
        "TAF 2",
        "TAF 3",
        "TAF 4",
        "MOS 1",
        "MOS 2",
        "MOS 3",
        "MOS 4",
    ]

    file_allowed_extensions = ["pem", "crt", "key"]

    def __init__(self, config, sysdata, airport_database, appinfo, led_mgmt, zeroconf):
        self._app_conf = config
        self._sysdata = sysdata
        self._airport_database = airport_database
        self._appinfo = appinfo
        self._zeroconf = zeroconf
        self._clean_reboot_request = False

        self.app = Flask(__name__)
        self.app.secret_key = secrets.token_hex(16)

        self.app.config["TEMPLATES_AUTO_RELOAD"] = True

        self.__http_port = self._app_conf.get_string("default", "http_port")
        self.ssl_enabled = False
        self.__ssl_cert = None
        self.__ssl_key = None
        self.__ssl_port = self.__http_port

        if self._app_conf.get_bool("default", "ssl_enabled"):
            # TODO: Add more error checking here rather than blindly assuming it works.
            self.ssl_enabled = True
            self.__ssl_cert = self._app_conf.get_string("default", "ssl_cert")
            self.__ssl_key = self._app_conf.get_string("default", "ssl_key")
            self.__ssl_port = self._app_conf.get_string("default", "ssl_port")

        self.app.add_url_rule("/", view_func=self.index, methods=["GET"])
        self.app.add_url_rule("/sysinfo", view_func=self.systeminfo, methods=["GET"])
        self.app.add_url_rule(
            "/oleddisplay", view_func=self.oled_display, methods=["GET"]
        )
        self.app.add_url_rule("/qrcode", view_func=self.gen_qrcode, methods=["GET"])
        self.app.add_url_rule(
            "/metar/<airport>", view_func=self.getmetar, methods=["GET"]
        )
        self.app.add_url_rule("/taf/<airport>", view_func=self.gettaf, methods=["GET"])
        self.app.add_url_rule("/wx/<airport>", view_func=self.getwx, methods=["GET"])
        self.app.add_url_rule(
            "/airport/<airport>", view_func=self.getairport, methods=["GET"]
        )
        self.app.add_url_rule("/tzset", view_func=self.tzset, methods=["GET", "POST"])
        self.app.add_url_rule("/wifi", view_func=self.wificonf, methods=["GET", "POST"])
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
        self.app.add_url_rule("/apedit", view_func=self.apedit, methods=["GET"])
        self.app.add_url_rule(
            "/appost", view_func=self.handle_appost_request, methods=["POST"]
        )
        self.app.add_url_rule(
            "/importap", view_func=self.importap, methods=["GET", "POST"]
        )
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
        self.app.add_url_rule(
            "/testled", view_func=self.handle_testled, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/check_updates", view_func=self.check_updates, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/perform_update", view_func=self.perform_updates, methods=["GET", "POST"]
        )
        self.app.add_url_rule(
            "/perform_restart", view_func=self.perform_restart, methods=["GET", "POST"]
        )

        self.app.add_url_rule(
            "/firstsetup", view_func=self.firstsetup_handler, methods=["GET", "POST"]
        )

        self.app.add_url_rule("/changelog", view_func=self.changelog, methods=["GET"])
        self.app.add_url_rule("/debug", view_func=self.debuginfo, methods=["GET"])

        self.app.add_url_rule(
            "/releaseinfo", view_func=self.releaseinfo, methods=["GET"]
        )

        self._led_strip = led_mgmt

        self.num = self._app_conf.get_int("default", "led_count")

    def check_auth(self, username, password):
        """Check if a username/password combination is valid."""
        adminuser = self._app_conf.cache["adminuser"]
        adminpass = self._app_conf.cache["adminpass"]
        if adminuser is not None and adminpass is not None:
            return username == adminuser and utils_system.match_password(
                password, adminpass
            )
        else:
            return False

    def authenticate(self):
        """Sends a 401 response that enables basic auth."""
        return Response(
            "Could not verify your access level for that URL.\n"
            "You have to login with proper credentials",
            401,
            {"WWW-Authenticate": 'Basic realm="Login Required"'},
        )

    def requires_auth(f):
        """Decorator to prompt for basic auth credentials."""

        def decorated(self, *args, **kwargs):
            auth = request.authorization
            if not auth or not self.check_auth(auth.username, auth.password):
                return self.authenticate()
            return f(self, *args, **kwargs)

        return decorated

    def run(self):
        """Run Flask Application.

        If debug is True, we need to make sure that auto-reload is disabled in threads
        """
        if self.ssl_enabled:
            context = (self.__ssl_cert, self.__ssl_key)
            active_port = self.__ssl_port
        else:
            context = None
            active_port = self.__http_port
        self.app.run(
            debug=False, host="0.0.0.0", ssl_context=context, port=active_port
        )  # nosec

    def standardtemplate_data(self):
        """Generate a standardized template_data."""
        # For performance reasons we should do the minimum of data generation now
        # This gets executed for every page load
        if self._zeroconf is not None:
            self.machines = self._zeroconf.get_neighbors()
        airport_dict_data = {}

        for (
            airport_icao,
            airport_obj,
        ) in self._airport_database.get_airport_dict_led().items():
            airport_record = {
                "ledindex": airport_obj.get_led_index(),
                "active": airport_obj.active(),
                "icaocode": airport_icao,
                "metarsrc": airport_obj.wxsrc(),
                "rawmetar": airport_obj.raw_metar(),
                "purpose": airport_obj.purpose(),
                "hmindex": airport_obj.heatmap_index(),
            }
            airport_dict_data[airport_icao] = airport_record

        current_ledmode = self._led_strip.ledmode()
        fresh_daily = utils_system.fresh_daily(self._app_conf)
        cpu_usage, mem_usage = self._sysdata.system_load()

        template_data = {
            "title": "NOT SET - " + self._appinfo.running_version(),
            "airports": airport_dict_data,
            "cpu_usage": cpu_usage,
            "mem_usage": mem_usage,
            "settings": self._app_conf.gen_settings_dict(),
            "ipadd": self._sysdata.local_ip(),
            "strip": self._led_strip,
            "timestr": utils.time_format(utils.current_time(self._app_conf)),
            "timestrutc": utils.time_format(utils.current_time_utc(self._app_conf)),
            "timemetarage": utils.time_format(
                self._airport_database.get_metar_update_time()
            ),
            "current_timezone": self._app_conf.get_string("default", "timezone"),
            "current_ledmode": current_ledmode,
            "num": self.num,
            "version": self._appinfo.running_version(),
            "update_available": self._appinfo.update_available(),
            "restart_to_upgrade": self._appinfo.update_ready(),
            "update_vers": self._appinfo.available_version(),
            "current_version": self._appinfo.current_version(),
            "machines": self.machines,
            "sysinfo": self._sysdata.query_system_information(),
            "fresh_daily": fresh_daily,
        }
        return template_data

    def firstsetup_handler(self):
        """Flask Route: /firstsetup - Upload HeatMap Data."""
        debugging.info("Processing initial data setup")

        admin_user = None
        admin_pass = None

        if (request.method == "POST") and not (
            self._app_conf.cache["first_setup_complete"]
        ):
            form_data = request.form
            if "adminuser" in form_data:
                admin_user = form_data["adminuser"]
            if "adminpass" in form_data:
                admin_pass = form_data["adminpass"]

            if (admin_user is not None) and (admin_pass is not None):
                self._app_conf.set_string("default", "adminuser", admin_user)
                self._app_conf.set_string(
                    "default", "adminpass", utils_system.encrypt_password(admin_pass)
                )

            if "use_proxies" in form_data:
                self._app_conf.set_bool("urls", "use_proxies", True)
                if "http_proxy" in form_data:
                    self._app_conf.set_string(
                        "urls", "http_proxy", form_data["http_proxy"]
                    )
                if "https_proxy" in form_data:
                    self._app_conf.set_string(
                        "urls", "https_proxy", form_data["https_proxy"]
                    )
            else:
                self._app_conf.set_string("urls", "use_proxies", False)
                self._app_conf.set_string("urls", "http_proxy", "")
                self._app_conf.set_string("urls", "htts_proxy", "")

            if "setup_enable_ssl" in form_data:
                self._app_conf.set_bool("default", "ssl_enabled", True)
                debugging.info("Setting SSL to True")

                if "https_cert" in request.files:
                    cert_file = request.files["https_cert"]
                    debugging.info(
                        f"File Upload: {cert_file.name} /type: {cert_file.content_type} /fname: {cert_file.filename} /length: {cert_file.content_length}"
                    )
                    cert_file.save("/tmp/https_cert.pem")
                    if utils_certificates.check_certificate("/tmp/https_cert.pem"):
                        debugging.info("Cert checks out")
                if "https_key" in request.files:
                    https_key = request.files["https_key"]
                    debugging.info(
                        f"File Upload: {https_key.name} /type: {https_key.content_type} /fname: {https_key.filename} /length: {https_key.content_length}"
                    )
                    https_key.save("/tmp/https_cert.key")
                    if utils_certificates.check_certificate("/tmp/https_cert.key"):
                        debugging.info("Key checks out")
            else:
                self._app_conf.set_string("urls", "ssl_enabled", False)

            self._app_conf.set_bool("default", "first_setup_complete", True)
            self._app_conf.save_config()

            flash("First Setup Complete")

        return redirect("/")

    def changelog(self):
        """Flask Route: /changelog - Display System Info."""
        self._sysdata.refresh()
        changelog = utils.read_file(self._app_conf.get_string("filenames", "changelog"))
        template_data = self.standardtemplate_data()
        template_data["title"] = "Change Log"
        template_data["showfile"] = changelog
        debugging.info("Opening System Information page")
        return render_template("showfile.html", **template_data)

    def releaseinfo(self):
        """Flask Route: /releaseinfo - Display System Info."""
        self._sysdata.refresh()
        releasenotes = utils.read_file(
            self._app_conf.get_string("filenames", "release_notes")
        )
        template_data = self.standardtemplate_data()
        template_data["title"] = "Release Notes"
        template_data["showfile"] = releasenotes
        debugging.info("Opening System Information page")
        return render_template("showfile.html", **template_data)

    @requires_auth
    def systeminfo(self):
        """Flask Route: /sysinfo - Display System Info."""
        self._sysdata.refresh()
        template_data = self.standardtemplate_data()
        template_data["title"] = "SysInfo"
        debugging.info("Opening System Information page")
        return render_template("sysinfo.html", **template_data)

    def debuginfo(self):
        """Flask Route: /sysinfo - Display System Info."""
        self._sysdata.refresh()
        template_data = self.standardtemplate_data()

        debug_output = "Selections of useful internal debug info"

        debug_output += "=-=-=-=-=-=-=-=-=-=-=-=-\n"
        debug_output += debugging.internal_debug()
        debug_output = "=-=-=-=-=-=-=-=-=-=-=-=-\n"
        debug_output += f"{self._app_conf.cache}\n"

        template_data["title"] = "Debugging Data"
        template_data["showfile"] = debug_output
        debugging.info("Displaying Debugging Info")
        return render_template("showfile.html", **template_data)

    def oled_display(self):
        """Flask Route: /oleddisplay - Display System Info."""
        self._sysdata.refresh()
        template_data = self.standardtemplate_data()
        template_data["title"] = "OLED Display"
        debugging.info("Opening OLED Display page")
        return render_template("oled.html", **template_data)

    def tzset(self):
        """Flask Route: /tzset - Display and Set Timezone Information."""
        if request.method == "POST":
            timezone = request.form["tzselected"]
            flash("Timezone set to " + timezone)
            debugging.info("Request to update timezone to: " + timezone)
            self._app_conf.set_string("default", "timezone", timezone)
            self._app_conf.save_config()
            return redirect("tzset")

        tzlist = pytz.common_timezones
        current_timezone = self._app_conf.get_string("default", "timezone")
        template_data = self.standardtemplate_data()
        template_data["title"] = "TZset"
        template_data["tzoptionlist"] = tzlist
        template_data["current_timezone"] = current_timezone
        debugging.info("Opening Time Zone Set page")
        return render_template("tzset.html", **template_data)

    def wificonf(self):
        """Flask Route: /wifi - Display and Set WiFi Information."""
        if request.method == "POST":
            req_wifi_ssid = request.form["ssid_selected"]
            req_wifi_pass = request.form["ssid_password"]
            flash(f"Changing WiFi to {req_wifi_ssid}")
            utils_system.rpi_config_wifi(req_wifi_ssid, req_wifi_pass)
            return redirect("/wifi")

        current_ssid, ssidlist = utils_system.wifi_list_ssid()
        template_data = self.standardtemplate_data()
        template_data["title"] = "WiFiConf"
        template_data["ssidlist"] = ssidlist
        template_data["current_ssid"] = current_ssid
        debugging.info("Opening WiFi Conf page")
        return render_template("wifi.html", **template_data)

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
            if newledmode_upper == "RADAR":
                self._led_strip.set_ledmode(LedMode.RADARWIPE)
            if newledmode_upper == "TAF 1":
                self._led_strip.set_ledmode(LedMode.TAF_1)
            if newledmode_upper == "TAF 2":
                self._led_strip.set_ledmode(LedMode.TAF_2)
            if newledmode_upper == "TAF 3":
                self._led_strip.set_ledmode(LedMode.TAF_3)
            if newledmode_upper == "TAF 4":
                self._led_strip.set_ledmode(LedMode.TAF_4)
            if newledmode_upper == "MORSE":
                self._led_strip.set_ledmode(LedMode.MORSE)
            if newledmode_upper == "MOS 1":
                self._led_strip.set_ledmode(LedMode.MOS_1)
            if newledmode_upper == "MOS 2":
                self._led_strip.set_ledmode(LedMode.MOS_2)
            if newledmode_upper == "MOS 3":
                self._led_strip.set_ledmode(LedMode.MOS_3)
            if newledmode_upper == "MOS 4":
                self._led_strip.set_ledmode(LedMode.MOS_4)

            flash(f"LED Mode set to {newledmode}")
            debugging.info(f"LEDMode set to {newledmode}")
            return redirect("ledmodeset")

        current_ledmode = self._led_strip.ledmode()

        template_data = self.standardtemplate_data()
        template_data["title"] = "LEDModeSet"
        template_data["ledoptionlist"] = self._ledmodelist
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
        loc_timestr = utils.time_format(utils.current_time(self._app_conf))
        loc_timestr_utc = utils.time_format(utils.current_time_utc(self._app_conf))
        with open(
            "/opt/NeoSectional/data/console_ip.txt", "r", encoding="utf-8"
        ) as file:
            for line in file.readlines()[-1:]:
                line = line.rstrip()
                console_ips.append(line)
        ipadd = self._sysdata.local_ip()
        console_ips.append(ipadd)
        debugging.info("Opening open_console in separate window")
        return render_template(
            "open_console.html",
            urls=console_ips,
            title="Display Console Output-" + self._appinfo.running_version(),
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
        loc_timestr = utils.time_format(utils.current_time(self._app_conf))
        loc_timestr_utc = utils.time_format(utils.current_time_utc(self._app_conf))
        ipadd = self._sysdata.local_ip()
        debugging.info("Opening stream_log in separate window")
        return render_template(
            "stream_log.html",
            title="Display Logfile-" + self._appinfo.running_version(),
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
            # FIXME: Move logfile name to config file
            with open("/opt/NeoSectional/logs/debugging.log", encoding="utf-8") as file:
                while True:
                    yield "{}\n".format(file.read())
                    time.sleep(1)

        return self.app.response_class(generate(), mimetype="text/plain")

    # Route to display map's airports on a digital map.
    # @app.route('/led_map', methods=["GET", "POST"])
    def led_map(self):
        """Flask Route: /led_map - Display LED Map with existing airports."""
        # Update Airport Boundary data based on set of airports
        self.max_lon, self.min_lon, self.max_lat, self.min_lat = (
            utils_coord.airport_boundary_calc(self._airport_database)
        )

        debugging.debug(
            f"Coordinates LON:{self.max_lon}/{self.min_lon}/ LAT:{self.max_lat}/{self.min_lat}/"
        )

        # FIXME: This needs to exit if we don't have proper location data loaded.

        points = []
        title_coords = (self.max_lat, (float(self.max_lon) + float(self.min_lon)) / 2)
        start_center_coord = (
            (float(self.max_lat) + float(self.min_lat)) / 2,
            (float(self.max_lon) + float(self.min_lon)) / 2,
        )
        # Initialize Map
        folium_map = folium.Map(
            location=start_center_coord,
            zoom_start=8,
            height="100%",
            width="100%",
            control_scale=True,
            zoom_control=True,
            tiles="OpenStreetMap",
            attr="OpenStreetMap",
        )
        # Place map within bounds of screen
        # This will override the zoom_start; which possibly prevents the sectional chart from displaying
        folium_map.fit_bounds(
            [[self.min_lat - 1, self.min_lon - 1], [self.max_lat + 1, self.max_lon + 1]]
        )
        # Set Marker Color by Flight Category
        airports = self._airport_database.get_airport_dict_led()
        for icao, airport_obj in airports.items():
            if not airport_obj.active():
                debugging.info(f"LED MAP: Skipping rendering inactive {icao}")
                continue
            if not airport_obj.valid_coordinates():
                debugging.info(
                    f"LED MAP: Skipping rendering {icao} invalid coordinates"
                )
                continue
            debugging.debug(f"LED MAP: Rendering {icao}")
            loc_color = utils_colors.flightcategory_color(
                self._app_conf, airport_obj.flightcategory()
            )

            # FIXME - Move URL to config file
            # https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId=kpae
            pop_url = f'<a href="https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId={icao} target="_blank">'
            wx_cond = airport_obj.wxconditions_str()
            wx_cond_str = None
            if len(wx_cond) > 0:
                wx_cond_str = f"<li>WX cond:{wx_cond}</li>"
            popup = f"<ul><li>{icao}</li><li><font color={loc_color}>{airport_obj.flightcategory()}</font></li>{wx_cond_str}</ul>"

            # Add airport markers with proper color to denote flight category
            folium.CircleMarker(
                radius=7,
                fill=True,
                color=loc_color,
                location=[airport_obj.latitude(), airport_obj.longitude()],
                popup=popup,
                # tooltip=f"{str(icao)}<br>led:{str(airport_obj.get_led_index())}",
                weight=6,
            ).add_to(folium_map)

            # Add lines between airports. Must make lat/lons
            # floats otherwise recursion error occurs.
            pin_index = int(airport_obj.get_led_index())
            # debugging.info(f"icao {icao} Lat:{airport_obj.latitude()}/Lon:{airport_obj.longitude()}")
            points.insert(pin_index, [airport_obj.latitude(), airport_obj.longitude()])

        folium.PolyLine(
            points, color="grey", weight=2.5, opacity=1, dash_array="2"
        ).add_to(folium_map)

        # Add Title to the top of the map
        map_icon = DivIcon(
            icon_size=(500, 36),
            icon_anchor=(150, 64),
            html='<div style="font-size: 24pt"><b>LiveSectional Map Layout</b></div>',
        )

        folium.map.Marker(
            location=title_coords,
            icon=map_icon,
        ).add_to(folium_map)

        # Extra features to add if desired
        folium_map.add_child(folium.LatLngPopup())
        # Terminator plugin adds overlay showing daylight/nighttime
        # folium.plugins.Terminator().add_to(folium_map)

        #    folium_map.add_child(folium.ClickForMarker(popup='Marker'))
        folium.plugins.Geocoder().add_to(folium_map)

        folium.plugins.Fullscreen(
            position="topright",
            title="Full Screen",
            title_cancel="Exit Full Screen",
            force_separate_button=True,
        ).add_to(folium_map)

        folium.TileLayer(
            "https://tiles.arcgis.com/tiles/ssFJjBXIUyZDrSYZ/arcgis/rest/services/VFR_Sectional/MapServer/WMTS/tile/1.0.0/VFR_Sectional/default/default028mm/{z}/{y}/{x}",
            attr="FAA Sectional",
            name="FAA ArcGIS Sectional",
            overlay=True,
        ).add_to(folium_map)
        folium.TileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
        ).add_to(folium_map)
        folium.TileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012",
        ).add_to(folium_map)

        folium.LayerControl().add_to(folium_map)

        # FIXME: Move filename to config.ini
        folium_map.save("/opt/NeoSectional/static/led_map.html")
        debugging.debug("Opening led_map in separate window")

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

        points = []

        self.max_lon, self.min_lon, self.max_lat, self.min_lat = (
            utils_coord.airport_boundary_calc(self._airport_database)
        )

        title_coords = (self.max_lat, (float(self.max_lon) + float(self.min_lon)) / 2)
        start_coords = (
            (float(self.max_lat) + float(self.min_lat)) / 2,
            (float(self.max_lon) + float(self.min_lon)) / 2,
        )

        # Initialize Map
        folium_map = folium.Map(
            location=start_coords,
            zoom_start=8,
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
        for icao, airport_obj in airports.items():
            if not airport_obj.active():
                continue
            if not airport_obj.valid_coordinates():
                debugging.info(
                    f"LED MAP: Skipping rendering {icao} invalid coordinates"
                )
                continue
            loc_color = utils_colors.flightcategory_color(
                self._app_conf, airport_obj.flightcategory()
            )

            # Get pin to display in popup
            heatmap_scale = airport_obj.heatmap_index()
            if heatmap_scale == 0:
                heatmap_radius = 10
            else:
                heatmap_radius = 10 + heatmap_scale / 100 * 30

            # FIXME - Move URL to config file
            pop_url = f'<a href="https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId={icao}target="_blank">'
            popup = (
                f"{pop_url}{icao}</a><br>[{airport_obj.latitude()},{airport_obj.longitude()}]<br>{airport_obj.flightcategory()}"
                f"<br>LED&nbsp;=&nbsp;{airport_obj.get_led_index()}<br><b>"
                f"<font size=+2 color={loc_color}>{loc_color}</font></b>"
            )

            # Add airport markers with proper color to denote flight category
            folium.CircleMarker(
                radius=heatmap_radius,
                fill=True,
                color=loc_color,
                location=[airport_obj.latitude(), airport_obj.longitude()],
                popup=popup,
                tooltip=f"{str(icao)}<br>{str(heatmap_radius)}%",
                weight=4,
            ).add_to(folium_map)

            pin_index = int(airport_obj.get_led_index())
            debugging.info(
                f"HeatMap: {airport_obj.icao_code()} :{airport_obj.latitude()}:{airport_obj.longitude()}:{pin_index}:"
            )
            points.insert(pin_index, [airport_obj.latitude(), airport_obj.longitude()])

        # debugging.info(points)
        # No polyline on HeatMap
        # folium.PolyLine(points, color="grey", weight=2.5, opacity=1, dash_array="10").add_to(folium_map)

        title_icon = DivIcon(
            icon_size=(500, 36),
            icon_anchor=(150, 64),
            html='<div style="font-size: 24pt"><b>LiveSectional HeatMap Layout</b></div>',
        )

        # Add Title to the top of the map
        folium.map.Marker(
            title_coords,
            icon=title_icon,
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
        # folium.TileLayer(
        #    "https://wms.chartbundle.com/tms/1.0.0/sec/{z}/{x}/{y}.png?origin=nw",
        #    attr="chartbundle.com",
        #    name="ChartBundle Sectional",
        # ).add_to(folium_map)
        folium.TileLayer(
            "Stamen Terrain", name="Stamen Terrain", attr="stamen.com"
        ).add_to(folium_map)
        folium.TileLayer(
            "CartoDB positron", name="CartoDB Positron", attr="charto.com"
        ).add_to(folium_map)

        folium.LayerControl().add_to(folium_map)

        # FIXME: Move filename to config.ini
        folium_map.save("/opt/NeoSectional/static/heat_map.html")
        debugging.info("Opening led_map in separate window")

        template_data = self.standardtemplate_data()
        template_data["title"] = "HEATmap"
        template_data["led_map_dict"] = self.led_map_dict
        template_data["max_lat"] = self.max_lat
        template_data["min_lat"] = self.min_lat
        template_data["max_lon"] = self.max_lon
        template_data["min_lon"] = self.min_lon

        return render_template("heat_map.html", **template_data)

    def gen_qrcode(self):
        """Flask Route: /qrcode - Generate QRcode for site URL."""
        # Generates qrcode that maps to the mobileconfedit version of
        # the configuration generator
        template_data = self.standardtemplate_data()

        ipadd = self._sysdata.local_ip()
        # FIXME: Needs to use properly generated http url/port
        qraddress = f"https://{ipadd.strip()}:8443/confmobile"
        debugging.info("Opening qrcode in separate window")
        qrcode_file = self._app_conf.get_string("filenames", "qrcode")
        qrcode_url = self._app_conf.get_string("filenames", "qrcode_url")

        qr_img = qrcode.QRCode(
            version=5,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=20,
            border=4,
        )
        qr_img.add_data(qraddress)
        qr_img.make(fit=True)
        img = qr_img.make_image(fill_color="black", back_color="white")
        img.save(qrcode_file)

        return render_template(
            "qrcode.html", qraddress=qraddress, qrimage=qrcode_url, **template_data
        )

    def getwx(self, airport):
        """Flask Route: /wx - Get WX JSON for Airport."""
        template_data = self.standardtemplate_data()

        # debugging.info(f"getwx: airport = {airport}")
        wx_data = {}

        airport = airport.lower()
        template_data["airport"] = airport

        if airport == "debug":
            # Debug request - dumping DB info
            with open("logs/airport_database.txt", "w", encoding="ascii") as outfile:
                airportdb = self._airport_database.get_airportdb()
                counter = 0
                for icao, airport_obj in airportdb.items():
                    airport_metar = airport_obj.raw_metar()
                    flight_category = airport_obj.flightcategory()
                    outfile.write(f"{icao}::{airport_metar}::{flight_category}:\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
            wx_data = {
                "airport": "Debugging Request",
                "metar": "",
                "flightcategory": "DB DUMPED",
            }
            return json.dumps(wx_data)
        try:
            airport_obj = self._airport_database.get_airport(airport)
            airport_taf = self._airport_database.get_airport_taf(airport)
            wx_data = self.airport_datadump(airport_obj)
        except Exception as err:
            debugging.error(f"Attempt to get wx for failed for :{airport}: ERR:{err}")

        return json.dumps(wx_data)

    def airport_datadump(self, airport_obj):
        """Generate dict of useful airport data."""
        dbdump = {
            "airport": "Default Value",
            "metar": "",
            "flightcategory": "UNKN",
            "latitude": "Not Set",
            "longitude": "Not Set",
            "get_wx_dir_degrees": "Not Set",
            "get_wx_windspeed": "Not Set",
            "taf": "No TAF Set",
            "mos_1hr": "No MOS 1hr set",
            "mos_8hr": "No MOS 8hr set",
            "wxsrc": "wxsrc Not Set",
            "best_runway": "best runway NotSet",
            "heatmap_index": "heatmap_index NotSet",
        }
        dbdump["metar"] = airport_obj.raw_metar()
        dbdump["airport"] = airport_obj.icao_code()
        dbdump["flightcategory"] = airport_obj.flightcategory()
        dbdump["latitude"] = airport_obj.latitude()
        dbdump["longitude"] = airport_obj.longitude()
        dbdump["get_wx_dir_degrees"] = airport_obj.winddir_degrees()
        dbdump["get_wx_windspeed"] = airport_obj.wx_windspeed()
        # html_response["taf"] = airport_taf
        dbdump["mos_1hr"] = utils_mos.get_mos_weather(
            airport_obj.get_full_mos_forecast(), self._app_conf, 1
        )
        dbdump["mos_8hr"] = utils_mos.get_mos_weather(
            airport_obj.get_full_mos_forecast(), self._app_conf, 8
        )
        dbdump["wxsrc"] = airport_obj.wxsrc()
        dbdump["heatmap_index"] = airport_obj.heatmap_index()
        dbdump["best_runway"] = airport_obj.best_runway()
        dbdump["runway_dataset"] = airport_obj.runway_data()
        return dbdump

    def getairport(self, airport):
        """Flask Route: /airport - Get WX JSON for Airport - primarily for debugging the details of the what's in the Airport"""
        template_data = self.standardtemplate_data()

        html_response = {}

        debugging.info(f"getairport: airport = {airport}")
        airport = airport.lower()
        template_data["airport"] = airport

        if airport == "debug":
            # Debug request - dumping DB info
            with open("logs/airport_database.txt", "w", encoding="ascii") as outfile:
                airportdb = self._airport_database.get_airportdb()
                counter = 0
                for icao, airport_obj in airportdb.items():
                    if not airport_obj.active():
                        continue
                    dbdump = self.airport_datadump(airport_obj)
                    outfile.write(f"{dbdump}\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
            html_response = {
                "airport": "Debugging Request",
                "metar": "",
                "flightcategory": "DB DUMPED",
            }
            return json.dumps(html_response)
        try:
            airport_obj = self._airport_database.get_airport(airport)
            airport_taf = self._airport_database.get_airport_taf(airport)
            html_response = self.airport_datadump(airport_obj)
        except Exception as err:
            debugging.error(f"Attempt to get wx for failed for :{airport}: ERR:{err}")

        return json.dumps(html_response)

    def getmetar(self, airport):
        """Flask Route: /metar - Get METAR for Airport."""
        template_data = self.standardtemplate_data()

        debugging.info(f"getmetar: airport = :{airport}:")
        template_data["airport"] = airport

        airport = airport.lower()

        if airport == "debug":
            # Debug request - dumping DB info
            debugging.info("getmetar: writing airport debug data")
            with open("logs/airport_database.txt", "w", encoding="ascii") as outfile:
                airportdb = self._airport_database.get_airportdb()
                counter = 0
                for icao, airport_obj in airportdb.items():
                    airport_metar = airport_obj.raw_metar()
                    airport_icao = airport_obj.icao_code()
                    outfile.write(f"{icao}: {airport_metar} / {airport_icao} :\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
        else:
            try:
                debugging.info("Get Metar 1")
                airport_obj = self._airport_database.get_airport(airport)
                debugging.info(f"Get Metar 2: {airport_obj.raw_metar()}")
                # debugging.info(airport_entry)
                template_data["metar"] = airport_obj.raw_metar()
            except Exception as err:
                debugging.error(
                    f"Attempt to get metar for failed for :{airport}: ERR:{err}"
                )
                template_data["metar"] = "ERR - Not found"

        return render_template("metar.html", **template_data)

    def gettaf(self, airport):
        """Flask Route: /taf - Get TAF for Airport."""
        template_data = self.standardtemplate_data()

        debugging.info(f"gettaf: airport = {airport}")
        template_data["airport"] = airport

        airport = airport.lower()

        if airport == "debug":
            # Debug request - dumping DB info
            with open(
                "logs/airport_database_taf.txt", "w", encoding="ascii"
            ) as outfile:
                airportdb = self._airport_database.get_airport_xmldb()
                counter = 0
                for icao, airport_obj in airportdb.items():
                    airport_metar = airport_obj.raw_metar()
                    outfile.write(f"{icao}: {airport_metar} :\n")
                    counter = counter + 1
                outfile.write(f"stats: {counter}\n")
        try:
            airport_taf_dict = self._airport_database.get_airport_taf(airport)
            debugging.info(f"{airport}:taf:{airport_taf_dict}")
            airport_taf_future = self._airport_database.airport_taf_future(airport, 5)
            debugging.info(f"{airport}:forecast:{airport_taf_future}")
            template_data["taf"] = airport_taf_future
        except Exception as err:
            debugging.error(f"Attempt to get TAF for :{airport}: ERR:{err}")
            template_data["taf"] = "ERR - Not found"

        return render_template("taf.html", **template_data)

    # @app.route('/', methods=["GET", "POST"])
    # @app.route('/intro', methods=["GET", "POST"])
    def index(self):
        """Flask Route: / and /index - Homepage."""
        template_data = self.standardtemplate_data()
        template_data["title"] = "Intro"

        # Check for initial setup state
        if not self._app_conf.cache["first_setup_complete"]:
            template_data["title"] = "First Time Setup"
            return render_template("initial_setup.html", **template_data)

        # System Reboot call will update the flag and redirect to here.
        # Should leave the end user with a clean URL
        if self._clean_reboot_request:
            self._clean_reboot_request = False  # Just in case the reboot request fails
            utils_system.system_reboot()

        # flash(machines) # Debug
        debugging.info("Opening Home Page/Intro")
        return render_template("intro.html", **template_data)

    # Routes to download airports, logfile.log and config.py to local computer
    # @app.route('/download_ap', methods=["GET", "POST"])
    def downloadairports(self):
        """Flask Route: /download_ap - Export airports file."""
        debugging.info("Downloaded Airport File")
        path = self._app_conf.get_string("filenames", "airports_json")
        return send_file(path, as_attachment=True)

    # @app.route('/download_cf', methods=["GET", "POST"])
    def downloadconfig(self):
        """Flask Route: /download_cf - Export configuration file."""
        debugging.info("Downloaded Config File")
        path = self._app_conf.get_string("filenames", "config_file")
        return send_file(path, as_attachment=True)

    # @app.route('/download_log', methods=["GET", "POST"])
    def downloadlog(self):
        """Flask Route: /download_log - Export log file."""
        debugging.info("Downloaded Logfile")
        path = self._app_conf.get_string("filenames", "log_file")
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
            for icao, airport_obj in airports.items():
                if not airport_obj.active():
                    continue
                if icao in form_data:
                    hm_value = int(form_data[icao])
                    airport_obj.set_heatmap_index(hm_value)
                    debugging.debug(f"hmpost: key {icao} : value {hm_value}")

        self._airport_database.save_airport_db()

        flash("Heat Map Data applied")
        return redirect("hmedit")

    # Routes for Airport Editor
    # @app.route("/apedit", methods=["GET", "POST"])
    def apedit(self):
        """Flask Route: /apedit - Airport Editor."""
        debugging.info("Opening apedit.html")

        # self.readairports(self._app_conf.get_string("filenames", "airports_file"))
        template_data = self.standardtemplate_data()
        template_data["title"] = "Airports Editor"
        return render_template("apedit.html", **template_data)

    # FIXME: Integrate into Class
    # @app.route("/numap", methods=["GET", "POST"])
    def numap(self):
        """Flask Route: /numap."""
        debugging.info("Updating Number of airports in airport file")

        loc_numap = 0

        if request.method == "POST":
            loc_numap = int(request.form["numofap"])
            debugging.dprint(loc_numap)

        # self.readairports(self._app_conf.get_string("filenames", "airports_file"))

        # FIXME: self.airports is retired
        newnum = loc_numap - int(len(self.airports))
        if newnum < 0:
            self.airports = self.airports[:newnum]
        else:
            for dummy in range(len(self.airports), loc_numap):
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

        airport_data = {}
        purpose_data = {}
        metarsrc_data = {}

        if request.method == "POST":
            data = request.form.to_dict()
            for field_label, field_data in data.items():
                field_function, led_id = field_label.split("/")
                if field_function == "airport":
                    airport_data[led_id] = field_data
                if field_function == "purpose":
                    purpose_data[led_id] = field_data
                if field_function == "metarsrc":
                    metarsrc_data[led_id] = field_data

            debugging.info(f"Airport Data: {airport_data}")
            debugging.info(f"Purpose Data: {purpose_data}")
            debugging.info(f"Metarsrc Data: {metarsrc_data}")

            self._airport_database.airport_dict_from_webform(
                airport_data, purpose_data, metarsrc_data
            )
            self._airport_database.save_airport_db()

        return redirect("apedit")

    # FIXME: Integrate into Class
    # Import a file to populate airports. Must Save self.airports to keep
    # @app.route("/importap", methods=["GET", "POST"])
    def importap(self):
        """Flask Route: /importap - Import airports File."""
        debugging.info("Importing airports File")

        if "file" not in request.files:
            flash("Import Airports - No File Selected")
            return redirect("./apedit")

        file = request.files["file"]

        if file.filename == "":
            flash("Import Airports - No Filename found")
            return redirect("./apedit")

        filedata = file.read()
        fdata = bytes.decode(filedata)
        try:
            new_airports = json.loads(fdata)
        except json.decoder.JSONDecodeError as err:
            debugging.error(f"Import Airports JSON decode error - {err}")
            flash(f"Import Airports - JSON Decode Error {err}")

        debugging.info(f"Airports File: {fdata}")

        # TODO: Would be good to parse the data and do some sanity checking rather than lobbing
        # it to the json importer without any validation.

        new_airports = json.loads(fdata)

        # TODO: if validation tests pass
        if "airports" in new_airports:
            self._airport_database.airport_dict_from_json(new_airports)
        else:
            debugging.info("Airports File: no airports key")
        # TODO: create a template for an import error page, and present that instead.

        template_data = self.standardtemplate_data()
        template_data["title"] = "Airports Editor"

        flash("Airport data imported")
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
        template_data["color_vfr_hex"] = self._app_conf.color("color_vfr")
        template_data["color_mvfr_hex"] = self._app_conf.color("color_mvfr")
        template_data["color_ifr_hex"] = self._app_conf.color("color_ifr")
        template_data["color_lifr_hex"] = self._app_conf.color("color_lifr")
        template_data["color_nowx_hex"] = self._app_conf.color("color_nowx")
        template_data["color_black_hex"] = self._app_conf.color("color_black")
        template_data["color_lghtn_hex"] = self._app_conf.color("color_lghtn")
        template_data["color_snow1_hex"] = self._app_conf.color("color_snow1")
        template_data["color_snow2_hex"] = self._app_conf.color("color_snow2")
        template_data["color_rain1_hex"] = self._app_conf.color("color_rain1")
        template_data["color_rain2_hex"] = self._app_conf.color("color_rain2")
        template_data["color_frrain1_hex"] = self._app_conf.color("color_frrain1")
        template_data["color_frrain2_hex"] = self._app_conf.color("color_frrain2")
        template_data["color_dustsandash1_hex"] = self._app_conf.color(
            "color_dustsandash1"
        )
        template_data["color_dustsandash2_hex"] = self._app_conf.color(
            "color_dustsandash2"
        )
        template_data["color_fog1_hex"] = self._app_conf.color("color_fog1")
        template_data["color_fog2_hex"] = self._app_conf.color("color_fog2")
        template_data["color_homeport_hex"] = self._app_conf.color("color_homeport")

        template_data["fade_color1_hex"] = self._app_conf.color("fade_color1")
        template_data["allsame_color1_hex"] = self._app_conf.color("allsame_color1")
        template_data["allsame_color2_hex"] = self._app_conf.color("allsame_color2")
        template_data["shuffle_color1_hex"] = self._app_conf.color("shuffle_color1")
        template_data["shuffle_color2_hex"] = self._app_conf.color("shuffle_color2")
        template_data["radar_color1_hex"] = self._app_conf.color("radar_color1")
        template_data["radar_color2_hex"] = self._app_conf.color("radar_color2")
        template_data["circle_color1_hex"] = self._app_conf.color("circle_color1")
        template_data["circle_color2_hex"] = self._app_conf.color("circle_color2")
        template_data["square_color1_hex"] = self._app_conf.color("square_color1")
        template_data["square_color2_hex"] = self._app_conf.color("square_color2")
        template_data["updn_color1_hex"] = self._app_conf.color("updn_color1")
        template_data["updn_color2_hex"] = self._app_conf.color("updn_color2")
        # template_data["morse_color1_hex"] = self._app_conf.color( "morse_color1")
        # template_data["morse_color2_hex"] = self._app_conf.color( "morse_color2")
        template_data["rabbit_color1_hex"] = self._app_conf.color("rabbit_color1")
        template_data["rabbit_color2_hex"] = self._app_conf.color("rabbit_color2")
        template_data["checker_color1_hex"] = self._app_conf.color("checker_color1")
        template_data["checker_color2_hex"] = self._app_conf.color("checker_color2")
        return render_template("confedit.html", **template_data)

    # @app.route("/cfpost", methods=["GET", "POST"])
    def cfedit_handler(self):
        """Flask Route: /cfpost ."""
        debugging.info("Processing Config Form")

        ipadd = self._sysdata.local_ip()

        if request.method == "POST":
            data = request.form.to_dict()
            # check and fix data with leading zeros.
            # for key in data:
            #    if data[key] == "0" or data[key] == "00":
            #        data[key] = "0"
            #    elif data[key][:1] == "0":
            #        # Check if first character is a 0. i.e. 01, 02 etc.
            #        data[key] = data[key].lstrip("0")
            #        # if so, then self.strip the leading zero before writing to file.
            debugging.info(f"config form post: {data}")

            self._app_conf.parse_config_input(data)
            self._app_conf.save_config()
            flash("Settings Successfully Saved")

            return redirect("/")
            # temp[3] holds name of page that called this route.
        return redirect("/")

    # FIXME: Integrate into Class
    # Routes for LSREMOTE - Allow Mobile Device Remote. Thank Lance
    # # @app.route('/', methods=["GET", "POST"])
    # @app.route('/confmobile', methods=["GET", "POST"])
    def confmobile(self):
        """Flask Route: /confmobile - Mobile Device API."""
        debugging.info("Opening lsremote.html")

        # ipadd = self._sysdata.local_ip()
        # current_timezone = self._app_conf.get_string("default", "timezone")
        # settings = self._app_conf.gen_settings_dict()
        # loc_timestr = utils.time_format(utils.current_time(self._app_conf))
        # loc_timestr_utc = utils.time_format(utils.current_time_utc(self._app_conf))

        # Pass data to html document
        template_data = self.standardtemplate_data()
        template_data["title"] = "Mobile Settings Editor"
        template_data["color_vfr_hex"] = self._app_conf.color("color_vfr")
        template_data["color_mvfr_hex"] = self._app_conf.color("color_mvfr")
        template_data["color_ifr_hex"] = self._app_conf.color("color_ifr")
        template_data["color_lifr_hex"] = self._app_conf.color("color_lifr")
        template_data["color_nowx_hex"] = self._app_conf.color("color_nowx")
        template_data["color_black_hex"] = self._app_conf.color("color_black")
        template_data["color_lghtn_hex"] = self._app_conf.color("color_lghtn")
        template_data["color_snow1_hex"] = self._app_conf.color("color_snow1")
        template_data["color_snow2_hex"] = self._app_conf.color("color_snow2")
        template_data["color_rain1_hex"] = self._app_conf.color("color_rain1")
        template_data["color_rain2_hex"] = self._app_conf.color("color_rain2")
        template_data["color_frrain1_hex"] = self._app_conf.color("color_frrain1")
        template_data["color_frrain2_hex"] = self._app_conf.color("color_frrain2")
        template_data["color_dustsandash1_hex"] = self._app_conf.color(
            "color_dustsandash1"
        )
        template_data["color_dustsandash2_hex"] = self._app_conf.color(
            "color_dustsandash2"
        )
        template_data["color_fog1_hex"] = self._app_conf.color("color_fog1")
        template_data["color_fog2_hex"] = self._app_conf.color("color_fog2")
        template_data["color_homeport_hex"] = self._app_conf.color("color_homeport")

        template_data["fade_color1_hex"] = self._app_conf.color("fade_color1")
        template_data["allsame_color1_hex"] = self._app_conf.color("allsame_color1")
        template_data["allsame_color2_hex"] = self._app_conf.color("allsame_color2")
        template_data["shuffle_color1_hex"] = self._app_conf.color("shuffle_color1")
        template_data["shuffle_color2_hex"] = self._app_conf.color("shuffle_color2")
        template_data["radar_color1_hex"] = self._app_conf.color("radar_color1")
        template_data["radar_color2_hex"] = self._app_conf.color("radar_color2")
        template_data["circle_color1_hex"] = self._app_conf.color("circle_color1")
        template_data["circle_color2_hex"] = self._app_conf.color("circle_color2")
        template_data["square_color1_hex"] = self._app_conf.color("square_color1")
        template_data["square_color2_hex"] = self._app_conf.color("square_color2")
        template_data["updn_color1_hex"] = self._app_conf.color("updn_color1")
        template_data["updn_color2_hex"] = self._app_conf.color("updn_color2")
        # template_data["morse_color1_hex"] = self._app_conf.color( "morse_color1")
        # template_data["morse_color2_hex"] = self._app_conf.color( "morse_color2")
        template_data["rabbit_color1_hex"] = self._app_conf.color("rabbit_color1")
        template_data["rabbit_color2_hex"] = self._app_conf.color("rabbit_color2")
        template_data["checker_color1_hex"] = self._app_conf.color("checker_color1")
        template_data["checker_color2_hex"] = self._app_conf.color("checker_color2")
        return render_template("lsremote.html", **template_data)

    # FIXME: Integrate into Class
    # Import Config file. Must Save Config File to make permenant
    # @app.route("/importconf", methods=["GET", "POST"])
    def importconf(self):
        """Flask Route: /importconf - Flask Config Uploader."""
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
        """Flask Route: /restoreconf."""
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
    #    debugging.dprint(self._app_config_profiles)
    #    tmp_profile = config_profiles[req_profile]
    #    stored_profile = "/opt/NeoSectional/profiles/" + tmp_profile
    #
    #    flash(
    #        tmp_profile
    #        + "Profile Loaded. Review And Tweak The Settings As Desired. Must Be Saved!"
    #    )
    #    self.readconf(stored_profile)  # read profile config file
    #    debugging.info("Loading a Profile into Settings Editor")
    #    return redirect("confedit")

    def check_updates(self):
        """Run check for updates."""
        self._appinfo.refresh()
        flash("Updated version data")
        return redirect("/")

    def perform_updates(self):
        """Execute scripts to perform updates."""
        returncode, stdout = utils_system.execute_script(
            "/opt/git/livesectional/scripts/update.sh"
        )
        self.check_updates()
        if returncode == 0:
            flash("Update Completed")
            return redirect("/")
        else:
            debugging.error(stdout)
            template_data = self.standardtemplate_data()
            template_data["title"] = f"Update Issue {self._appinfo.current_version()}"
            template_data["stdout"] = stdout
            return render_template("update_error.html", **template_data)

    def perform_restart(self):
        """Execute scripts to restart app."""
        # Need to put in some checks here to just ignore this call unless the versions are appropriate for updates
        self.check_updates()
        if not self._appinfo.update_ready():
            flash(
                "Ignoring restart call as it likely came from previous restart request"
            )
            return redirect("/")
        returncode, stdout = utils_system.execute_script(
            "/opt/git/livesectional/scripts/restart.sh"
        )
        # IF this worked; then the process ended, and shouldn't be executing code
        if returncode == 0:
            flash("Restart says it worked - but HUH ?")
            return redirect("/")
        else:
            debugging.error(stdout)
            template_data = self.standardtemplate_data()
            template_data["title"] = f"Restart Issue {self._appinfo.current_version()}"
            template_data["stdout"] = stdout
            return render_template("update_error.html", **template_data)

    def system_reboot(self):
        """Flask Route: /system_reboot - Request host reboot."""
        flash("Rebooting System")
        debugging.info(f"Rebooting Map from {request.referrer}")
        self._clean_reboot_request = True
        # utils.system_reboot() # Executed as part of the return to the self.index rendering.
        return redirect("/")

    def handle_mapturnoff(self):
        """Flask Route: /mapturnoff - Trigger process shutdown."""
        debugging.info(f"Shutoff Map from {request.referrer}")
        self._led_strip.set_ledmode(LedMode.OFF)
        flash("Map Turned Off")
        return redirect("/")

    def handle_mapturnon(self):
        """Flask Route: /mapturnon - Trigger process shutdown."""
        debugging.info(f"Turn Map ON from {request.referrer}")
        self._led_strip.set_ledmode(LedMode.METAR)
        flash("Map Turned On")
        return redirect("/")

    # FIXME: Integrate into Class
    # Route to power down the RPI
    # @app.route("/shutoffnow1", methods=["GET", "POST"])
    def shutoffnow1(self):
        """Flask Route: /shutoffnow1 - Turn Off RPI."""
        url = request.referrer
        ipadd = self._sysdata.local_ip()
        debugging.info(
            "Disabled - Security Concerns - Investigating Shutdown RPI from " + url
        )
        # FIXME: Security Fixup
        # os.system('sudo shutdown -h now')
        return redirect("/")

    def handle_testled(self):
        """Flask Route: /testled - Run LED Test scripts."""
        debugging.info(f"Running testled.py from {request.referrer}")
        self._led_strip.set_ledmode(LedMode.TEST)
        flash("Set LED mode to TEST")
        return redirect("/")

    # FIXME: Integrate into Class
    # Route to run OLED test
    # @app.route("/testoled", methods=["GET", "POST"])
    def testoled(self):
        """Flask Route: /testoled - Run OLED Test sequence."""
        url = request.referrer
        ipadd = self._sysdata.local_ip()
        if (self._app_conf.get_int("oled", "displayused") != 1) or (
            self._app_conf.get_int("oled", "oledused") != 1
        ):
            return redirect("/")
            # temp[3] holds name of page that called this route.

        # flash("Testing OLEDs ")
        debugging.info("Running testoled.py from " + url)
        # FIXME: Call update_oled equivalent functions
        # os.system('sudo python3 /opt/NeoSectional/testoled.py')
        return redirect("/")
