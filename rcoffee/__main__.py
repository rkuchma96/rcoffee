"""CLI entry point for the sync process."""

from argparse import ArgumentParser, Namespace
from datetime import timedelta
from pathlib import Path

from pytimeparse.timeparse import timeparse

from rcoffee.process import Process


def _duration(value: str) -> timedelta:
    return timedelta(seconds=timeparse(value))


def parse_args() -> Namespace:
    """Parses command-line arguments."""

    parser = ArgumentParser(
        prog="rcoffee",
        description="""
Yet another rclone offline folder implementation.

Stateless rclone-based process that cross-copies remote and local content upon start, then watches local and remote for
changes, and reactively syncs them, resolving possible conflicts. Rclone itself has to be installed (see
https://rclone.org/install/) and a remote set up first (see https://rclone.org/remote_setup/).

Human-readable durations are supported (https://pypi.org/project/pytimeparse/) unless stated otherwise.
""",
    )

    parser.add_argument(
        "remote_path",
        type=str,
        help='Fully-qualified remote path to sync like "gdrive:Sync"',
    )

    parser.add_argument(
        "local_path",
        type=Path,
        help='Local path to sync like "/home/bob/gdrive" or "C:\\Users\\Alice\\onedrive"',
    )

    parser.add_argument(
        "--poll-interval",
        dest="poll_interval",
        type=_duration,
        default="1s",
        help="Interval to poll the remote for changes (default 1s)",
    )

    parser.add_argument(
        "--modify-window",
        dest="modify_window",
        type=str,
        default="1s",
        help="""
Max time diff to be considered the same (default 1s). Passed to rclone as is, may not support all human-readable
durations.""",
    )

    parser.add_argument(
        "--batch-cooldown",
        dest="batch_cooldown",
        type=_duration,
        default="1s",
        help="Minimum time between the last detected change and actual sync (default 1s)",
    )

    return parser.parse_args()


def _main():
    Process(**vars(parse_args())).run()


if __name__ == "__main__":
    _main()
