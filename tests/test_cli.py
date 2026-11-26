"""End-to-end tests that run duhist against a real directory tree with du."""

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

import du_histogram

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(shutil.which("du") is None, reason="du not found")

LINE_PATTERN = re.compile(
    r"^(?P<name>.*?)\s*(?P<size>[ (][ .\d]\d[KMGTPE][ )])\|(?P<bar>.*)$"
)


def write_random_file(path, size_bytes):
    """Write size_bytes of incompressible data to path."""
    path.write_bytes(os.urandom(size_bytes))


@pytest.fixture
def sample_tree(tmp_path):
    """
    Build a small directory tree to run duhist on.

    Contains files of different sizes (one with a space in its name), a
    subdirectory, a hidden file, a broken symlink and a name starting with '-'.
    """
    root = tmp_path / "tree"
    root.mkdir()
    write_random_file(root / "small.txt", 100)
    write_random_file(root / "med file.bin", 200_000)
    (root / "subdir").mkdir()
    write_random_file(root / "subdir" / "inner.bin", 2_000_000)
    write_random_file(root / ".hidden", 3_000_000)
    write_random_file(root / "-dash", 100)
    (root / "broken_link").symlink_to(root / "does_not_exist")
    return root


def run_main(capsys, *argv):
    """Run du_histogram.main with argv and return its stdout lines."""
    assert du_histogram.main(list(argv)) == 0
    return capsys.readouterr().out.splitlines()


def parse_lines(lines):
    """Parse histogram lines (excluding the total) into match objects."""
    assert lines[-1].startswith("Total: ")
    matches = [LINE_PATTERN.match(line) for line in lines[:-1]]
    assert all(matches), lines
    return matches


def test_default_output(capsys, sample_tree):
    """Lists non-hidden items, sorted by size, with directories in parentheses."""
    lines = run_main(capsys, str(sample_tree))
    parsed = parse_lines(lines)
    names = [match["name"] for match in parsed]

    assert sorted(names) == sorted(
        ["small.txt", "med file.bin", "subdir", "-dash", "broken_link"]
    )
    assert ".hidden" not in " ".join(lines)
    assert names[-1] == "subdir"
    assert names[-2] == "med file.bin"
    subdir_line = parsed[-1]
    assert subdir_line["size"].startswith("(") and subdir_line["size"].endswith(")")
    assert all(len(line) <= 80 for line in lines)
    # the biggest entry fills the bar width
    assert len(lines[-2]) == 80
    assert re.match(r"^Total: [ .\d]\d[KMGTPE]$", lines[-1])


def test_current_directory_is_default(capsys, sample_tree, monkeypatch):
    """With no path argument the current directory is used."""
    monkeypatch.chdir(sample_tree)
    assert run_main(capsys) == run_main(capsys, ".")
    assert run_main(capsys) == run_main(capsys, str(sample_tree))


@pytest.mark.parametrize(("max_width", "name_width"), [(60, 13), (100, 20), (40, 5)])
def test_widths(capsys, sample_tree, max_width, name_width):
    """-w sets the total line width and -W the name column width."""
    lines = run_main(
        capsys, "-w", str(max_width), "-W", str(name_width), str(sample_tree)
    )
    assert max(len(line) for line in lines) == max_width
    for line in lines[:-1]:
        assert line[name_width + 5] == "|"


def test_time_sort(capsys, sample_tree):
    """-t sorts by modification time (oldest first) and prints ages."""
    now = time.time()
    for name, age_days in [("small.txt", 600), ("med file.bin", 3), ("subdir", 50)]:
        mtime = now - age_days * 24 * 3600
        os.utime(sample_tree / name, (mtime, mtime))
    lines = run_main(capsys, "-t", str(sample_tree))
    ages_and_names = [line.split()[:2] for line in lines[:-1]]
    assert ages_and_names[:3] == [
        ["01y", "small.txt"],
        ["01m", "subdir"],
        ["03d", "med"],
    ]


def test_time_on_single_file(capsys, sample_tree):
    """Regression: -t on a file (not a directory) used to crash."""
    target = sample_tree / "med file.bin"
    lines = run_main(capsys, "-t", str(target))
    assert len(lines) == 2
    assert lines[0].startswith("00h ")


def test_log_scale(capsys, sample_tree):
    """-l uses the log scale bar characters."""
    lines = run_main(capsys, "-l", str(sample_tree))
    bars = [match["bar"] for match in parse_lines(lines)]
    assert bars[-1].startswith("-")
    assert bars[-1].endswith("#")


def test_multiple_paths_show_full_names(capsys, sample_tree):
    """With several paths, directory contents are listed by full path."""
    small_file = str(sample_tree / "small.txt")
    subdir = str(sample_tree / "subdir")
    lines = run_main(capsys, "-W", "200", "-w", "300", small_file, subdir)
    names = [match["name"] for match in parse_lines(lines)]
    assert names == [small_file, os.path.join(subdir, "inner.bin")]


def test_all_filesystems_flag(capsys, sample_tree):
    """-X gives the same result on a single filesystem."""
    assert run_main(capsys, "-X", str(sample_tree)) == run_main(
        capsys, str(sample_tree)
    )


def test_debug_logs_du_command(capsys, sample_tree, caplog):
    """-d logs the du command that was run."""
    with caplog.at_level("DEBUG", logger="duhist"):
        run_main(capsys, "-d", str(sample_tree))
    assert any("du -d 0 -k -x --" in message for message in caplog.messages)


def test_empty_directory(capsys, tmp_path):
    """An empty directory is reported as an error."""
    with pytest.raises(SystemExit, match="No results"):
        du_histogram.main([str(tmp_path)])


def test_missing_path(capsys, tmp_path):
    """A path that doesn't exist is a usage error."""
    with pytest.raises(SystemExit) as exit_info:
        du_histogram.main([str(tmp_path / "missing")])
    assert exit_info.value.code == 2
    assert "No such file or directory" in capsys.readouterr().err


def test_name_width_too_small(capsys, sample_tree):
    """A name column narrower than 5 characters is a usage error."""
    with pytest.raises(SystemExit) as exit_info:
        du_histogram.main(["-W", "4", str(sample_tree)])
    assert exit_info.value.code == 2


def test_version(capsys):
    """--version prints the version."""
    with pytest.raises(SystemExit) as exit_info:
        du_histogram.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == "duhist " + du_histogram.__version__


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, "-m", "du_histogram"],
        [sys.executable, str(REPO_ROOT / "duhist.py")],
    ],
    ids=["module", "checkout-shim"],
)
def test_runs_as_script(sample_tree, command):
    """The module and the ./duhist.py shim both run as scripts."""
    result = subprocess.run(
        [*command, str(sample_tree)], capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines()[-1].startswith("Total: ")


@pytest.mark.parametrize("command_name", ["duhist", "duhist.py"])
def test_installed_commands(sample_tree, command_name):
    """The installed console scripts work (skipped if not installed)."""
    command_path = shutil.which(command_name, path=os.path.dirname(sys.executable))
    if command_path is None:
        pytest.skip(f"{command_name} is not installed next to {sys.executable}")
    result = subprocess.run(
        [command_path, str(sample_tree)], capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines()[-1].startswith("Total: ")
