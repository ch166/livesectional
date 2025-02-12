#!/usr/bin/env bash

source "$(dirname "$0")"/utils.sh

echo "Asking systemctl to restart livemap" | logger -t livemap-restart

systemctl restart livemap
error_check $?


# Sync filesystems
sync
