# du_histogram
Simple ASCII histogram of du (disk usage) output

## What it does
This script runs the "du" utility and prints a text histogram of the output sorted by size
or date.

## Installation
### Requirements
It should work with python 2 or 3 on any unix-like system with "du" installed. It
needs just two non-standard python packages:

 * docopt
 * numpy

### Installation
You can call the script directly from the repo:

```
./duhist.py
```

Or install it with setuptools:

```
python setup.py install
```

## Usage
### Basic
Calling the script with no arguments will git a histograms of files and folders
in the current path sorted by size.

### Advanced
```
Usage:
    duhist.py [-ltX] [-w WIDTH] [<directory>]
    duhist.py -h | --help
    duhist.py --version

Options:
    -h, --help     Show this screen.
    --version      Show version.
    -l, --log      Use log scale. (Chars - ~ = and # indicate order of mag)
    -t, --time     Print and sort by age. (10m -> 10 months, 5h -> 5 hours)
    -X, --allfs    Cross file system boundaries (don't use du -x)
    -w <WIDTH>     Width of text to print [default: 80]
```
