"""Utilities for working with statistics files."""

import bz2
import zipfile


def compress(stats_file: str, out_file: str, compression: str = "zip") -> None:
    """Compress statistics file.

    Args:
        stats_file: Path to statistics file.
        out_file: Path to output file.
        compression: Compression method to use.
    """
    if compression == "bz2":
        with open(stats_file, "rb") as f_in, bz2.open(out_file, "wb") as f_out:
            f_out.writelines(f_in)
    else:
        with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(stats_file, stats_file)
