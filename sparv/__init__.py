"""Main Sparv package."""

from __future__ import annotations

import queue
import threading
from collections.abc import Generator
from contextlib import redirect_stdout
from io import StringIO

__version__ = "5.4.0.dev0"


class SparvCall:
    """Context manager for calling the Sparv pipeline."""

    def __init__(self, args: list[str] | None = None) -> None:
        """Initialize the context manager and start the Sparv pipeline in a separate thread."""
        self.args = args
        self.log_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.thread = threading.Thread(target=self._run_main)
        self.thread.start()
        self._log_generator = self._create_log_generator()

    def _run_main(self) -> None:
        """Run the main function and store its return value in the result queue."""
        from sparv.__main__ import main  # noqa: PLC0415

        # Log messages are automatically sent to the log queue, but we also need to capture stdout
        stdout_buffer = StringIO()
        try:
            with redirect_stdout(stdout_buffer):
                result = main(self.args, self.log_queue)
            self.result_queue.put(result)
        except Exception as e:
            self.result_queue.put(e)
        finally:
            # Send captured stdout to the log queue
            stdout_buffer.seek(0)
            self.log_queue.put(stdout_buffer.read())
            self.log_queue.put(None)

    def __enter__(self) -> SparvCall:
        """Enter the context and return the SparvCall instance.

        Returns:
            The SparvCall instance.
        """
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: object | None
    ) -> None:
        """Exit the context and ensure the thread finishes."""
        self.thread.join()

    def _create_log_generator(self) -> Generator[str, None, None]:
        """Create a generator that yields log messages from the queue.

        Yields:
            Log messages from the queue.
        """
        while self.thread.is_alive() or not self.log_queue.empty():
            try:
                record = self.log_queue.get(timeout=1)
                if record is None:
                    break
                yield record
            except queue.Empty:
                continue

    def __iter__(self) -> SparvCall:
        """Return the SparvCall instance as an iterator."""
        return self

    def __next__(self) -> str:
        """Return the next log message from the generator."""
        return next(self._log_generator)

    def get_return_value(self) -> bool:
        """Retrieve the return value of the pipeline call.

        Returns:
            True if the pipeline call was successful, False otherwise.

        Raises:
            RuntimeError: If the thread is still running or no return value is available.
            Any exception that occurred during the pipeline call.
        """
        if not self.thread.is_alive() and not self.result_queue.empty():
            result = self.result_queue.get()
            if isinstance(result, Exception):
                raise result  # Re-raise the exception if one occurred
            return result
        raise RuntimeError("The thread is still running or no return value is available.")

    def wait(self) -> bool:
        """Wait for the thread to finish without consuming logs, and return the return value.

        Returns:
            True if the pipeline call was successful, False otherwise.

        Raises:
            RuntimeError: If the thread is still running or no return value is available.
            Any exception that occurred during the pipeline call.
        """  # noqa: DOC502
        self.thread.join()
        return self.get_return_value()


def call(args: list[str] | None = None, /) -> SparvCall:
    """Call the Sparv pipeline.

    This function returns a context manager that can be used to either iterate over log messages
    or simply wait for the pipeline to finish.

    The list of arguments are the same as the arguments you would pass to the command-line interface,
    e.g. `["run", "xml_export:pretty", "--log"]`.

    Args:
        args: List of arguments to pass to the Sparv pipeline.

    Returns:
        A context manager for managing the Sparv pipeline call.
    """
    return SparvCall(args)
