#!/usr/bin/env bash
set -euo pipefail

sudo /sbin/sysctl -w fs.inotify.max_user_watches=1048576
sudo /sbin/sysctl -w fs.inotify.max_user_instances=8192
sudo /sbin/sysctl -w fs.inotify.max_queued_events=32768
