"""Paths used by Sparv."""

from __future__ import annotations

import os
from pathlib import Path

import appdirs
import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


def read_sparv_config() -> dict:
    """Get Sparv data path from config file.

    Returns:
        dict: Sparv config data.
    """
    data = {}
    if sparv_config_file.is_file():
        try:
            with sparv_config_file.open(encoding="utf-8") as f:
                data = yaml.load(f, Loader=SafeLoader)
        except Exception:
            data = {}
    return data


def get_data_path(subpath: str | Path = "") -> Path | None:
    """Get location of directory containing Sparv models, binaries and other files.

    Args:
        subpath: Optional subpath to append to data dir.

    Returns:
        Path to data dir or data dir subpath.
    """
    global data_dir

    # Environment variable overrides config
    if not data_dir and (data_dir_str := os.environ.get(data_dir_env) or read_sparv_config().get("sparv_data")):
        data_dir = Path(data_dir_str).expanduser()

    if subpath:
        return data_dir / subpath if data_dir else Path(subpath)
    return data_dir


# Path to the 'sparv' package
sparv_path = Path(__file__).parent.parent

# Config file containing path to Sparv data dir
sparv_config_file = Path(appdirs.user_config_dir("sparv"), "config.yaml")
autocomplete_cache = Path(appdirs.user_config_dir("sparv"), "autocomplete")

# Package-internal paths
modules_dir = "modules"
core_modules_dir = "core_modules"

# Sparv data path (to be read from config)
data_dir = None
# Environment variable to override data path from config
data_dir_env = "SPARV_DATADIR"

# Data resource paths (below data_dir)
config_dir = get_data_path("config")
default_config_file = get_data_path(config_dir / "config_default.yaml")
presets_dir = get_data_path(config_dir / "presets")
models_dir = get_data_path("models")
bin_dir = get_data_path("bin")

# Corpus relative paths
corpus_dir = Path(os.environ.get("CORPUS_DIR", ""))
work_dir = Path("sparv-workdir")
log_dir = "logs"
source_dir = "source"
export_dir = Path("export")
config_file = "config.yaml"
