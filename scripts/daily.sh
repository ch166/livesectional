#! /bin/sh

# livesectional Daily Tasks - to be run under cron
#
PATH=/usr/sbin:/usr/bin:/sbin:/bin

# 1. cd to git repo ; git remote update ; git pull
# Assuming HTTPS git URL ; so no need for auth keys

cd /opt/git/livesectional
git remote update
git pull

# This should allow the code to look at the git repo to check version information ; and then run the 
# install / upgrade scripts

# 2. check log files for errors
now=`date +"%m_%d_%Y"`

cd /opt/NeoSectional/logs
grep -A 5 -i error debugging.log* > error.log-${now}

# 

