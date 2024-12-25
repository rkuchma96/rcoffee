# Rcoffee

## About

Yet another <ins>**rc**</ins>lone <ins>**off**</ins>line <ins>**f**</ins>older <ins>**i**</ins>mplementation.

Stateless rclone-based process that cross-copies remote and local content upon start, then watches local and remote
for changes, and reactively syncs them, resolving possible conflicts. Rclone itself has to be installed (see
https://rclone.org/install/) and a remote set up first (see https://rclone.org/remote_setup/).

## Usage

usage: `rcoffee [-h] [--poll-interval POLL_INTERVAL] [--modify-window MODIFY_WINDOW] [--batch-cooldown BATCH_COOLDOWN]
               remote_path local_path`

[Human-readable durations are supported](https://pypi.org/project/pytimeparse/) unless stated otherwise.

positional arguments:

  `remote_path`           Fully-qualified remote path to sync like `"gdrive:Sync"`

  `local_path`            Local path to sync like `"/home/bob/gdrive"` or `"C:\Users\Alice\onedrive"`

options:

  `-h`, `--help`            show this help message and exit

  `--poll-interval POLL_INTERVAL`
                        Interval to poll the remote for changes (default `1s`)
  
  `--modify-window MODIFY_WINDOW`
                        Max time diff to be considered the same (default `1s`). Passed to rclone as is, may not support
                        all human-readable durations.

  `--batch-cooldown BATCH_COOLDOWN`
                        Minimum time between the last detected change and actual sync (default `1s`)