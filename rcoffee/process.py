"""
Stateless rclone-based process that cross-copies remote and local content upon start, then watches local and remote for
changes, and reactively syncs them, resolving possible conflicts. Rclone itself has to be installed (see
https://rclone.org/install/) and a remote set up first (see https://rclone.org/remote_setup/).
"""

import asyncio
import json
import logging
import subprocess
from asyncio import Future
from asyncio.subprocess import Process as Subprocess
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Coroutine, Optional, Union

from watchfiles import awatch

log = logging.getLogger(__name__)


def spawn(*cmd, stdout: Optional[int] = subprocess.PIPE) -> Coroutine[Any, Any, Subprocess]:
    """Awaits subprocess spawn, but NOT its exit"""
    assert isinstance(cmd[0], str)
    return asyncio.create_subprocess_exec(cmd[0], *cmd[1:], stdout=stdout)


@dataclass
class Process:
    """Synchronizes a remote and local directory, watching for changes and polling for updates."""

    remote_path: str
    local_path: Path
    modify_window: str
    batch_cooldown: timedelta
    poll_interval: timedelta

    _local_changed: bool = field(default=False, init=False)
    _remote_changed: bool = field(default=False, init=False)
    _sync_request: Optional[Future] = field(default=None, init=False)

    def _spawn_rclone(
        self, command: str, *args, stdout: Optional[int] = subprocess.PIPE
    ) -> Coroutine[Any, Any, Subprocess]:
        return spawn("rclone", command, "-vv", *args, stdout=stdout)

    async def _exit_rclone(self, command: str, *args) -> None:
        """Awaits the actual exit of the spawned rclone subprocess"""
        await (await self._spawn_rclone(command, *args, stdout=None)).wait()

    async def _transfer(self, command: str, source: Union[str, Path], dest: Union[str, Path], *args) -> None:
        await self._exit_rclone(command, "--update", f"--modify-window={self.modify_window}", source, dest, *args)

    async def _sync_update(self, source: str, dest: str) -> None:
        await self._transfer("sync", source, dest, "--delete-before")

    async def _copy_update(self, source: Union[str, Path], dest: Union[str, Path]) -> None:
        await self._transfer("copy", source, dest)

    async def _cross_copy(self) -> None:
        log.info("Starting cross-copy...")
        await self._copy_update(self.remote_path, self.local_path)
        await self._copy_update(self.local_path, self.remote_path)
        log.info("Cross-copy complete")

    async def _dedupe(self) -> None:
        log.info("Starting dedupe...")
        await self._exit_rclone("dedupe", "--dedupe-mode", "newest", self.remote_path)
        log.info("Dedupe complete")

    async def _fetch_remote_state(self) -> Any:
        subproc = await self._spawn_rclone("lsjson", "--recursive", self.remote_path)
        stdout_reader = subproc.stdout
        stdout_content = await stdout_reader.read() if stdout_reader else None
        return sorted(json.loads(stdout_content) if stdout_content else None, key=lambda item: item["Path"])

    def _request_sync(self):
        """Triggers the `._sync_request` future which awakes the `._sync()` task"""
        if self._sync_request and not self._sync_request.done():
            self._sync_request.set_result(True)

    async def _watch_local(self):
        """Asynchronously watches changes in the local path and awakes the `._sync()` task when needed"""

        async for _ in awatch(self.local_path, recursive=True):
            log.info("Local changes detected")
            self._local_changed = True
            self._request_sync()

    async def _poll_remote(self) -> None:
        """
        Continuously polls the remote and awakes the `._sync()` task when needed
        """
        last_state: Optional[Any] = None

        while True:
            new_state = await self._fetch_remote_state()

            if last_state and new_state != last_state:
                # json.dump(last_state, open("last_state.json", "w", encoding="utf-8"), indent=2)
                # json.dump(new_state, open("new_state.json", "w", encoding="utf-8"), indent=2)

                log.info("Remote changes detected")
                self._remote_changed = True
                self._request_sync()

            last_state = new_state
            await asyncio.sleep(self.poll_interval.total_seconds())

    async def _sync(self):
        """
        Continuously awaits the `._sync_request` future from `._watch_local()` and/or `._poll_remote()` task, batches
        the changes, then proceeds to perform the actual sync afterwards, resolving possible conflicts
        """

        while True:
            await self._sync_request
            await self._dedupe()

            log.info("Batching changes...")

            need_push = False
            need_pull = False

            while self._local_changed or self._remote_changed:
                need_push |= self._local_changed
                need_pull |= self._remote_changed
                self._local_changed, self._remote_changed = False, False
                log.info("Changes detected, sleeping for %ss...", self.batch_cooldown.total_seconds())
                await asyncio.sleep(self.batch_cooldown.total_seconds())

            # Any changes in destination(s) between now and the end of deletion in destination(s) will be lost.
            # Use "rclone sync --delete-before ..." to delete files in destination before transfer and minimize data 
            # loss.

            self._sync_request = asyncio.get_running_loop().create_future()

            log.info("Batching complete, processing batched changes...")

            if need_push and need_pull:
                log.info("Both local and remote have changed")
                await self._cross_copy()
            elif need_push:
                log.info("Pushing local changes...")
                await self._sync_update(self.local_path, self.remote_path)
            elif need_pull:
                log.info("Pulling remote changes...")
                await self._sync_update(self.remote_path, self.local_path)
            else:
                assert False, "Unreachable"

            log.info("Sync complete")

            await self._dedupe()

    async def run_async(self):
        """
        Asynchronously cross-copies remote and local content upon start, then watches local and remote for changes, and
        reactively syncs them, resolving possible conflicts. Rclone itself has to be installed (see
        https://rclone.org/install/) and a remote set up first (see https://rclone.org/remote_setup/).
        """
        await self._cross_copy()

        self._sync_request = asyncio.get_running_loop().create_future()

        # TODO: Replace with TaskGroup from Python 3.11
        await asyncio.gather(
            self._watch_local(),
            self._poll_remote(),
            self._sync(),
        )

    def run(self):
        """
        Synchronously cross-copies remote and local content upon start, then watches local and remote for changes, and
        reactively syncs them, resolving possible conflicts. Rclone itself has to be installed (see
        https://rclone.org/install/) and a remote set up first (see https://rclone.org/remote_setup/).
        """
        logging.basicConfig(level=logging.INFO)
        asyncio.run(self.run_async())
