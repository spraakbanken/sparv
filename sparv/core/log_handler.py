"""Handler for log messages.

This module handles logging for both the standard logging library and Snakemake, providing additional functionality for
progress tracking and internal messaging.

The LogHandler class is responsible for setting up the logging configuration, and contains most of the code for handling
log messages. It also provides a progress bar and additional features for enhanced logging capabilities. The logging in
this module uses a logger named "sparv_logging".

The Sparv modules (run in separate processes) get their logger using the `get_logger()` function, which returns a logger
("sparv") that communicates with the Sparv log handler (in the main thread) over a TCP socket, and the messages are then
handled by the "sparv_logging" logger.

Log messages from Snakemake are handled by the `log_handler()` method, which processes messages and updates the progress
bars. Some messages are printed to the console instead of being logged.
"""

from __future__ import annotations

import datetime
import logging
import logging.handlers
import pickle
import queue
import re
import socketserver
import struct
import threading
import time
from collections import OrderedDict, defaultdict
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path
from typing import Any

from pythonjsonlogger import jsonlogger
from rich import box, progress
from rich.control import Control, ControlType
from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text
from snakemake import logger

from sparv.core import io
from sparv.core.console import console
from sparv.core.misc import SparvErrorMessage
from sparv.core.paths import paths

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FORMAT_DEBUG = "%(asctime)s - %(name)s (%(process)d) - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"


class CurrentProgress:
    """Class to store current file and job for logging progress.

    These are set by setup_logging() and used by _log_progress().
    """

    current_file = None
    current_job = None


# Add internal logging level used for non-logging-related communication from child processes to log handler
INTERNAL = 100
logging.addLevelName(INTERNAL, "INTERNAL")


def _log_progress(
    self: logging.Logger, progress: int | None = None, advance: int | None = None, total: int | None = None
) -> None:
    """Log progress of task."""
    if self.isEnabledFor(INTERNAL):
        self._log(
            INTERNAL,
            "progress",
            (),
            extra={
                "progress": progress,
                "advance": advance,
                "total": total,
                "job": CurrentProgress.current_job,
                "file": CurrentProgress.current_file,
            },
        )


# Add progress function to logger
logging.progress = _log_progress
logging.Logger.progress = _log_progress

# Add logging level used for progress output (must be lower than INTERNAL)
PROGRESS = 90
logging.addLevelName(PROGRESS, "PROGRESS")

# Add logging level used for final messages when logging in JSON format, always displayed
FINAL = 80
logging.addLevelName(FINAL, "FINAL")


def _export_dirs(self: logging.Logger, dirs: list[str]) -> None:
    """Send list of export dirs to log handler."""
    if self.isEnabledFor(INTERNAL):
        self._log(INTERNAL, "export_dirs", (), extra={"export_dirs": dirs})


# Add log function to logger
logging.export_dirs = _export_dirs
logging.Logger.export_dirs = _export_dirs

# Messages from the Sparv core
messages = {
    "missing_configs": defaultdict(set),
    "missing_binaries": defaultdict(set),
    "missing_classes": defaultdict(set),
}

missing_annotations_msg = (
    "There can be many reasons for this. Please make sure that there are no problems with the "
    "corpus configuration file, like misspelled annotation names (including unintentional "
    "whitespace characters) or references to non-existent or implicit source annotations."
)


class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    """Handler for streaming logging requests.

    This handler receives logging records from a TCP socket and logs them using the Sparv logger.
    """

    def handle(self) -> None:
        """Handle multiple requests - each expected to be a 4-byte length followed by the LogRecord in pickle format."""
        data_length_bytes = 4
        while True:
            chunk = self.connection.recv(data_length_bytes)
            if len(chunk) < data_length_bytes:
                break
            slen = struct.unpack(">L", chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk += self.connection.recv(slen - len(chunk))
            obj = pickle.loads(chunk)
            record = logging.makeLogRecord(obj)
            self.handle_log_record(record)

    @staticmethod
    def handle_log_record(record: logging.LogRecord) -> None:
        """Handle log record."""
        sparv_logger = logging.getLogger("sparv_logging")
        sparv_logger.handle(record)


class LogLevelCounterHandler(logging.Handler):
    """Handler that counts the number of log messages per log level."""

    def __init__(self, count_dict: dict[str, int], *args: Any, **kwargs: Any) -> None:
        """Initialize handler.

        Args:
            count_dict: Dictionary to store the count of log messages per log level.
            args: Additional arguments.
            kwargs: Additional keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.levelcount = count_dict

    def emit(self, record: logging.LogRecord) -> None:
        """Increment level counter for each log message."""
        if record.levelno < FINAL:
            self.levelcount[record.levelname] += 1


class FileHandlerWithDirCreation(logging.FileHandler):
    """FileHandler which creates necessary directories when the first log message is handled."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record and create necessary directories if needed."""
        if self.stream is None:
            Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
        super().emit(record)


class InternalFilter(logging.Filter):
    """Filter out internal log messages."""

    @staticmethod
    def filter(record: logging.LogRecord) -> bool:
        """Filter out internal records.

        Args:
            record: Log record.

        Returns:
            True if record is not internal, False otherwise.
        """
        return record.levelno < INTERNAL


class ProgressInternalFilter(logging.Filter):
    """Filter out progress and internal log messages."""

    @staticmethod
    def filter(record: logging.LogRecord) -> bool:
        """Filter out progress and internal records.

        Args:
            record: Log record.

        Returns:
            True if record is not progress or internal, False otherwise.
        """
        return record.levelno < PROGRESS


class InternalLogHandler(logging.Handler):
    """Handler for internal log messages.

    Used to update the progress bar and collect export directories.
    """

    def __init__(self, export_dirs_list: set, progress_: progress.Progress, jobs: OrderedDict, job_ids: dict) -> None:
        """Initialize handler.

        Args:
            export_dirs_list: Set to be updated with export directories.
            progress_: Progress bar object.
            jobs: Dictionary of jobs.
            job_ids: Translation from (Sparv task name, source file) to Snakemake job ID.
        """
        self.export_dirs_list = export_dirs_list
        self.progress: progress.Progress = progress_
        self.jobs = jobs
        self.job_ids = job_ids
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        """Handle log record."""
        if record.msg == "export_dirs":
            self.export_dirs_list.update(record.export_dirs)
        elif record.msg == "progress":
            job_id = self.job_ids.get((record.job, record.file or ""))
            if job_id is not None:
                try:
                    if not self.jobs[job_id]["task"]:
                        self.jobs[job_id]["task"] = self.progress.add_task(
                            "",
                            start=bool(record.total),
                            completed=record.progress or record.advance or 0,
                            total=record.total or 100.0,
                        )
                    else:
                        if record.total:
                            self.progress.start_task(self.jobs[job_id]["task"])
                            self.progress.update(self.jobs[job_id]["task"], total=record.total)
                        if record.progress:
                            self.progress.update(self.jobs[job_id]["task"], completed=record.progress)
                        elif record.advance or not record.total:
                            self.progress.advance(self.jobs[job_id]["task"], advance=record.advance or 1)
                except KeyError:
                    pass


class ModifiedRichHandler(RichHandler):
    """RichHandler modified to print names instead of paths."""

    def emit(self, record: logging.LogRecord) -> None:
        """Replace path with name and call parent method."""
        record.pathname = record.name if record.name != "sparv_logging" else ""
        record.lineno = 0
        super().emit(record)


class ProgressWithTable(progress.Progress):
    """Progress bar with additional table."""

    def __init__(self, all_tasks: dict, current_tasks: OrderedDict, max_len: int, *args: Any, **kwargs: Any) -> None:
        """Initialize progress bar with table.

        Args:
            all_tasks: Dictionary of all tasks.
            current_tasks: Currently running tasks.
            max_len: Maximum length of task names.
            args: Additional arguments.
            kwargs: Additional keyword arguments.
        """
        self.all_tasks = all_tasks
        self.current_tasks = current_tasks
        self.task_max_len = max_len
        super().__init__(*args, **kwargs)

    def get_renderables(self) -> Iterable[progress.RenderableType]:
        """Get a number of renderables for the progress display.

        Yields:
            Renderables for the progress display.
        """
        # Progress bar
        yield self.make_tasks_table(self.tasks[:1])

        # Task table
        if self.all_tasks:
            rows = []
            elapsed_max_len = 7
            bar_col = progress.BarColumn(bar_width=20)
            for task in list(self.current_tasks.values()):  # Make a copy to avoid mutations while iterating
                elapsed = str(timedelta(seconds=round(time.time() - task["starttime"])))
                elapsed_max_len = max(len(elapsed), elapsed_max_len)
                try:
                    rows.append(
                        (
                            task["name"],
                            f"[dim]{task['file']}[/dim]",
                            bar_col(self._tasks[task["task"]]) if task["task"] else "",
                            elapsed,
                        )
                    )
                except KeyError:  # May happen if self._tasks has changed
                    pass

            table = Table(show_header=False, box=box.SIMPLE, expand=True)
            table.add_column("Task", no_wrap=True, min_width=self.task_max_len + 2, ratio=1)
            table.add_column("File", no_wrap=True)
            table.add_column("Bar", width=10)
            table.add_column(
                "Elapsed", no_wrap=True, width=elapsed_max_len, justify="right", style="progress.remaining"
            )
            table.add_row("[b]Task[/]", "[b]File[/]", "", "[default b]Elapsed[/]")
            for row in rows:
                table.add_row(*row)
            yield table


class QueueHandler(logging.Handler):
    """Custom logging handler that stores log records in a queue.

    This is used when Sparv is run as a library rather than a command-line tool.
    """

    def __init__(self, log_queue: queue.Queue) -> None:
        """Initialize handler."""
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        """Store log record in the queue."""
        self.log_queue.put(self.format(record))


class LogHandler:
    """Class providing a log handler for Snakemake."""

    icon = "\U0001f426"

    def __init__(
        self,
        progressbar: bool = True,
        log_level: str | None = None,
        log_file_level: str | None = None,
        simple: bool = False,
        stats: bool = False,
        pass_through: bool = False,
        dry_run: bool = False,
        keep_going: bool = False,
        json: bool = False,
        log_queue: queue.Queue | None = None,
        root_dir: str | None = None,
    ) -> None:
        """Initialize log handler.

        Args:
            progressbar: Set to False to disable progress bar. Enabled by default.
            log_level: Log level for logging to stdout.
            log_file_level: Log level for logging to file.
            simple: Set to True to show less info about currently running jobs.
            stats: Set to True to show stats after completion.
            pass_through: Let Snakemake's log messages pass through uninterrupted.
            dry_run: Set to True to print summary about jobs.
            keep_going: Set to True if the keepgoing flag is enabled for Snakemake.
            json: Set to True to enable JSON output.
            log_queue: Queue to store log messages.
            root_dir: Root directory for the corpus (if set using `--dir`).
        """
        self.use_progressbar = progressbar and console.is_terminal
        self.simple = simple or not console.is_terminal
        self.pass_through = pass_through
        self.dry_run = dry_run
        self.keep_going = keep_going
        self.json = json
        self.log_queue = log_queue
        self.log_level = log_level
        self.log_file_level = log_file_level
        self.log_filename = None
        self.log_levelcount = defaultdict(int)
        self.root_dir = root_dir
        self.finished = False
        self.handled_error = False
        self.messages = defaultdict(list)
        self.missing_configs_re = None
        self.missing_binaries_re = None
        self.missing_classes_re = None
        self.export_dirs = set()
        self.start_time = time.time()
        self.jobs = {}
        self.jobs_max_len = 0
        self.stats = stats
        self.stats_data = defaultdict(float)
        self.logger = None
        self.terminated = False

        # Progress bar related variables
        self.progress: progress.Progress | None = None
        self.bar: progress.TaskID | None = None
        self.bar_started: bool = False
        self.last_percentage = 0
        self.current_jobs = OrderedDict()
        self.job_ids = {}  # Translation from (Sparv task name, source file) to Snakemake job ID

        # Create a simple TCP socket-based logging receiver
        tcpserver = socketserver.ThreadingTCPServer(("localhost", 0), RequestHandlerClass=LogRecordStreamHandler)
        self.log_server = tcpserver.server_address

        # Start a thread with the server
        server_thread = threading.Thread(target=tcpserver.serve_forever)
        server_thread.daemon = True  # Exit the server thread when the main thread terminates
        server_thread.start()

        if self.use_progressbar:
            self.setup_bar()
        else:
            # When using progress bar, we must hold off on setting up logging until after the bar is initialized
            self.setup_loggers()

    def setup_loggers(self) -> None:
        """Set up log handlers for logging to stdout and log file."""
        if not self.log_level or not self.log_file_level:
            return

        self.logger = logging.getLogger("sparv_logging")
        internal_filter = InternalFilter()
        progress_internal_filter = ProgressInternalFilter()

        # Set logger to the lowest selected log level, but not higher than warning (we still want to count warnings)
        self.logger.setLevel(
            min(
                logging.WARNING, getattr(logging, self.log_level.upper()), getattr(logging, self.log_file_level.upper())
            )
        )

        # stdout logger or log queue
        if self.log_queue:
            # Used when running as a library
            stream_handler = QueueHandler(self.log_queue)
        elif self.json:
            stream_handler = logging.StreamHandler()
        else:
            stream_handler = ModifiedRichHandler(enable_link_path=False, rich_tracebacks=True, console=console)

        stream_handler.setLevel(self.log_level.upper())
        stream_handler.addFilter(internal_filter)
        stream_handler.addFilter(lambda record: not getattr(record, "to_file", False))

        if self.json:
            stream_formatter = json_formatter = jsonlogger.JsonFormatter(
                LOG_FORMAT_DEBUG, rename_fields={"asctime": "time", "levelname": "level"}
            )
        else:
            stream_formatter = logging.Formatter(
                "%(message)s" if stream_handler.level > logging.DEBUG else "(%(process)d) - %(message)s",
                datefmt=TIME_FORMAT,
            )

        stream_handler.setFormatter(stream_formatter)
        self.logger.addHandler(stream_handler)

        # File logger
        self.log_filename = f"{datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S.%f')}.log"
        file_handler = FileHandlerWithDirCreation(
            Path(self.root_dir or Path().cwd()) / paths.log_dir / self.log_filename,
            mode="w",
            encoding="UTF-8",
            delay=True,
        )
        file_handler.setLevel(self.log_file_level.upper())
        file_handler.addFilter(progress_internal_filter)
        file_handler.addFilter(lambda record: not getattr(record, "to_stdout", False))

        if self.json:
            file_formatter = json_formatter
        else:
            file_formatter = logging.Formatter(LOG_FORMAT if file_handler.level > logging.DEBUG else LOG_FORMAT_DEBUG)

        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Level counter
        levelcount_handler = LogLevelCounterHandler(self.log_levelcount)
        levelcount_handler.setLevel(logging.WARNING)
        self.logger.addHandler(levelcount_handler)

        # Internal log handler
        internal_handler = InternalLogHandler(self.export_dirs, self.progress, self.current_jobs, self.job_ids)
        internal_handler.setLevel(INTERNAL)
        self.logger.addHandler(internal_handler)

    def setup_bar(self) -> None:
        """Initialize the progress bar but don't start it yet."""
        console.print()
        progress_layout = [
            progress.SpinnerColumn("dots2"),
            progress.BarColumn(bar_width=40 if self.simple else None),
            progress.TextColumn("[progress.description]{task.description}"),
            progress.TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            progress.TextColumn("[progress.remaining]{task.completed} of {task.total} tasks"),
            progress.TextColumn("{task.fields[text]}"),
        ]
        if self.simple:
            self.progress = progress.Progress(*progress_layout, console=console)
        else:
            self.progress = ProgressWithTable(
                self.jobs, self.current_jobs, self.jobs_max_len, *progress_layout, console=console
            )
        self.progress.start()
        self.bar = self.progress.add_task(self.icon, start=False, total=0, text="[dim]Preparing...[/dim]")

        # Logging needs to be set up after the bar, to make use of its print hook
        self.setup_loggers()

    def start_bar(self, total: int) -> None:
        """Start progress bar.

        Args:
            total: Total number of tasks.
        """
        self.progress.update(self.bar, total=total)
        self.progress.start_task(self.bar)
        self.bar_started = True

    def info(self, msg: str) -> None:
        """Print info message.

        Args:
            msg: Message to print.
        """
        if self.json:
            self.logger.log(FINAL, msg)
        else:
            console.print(Text(msg, style="green"))

    def warning(self, msg: str) -> None:
        """Print warning message.

        Args:
            msg: Message to print.
        """
        if self.json:
            self.logger.log(FINAL, msg)
        else:
            console.print(Text(msg, style="yellow"))

    def error(self, msg: str) -> None:
        """Print error message.

        Args:
            msg: Message to print.
        """
        if self.json:
            self.logger.log(FINAL, msg)
        else:
            console.print(Text(msg, style="red"))

    def log_handler(self, msg: dict) -> None:
        """Log handler for Snakemake displaying a progress bar.

        Args:
            msg: Log message dictionary.

        Raises:
            BrokenPipeError: If a missing config variable is detected. This stops Snakemake.
        """

        def missing_config_message(source: str) -> None:
            """Create error message when config variables are missing."""
            variables = messages["missing_configs"][source]
            message = "The following config variable{} need{} to be set:\n • {}".format(
                *("s", "") if len(variables) > 1 else ("", "s"), "\n • ".join(variables)
            )
            self.messages["error"].append((source, message))

        def missing_binary_message(source: str) -> None:
            """Create error message when binaries are missing."""
            binaries = messages["missing_binaries"][source]
            message = "The following executable{} {} needed but could not be found:\n • {}".format(
                *("s", "are") if len(binaries) > 1 else ("", "is"), "\n • ".join(binaries)
            )
            self.messages["error"].append((source, message))

        def missing_class_message(source: str, classes: list[str] | None = None) -> None:
            """Create error message when class variables are missing."""
            variables = messages["missing_classes"][source] or classes
            message = "The following class{} need{} to be set:\n • {}".format(
                *("es", "") if len(variables) > 1 else ("", "s"), "\n • ".join(variables)
            )

            if "text" in variables:
                message += (
                    "\n\nNote: The 'text' class can also be set using the configuration variable "
                    "'import.text_annotation', but only if it refers to an annotation from the "
                    "source files."
                )

            self.messages["error"].append((source, message))

        def missing_annotations_or_files(source: str, files: str) -> None:
            """Create error message when annotations or other files are missing."""
            errmsg = []
            missing_annotations = []
            missing_other = []
            for f in map(Path, files.splitlines()):
                if paths.work_dir in f.parents:
                    # If the missing file is within the Sparv workdir, it is probably an annotation
                    f_rel = f.relative_to(paths.work_dir)
                    *_, annotation, attr = f_rel.parts
                    if attr == io.SPAN_ANNOTATION:
                        missing_annotations.append((annotation,))
                    else:
                        missing_annotations.append((annotation, attr))
                else:
                    missing_other.append(str(f))
            if missing_annotations:
                errmsg = [
                    "The following input annotation{} {} missing:\n • {}\n".format(
                        "s" if len(missing_annotations) > 1 else "",
                        "are" if len(missing_annotations) > 1 else "is",
                        "\n • ".join(
                            ":".join(ann) if len(ann) == 2 else ann[0]  # noqa: PLR2004
                            for ann in missing_annotations
                        ),
                    )
                ]
            if missing_other:
                if errmsg:
                    errmsg.append("\n")
                errmsg.append(
                    "The following input file{} {} missing:\n • {}\n".format(
                        "s" if len(missing_other) > 1 else "",
                        "are" if len(missing_other) > 1 else "is",
                        "\n • ".join(missing_other),
                    )
                )
            if errmsg:
                errmsg.append("\n" + missing_annotations_msg)
            self.messages["error"].append((source, "".join(errmsg)))

        level = msg["level"]

        if level == "run_info":
            # Parse list of jobs do to and total job count
            lines = msg["msg"].splitlines()[3:]
            total_jobs = lines[-1].split()[1]
            for j in lines[:-1]:
                job, count = j.split()
                if ":" in job and "::" not in job:
                    job += "*"  # Differentiate entrypoints from actual rules in the list
                self.jobs[job.replace("::", ":")] = int(count)
            self.jobs_max_len = max(map(len, self.jobs))

            # Get number of jobs and start progress bar
            if self.use_progressbar and not self.bar_started and total_jobs.isdigit():
                self.start_bar(int(total_jobs))

        elif level == "progress":
            if self.use_progressbar:
                # Advance progress
                self.progress.advance(self.bar)

            # Print regular progress updates if output is not a terminal (i.e. doesn't support the progress bar) or
            # output format is JSON
            elif self.logger and (self.json or not console.is_terminal):
                percentage = (100 * msg["done"]) // msg["total"]
                if percentage > self.last_percentage:
                    self.last_percentage = percentage
                    self.logger.log(PROGRESS, f"{percentage}%")  # noqa: G004

            if msg["done"] == msg["total"]:
                self.stop()

        elif level == "job_info" and self.use_progressbar:
            if msg["msg"] and self.bar is not None:
                # Update progress status message
                self.progress.update(self.bar, text=msg["msg"] if self.simple else "")

                if not self.simple:
                    file = msg["wildcards"].get("file", "")
                    if file.startswith(str(paths.work_dir)):
                        file = file[len(str(paths.work_dir)) + 1 :]

                    self.current_jobs[msg["jobid"]] = {
                        "task": None,
                        "name": msg["msg"],
                        "starttime": time.time(),
                        "file": file,
                    }

                    self.job_ids[msg["msg"], file] = msg["jobid"]

        elif (
            (level == "job_finished" or (level == "job_error" and self.keep_going))
            and self.use_progressbar
            and msg["jobid"] in self.current_jobs
        ):
            this_job = self.current_jobs[msg["jobid"]]
            if self.stats:
                self.stats_data[this_job["name"]] += time.time() - this_job["starttime"]
            if this_job["task"]:
                self.progress.remove_task(this_job["task"])
            self.job_ids.pop((this_job["name"], this_job["file"]), None)
            self.current_jobs.pop(msg["jobid"], None)
            if level == "job_error" and msg.get("msg"):
                self.messages["unhandled_error"].append(msg)

        elif level == "info":
            if self.pass_through:
                self.info(msg["msg"])
            elif msg["msg"].startswith("Nothing to be done"):
                self.info("Nothing to be done.")
            elif msg["msg"].startswith("Will exit after finishing currently running jobs") and not self.terminated:
                self.logger.log(logging.INFO, "Will exit after finishing currently running jobs")
                self.terminated = True

        elif level == "debug":
            # SparvErrorMessage in rules causes another exception (RuleException) to be raised, so skip those
            if "SparvErrorMessage" in msg["msg"] and "RuleException" not in msg["msg"]:
                # SparvErrorMessage exception from pipeline core
                # Parse error message
                message = re.search(
                    rf"{SparvErrorMessage.start_marker}([^\n]*)\n([^\n]*)\n(.*?){SparvErrorMessage.end_marker}",
                    msg["msg"],
                    flags=re.DOTALL,
                )
                if message:
                    module, function, error_message = message.groups()
                    error_source = f"{module}:{function}" if module and function else None
                    self.messages["error"].append((error_source, error_message))
                    self.handled_error = True
            elif "exit status 123" in msg["msg"]:
                # Exit status 123 means a Sparv module caused an exception, either a SparvErrorMessage exception, or
                # an unexpected exception. Either way, the error message has already been logged, so it doesn't need to
                # be printed again.
                self.handled_error = True
            elif "died with <Signals." in msg["msg"]:
                # The run_snake.py subprocess was killed
                signal_match = re.search(r"died with <Signals.([A-Z]+)", msg["msg"])
                self.messages["error"].append(
                    (
                        None,
                        f"A Sparv subprocess was unexpectedly killed due to receiving a {signal_match[1]} signal.",
                    )
                )
                self.handled_error = True
        elif level == "error":
            if self.pass_through:
                self.messages["unhandled_error"].append(msg)
                return
            handled = False

            # Errors due to missing config variables or binaries leading to missing input files
            if "MissingInputException" in msg["msg"]:
                msg_contents = re.search(r" for rule (\S+):\n.*affected files:\n(.+)", msg["msg"], flags=re.DOTALL)
                rule_name, filelist = msg_contents.groups()
                rule_name = rule_name.replace("::", ":")
                if self.missing_configs_re.search(filelist):
                    missing_config_message(rule_name)
                elif self.missing_binaries_re.search(filelist):
                    missing_binary_message(rule_name)
                elif self.missing_classes_re.search(filelist):
                    missing_class_message(rule_name, self.missing_classes_re.findall(filelist))
                else:
                    missing_annotations_or_files(rule_name, filelist)
                handled = True

            # Missing output files
            elif "MissingOutputException" in msg["msg"]:
                msg_contents = re.search(r"Missing files after .*?:\n(.+)", msg["msg"], flags=re.DOTALL)
                missing_files = "\n • ".join(msg_contents[1].strip().splitlines())
                message = (
                    "The following output files were expected but are missing:\n"
                    f" • {missing_files}\n{missing_annotations_msg}"
                )
                self.messages["error"].append((None, message))
                handled = True
            elif "Exiting because a job execution failed." in msg["msg"]:
                pass
            elif "run_snake.py' returned non-zero exit status 1." in msg["msg"]:
                handled = True
            elif "Error: Directory cannot be locked." in msg["msg"]:
                message = (
                    "Directory cannot be locked. Please make sure that no other Sparv instance is currently "
                    "processing this corpus. If you are sure that no other Sparv instance is using this "
                    "directory, run 'sparv run --unlock' to remove the lock."
                )
                self.messages["error"].append((None, message))
                handled = True

            # Unhandled errors
            if not handled:
                self.messages["unhandled_error"].append(msg)
            else:
                self.handled_error = True

        elif level in {"warning", "job_error"}:
            # Save other errors and warnings for later
            if msg.get("msg"):
                self.messages["unhandled_error"].append(msg)

        elif level == "dag_debug" and "job" in msg:
            # Create regular expressions for searching for missing config variables or binaries
            if self.missing_configs_re is None:
                all_configs = {v for varlist in messages["missing_configs"].values() for v in varlist}
                self.missing_configs_re = re.compile(r"\[({})]".format("|".join(all_configs)))

            if self.missing_binaries_re is None:
                all_binaries = {b for binlist in messages["missing_binaries"].values() for b in binlist}
                self.missing_binaries_re = re.compile(r"^({})$".format("|".join(all_binaries)), flags=re.MULTILINE)

            if self.missing_classes_re is None:
                all_classes = {v for varlist in messages["missing_classes"].values() for v in varlist}
                self.missing_classes_re = re.compile(r"<({})>".format("|".join(all_classes)))

            # Check the rules selected for the current operation, and see if any is unusable due to missing configs
            if msg["status"] == "selected":
                job_name = str(msg["job"]).replace("::", ":")
                if job_name in messages["missing_configs"]:
                    missing_config_message(job_name)
                    self.handled_error = True
                    # We need to stop Snakemake by raising an exception, and BrokenPipeError is the only exception
                    # not leading to a full traceback being printed (due to Snakemake's handling of exceptions)
                    raise BrokenPipeError

    def stop(self) -> None:
        """Stop the progress bar and output any messages."""
        # Make sure this is only run once
        if self.finished:
            return

        # Stop progress bar
        if self.bar is not None:
            if self.bar_started:
                # Add message about elapsed time
                elapsed = round(time.time() - self.start_time)
                self.progress.update(self.bar, text=f"Total time: {timedelta(seconds=elapsed)}")
            else:
                # Hide bar if it was never started
                self.progress.update(self.bar, visible=False)

            # Stop bar
            self.progress.stop()
            if not self.simple and self.bar_started:
                # Clear table header from screen
                console.control(
                    Control(
                        ControlType.CARRIAGE_RETURN, *((ControlType.CURSOR_UP, 1), (ControlType.ERASE_IN_LINE, 2)) * 2
                    )
                )

        self.finished = True

        # Execution failed but we handled the error
        if self.handled_error:
            # Print any collected core error messages
            if self.messages["error"]:
                errmsg = [f"Sparv exited with the following error message{'s' if len(self.messages) > 1 else ''}:"]
                for message in self.messages["error"]:
                    error_source, msg = message
                    error_source = f"[{error_source}]\n" if error_source else ""
                    errmsg.append(f"\n{error_source}{msg}")
                self.error("\n".join(errmsg))
            elif self.log_filename:
                # Errors from modules have already been logged to both stdout and the log file
                self.error(
                    f"Job execution failed. See log messages above or {paths.log_dir / self.log_filename} for details."
                )
            else:
                # Errors from modules have already been logged to stdout
                self.error("Job execution failed. See log messages above for details.")
        # Unhandled errors
        elif self.messages["unhandled_error"]:
            for error in self.messages["unhandled_error"]:
                errmsg = ["An unexpected error occurred."]
                if self.log_level and logging._nameToLevel[self.log_level.upper()] > logging.DEBUG:
                    errmsg[0] += (
                        f" For more details, please check '{paths.log_dir / self.log_filename}', or rerun Sparv "
                        "with the '--log debug' argument.\n"
                    )
                    if error.get("msg"):
                        # Show only a summary of the error
                        # Parsing is based on the format in format_error() in snakemake/exceptions.py
                        error_lines = error["msg"].splitlines()
                        if " in file " in error_lines[0]:
                            errmsg.append(error_lines[0].split(" in file ")[0] + ":")
                            for line in error_lines[1:]:
                                if line.startswith("  File "):
                                    break
                                errmsg.append(line)
                else:
                    errmsg.append("")
                    errmsg.append(error.get("msg") or "An unknown error occurred.")
                self.error("\n".join(errmsg))
                # Always log full error message to file, no matter the log level
                self.logger.error(error.get("msg") or "An unknown error occurred.", extra={"to_file": True})
        else:
            spacer = ""
            if self.export_dirs:
                spacer = "\n"
                self.info(
                    "The exported files can be found in the following location{}:\n • {}".format(
                        "s" if len(self.export_dirs) > 1 else "", "\n • ".join(sorted(self.export_dirs))
                    )
                )

            if self.stats_data:
                spacer = ""
                table = Table(show_header=False, box=box.SIMPLE)
                table.add_column("Task", no_wrap=True, min_width=self.jobs_max_len + 2, ratio=1)
                table.add_column("Time taken", no_wrap=True, justify="right", style="progress.remaining")
                table.add_column("Percentage", no_wrap=True, justify="right")
                table.add_row("[b]Task[/]", "[default b]Time taken[/]", "[b]Percentage[/b]")
                total_time = sum(self.stats_data.values())
                for task, elapsed in sorted(self.stats_data.items(), key=lambda x: -x[1]):
                    table.add_row(task, str(timedelta(seconds=round(elapsed))), f"{100 * elapsed / total_time:.1f}%")
                console.print(table)

            if self.log_levelcount:
                # Errors or warnings were logged but execution finished anyway. Notify user of potential problems.
                problems = []
                if self.log_levelcount["ERROR"]:
                    problems.append(
                        f"{self.log_levelcount['ERROR']} error{'s' if self.log_levelcount['ERROR'] > 1 else ''}"
                    )
                if self.log_levelcount["WARNING"]:
                    problems.append(
                        f"{self.log_levelcount['WARNING']} warning{'s' if self.log_levelcount['WARNING'] > 1 else ''}"
                    )
                self.warning(
                    f"{spacer}Job execution finished but {' and '.join(problems)} occurred. See log messages "
                    f"above or {paths.log_dir / self.log_filename} for details."
                )
            elif self.dry_run:
                console.print("The following tasks were scheduled but not run:")
                table = Table(show_header=False, box=box.SIMPLE)
                table.add_column(justify="right")
                table.add_column()
                for job in self.jobs:
                    table.add_row(str(self.jobs[job]), job)
                table.add_row()
                table.add_row(str(sum(self.jobs.values())), "Total number of tasks")
                console.print(table)

            if self.terminated:
                self.info(f"{spacer}Sparv was stopped by a TERM signal")

    @staticmethod
    def cleanup() -> None:
        """Remove Snakemake log files."""
        snakemake_log_file = logger.get_logfile()
        if snakemake_log_file is not None:
            log_file = Path(snakemake_log_file)
            if log_file.is_file():
                try:
                    log_file.unlink()
                except PermissionError:
                    pass


def setup_logging(
    log_server: tuple[str | bytes | bytearray, int],
    log_level: str = "warning",
    log_file_level: str = "warning",
    file: str | None = None,
    job: str | None = None,
) -> None:
    """Set up logging with socket handler.

    This is used to send log messages from child processes (e.g. Sparv modules) to the main process over a socket.

    Args:
        log_server: Tuple with host and port for logging server.
        log_level: Log level for logging to stdout.
        log_file_level: Log level for logging to file.
        file: Source file name for current job.
        job: Current task name.
    """
    # Set logger to use the lowest selected log level, but never higher than warning (we still want to count warnings)
    log_level = min(logging.WARNING, getattr(logging, log_level.upper()), getattr(logging, log_file_level.upper()))
    socket_logger = logging.getLogger("sparv")
    socket_logger.setLevel(log_level)
    socket_handler = logging.handlers.SocketHandler(*log_server)
    socket_logger.addHandler(socket_handler)
    CurrentProgress.current_file = file
    CurrentProgress.current_job = job
