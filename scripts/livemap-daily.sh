#!/usr/bin/env bash

# livesectional Daily Tasks - to be run under cron
# Self contained for now

error_check() {
	[ "$1" != 0 ] && {
		echo "livemap daily - error: $2 " | logger -t livemap-daily
		exit 1
	}
}

#
PATH=/usr/sbin:/usr/bin:/sbin:/bin

# 1. cd to git repo ; git remote update ; git pull
# Assuming HTTPS git URL ; so no need for auth keys

cd /opt/git/livesectional || exit
git remote update 2>&1 | logger -t livemap-daily
error_check $? "git remote update problems"
git pull 2>&1 | logger -t livemap-daily
error_check $? "git pull problems"

# 2. Can we safely run create-venv script to update any new entries in requirements.txt
#
# 

echo "Livemap starting daily script to update environment" | logger -t livemap-daily

# Doing the environment update first - in case new requirements must be installed early
/opt/git/livesectional/scripts/create-venv.sh 2>&1 | logger -t livemap-daily
error_check $? "create-venv.sh problems"

/opt/git/livesectional/scripts/update.sh 2>&1 | logger -t livemap-daily
error_check $? "scripts/update.sh problems"

# This should allow the code to look at the git repo to check version information ; and then run the 
# install / upgrade scripts

# 3. check log files for errors
now=$(date +"%m_%d_%Y")

cd /opt/NeoSectional/logs || exit
grep -A 5 -i error debugging.log* > error.log-"${now}"

# Sync filesystems
sync

# 4. Update timestamp on daily-complete.txt

date > /opt/NeoSectional/daily-complete.txt

echo "livemap update cron daily script complete" | logger -t livemap-daily
exit 0
