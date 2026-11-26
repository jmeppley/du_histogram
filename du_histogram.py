"""
Disk Usage Histogram

Calculates the usage of all files in the given (or current) path(s) and plots
an ASCII histogram of sizes. Omit path name to process current dir.
"""

import argparse
import logging
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass

__version__ = "0.10.0"

LOG_CHARS = ["-", "~", "=", "#"]
SIZE_SUFFIXES = ["K", "M", "G", "T", "P", "E"]
AGE_UNITS = {"y": 24 * 3600 * 365, "m": 24 * 3600 * 30, "d": 24 * 3600, "h": 3600}
MIN_NAME_WIDTH = 5

logger = logging.getLogger("duhist")


@dataclass
class UsageEntry:
    """Disk usage of one file or directory, as reported by du."""

    display_name: str
    full_path: str
    size_kb: int
    mtime: float | None = None

    @property
    def is_dir(self):
        """True if this entry is a directory (not following symlinks)."""
        return os.path.isdir(self.full_path) and not os.path.islink(self.full_path)


###############
# Formatting
###############
def format_name(name, name_width=13):
    """
    Return name padded or truncated to exactly name_width characters.

    Long names have their middle replaced with '***' so that both the
    start and the end of the name remain visible.
    """
    if len(name) > name_width:
        start_length = math.ceil((name_width - 3) / 2)
        end_length = name_width - 3 - start_length
        tail = name[-end_length:] if end_length > 0 else ""
        return name[:start_length] + "***" + tail
    return name.ljust(name_width)


def get_bar(value, scale):
    """
    Return a string of equal signs ('=') whose length is value / scale,
    rounded up. Values smaller than one unit of scale get an empty bar.
    """
    if scale <= 0:
        return ""
    bar_length = value / scale
    if bar_length < 1:
        return ""
    return "=" * math.ceil(bar_length)


def get_log_bar(value, scale, max_width):
    """
    Return a bar of length value / scale (rounded up) for log-scaled values.

    The bar character changes (-, ~, =, #) as the bar grows across
    max_width, so each character roughly indicates an order of magnitude.
    """
    if scale <= 0:
        return ""
    bar_length = value / scale
    if bar_length < 1:
        return ""
    bar_chars = [LOG_CHARS[0]]
    while len(bar_chars) < bar_length:
        char_index = math.ceil(len(LOG_CHARS) * len(bar_chars) / float(max_width)) - 1
        char_index = min(max(char_index, 0), len(LOG_CHARS) - 1)
        bar_chars.append(LOG_CHARS[char_index])
    return "".join(bar_chars)


def get_size_string(size_kb):
    """
    Given a number of kilobytes, return a short string like 34K, .4M or 4T.
    The result is always 3 characters long.
    """
    size = float(size_kb)
    suffix_index = 0
    while size > 99 and suffix_index < len(SIZE_SUFFIXES) - 1:
        size /= 1024
        suffix_index += 1

    if size >= 0.95:
        size_string = f"{size:2.0f}"
    else:
        size_string = f"{size:.1f}"[-2:]
    return size_string + SIZE_SUFFIXES[suffix_index]


def get_age_string(age_seconds):
    """
    Return a 3 character age string such as '10m' (10 months) or '05h' (5 hours).

    The largest unit with at least 1.5 units of age is used. Anything
    younger than 1.5 hours is reported as '00h'.
    """
    for unit, unit_seconds in AGE_UNITS.items():
        unit_count = age_seconds / float(unit_seconds)
        if unit_count >= 1.5:
            return f"{int(unit_count):02d}{unit}"
    return "00h"


###############
# Running du
###############
def build_du_command(targets, one_fs):
    """
    Return the du argument list for the given targets.

    Uses only options shared by GNU (Linux) and BSD (macOS) du.
    """
    command = ["du", "-d", "0", "-k"]
    if one_fs:
        command.append("-x")
    command.append("--")
    command.extend(targets)
    return command


def run_du(targets, one_fs, cwd=None):
    """
    Run du on the given targets and yield (name, size_kb) for each output line.

    Any error output from du (e.g. permission denied) is logged as a warning.
    """
    command = build_du_command(targets, one_fs)
    logger.debug("command: %s", " ".join(command))
    logger.debug("cwd: %s", cwd or ".")
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, errors="replace", check=False
    )
    if result.stderr.strip():
        logger.warning("du reports an error: %s", result.stderr.strip())

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        size_text, name = line.split("\t", 1)
        yield name, int(size_text)


def du_directory(directory, one_fs):
    """
    Yield (name, size_kb) for each non-hidden item in directory.

    This matches the behavior of running 'du *' inside the directory.
    """
    names = sorted(name for name in os.listdir(directory) if not name.startswith("."))
    if not names:
        return
    yield from run_du(names, one_fs, cwd=directory)


def du_file(filename, one_fs):
    """Return the size in kilobytes of a single file (or directory as a whole)."""
    for _name, size_kb in run_du([filename], one_fs):
        return size_kb
    raise RuntimeError(f"du returned no output for {filename}")


def get_mtime(path):
    """Return the modification time of path, without following symlinks."""
    return os.lstat(path).st_mtime


def collect_usage(paths, one_fs=True, with_mtime=False):
    """
    Return a list of UsageEntry objects for the given paths.

    Directories are expanded to their (non-hidden) contents; files are
    reported as is. When only one path is given, entry names are shown
    relative to it; otherwise the full path is shown.
    """
    entries = []
    show_full_path = len(paths) > 1
    for path in paths:
        if os.path.isdir(path):
            for name, size_kb in du_directory(path, one_fs):
                full_path = os.path.join(path, name)
                display_name = full_path if show_full_path else name
                entries.append(UsageEntry(display_name, full_path, size_kb))
        else:
            entries.append(UsageEntry(path, path, du_file(path, one_fs)))

    if with_mtime:
        for entry in entries:
            entry.mtime = get_mtime(entry.full_path)
    return entries


###############
# Histogram
###############
def format_histogram(
    entries, max_width=80, name_width=13, log_scale=False, time_sort=False, now=None
):
    """
    Return the histogram for entries as a list of text lines.

    Entries are sorted by size (or by age if time_sort is set), and the
    last line gives the total size.
    """
    if time_sort:
        now = time.time() if now is None else now
        sorted_entries = sorted(entries, key=lambda entry: entry.mtime)
    else:
        sorted_entries = sorted(entries, key=lambda entry: entry.size_kb)

    label_width = name_width + 6
    if time_sort:
        label_width += 4
    bar_width = max(max_width - label_width, 1)

    total_kb = sum(entry.size_kb for entry in entries)
    max_value = max(entry.size_kb for entry in entries)
    if log_scale:
        max_value = math.log(max_value) if max_value > 0 else 0
    scale = max_value / float(bar_width)

    lines = []
    for entry in sorted_entries:
        if log_scale:
            log_size = math.log(entry.size_kb) if entry.size_kb > 0 else 0
            bar = get_log_bar(log_size, scale, bar_width)
        else:
            bar = get_bar(entry.size_kb, scale)

        prefix = ""
        if time_sort:
            prefix = get_age_string(now - entry.mtime) + " "
        name = format_name(entry.display_name, name_width)
        size_string = get_size_string(entry.size_kb)
        if entry.is_dir:
            lines.append(f"{prefix}{name}({size_string})|{bar}")
        else:
            lines.append(f"{prefix}{name} {size_string} |{bar}")

    lines.append(f"Total: {get_size_string(total_kb)}")
    return lines


###########
# Main code
###########
def build_parser():
    """Return the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="duhist",
        description="Calculates the usage of all files in the given (or current) "
        "path(s) and plots an ASCII histogram of sizes. Directories are shown "
        "with their size in parentheses.",
    )
    parser.add_argument(
        "paths", metavar="path", nargs="*", help="Files or directories (default: .)"
    )
    parser.add_argument("--version", action="version", version="duhist " + __version__)
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Print debug messages."
    )
    parser.add_argument(
        "-l",
        "--log",
        action="store_true",
        help="Use log scale. (Chars - ~ = and # indicate order of mag)",
    )
    parser.add_argument(
        "-t",
        "--time",
        action="store_true",
        help="Print and sort by age. (10m -> 10 months, 5h -> 5 hours)",
    )
    parser.add_argument(
        "-X",
        "--allfs",
        action="store_true",
        help="Cross file system boundaries (don't use du -x)",
    )
    parser.add_argument(
        "-w",
        dest="width",
        metavar="WIDTH",
        type=int,
        default=80,
        help="Width of text to print [default: %(default)s]",
    )
    parser.add_argument(
        "-W",
        dest="name_width",
        metavar="WIDTH",
        type=int,
        default=13,
        help="Width of filename column [default: %(default)s]",
    )
    return parser


def main(argv=None):
    """Parse command line arguments, run du, and print the histogram."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if arguments.debug else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if arguments.name_width < MIN_NAME_WIDTH:
        parser.error(
            f"The name column must be at least {MIN_NAME_WIDTH} characters wide!"
        )

    paths = arguments.paths or ["."]
    for path in paths:
        if not os.path.lexists(path):
            parser.error(f"No such file or directory: {path}")

    entries = collect_usage(
        paths, one_fs=not arguments.allfs, with_mtime=arguments.time
    )
    if not entries:
        sys.exit(f"ERROR: No results from paths: {','.join(paths)}")

    lines = format_histogram(
        entries,
        max_width=arguments.width,
        name_width=arguments.name_width,
        log_scale=arguments.log,
        time_sort=arguments.time,
    )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
