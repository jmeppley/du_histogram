"""Unit tests for the pure formatting helpers in du_histogram."""

import pytest

import du_histogram
from du_histogram import (
    UsageEntry,
    build_du_command,
    format_histogram,
    format_name,
    get_age_string,
    get_bar,
    get_log_bar,
    get_size_string,
)

HOUR = 3600
DAY = 24 * HOUR


# ---------- format_name ----------
@pytest.mark.parametrize("name_width", [5, 6, 13, 14, 20])
def test_format_name_always_has_requested_width(name_width):
    """Short, exact and long names are all padded/truncated to name_width."""
    for name in ["a", "x" * name_width, "a_very_long_file_name_indeed.txt"]:
        assert len(format_name(name, name_width)) == name_width


def test_format_name_pads_short_names():
    """Short names are left aligned and padded with spaces."""
    assert format_name("abc", 6) == "abc   "


def test_format_name_keeps_start_and_end_of_long_names():
    """Long names keep their start and end around a '***' marker."""
    assert format_name("abcdefghijklmnopqrstuvwxyz", 13) == "abcde***vwxyz"
    assert format_name("abcdefghijklmnopqrstuvwxyz", 14) == "abcdef***vwxyz"
    assert format_name("abcdefghijklmnopqrstuvwxyz", 5) == "a***z"


# ---------- get_size_string ----------
@pytest.mark.parametrize(
    ("size_kb", "expected"),
    [
        (0, ".0K"),
        (4, " 4K"),
        (99, "99K"),
        (100, ".1M"),
        (5 * 1024, " 5M"),
        (3 * 1024**2, " 3G"),
        (2 * 1024**3, " 2T"),
        (7 * 1024**4, " 7P"),
    ],
)
def test_get_size_string(size_kb, expected):
    """Sizes in KB are rendered as short human readable strings."""
    assert get_size_string(size_kb) == expected


@pytest.mark.parametrize("size_kb", [0, 1, 50, 99, 100, 1000, 10**6, 10**12, 10**17])
def test_get_size_string_is_three_chars(size_kb):
    """Size strings are always 3 characters, even for absurdly large sizes."""
    assert len(get_size_string(size_kb)) == 3


# ---------- get_age_string ----------
@pytest.mark.parametrize(
    ("age_seconds", "expected"),
    [
        (0, "00h"),
        (HOUR, "00h"),
        (2 * HOUR, "02h"),
        (3 * DAY, "03d"),
        (65 * DAY, "02m"),
        (800 * DAY, "02y"),
    ],
)
def test_get_age_string(age_seconds, expected):
    """Ages use the largest unit with at least 1.5 units."""
    assert get_age_string(age_seconds) == expected


# ---------- bars ----------
def test_get_bar_lengths():
    """Linear bars are value/scale long, rounded up, and empty below 1."""
    assert get_bar(0, 1.0) == ""
    assert get_bar(0.5, 1.0) == ""
    assert get_bar(2.5, 1.0) == "==="
    assert get_bar(10, 2.0) == "====="


def test_get_bar_handles_zero_scale():
    """A zero scale (e.g. all sizes are 0) gives an empty bar, not an error."""
    assert get_bar(5, 0) == ""


def test_get_log_bar_characters_progress():
    """Log bars start with '-' and switch through ~ and = to # across the width."""
    bar_width = 40
    full_bar = get_log_bar(bar_width, 1.0, bar_width)
    assert len(full_bar) == bar_width
    assert full_bar[0] == "-"
    assert full_bar[-1] == "#"
    # characters never go back down the sequence
    positions = [du_histogram.LOG_CHARS.index(char) for char in full_bar]
    assert positions == sorted(positions)
    assert set(full_bar) == set(du_histogram.LOG_CHARS)


def test_get_log_bar_edge_cases():
    """Log bars are empty for tiny values or zero scale."""
    assert get_log_bar(0.5, 1.0, 40) == ""
    assert get_log_bar(5, 0, 40) == ""


# ---------- du command ----------
def test_build_du_command_one_fs():
    """du uses portable options and '--' so names starting with '-' are safe."""
    assert build_du_command(["a", "-b"], one_fs=True) == [
        "du",
        "-d",
        "0",
        "-k",
        "-x",
        "--",
        "a",
        "-b",
    ]


def test_build_du_command_all_fs():
    """With one_fs False, -x is not passed to du."""
    assert "-x" not in build_du_command(["a"], one_fs=False)


# ---------- format_histogram ----------
def make_entries(tmp_path, sizes_and_mtimes):
    """Create UsageEntry objects (as plain files) for {name: (size_kb, mtime)}."""
    entries = []
    for name, (size_kb, mtime) in sizes_and_mtimes.items():
        full_path = tmp_path / name
        full_path.touch()
        entries.append(UsageEntry(name, str(full_path), size_kb, mtime))
    return entries


def test_format_histogram_sorted_by_size(tmp_path):
    """Lines are sorted by increasing size, the biggest bar fills the width."""
    entries = make_entries(
        tmp_path, {"big": (1000, 1.0), "small": (10, 2.0), "mid": (100, 3.0)}
    )
    lines = format_histogram(entries, max_width=60)
    assert [line.split()[0] for line in lines[:-1]] == ["small", "mid", "big"]
    assert lines[-1] == "Total: " + get_size_string(1110)
    assert max(len(line) for line in lines) == 60
    assert lines[2].endswith("|" + "=" * (60 - 19))


def test_format_histogram_time_sort(tmp_path):
    """With time_sort, lines are oldest first and prefixed with an age."""
    now = 1_000_000_000.0
    entries = make_entries(
        tmp_path,
        {
            "newest": (1, now - 2 * HOUR),
            "oldest": (2, now - 3 * DAY),
            "mid": (3, now - 2 * DAY),
        },
    )
    lines = format_histogram(entries, time_sort=True, now=now)
    assert [line.split()[:2] for line in lines[:-1]] == [
        ["03d", "oldest"],
        ["02d", "mid"],
        ["02h", "newest"],
    ]


def test_format_histogram_marks_directories(tmp_path):
    """Directories have their size in parentheses."""
    (tmp_path / "folder").mkdir()
    entries = [
        UsageEntry("folder", str(tmp_path / "folder"), 8),
        *make_entries(tmp_path, {"file": (4, None)}),
    ]
    lines = format_histogram(entries)
    assert lines[0].startswith("file           4K |")
    assert lines[1].startswith("folder       ( 8K)|")


@pytest.mark.parametrize("log_scale", [False, True])
@pytest.mark.parametrize("size_kb", [0, 1])
def test_format_histogram_tiny_sizes(tmp_path, log_scale, size_kb):
    """All-zero or all-1K sizes (log(1) == 0) don't divide by zero."""
    entries = make_entries(tmp_path, {"a": (size_kb, None), "b": (size_kb, None)})
    lines = format_histogram(entries, log_scale=log_scale)
    assert len(lines) == 3


def test_format_histogram_log_scale(tmp_path):
    """Log scale bars use the log characters and grow with size."""
    entries = make_entries(
        tmp_path, {"a": (10, None), "b": (10_000, None), "c": (10_000_000, None)}
    )
    lines = format_histogram(entries, log_scale=True)
    bars = [line.split("|", 1)[1] for line in lines[:-1]]
    assert len(bars[0]) < len(bars[1]) < len(bars[2])
    assert bars[2][-1] == "#"
