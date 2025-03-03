"""Util functions for installations on remote servers."""
from __future__ import annotations

import shlex
import subprocess
from collections.abc import Iterable
from pathlib import Path

from sparv.api import SparvErrorMessage, get_logger
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
    if isinstance(sqlfile, (str, Path)):
        sqlfile = [sqlfile]
    sqlfile = [Path(f) for f in sqlfile]
    file_total = len(sqlfile)

    for file_count, f in enumerate(sqlfile):
        if not f.exists():
            logger.error("Missing SQL file: %s", f)
        elif f.stat().st_size < 10:
            logger.info("Skipping empty file: %s (%d/%d)", f, file_count + 1, file_total)
        else:
            logger.info("Installing MySQL database: %s, source: %s (%d/%d)", db_name, f, file_count + 1, file_total)
            if not host:
                subprocess.check_call(
                    f"cat {shlex.quote(str(f))} | mysql {shlex.quote(db_name)}", shell=True
                )
            else:
                subprocess.check_call(
                    f"cat {shlex.quote(str(f))} | ssh {shlex.quote(host)} {shlex.quote(f'mysql {db_name}')}", shell=True
                )


def install_mysql_dump(host: str, db_name: str, tables: str | Iterable[str]) -> None:
    """Copy selected tables (including data) from local to remote MySQL database."""
    if isinstance(tables, str):
        tables = tables.split()
    logger.info("Copying MySQL database: %s, tables: %s", db_name, ", ".join(tables))
    subprocess.check_call(f'mysqldump {db_name} {" ".join(tables)} | ssh {host} "mysql {db_name}"', shell=True)


def install_svn(source_file: str | Path, svn_url: str) -> None:
    """Check in a file to a SVN repository.

    If the file is already in the repository, it will be deleted and added again.

    Args:
        source_file: The file to check in.
        svn_url: The URL to the SVN repository.

    Raises:
        SparvErrorMessage: If the source file does not exist, if svn_url is not set if it is not possible to list or
            delete the file in the SVN repository, or if it is not possible to import the file to the SVN repository.
    """
    source_file = Path(source_file)
    if not source_file.exists():
        raise SparvErrorMessage(f"Source file does not exist: {source_file}",
                                module="api.util.install", function="install_svn")

    # Check if svn_url is set
    if not svn_url:
        raise SparvErrorMessage("No SVN URL specified", module="api.util.install", function="install_svn")

    # Check if file exists in SVN repository and delete it (existing files cannot be updated in SVN)
    try:
        result = subprocess.run(["svn", "ls", svn_url], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logger.info("File exists in SVN repository, updating: %s", svn_url)
            subprocess.check_call(["svn", "delete", svn_url, "-m", "Deleting file with Sparv in order to update"])
    except subprocess.CalledProcessError as e:
        raise SparvErrorMessage(
            f"Failed to list or delete file in SVN repository: {e}", module="api.util.install", function="install_svn"
        ) from e

    # Import file to SVN
    try:
        logger.info("Importing file to SVN: %s", svn_url)
        subprocess.check_call(["svn", "import", str(source_file), svn_url, "-m", "Adding file with Sparv"])
    except subprocess.CalledProcessError as e:
        raise SparvErrorMessage(
            f"Failed to import file to SVN repository: {e}", module="api.util.install", function="install_svn"
        ) from e
