#ftp-v4.py - Mark Harris. This script is used to send the rpi's IP and hostname to a central location, ftp server.
#     Obsolete script and no longer used on the LiveSectional platform. Saved for posterity sake only.

#     Updated to work under Python 3.7
#     This is used for multiple LiveSectional maps all on the same local network so the editors will
#     populate a dropdown box for easy selection of which board to edit. If only one board is present
#     then there will be no dropdown box in the editor.
#     This script will be executed by webapp.py, which once executed will read the local_file and
#     populate a dropdown box in the editors with all the map's IP addresses to make it easier to switch.
#     Added Logging capabilities which is stored in /NeoSectional/logfile.log

#required imports
import ftplib
import socket
import time
import sys
import config
import logging
import logzero
from logzero import logger
import os
import admin

# Setup rotating logfile with 3 rotations, each with a maximum filesize of 1MB:
version = admin.version                         #Software version
loglevel = config.loglevel
loglevels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]
logzero.loglevel(loglevels[loglevel])           #Choices in order; DEBUG, INFO, WARNING, ERROR
logzero.logfile('/NeoSectional/logfile.log', maxBytes=1e6, backupCount=3)
logger.info("\nStartup of metar-v4.py Script, Version " + version)
logger.info("Log Level Set To: " + str(loglevels[loglevel]))

use_ftp = admin.use_ftp                         #0 = No, 1 = Yes. Use this script for admin and debug only.

#ftp credentials etc. which comes from admin.py
hostname = admin.hostname
username = admin.username
password = admin.password
remote_dir = admin.remote_dir
logger.debug(hostname)

#misc settings
counter = 0                                     #used to count up to max_delay_time for checking internet connectivity
delay_time = 60                                 #delay in Seconds for checking internet connectivity
local_file = '/NeoSectional/lsinfo.txt'         #holds the ip addresses for other maps on local network.
remote_file = 'lsinfo.txt'
ipaddresses = []

#Functions
def uploadfile():
    with open(local_file, 'rb') as fp:
        res = ftp.storlines("STOR " + remote_file, fp)
        if not res.startswith('226'):
            logger.error('ERROR - Upload failed')
#       ftp.close()

def downloadfile():
    with open(local_file, 'w+') as fp:
        res = ftp.retrlines('RETR ' + remote_file, lambda s, w=fp.write: w(s+'\n'))
        if not res.startswith('226'):
            logger.error('ERROR - Download failed')
            if os.path.isfile(local_file):
                os.remove(local_file)
#       fp.close()

#start of execution
if use_ftp == 1:                                #use this for admin and development only.

    #Get machine's IP address and hostname to store.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ipadd = s.getsockname()[0]
    rpi_name = socket.gethostname()
    logger.debug(ipadd)

    #start ftp session, give it 3 attempts with a delay between.
    try:
        ftp = ftplib.FTP(hostname, username, password)
        logger.info('FTP Connection Secured on first try on ' + hostname)
    except:
        #verify internet is available before moving on.
        logger.warning('Server unavailable. Try 1. Checking again in ' + str(delay_time) + ' seconds')
        time.sleep(delay_time)

        try:
            ftp = ftplib.FTP(hostname, username, password)
            logger.info('FTP Connection Secured on second try')
        except:
            #verify internet is available before moving on.
            logger.warning('Server unavailable. Try 2. Checking again in ' + str(delay_time) + ' seconds')
            time.sleep(delay_time)

            try:
                ftp = ftplib.FTP(hostname, username, password)
                logger.info('FTP Connection Secured on third try')
            except ftplib.all_errors as e:
                logger.error('FTP error:', e)
                logger.error('Ending ftp-v4.py Script')
                sys.exit()                      #End script

    #change the ftp's directory if necessary
    if remote_dir != "":
        ftp.cwd(remote_dir)

    #check to see if file is on the ftp server or not.
    file_list = ftp.nlst()
    if remote_file in file_list:
        logger.info('Remote File is Present on FTP Server')
        #download file from ftp server
        downloadfile()
        logger.info(local_file + ' Downloaded to RPI')

    else:
        logger.info('Remote File is Missing from ' + hostname)
        uploadfile()                            #create file on ftp server
        logger.info('Data File has been uploaded to ' + hostname)

    #read local file and compare to local rpi address to see if its' already in the file.
    #if it is, then we are done. If not, then add it to the file and upload it to the ftp server.
    try:
        with open(local_file) as fp:
            for line in fp:
                ipaddresses.append(line.strip())
        fp.close()
    except IOError as error:
        logger.error(local_file + ' file could not be loaded.')
        logger.error(error)

    info = ipadd + ' ' + rpi_name               #create line for file with space separating info

    if info in ipaddresses:
        pass
    else:
        ipaddresses.append(info)

        fp = open(local_file, 'w+')
        for j in range(len(ipaddresses)):
            fp.write(ipaddresses[j])
            fp.write('\n')
        fp.close()

        logger.debug(ipaddresses)
        uploadfile()                            #upload updated file back to the ftp server.
        logger.info(local_file + ' Uploaded to ' + hostname)

    logger.info('ftp-v4.py Completed')

else:
    logger.info('ftp-v4.py Not Run')
