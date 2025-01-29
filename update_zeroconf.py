# -*- coding: utf-8 -*- #
""" Manage i2c Light Sensors. """

# Update i2c attached devices
import time
import traceback
import random
import debugging
import socket

from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceStateChange,
    Zeroconf,
    ZeroconfServiceTypes,
    ServiceListener,
    ServiceInfo,
)

# Building from https://github.com/python-zeroconf/python-zeroconf/tree/master


class ZCListener(ServiceListener):

    _livemap_server_list = {}

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        zc_info = zc.get_service_info(service_type, name)
        self.handle_service(zc_info)

    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        zc_info = zc.get_service_info(service_type, name)
        self.handle_service(zc_info)

    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        zc_info = zc.get_service_info(service_type, name)
        self._livemap_server_list.pop(zc_info.server, None)
        debugging.info(f"zc: Service {name} removed")

    def handle_service(self, zc_info) -> None:
        if zc_info is not None:
            if zc_info.properties is not None:
                for key, value in zc_info.properties.items():
                    if (key == b"function") and (value == b"livemap"):
                        debugging.info(f"zc : {zc_info.server} / {key!r}: {value!r}")
                        self._livemap_server_list[zc_info.server] = zc_info

    def neighbors(self):
        """Return discovered neighbors"""
        return self._livemap_server_list

    def neighbor_count(self):
        """Count of items in neighbor list."""
        return len(self._livemap_server_list)


class NeighListener(ServiceListener):
    """Class to Discover Multicast Neighbors."""

    # Used for both host_ttl and other_ttl
    _REFRESH_TIMER = 140
    # Refresh timer should be longer than the two numbers below multiplied together.
    _LOOP_DELAY_INTERVAL = 60
    _LOOP_SKIP_COUNT = 2

    led_mgmt = None
    _app_conf = None
    _sysdata = None
    _zeroconf = None
    _ipversion = None

    _browser = None

    # Guidance is to publish as a _http service, and allow HTTP redirects to handle the
    # rewrite to HTTPS.
    _services = [
        "_http._tcp.local.",
    ]
    _livemap_neighbors = []

    _announce_services = "_http._tcp.local."
    _announce_description = {
        "path": "/",
        "function": "livemap",
        "version": "0.99",
        "netport": 0,
    }
    _announce_name_svc = "_http._tcp.local."
    _announce_name = None
    _announce_server = "livemap4.local."

    # FIXME: Pull from config
    _net_port = 8443

    def __init__(self, conf, sysdata, appinfo):
        self._app_conf = conf
        self._sysdata = sysdata
        self._app_info = appinfo

        # TODO: Look into including useful state information here (LED states /
        self._announce_description["version"] = self._app_info.running_version()
        self._announce_description["netport"] = self._net_port
        self._announce_description["fqdn"] = socket.gethostname()
        self._announce_server = f"_{socket.gethostname()}.{self._announce_name_svc}"
        self._announce_name = f"_{socket.gethostname()}.{self._announce_name_svc}"

        # TODO: Does it matter if this is .ALL or .V4Only ?
        self._ip_version = IPVersion.V4Only
        self._zeroconf = Zeroconf(ip_version=self._ip_version)
        self._listener = ZCListener()

        self._browser = ServiceBrowser(
            self._zeroconf,
            self._services,
            self._listener,
        )

    def update_node_identity(self):
        """... do stuff ..."""
        self._announce_description["version"] = self._app_info.running_version()
        self._announce_description["netport"] = self._net_port
        self._announce_description["fqdn"] = socket.gethostname()
        self._announce_server = f"_{socket.gethostname()}.{self._announce_name_svc}"
        self._announce_name = f"_{socket.gethostname()}.{self._announce_name_svc}"
        self._announce_addresses = [self._sysdata.local_ip()]
        self._announce_info = ServiceInfo(
            type_=self._announce_services,
            name=self._announce_name,
            addresses=self._announce_addresses,
            port=self._net_port,
            properties=self._announce_description,
            server=self._announce_server,
            host_ttl=self._REFRESH_TIMER,
            other_ttl=self._REFRESH_TIMER,
        )
        return

    def get_neighbors(self):
        """Array of formatted neighbors"""
        neighbors = []
        if self._listener is not None:
            debugging.debug(
                f"zc self._listener.neighbors() : {self._listener.neighbors()}"
            )
            for zc_name, zc_info in self._listener.neighbors().items():
                debugging.debug(f"zc get_neighbors {zc_name}/{zc_info}")
                if b"netport" in zc_info.properties:
                    n_port = zc_info.properties[b"netport"].decode("UTF-8")
                else:
                    n_port = "missing"
                if b"version" in zc_info.properties:
                    n_version = zc_info.properties[b"version"].decode("UTF-8")
                else:
                    n_version = "missing"
                if b"fqdn" in zc_info.properties:
                    n_hostname = zc_info.properties[b"fqdn"].decode("UTF-8")
                else:
                    n_hostname = "missing"
                n_ip_list = zc_info.parsed_scoped_addresses()
                n_ip = f"{n_ip_list[0]}"
                label = f"{n_hostname}, ({n_version})"
                neighbors.append(f"{zc_name},{n_hostname}, {label} )")
        debugging.debug(f"zc get neighbors: {neighbors}")
        return neighbors

    def stats(self):
        """Generate some useful stats."""
        return f"Statistics: zeroconf\n\tNeighbor Count : {self._listener.neighbor_count()}"

    def update_loop(self):
        """Thread Main Loop."""
        outerloop = True  # Set to TRUE for infinite outerloop
        loop_counter = 1
        self.update_node_identity()
        self._zeroconf.register_service(self._announce_info)
        debugging.debug(f"zc register: {self._announce_info}")
        while outerloop:
            if loop_counter % self._LOOP_SKIP_COUNT == 0:
                debugging.debug("zc update service cycle")
                self.update_node_identity()
                self._zeroconf.update_service(self._announce_info)
            time.sleep(self._LOOP_DELAY_INTERVAL)
            loop_counter += 1
