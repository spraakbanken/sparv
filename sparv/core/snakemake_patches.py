"""Temporarily patch Snakemake to reduce repeated work on large corpora.

Reuse successful script checks during workflow preparation and skip scanning job outputs when there are no until-file
targets.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path


@contextmanager
def cache_script_validation() -> Generator[None]:
    """Validate each static script once per DAG instead of reading it for every job.

    Snakemake's ScriptProcessor reads and checks a script for each job during preparation. Sparv's processor jobs all
    share `run_snake.py`. Without this patch, large corpora with many jobs would repeat the same checks and reads
    hundreds of thousands of times. This patch caches successful preflight validation.

    Snakemake still evaluates every job's parameters and uses its usual checks for scripts with dynamic paths.
    """
    # Import through the API first to avoid Snakemake's circular imports.
    from snakemake.api import SnakemakeApi  # noqa: F401, PLC0415
    from snakemake.dag import ScriptProcessor  # noqa: PLC0415
    from snakemake.jobs import Job  # noqa: PLC0415

    original = ScriptProcessor.process_job
    validated: dict[ScriptProcessor, set[tuple[str, str]]] = defaultdict(set)

    @wraps(original)
    def process_job(self: ScriptProcessor, job: Job) -> None:
        entry = job.rule.script
        if self.script_type != "script" or not job.is_script or not isinstance(entry, (str, Path)):
            original(self, job)
            return
        path = str(entry)
        if "{" in path or "}" in path:
            original(self, job)
            return

        # Relative paths are resolved against the rule's basedir. Identical spellings in different directories must
        # be validated separately.
        key = (str(job.rule.basedir), path)
        if key in validated[self]:
            # Evaluate this job's parameters and surface errors even when script validation is cached.
            _ = job.params
        else:
            original(self, job)
            validated[self].add(key)

    ScriptProcessor.process_job = process_job
    try:
        yield
    finally:
        ScriptProcessor.process_job = original


@contextmanager
def skip_unused_until_checks() -> Generator[None]:
    """Avoid scanning a job's output list when there are no until-file targets.

    Snakemake calls `in_until()` for each dependent of a finished job. Even with no until-file targets, Snakemake still
    iterates through the job's output list to check for matches. This patch skips that iteration when there are no
    until-file targets.
    """
    from snakemake.api import SnakemakeApi  # noqa: F401, PLC0415
    from snakemake.dag import DAG  # noqa: PLC0415
    from snakemake.jobs import Job  # noqa: PLC0415

    original = DAG.in_until

    @wraps(original)
    def in_until(self: DAG, job: Job) -> bool:
        if not self.untilfiles:
            return job.rule.name in self.untilrules
        return original(self, job)

    DAG.in_until = in_until
    try:
        yield
    finally:
        DAG.in_until = original
