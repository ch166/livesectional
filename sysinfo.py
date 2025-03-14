# -*- coding: utf-8 -*- #
"""Use psutil to query system information"""

import os
import sys
import platform
import datetime
import time
import psutil
import flask
import utils


class SystemData:
    """Gather useful information about this system."""

    _sysinfo = None
    ipaddr = None
    _uptime = None
    _internet_active = None

    def __init__(self):
        """Start from zero."""
        self._sysinfo = self.query_system_information()
        self._uptime = self.system_uptime()
        (online_status, ipaddr) = utils.is_connected()
        self.ipaddr = ipaddr
        self._internet_active = online_status

    def system_uptime(self) -> datetime.timedelta:
        """Update system uptime, in (days, hh:mm:ss) format."""
        uptime = datetime.timedelta(seconds=(time.time() - psutil.boot_time()))
        return datetime.timedelta(days=uptime.days, seconds=uptime.seconds)

    def uptime(self):
        """Return Uptime."""
        return self._uptime

    def internet_connected(self):
        """Internet Connected Status."""
        return self._internet_active

    def update_local_ip(self) -> str:
        """Create Socket to the Internet, Query Local IP."""
        (online_status, ipaddr) = utils.is_connected()
        self.ipaddr = ipaddr
        return ipaddr

    def local_ip(self) -> str:
        """Return IP addr."""
        return self.ipaddr

    def refresh(self):
        """Update data."""
        # TODO: Need to refresh this data on a regular basis
        self._sysinfo = self.query_system_information()
        self._uptime = self.system_uptime()
        (online_status, ipaddr) = utils.is_connected()
        self._internet_active = online_status
        self.ipaddr = ipaddr

    def get_size(self, bytes_size, suffix="B") -> str:
        """Scale bytes to its proper format."""
        # e.g:
        # 1253656 => '1.20MB'
        # 1253656678 => '1.17GB'
        factor = 1024
        for unit in ["", "K", "M", "G", "T", "P"]:
            if bytes_size < factor:
                return f"{bytes_size:.2f}{unit}{suffix}"
            bytes_size /= factor
        return "ERR"

    def poll_system_information(self):
        """Generate useful system description."""
        uname = platform.uname()
        # Get system information
        sysinfo_text = "=" * 20 + "System Information" + "=" * 20 + "<br> \n"
        sysinfo_text += f"System: {uname.system}" + "<br> \n"
        sysinfo_text += f"Node Name: {uname.node}" + "<br> \n"
        sysinfo_text += f"Release: {uname.release}" + "<br> \n"
        sysinfo_text += f"Version: {uname.version}" + "<br> \n"
        sysinfo_text += f"Machine: {uname.machine}" + "<br> \n"
        # Software Information
        sysinfo_text += "=" * 20 + "Software Info" + "=" * 20 + "<br> \n"
        sysinfo_text += f"Python Version: {sys.version}" + "<br> \n"
        sysinfo_text += f"Flask Version : {flask.__version__}" + "<br> \n"
        # Get CPU information
        sysinfo_text += "=" * 20 + "CPU Info" + "=" * 20 + "<br> \n"
        sysinfo_text += f"Physical cores: {psutil.cpu_count(logical=False)}" + "<br> \n"
        sysinfo_text += f"Total cores: {psutil.cpu_count(logical=True)}" + "<br> \n"
        # CPU Frequencies
        cpufreq = psutil.cpu_freq()
        sysinfo_text += f"Max Frequency: {cpufreq.max:.2f}Mhz" + "<br> \n"
        sysinfo_text += f"Min Frequency: {cpufreq.min:.2f}Mhz" + "<br> \n"
        sysinfo_text += f"Current Frequency: {cpufreq.current:.2f}Mhz" + "<br> \n"
        # CPU usage
        sysinfo_text += f"Total CPU Usage: {psutil.cpu_percent()}%" + "<br> \n"
        # Memory Information
        sysinfo_text += "=" * 20 + "Memory Information" + "=" * 20 + "<br> \n"
        svmem = psutil.virtual_memory()
        sysinfo_text += f"Total: {self.get_size(svmem.total)}" + "<br> \n"
        sysinfo_text += f"Available: {self.get_size(svmem.available)}" + "<br> \n"
        sysinfo_text += f"Used: {self.get_size(svmem.used)}" + "<br> \n"
        sysinfo_text += f"Percentage: {svmem.percent}%" + "<br> \n"
        sysinfo_text += "=" * 10 + "SWAP" + "=" * 10 + "<br> \n"
        # SWAP memory details
        swap = psutil.swap_memory()
        sysinfo_text += f"Total: {self.get_size(swap.total)}" + "<br> \n"
        sysinfo_text += f"Free: {self.get_size(swap.free)}" + "<br> \n"
        sysinfo_text += f"Used: {self.get_size(swap.used)}" + "<br> \n"
        sysinfo_text += f"Percentage: {swap.percent}%" + "<br> \n"
        sysinfo_text += "=" * 20 + "Disk Information" + "=" * 20 + "<br> \n"
        sysinfo_text += "Partitions and Usage:" + "<br> \n"
        # get all disk partitions
        partitions = psutil.disk_partitions()
        for partition in partitions:
            sysinfo_text += f"=== Device: {partition.device} ===" + "<br> \n"
            sysinfo_text += f"  Mountpoint: {partition.mountpoint}" + "<br> \n"
            sysinfo_text += f"  File system type: {partition.fstype}" + "<br> \n"
            try:
                partition_usage = psutil.disk_usage(partition.mountpoint)
            except PermissionError:
                # this can be catched due to the disk that
                # isn't ready
                continue
            sysinfo_text += (
                f"  Total Size: {self.get_size(partition_usage.total)}" + "<br> \n"
            )
            sysinfo_text += f"  Used: {self.get_size(partition_usage.used)}" + "<br>\n"
            sysinfo_text += f"  Free: {self.get_size(partition_usage.free)}" + "<br>\n"
            sysinfo_text += f"  Percentage: {partition_usage.percent}%" + "<br>\n"
        # get IO statistics since boot
        disk_io = psutil.disk_io_counters()
        sysinfo_text += f"Total read: {self.get_size(disk_io.read_bytes)}" + "<br>\n"
        sysinfo_text += f"Total write: {self.get_size(disk_io.write_bytes)}" + "<br>\n"

        # Network information
        sysinfo_text += "=" * 20 + "IPv4 Network Information" + "=" * 20 + "<br>\n"
        # get all network interfaces (virtual and physical)
        if_addrs = psutil.net_if_addrs()
        for interface_name, interface_addresses in if_addrs.items():
            for address in interface_addresses:
                if str(address.family) == "AddressFamily.AF_INET":
                    sysinfo_text += (
                        f"=== Interface: {interface_name} ({address.family}) ==="
                        + "<br>\n"
                    )
                    sysinfo_text += f"  IP Address: {address.address}" + "<br>\n"
                    sysinfo_text += f"  Netmask: {address.netmask}" + "<br>\n"
        # get IO statistics since boot
        net_io = psutil.net_io_counters()
        sysinfo_text += (
            f"Total Bytes Sent: {self.get_size(net_io.bytes_sent)}" + "<br>\n"
        )
        sysinfo_text += (
            f"Total Bytes Received: {self.get_size(net_io.bytes_recv)}" + "<br>\n"
        )
        self._sysinfo = sysinfo_text

    def query_system_information(self) -> str:
        """Run query."""
        if (self._sysinfo == "") or (self._sysinfo is None):
            self.poll_system_information()
        return self._sysinfo

    def system_load(self) -> (str, str):
        """Get System Load"""
        load_avg = f"Loadavg ({round(os.getloadavg()[0],2)},{round(os.getloadavg()[1],2)},{round(os.getloadavg()[2],2)})"
        mem_usage = f"Memory: {psutil.virtual_memory().percent}%, Swap: {psutil.swap_memory().percent}%"
        return load_avg, mem_usage
