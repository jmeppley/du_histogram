#!/usr/bin/env python
"""
Disk Usage Histogram

Calculates the usage of all files in the given (or current) directory and plots
an ASCII histogram of sizes. Omit directory name to process current dir.

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
"""

from docopt import docopt
import subprocess, sys, os, time
import numpy as np

###############
# Functions
###############
def get13charName(name):
    if len(name)>13:
        # remove middle and insert elipsis to get to 13 characters
        return name[:5]+'***'+name[-5:]
    while len(name)<13:
        # pad with trailing space to get to 13 characters
        name+=' '
    return name

def getBar(value, scale, log):
    """
    return string of equal signs ('=') based on value and scale
    """
    width=value/scale
    if width<1:
        return ''
    char='='
    s=char
    while len(s)<width:
        if log:
            char=logChars[int(ceil(len(logChars)*value/float(maxVal))-1)]
        s+=char
    return s

from numpy import ceil
logChars=['-','~','=','#']
def getLogBar(value, scale, maxWidth, log):
    """
    return string of various signs (-,~,=,#) based on value and scale
    """
    width=value/scale
    if width<1:
        return ''
    char=logChars[0]
    s=char
    while len(s)<width:
        if log:
            char=logChars[int(ceil(len(logChars)*len(s)/float(maxWidth))-1)]
        s+=char
    return s

steps=['K','M','G','T','P']
def getSizeString(val):
    """
    Given number of kilobytes, return string like 34K or .4M or 4T.
    Will always be 3 characters lone
    """

    # first, figure out ourder of magnitude
    size=float(val)
    step=0
    while size>99:
        size/=1024
        step+=1

    # next, format
    if size>=.95:
        size='%2.f' % size
    else:
        size='%.1f' % size
        size=size[-2:]

    # add suffix
    size+=steps[step]
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

def getLastModDate(path, directory):
    """
    Return the last modification date of this thing
    """
    return os.path.getmtime(os.path.sep.join([directory,path]))

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
          "<directory>": "."
    }
    """
    ##TODO: fix log and timeSort arguments
    try:
        log = arguments["--log"]
        timeSort = arguments["--time"]
        one_fs = not arguments["--allfs"]
        max_width = int(arguments["-w"])
        directory=arguments['<directory>']
    except KeyError:
        print(repr(arguments))
        raise
    if directory is None:
        directory = "."

    # run du
    one_fs_arg = "-x" if one_fs else ""
    print('du -d 0 %s -k *' % (one_fs_arg))
    print('cwd: %s' % (directory))
    p=subprocess.Popen('du -d 0 %s -k *' % (one_fs_arg),
                       shell=True,
                       stdout=subprocess.PIPE,
                       cwd=directory)
    sizeMap={}

    # get file and size from each line
    for line in p.stdout:
        if not isinstance(line, str):
            line = line.decode()
        cells=line.rstrip('\n\r').split(None,1)
        sizeMap[cells[1]]=int(cells[0])

    # sort names by size
    if timeSort:
        date_map={}
        now = time.time()
        for x in sizeMap:
            date_map[x]=getLastModDate(x,directory)
        sorted_names=sorted(sizeMap.keys(),key=lambda x: date_map[x])
    else:
        sorted_names=sorted(sizeMap.keys(),key=lambda x: sizeMap[x])

    # empty directory
    if len(sizeMap)==0:
        sys.exit("ERROR: %s is empty" % (directory))

    # figure out range (may be more efficient to do while parsing, but not worth it)
    label_width = 19
    if timeSort:
        label_width += 4
    width = max_width - label_width
    tot=sum(sizeMap.values())
    maxVal=max(sizeMap.values())

    # log
    if log:
        maxVal=np.log(maxVal)

    scale=maxVal/float(width)

    # print histogram
    for name in sorted_names:
        size=sizeMap[name]
        if log and size>0:
            barSize=np.log(size)
            barString=getLogBar(barSize,scale,width, log)
        else:
            barSize=size
            barString=getBar(barSize,scale, log)
        if timeSort:
            sys.stdout.write(get3charAge(now - date_map[name]))
            sys.stdout.write(" ")
        if os.path.isdir(name):
            sys.stdout.write("%s(%s)|%s\n" % (get13charName(name),getSizeString(size),barString))
        else:
            sys.stdout.write("%s %s |%s\n" % (get13charName(name),getSizeString(size),barString))

    # print total
    sys.stdout.write("Total: %s\n" % (getSizeString(tot)))

if __name__ == '__main__':
    arguments=docopt(__doc__, version='duhist 0.9')
    main(arguments)