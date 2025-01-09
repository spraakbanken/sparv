"""Util functions for installations on remote servers."""
from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Iterable
from pathlib import Path

from sparv.api import get_logger
from sparv.api.util import system

logger = get_logger(__name__)


def install_path(
    source_path: str | Path,
    host: str | None,
    target_path: str | Path
) -> None:
    """Transfer a file or the contents of a directory to a target destination, optionally on a different host.

    Args:
        source_path: The file or directory to transfer.
        host: The remote host to transfer to. Set to None to transfer locally.
        target_path: The destination path.
    """
    system.rsync(source_path, host, target_path)


def uninstall_path(path: str | Path, host: str | None = None) -> None:
    """Remove a file or directory, optionally on a remote host.

    Args:
        path: The file or directory to remove.
        host: The remote host to remove from. Set to None to remove locally.
    """
    system.remove_path(path, host)


def install_mysql(host: str | None, db_name: str, sqlfile: Path | str | list[Path | str]) -> None:
    """Insert tables and data from SQL-file(s) to local or remote MySQL database.

    Args:
        host: The remote host to install to. Set to None to install locally.
        db_name: Name of the database.
        sqlfile: Path to a SQL file, or list of paths.
    """
    if isinstance(sqlfile, str):
        sqlfile = [sqlfile]
    file_total = len(sqlfile)

    for file_count, f in enumerate(sqlfile):
        if not os.path.exists(f):
            logger.error("Missing SQL file: %s", f)
        elif os.path.getsize(f) < 10:
            logger.info("Skipping empty file: %s (%d/%d)", f, file_count + 1, file_total)
        else:
            logger.info("Installing MySQL database: %s, source: %s (%d/%d)", db_name, f, file_count + 1, file_total)
            if not host:
                subprocess.check_call(
                    f"cat {shlex.quote(f)} | mysql {shlex.quote(db_name)}", shell=True
                )
            else:
                subprocess.check_call(
                    f"cat {shlex.quote(f)} | ssh {shlex.quote(host)} {shlex.quote(f'mysql {db_name}')}", shell=True
                )


def install_mysql_dump(host: str, db_name: str, tables: str | Iterable[str]) -> None:
    """Copy selected tables (including data) from local to remote MySQL database."""
    if isinstance(tables, str):
        tables = tables.split()
    logger.info("Copying MySQL database: %s, tables: %s", db_name, ", ".join(tables))
    subprocess.check_call(f'mysqldump {db_name} {" ".join(tables)} | ssh {host} "mysql {db_name}"', shell=True)
