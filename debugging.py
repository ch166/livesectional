# -*- coding: utf-8 -*- #
""" Support Debugging Printing """

import time
import sys
import datetime
import logging
import logging.handlers
import pprint


# FIXME: Move these flags to configuration
DEBUG_MSGS = False
PRINT_MSGS = True
INFO_MSGS = True
WARN_MSGS = True
ERR_MSGS = True

logger = None


def loginit(conf):
    """Init logging data."""
    global logger
    # FIXME: Move filename to config
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logfilename = conf.get_string("filenames", "log_file")
    # logging.basicConfig(filename="logs/debugging.log", level=logging.DEBUG)
    logfilehandler = logging.handlers.TimedRotatingFileHandler(
        logfilename, when="midnight", interval=1, backupCount=5, utc=True
    )
    logfilehandler.setLevel(logging.DEBUG)
    logger.addHandler(logfilehandler)

    DEBUG_MSGS = conf.get_bool("logging", "debug_msgs")
    PRINT_MSGS = conf.get_bool("logging", "print_msgs")
    INFO_MSGS = conf.get_bool("logging", "info_msgs")
    WARN_MSGS = conf.get_bool("logging", "warn_msgs")
    ERR_MSGS = conf.get_bool("logging", "err_msgs")

    logconsolehandler = logging.StreamHandler(sys.stdout)
    logconsolehandler.setLevel(logging.INFO)
    logger.addHandler(logconsolehandler)

    formatter = logging.Formatter("%(asctime)s livemap: %(message)s", "%b %d %H:%M:%S")
    formatter.converter = time.gmtime

    logfilehandler.setFormatter(formatter)
    logconsolehandler.setFormatter(formatter)

    # Disable PIL debug logs by default
    # Should eliminate STREAM b'IHDR' and STREAM b'IDAT' unnecessary logs
    logging.getLogger("PIL").setLevel(logging.WARNING)


def crash(args):
    """Handle Crash Data - Append to crash.log."""
    global logger
    # FIXME: Move filename to config
    appname = "LIVEMAP:"
    logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.debug(args)

    with open("logs/crash.log", "w+", encoding="utf-8") as log_file:
        log_file.write("***********************************************************")
        log_file.write(appname)
        log_file.write(logtime)
        log_file.write(args)
        log_file.write("-----------------------------------------------------------")
        log_file.flush()


def dprint(args):
    """Passthrough call to print() if DEBUG_MSGS is enabled."""
    global logger
    if PRINT_MSGS:
        logger.info(args)
        appname = "LIVEMAP:"
        logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(logtime, appname, "PRINT:", args, flush=True)
    else:
        return


def info(args):
    """Passthrough call to print() if DEBUG_MSGS is enabled."""
    global logger
    if INFO_MSGS:
        logger.info(args)
        # appname = "LIVEMAP:"
        # logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # print(logtime, appname, "INFO:", args, flush=True)
    else:
        return


def warn(args):
    """Passthrough call to print() if WARN_MSGS is enabled."""
    global logger
    if WARN_MSGS:
        logger.warning(args)
        # appname = "LIVEMAP:"
        # logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # print(logtime, appname, "WARN:", args, flush=True)
    else:
        return


def error(args):
    """Passthrough call to print() if ERR_MSGS is enabled."""
    global logger
    if ERR_MSGS:
        logger.error(args)
        # appname = "LIVEMAP:"
        # logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # logging.error(args)
        # print(logtime, appname, "ERROR:", args, flush=True)
    else:
        return


def debug(args):
    """Passthrough call to print() if ERR_MSGS is enabled."""
    global logger
    if DEBUG_MSGS:
        logger.debug(args)
        # appname = "LIVEMAP:"
        # logtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # logging.debug(args)
        # print(logtime, appname, "DEBUG:", args, flush=True)
    else:
        return


def prettify_dict(args):
    return pprint.pformat(args, indent=2, compact=True, width=240)
