from urllib.request import urlopen
import json
from time import sleep

import conf

class AppInfo:
    ''' Class to store information and data about the install environment.
    Gather information about the currently installed version, and check for new versions.
    As this gets smarter - we should be able to handle
    - Hardware Info
    - Performance Data
    - Crash Data
    - Version Information
    - Update Information
    '''
    def __init__(self):
        self.cur_version_info =  3.0
        self.available_version = 3.0
        self.refresh()

    def refresh(self):
        """ Update AppInfo data """
        self.checkForUpdate()

    def updateAvailable(self):
        """ Return True if update is available """
        if self.available_version > self.cur_version_info:
            return True
        return False

    def checkForUpdate(self):
        """ Query for new versions """
