"""Functions related to handling plugins."""

import json
import subprocess
import sys
from importlib.metadata import Distribution, entry_points
from pathlib import Path

import rich
import rich.box
from rich.table import Table

from sparv.core.console import console


def check_pip() -> bool:
    """Check if pip is available in the current environment.

    Prints an error message if pip is not available.

    Returns:
        True if pip is available, False otherwise.
    """
    try:
        import pip  # noqa
    except ImportError:
        console.print(
            "[red]ERROR:[/] 'pip' is required to install plugins, but it is not available in the current environment."
        )
        return False

    return True


def install_plugin(plugin_package: str, editable: bool = True, verbose: bool = False) -> bool:
    """Install a Sparv plugin.

    Args:
        plugin_package: The plugin to install. Either a package name on PyPI, a local directory, or a full URL.
        editable: Install the plugin in editable mode. Only applicable for local directories.
        verbose: Print output from pip.

    Returns:
        True if the plugin was successfully installed, False otherwise.
    """
    if not check_pip():
        return False

    extra_args = []

    if Path(plugin_package).is_dir():
        console.print(f"Installing local plugin {plugin_package!r}")
        if editable:
            extra_args.append("-e")
    else:
        console.print(f"Installing plugin {plugin_package!r}")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", *extra_args, plugin_package], capture_output=True, check=False
    )
    if verbose:
        console.print(result.stdout.decode())
    if result.returncode != 0:
        console.print(f"Plugin {plugin_package!r} could not be installed:\n\n{result.stderr.decode()}")
        return False

    console.print(f"Plugin {plugin_package!r} installed successfully.")
    return True


def uninstall_plugin(plugin_name: str, verbose: bool = False) -> bool:
    """Uninstall a Sparv plugin.

    Args:
        plugin_name: The name of the plugin to uninstall (either the import package name or distribution package name).
        verbose: Print output from pip.

    Returns:
        True if the plugin was successfully uninstalled, False otherwise.
    """
    if not check_pip():
        return False

    found_entry_points = {e.name: e for e in entry_points(group="sparv.plugin")}
    found_entry_points_dist = {e.dist.name: e for e in found_entry_points.values()}
    entry_point = found_entry_points.get(plugin_name) or found_entry_points_dist.get(plugin_name)
    if not entry_point:
        console.print(f"Plugin {plugin_name!r} is not installed.")
        return False

    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", entry_point.dist.name], capture_output=True, check=False
    )
    if verbose:
        console.print(result.stdout.decode())
    if result.returncode != 0:
        console.print(f"Plugin {plugin_name!r} could not be uninstalled:\n\n{result.stderr.decode()}")
        return False

    console.print(f"Plugin {plugin_name!r} uninstalled successfully.")
    return True


def list_installed_plugins(verbose: bool = False) -> None:
    """Print a list of installed plugins.

    Args:
        verbose: Show more detailed information about the plugins.
    """
    console.print()
    table = Table(title="Installed Sparv plugins", box=rich.box.SIMPLE, show_header=False, title_justify="left")
    table.add_column(no_wrap=True)
    table.add_column()
    table.add_column()

    plugins = entry_points(group="sparv.plugin")

    for entry_point in sorted(plugins):
        pypi = True
        inner_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))

        direct_url = Distribution.from_name(entry_point.dist.name).read_text("direct_url.json")
        pypi = not direct_url

        inner_table.add_row(
            "[i dim]package:[/]",
            f"[link=https://pypi.org/project/{entry_point.dist.name}/]{entry_point.dist.name}[/link]"
            if pypi
            else entry_point.dist.name,
        )

        if verbose:
            if direct_url:
                origin_data = json.loads(direct_url)
                url = origin_data.get("url")
                is_editable = origin_data.get("dir_info", {}).get("editable", False)
                inner_table.add_row("[i dim]source:[/]", f"{url}{' (editable)' if is_editable else ''}")
            else:
                inner_table.add_row("[i dim]source:[/]", "PyPI")

        table.add_row(f"{entry_point.name}", f"[i dim]v{entry_point.dist.version}[/]", inner_table)

    if not plugins:
        table.add_row("No plugins installed.", "", "")

    console.print(table)
    console.print("Run 'sparv modules \\[plugin name]' to get more information about a plugin module and its features.")
    console.print("Run 'sparv plugins --help' for more information about managing plugins.")
