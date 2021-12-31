''' Support Debugging Printing '''

# -*- coding: utf-8 -*-


import datetime

# FIXME: Move these flags to configuration
DEBUG_MSGS = False
PRINT_MSGS = True
INFO_MSGS = True
WARN_MSGS = True
ERR_MSGS = True


def dprint(args):
    ''' Passthrough call to print() if DEBUG_MSGS is enabled '''
    if PRINT_MSGS:
        appname = "LIVEMAP:"
        logtime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(logtime, appname, "PRINT:", args, flush=True )
    else:
        return

def info(args):
    ''' Passthrough call to print() if DEBUG_MSGS is enabled '''
    if INFO_MSGS:
        appname = "LIVEMAP:"
        logtime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(logtime, appname, "INFO:", args, flush=True )
    else:
        return

def warn(args):
    ''' Passthrough call to print() if WARN_MSGS is enabled '''
    if WARN_MSGS:
        appname = "LIVEMAP:"
        logtime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(logtime, appname, "WARN:", args, flush=True )
    else:
        return

def error(args):
    ''' Passthrough call to print() if ERR_MSGS is enabled '''
    if ERR_MSGS:
        appname = "LIVEMAP:"
        logtime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(logtime, appname, "ERROR:", args, flush=True )
    else:
        return

def debug(args):
    ''' Passthrough call to print() if ERR_MSGS is enabled '''
    if DEBUG_MSGS:
        appname = "LIVEMAP:"
        logtime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(logtime, appname, "DEBUG:", args, flush=True )
    else:
        return
