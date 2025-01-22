#! /bin/sh

# livesectional Daily Tasks - to be run under cron
#
PATH=/usr/sbin:/usr/bin:/sbin:/bin

# 1. cd to git repo ; git remote update ; git pull
# Assuming HTTPS git URL ; so no need for auth keys

cd /opt/git/livesectional
git remote update
git pull

# 2. Can we safely run create-venv script to update any new entries in requirements.txt
#
# 

echo "Going to run the create-venv.sh script to update environment"

/opt/git/livesectional/scripts/create-venv.sh


# This should allow the code to look at the git repo to check version information ; and then run the 
# install / upgrade scripts

# 3. check log files for errors
now=`date +"%m_%d_%Y"`

cd /opt/NeoSectional/logs
grep -A 5 -i error debugging.log* > error.log-${now}

# 


# Sync filesystems
sync
