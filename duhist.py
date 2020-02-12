#!/usr/bin/env python
"""
Disk Usage Histogram

Calculates the usage of all files in the given (or current) path(s) and plots
an ASCII histogram of sizes. Omit path name to process current dir.

Usage:
  duhist.py [options] [<path>...]
  duhist.py -h | --help
  duhist.py --version

Options:
  -h, --help     Show this screen.
  --version      Show version.
  -d, --debug    Print debug messages.
  -l, --log      Use log scale. (Chars - ~ = and # indicate order of mag)
  -t, --time     Print and sort by age. (10m -> 10 months, 5h -> 5 hours)
  -X, --allfs    Cross file system boundaries (don't use du -x)
  -w <WIDTH>     Width of text to print [default: 80]
  -W <WIDTH>     Width of filename column [default: 13]
"""

from docopt import docopt
import subprocess, sys, os, time, logging
import math

###############
# Functions
###############
def get13charName(name, name_width=13):
    if len(name) > name_width:
        # remove middle and insert elipsis to get to 13 characters
        start_end = math.ceil((name_width - 3)/2)
        end_start = math.ceil((3 - name_width)/2)
        return name[:start_end]+'***'+name[end_start:]
    while len(name) < name_width:
        # pad with trailing space to get to 13 characters
        name += ' '
    return name

def getBar(value, scale, log):
    """
    return string of equal signs ('=') based on value and scale
    """
    width = value/scale
    if width<1:
        return ''
    char = '='
    s = char
    while len(s)<width:
        if log:
            char = logChars[int(math.ceil(len(logChars)*value/float(maxVal))-1)]
        s += char
    return s

logChars = ['-', '~', '=', '#']
def getLogBar(value, scale, maxWidth, log):
    """
    return string of various signs (-,~,=,#) based on value and scale
    """
    width = value / scale
    if width < 1:
        return ''
    char = logChars[0]
    s = char
    while len(s) < width:
        if log:
            char = logChars[int(math.ceil(len(logChars)*len(s)/float(maxWidth))-1)]
        s += char
    return s

steps = ['K','M','G','T','P']
def getSizeString(val):
    """
    Given number of kilobytes, return string like 34K or .4M or 4T.
    Will always be 3 characters lone
    """

    # first, figure out ourder of magnitude
    size = float(val)
    step = 0
    while size > 99:
        size /= 1024
        step += 1

    # next, format
    if size >= .95:
        size = '%2.f' % size
    else:
        size = '%.1f' % size
        size = size[-2:]

    # add suffix
    size += steps[step]
    return size

units = {'h':3600, 'd':24*3600, 'm':24*3600*30, 'y':24*3600*365}
def get3charAge(age_s):
    for unit in sorted(units.keys(), key=lambda u: units[u], reverse=True):
        unit_size = units[unit]
        unit_count = age_s/float(unit_size)
        if unit_count >= 1.5:
            return '{:02d}{}'.format(int(unit_count), unit)
    else:
        return "00h"

def du_directory(directory, one_fs):
    """
    get folder contents by cd-ing in and using glob (*)
    """
    # run du
    one_fs_arg = "-x" if one_fs else ""
    logging.debug('command: du --max-depth 0 %s -k *' % (one_fs_arg))
    logging.debug('cwd: %s' % (directory))
    p = subprocess.Popen('du --max-depth 0 %s -k *' % (one_fs_arg),
                       shell=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE,
                       cwd=directory)

    # get file and size from each line
    for line in maybe_decode(p.stdout):
        cells = line.rstrip('\n\r').split(None,1)
        yield cells[1], int(cells[0])

    # check for error message
    error_msgs = "\n".join(maybe_decode(p.stderr))
    if len(error_msgs) > 0:
        logging.warning("du reports an error: " + error_msgs)

def maybe_decode(lines):
    for line in lines:
        if not isinstance(line, str):
            line = line.decode()
        yield line

def du_file(filename, one_fs):
    """
    get file size with du
    """
    # run du
    one_fs_arg = "-x" if one_fs else ""
    logging.debug('command: du --max-depth 0 %s -k %s' % (one_fs_arg, filename))
    p = subprocess.Popen('du --max-depth 0 %s -k %s' % (one_fs_arg, filename),
                       shell=True,
                       stderr=subprocess.PIPE,
                       stdout=subprocess.PIPE)

    # get file and size from each line
    line = next(iter(p.stdout))
    if not isinstance(line, str):
        line = line.decode()
    cells = line.rstrip('\n\r').split(None,1)
    return int(cells[0])

###########
# Main code
###########
def main(arguments):
    """
    Arguments from docopt like:
    {
          "--help": false, 
          "--log": true, 
          "--time": true, 
          "--version": false, 
          "<path>": "."
    }
    """
    ##TODO: fix log and time_sort arguments
    try:
        debug = arguments['--debug']
        log = arguments["--log"]
        time_sort = arguments["--time"]
        one_fs = not arguments["--allfs"]
        max_width = int(arguments["-w"])
        name_width = int(arguments["-W"])
        du_paths = arguments['<path>']
    except KeyError:
        print("ERROR decoding arguments.")
        print(repr(arguments))
        raise

    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level)

    if du_paths is None or len(du_paths) == 0:
        du_paths = [".",]

    if name_width < 5:
        raise Exception("The name column must be at least 5 characters wide!")

    size_map = {}
    if time_sort:
        date_map = {}

    for path in du_paths:
        if os.path.isdir(path):
            for name, size in du_directory(path, one_fs):
                full_name = os.path.join(path, name)
                # hide dir name if only processing one
                map_name = name if len(du_paths) == 1 else full_name
                size_map[map_name] = size
                if time_sort:
                    date_map[map_name] = os.lstat(full_name).st_mtime
        else:
            size_map[path] = du_file(path, one_fs)
            if time_sort:
                date_map[map_name] = os.lstat(path).st_mtime

    # sort names by size
    if time_sort:
        now = time.time()
        sorted_names = sorted(size_map.keys(),key=lambda x: date_map[x])
    else:
        sorted_names = sorted(size_map.keys(),key=lambda x: size_map[x])

    # empty directory
    if len(size_map) == 0:
        sys.exit("ERROR: No results from paths: %s" % (",".join(du_paths)))

    # figure out range (may be more efficient to do while parsing, but not worth it)
    label_width = name_width + 6
    if time_sort:
        label_width += 4
    width = max_width - label_width
    tot = sum(size_map.values())
    maxVal = max(size_map.values())

    # log
    if log:
        maxVal = math.log(maxVal)

    scale = maxVal/float(width)

    # print histogram
    for name in sorted_names:
        size = size_map[name]
        if log and size>0:
            barSize = math.log(size)
            barString = getLogBar(barSize,scale,width, log)
        else:
            barSize = size
            barString = getBar(barSize,scale, log)
        if time_sort:
            sys.stdout.write(get3charAge(now - date_map[name]))
            sys.stdout.write(" ")
        if os.path.isdir(name):
            sys.stdout.write("%s(%s)|%s\n" % (get13charName(name, name_width),getSizeString(size),barString))
        else:
            sys.stdout.write("%s %s |%s\n" % (get13charName(name, name_width),getSizeString(size),barString))

    # print total
    sys.stdout.write("Total: %s\n" % (getSizeString(tot)))

if __name__ == '__main__':
    arguments = docopt(__doc__, version='duhist 0.9.3')
    main(arguments)
