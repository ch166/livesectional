#!/usr/bin/env bash

source $(dirname "$0")/utils.sh

systemctl restart livemap
error_check $?

echo "Asked systemctl to restart livemap"

# Sync filesystems
sync
