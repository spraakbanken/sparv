"""System utility functions."""
from __future__ import annotations

import errno
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from sparv.api import SparvErrorMessage, get_logger
from sparv.core.paths import paths

logger = get_logger(__name__)


def kill_process(process: subprocess.Popen) -> None:
    """Kill a process, and ignore the error if it is already dead.

    Args:
        process: The process to kill.

    Raises:
        OSError: If an error occurs while killing the process.
    """
    try:
        process.kill()
    except OSError as exc:
        if exc.errno == errno.ESRCH:  # No such process
            pass
        else:
            raise


def clear_directory(path: str | Path) -> None:
    """Create a new empty directory at the given path, and remove its contents if it already exists.

    Args:
        path: The path to the directory.
    """
    shutil.rmtree(path, ignore_errors=True)
    Path(path).mkdir(parents=True, exist_ok=True)


def call_java(
    jar: str,
    arguments: list | tuple,
    options: list | tuple = (),
    stdin: str = "",
    search_paths: list | tuple = (),
    encoding: str | None = None,
    verbose: bool = False,
    return_command: bool = False
) -> tuple[str, str]:
    """Call java with a jar file, command line arguments and stdin.

    Args:
        jar: The jar file to run.
        arguments: List of arguments to pass to the jar.
        options: List of options to pass to java.
        stdin: Input to pass to the process.
        search_paths: List of paths where to look for the jar file.
        encoding: Encoding to use for stdin and stdout.
        verbose: If True, pipe stderr to stderr in the terminal, instead of returning it.
        return_command: If True, return the process instead of stdout and stderr.

    Returns:
        A tuple with stdout and stderr, or the process if return_command is True.
        If verbose is True, stderr is an empty string.
    """
    assert isinstance(arguments, (list, tuple))
    assert isinstance(options, (list, tuple))
    jarfile = find_binary(jar, search_paths, executable=False)
    java_executable = "java"
    # If JAVA_HOME is set, try to find java there
    if java_home := os.getenv("JAVA_HOME"):
        java_executable = Path(java_home) / "bin" / "java"
        if not java_executable.is_file():
            java_executable = "java"

    # Convert tuple arguments to "a=b"
    arguments = [f"{a[0]}={a[1]}" if isinstance(a, tuple) else a for a in arguments]
    java_args = [*options, "-jar", jarfile, *arguments]
    return call_binary(
        str(java_executable),
        arguments=java_args,
        stdin=stdin,
        search_paths=search_paths,
        encoding=encoding,
        verbose=verbose,
        return_command=return_command,
    )


def call_binary(
    name: str,
    arguments: list | tuple = (),
    stdin: str | list | tuple = "",
    raw_command: str | None = None,
    search_paths: list | tuple = (),
    encoding: str | None = None,
    verbose: bool = False,
    use_shell: bool = False,
    allow_error: bool = False,
    return_command: bool = False
) -> tuple[str, str] | subprocess.Popen:
    """Call a binary with arguments and stdin, return a pair (stdout, stderr) or the process.

    Args:
        name: Name of the binary to call.
        arguments: List of arguments to pass to the binary.
        stdin: Input to pass to the process.
        raw_command: Raw command to execute (implies use_shell=True).
        search_paths: List of paths where to look for the binary.
        encoding: Encoding to use for stdin and stdout.
        verbose: If True, pipe stderr to stderr in the terminal, instead of returning it.
        use_shell: If True, execute the command through the shell.
        allow_error: If True, do not raise an error if the binary returns a non-zero exit code.
        return_command: If True, return the process instead of stdout and stderr.

    Returns:
        A tuple with stdout and stderr, or the process if return_command is True.
        If verbose is True, stderr is an empty string.

    Raises:
        OSError: If an error occurs while calling the binary.
    """
    assert isinstance(arguments, (list, tuple))
    assert isinstance(stdin, (str, list, tuple))

    binary = find_binary(name, search_paths, raise_error=True)
    if raw_command:
        use_shell = True
        command = raw_command % binary
        if arguments:
            command = " ".join([command, *arguments])
    else:
        command = [binary] + [str(a) for a in arguments]
    if isinstance(stdin, (list, tuple)):
        stdin = "\n".join(stdin)
    if encoding is not None and isinstance(stdin, str):
        stdin = stdin.encode(encoding)
    logger.info("CALL: %s", " ".join(str(c) for c in command) if not raw_command else command)
    command = subprocess.Popen(
        command,
        shell=use_shell,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=(None if verbose else subprocess.PIPE),
        close_fds=False,
    )
    if return_command:
        return command
    stdout, stderr = command.communicate(stdin)
    if not allow_error and command.returncode:
        if stdout:
            logger.info(stdout.decode())
        if stderr:
            logger.warning(stderr.decode())
        raise OSError(f"{binary} returned error code {command.returncode:d}")
    if encoding:
        stdout = stdout.decode(encoding)
        if stderr:
            stderr = stderr.decode(encoding)
    return stdout, stderr


def find_binary(
    name: str | list[str],
    search_paths: list | tuple = (),
    executable: bool = True,
    allow_dir: bool = False,
    raise_error: bool = False
) -> str | None:
    """Search for the binary for a program.

    Args:
        name: Name of the binary, either a string or a list of strings with alternative names.
        search_paths: List of paths where to look, in addition to the environment variable PATH.
        executable: Set to False to not fail when binary is not executable.
        allow_dir: Set to True to allow the target to be a directory instead of a file.
        raise_error: Raise error if binary could not be found.

    Returns:
        Path to binary, or None if not found.

    Raises:
        SparvErrorMessage: If raise_error is True and the binary could not be found.
    """
    if isinstance(name, str):
        name = [name]
    name = list(map(os.path.expanduser, name))
    search_paths = [*list(search_paths), ".", paths.bin_dir, *os.getenv("PATH").split(":")]
    search_paths = list(map(os.path.expanduser, search_paths))

    # Use absolute paths or 'which' first
    for binary in name:
        binary_path = Path(binary)
        if binary_path.parent:
            # If absolute path, use if executable exists
            if (binary_path.is_absolute() and binary_path.is_file()) or (allow_dir and binary_path.is_dir()):
                if executable and not allow_dir:
                    assert os.access(binary_path, os.X_OK), f"Binary is not executable: {binary_path}"
                return str(binary_path)
            # Skip any relative paths in this step
            continue
        path_to_bin = shutil.which(binary)
        if path_to_bin:
            return path_to_bin

    # Look for file in paths
    for directory in search_paths:
        for binary in name:
            path_to_bin = Path(directory) / binary
            if path_to_bin.is_file() or (allow_dir and path_to_bin.is_dir()):
                if executable and not allow_dir:
                    assert os.access(path_to_bin, os.X_OK), f"Binary is not executable: {path_to_bin}"
                return path_to_bin

    if raise_error:
        err_msg = f"Couldn't find binary: {name[0]}\nSearched in: {', '.join(search_paths)}\n"
        if len(name) > 1:
            err_msg += f"for binary names: {', '.join(name)}"
        raise SparvErrorMessage(err_msg)
    return None


def rsync(local: str | Path, host: str | None, remote: str | Path) -> None:
    """Transfer files and/or directories using rsync.

    When syncing a directory, extraneous files in the destination directory are deleted, and it is always the contents
    of the source directory that are synced, not the directory itself (i.e. the rsync source directory is always
    suffixed with a slash).

    Args:
        local: The file or directory to transfer.
        host: The remote host to transfer to. Set to None to transfer locally.
        remote: The destination path (file or directory).
    """
    assert local and remote, "Both 'local' and 'remote' must be set."  # noqa: PT018
    remote_dir = os.path.dirname(remote)  # noqa: PTH120 - pathlib doesn't handle ending slash

    if Path(local).is_dir():
        logger.info("Copying directory: %s => %s%s", local, host + ":" if host else "", remote)
        args = ["--recursive", "--delete", f"{local}/"]
    else:
        logger.info("Copying file: %s => %s%s", local, host + ":" if host else "", remote)
        args = [local]

    if host:
        subprocess.check_call(["ssh", host, f"mkdir -p {shlex.quote(remote_dir)}"])
        subprocess.check_call(["rsync", *args, f"{host}:{remote}"])
    else:
        subprocess.check_call(["mkdir", "-p", remote_dir])
        subprocess.check_call(["rsync", *args, remote])


def remove_path(path: str | Path, host: str | None = None) -> None:
    """Remove a file or directory, either locally or remotely.

    Args:
        path: The file or directory to remove.
        host: The remote host to remove from. Leave empty to remove locally.
    """
    assert path, "'path' must not be empty."
    if host:
        subprocess.check_call(["ssh", host, f"rm -rf {shlex.quote(str(path))}"])
    else:
        p = Path(path)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)


def gpus(reorder: bool = True) -> list[int] | None:
    """Get a list of available GPUs, sorted by free memory in descending order.

    Only works for NVIDIA GPUs, and requires the `nvidia-smi` utility to be installed.

    If `reorder` is `True` (default), the GPUs are renumbered according to the order specified in the environment
    variable `CUDA_VISIBLE_DEVICES`. For example, if `CUDA_VISIBLE_DEVICES=1,0`, and the GPUs with most free memory are
    0, 1, the function will return `[1, 0]`.

    This is needed for PyTorch, which uses the GPU indices as specified in `CUDA_VISIBLE_DEVICES`, not the actual GPU
    indices. In the example above, PyTorch would consider GPU 1 as GPU 0 and GPU 0 as GPU 1.

    Args:
        reorder: Whether to renumber the GPUs according to the order in the environment variable
            `CUDA_VISIBLE_DEVICES`.

    Returns:
        A list of GPU indices, or None if no GPUs are available or if the nvidia-smi command failed.
    """
    try:
        cmd = ["nvidia-smi", "--query-gpu=index,memory.free", "--format=csv"]
        memory_info = subprocess.check_output(cmd).decode().splitlines()[1:]
        # Sort by free memory in descending order
        gpus = sorted(
            ((int(free_mem.split()[0]), int(index)) for index, free_mem in (line.split(",") for line in memory_info)),
            reverse=True,
        )
        gpus = [gpu[1] for gpu in gpus]
        if reorder:
            cuda_visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES")
            if cuda_visible_devices:
                cuda_visible_devices = [int(i) for i in cuda_visible_devices.split(",")]
                # Reorder GPUs according to CUDA_VISIBLE_DEVICES
                gpus = [cuda_visible_devices.index(gpu) for gpu in gpus if gpu in cuda_visible_devices]
        return gpus
    except Exception:
        return None
