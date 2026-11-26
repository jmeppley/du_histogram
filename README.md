# du_histogram
Simple ASCII histogram of du (disk usage) output

```
$ duhist
README.md      4K |=====================
duhist.py      4K |=====================
pypro***.toml  4K |=====================
LICENSE       12K |=============================================================
du_hi***am.py 12K |=============================================================
Total: 36K
```

## What it does
This script runs the `du` utility and prints a text histogram of the output,
sorted by size or date. Directories are shown with their size in parentheses.

## Installation
### Requirements
Python 3.10 or newer on Linux or macOS (any system with a GNU or BSD `du`).
There are no third-party Python dependencies.

### Conda
```
conda install -c jmeppley du_histogram
```

### pip
```
pip install git+https://github.com/jmeppley/du_histogram
```

or, from a checkout of this repository:

```
pip install .
```

Either installs the `duhist` command (and `duhist.py`, for compatibility with
older versions).

### Without installing
You can also call the script directly from a checkout of the repository:

```
./duhist.py
```

## Usage
### Basic
Calling the script with no arguments will give a histogram of files and
folders in the current path sorted by size. Hidden files (names starting with
".") are skipped, just like `du *`.

### Advanced
```
usage: duhist [-h] [--version] [-d] [-l] [-t] [-X] [-w WIDTH] [-W WIDTH]
              [path ...]

Calculates the usage of all files in the given (or current) path(s) and plots
an ASCII histogram of sizes. Directories are shown with their size in
parentheses.

positional arguments:
  path         Files or directories (default: .)

options:
  -h, --help   show this help message and exit
  --version    show program's version number and exit
  -d, --debug  Print debug messages.
  -l, --log    Use log scale. (Chars - ~ = and # indicate order of mag)
  -t, --time   Print and sort by age. (10m -> 10 months, 5h -> 5 hours)
  -X, --allfs  Cross file system boundaries (don't use du -x)
  -w WIDTH     Width of text to print [default: 80]
  -W WIDTH     Width of filename column [default: 13]
```

When more than one path is given, each directory's contents are listed with
their full path.
