# -*- coding: utf-8 -*- #
"""Support Debugging Printing"""

import time
import sys
import datetime
import logging
import logging.handlers
import pprint

__logger = None


def loginit(app_conf):
    """Init logging data."""
    global __logger
    # FIXME: Move filename to config
    __logger = logging.getLogger()
    __logger.setLevel(logging.INFO)

    logfile_name = app_conf.get_string("filenames", "log_file")
    logfile_handler = logging.handlers.TimedRotatingFileHandler(
        logfile_name, when="midnight", interval=1, backupCount=5, utc=True
    )
    log_console_handler = logging.StreamHandler(sys.stdout)

    logfile_loglevel = str2loglevel(app_conf.get_string("logging", "loglevel_logfile"))
    logfile_handler.setLevel(logfile_loglevel)

    console_loglevel = str2loglevel(app_conf.get_string("logging", "loglevel_console"))

    log_console_handler.setLevel(console_loglevel)

    __logger.addHandler(logfile_handler)
    __logger.addHandler(log_console_handler)

    formatter = logging.Formatter("%(asctime)s livemap: %(message)s", "%b %d %H:%M:%S")
    formatter.converter = time.gmtime

    logfile_handler.setFormatter(formatter)
    log_console_handler.setFormatter(formatter)

    # Disable PIL debug logs by default
    # Should eliminate STREAM b'IHDR' and STREAM b'IDAT' unnecessary logs
    logging.getLogger("PIL").setLevel(logging.WARNING)

    listloggers()


def str2loglevel(logstr):
    """Convert string to log level."""
    if (logstr is None) or logstr.lower() == "critical":
        return logging.CRITICAL
    if logstr.lower() == "debug":
        return logging.DEBUG
    if logstr.lower() == "info":
        return logging.INFO
    if logstr.lower() == "warning":
        return logging.WARNING
    if logstr.lower() == "error":
        return logging.ERROR


def listloggers() -> str:
    rootlogger = logging.getLogger()

    logger_data = f"loginit: {rootlogger}\n"
    for h in rootlogger.handlers:
        logger_data += f"loginit:\t{h}"

    for nm, lgr in logging.Logger.manager.loggerDict.items():
        logger_data += f"loginit: + [%-20s] {nm}  % {lgr}"
        if not isinstance(lgr, logging.PlaceHolder):
            for h in lgr.handlers:
                logger_data += f"loginit:\t{h}"
    return logger_data


def setLogLevel(newlevel):
    """Set debugging loglevel"""
    # FIXME: Set the correct loglevels for the different log handlers .. rather than brute forcing it
    dprint(f"LOG Updating - setting log level to {newlevel}")
    global __logger
    __logger.setLevel(newlevel)
    for handler in __logger.handlers:
        handler.setLevel(newlevel)


def crash(args):
    """Handle Crash Data - Append to crash.log."""
    global __logger
    # FIXME: Move filename to config
    appname = "LIVEMAP:"
    logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    __logger.debug(args)

    with open("logs/crash.log", "w+", encoding="utf-8") as log_file:
        log_file.write("***********************************************************")
        log_file.write(appname)
        log_file.write(logtime)
        log_file.write(args)
        log_file.write("-----------------------------------------------------------")
        log_file.flush()


def dprint(args):
    """Passthrough call to __logger."""
    global __logger
    __logger.info(args)
    appname = "LIVEMAP:"
    logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(logtime, appname, "PRINT:", args, flush=True)


def info(args):
    """Passthrough call to __logger."""
    global __logger
    __logger.info(args)


def warn(args):
    """Passthrough call to __logger."""
    global __logger
    __logger.warning(args)


def error(args):
    """Passthrough call to __logger."""
    global __logger
    __logger.error(args)


def debug(args):
    """Passthrough call to __logger."""
    global __logger
    __logger.debug(args)


def prettify_dict(args):
    return pprint.pformat(args, indent=2, compact=True, width=240)


def internal_debug() -> str:
    """Return internal debugging data"""
    global __logger
    debug_str = f"DEBUGGING\n{listloggers()}\n"
    return debug_str
