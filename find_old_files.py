#!/usr/bin/env python
"""
find_old_files

Locates files on a volume by age and size. Can generate 3 types of output:

 1. -H: Prints a text-art histogram of usage by user
 2. -L <output_list>: Write list of files older than age, organized by user
 3. -T <output_table>: Writes table of usage by user and date 

All three outputs can be generated on one run. This is useful, because it 
can take a long time to gather the underlying data.

Usage:
  find_old_files.py -H <directory>
  find_old_files.py -L <output_list> <directory>
  find_old_files.py -T <output_table> <directory>
  find_old_files.py [-H] [-w <WIDTH>] [-T <output_table>] [-L <output_list>] \
[-t <age_bin_type>] [-s <age_bin_size>] [-a <min_age>] [-u=<USER>...] [-Xv] <directory>
  find_old_files.py -h | --help
  find_old_files.py --version

Options:
  -h, --help     Show this screen.
  --version      Show version.
  -v             Print debug messages
  -L <output_list>, --list <output_list>     Generate list of files by user
  -T <output_table>, --table <output_table>  Generate table of usage by 
                                             user*age
  -t <age_bin_type>, --type <age_bin_type>   minutes, hours, days, weeks,
                                             or months [default: months]
  -a <min_age>, --age <min_age>              Minimum file age to considers
                                             unit is set by --type 
                                             [default: 6]
  -s <age_bin_size>, --size <age_bin_size>   Age bins for table outputs
                                             [default: 6]
  -u <USER>, --user <USER>                   Limit results to userids
                                             use multiple flags for g.t. 1 user
                                             must be uid num, not name
  -X, --follow_links                         Follow symbolic links
  -H, --hist     Print text histogram of usage by user to stdout
  -w <WIDTH>, --width <WIDTH>                Width of text histogram [default: 80]

"""
from docopt import docopt
import os, glob, numpy, re, sys
from os.path import join, getsize
from collections import defaultdict
from datetime import datetime
import pandas, numpy
from duhist import getLogBar, getBar, get13charName, getSizeString
import logging

def main(arguments):
    """
    Do the work. Arguments from docopt.
    """
    if arguments['-v']:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO
    logging.basicConfig(stream=sys.stderr, level=loglevel)

    # check the arguments
    volume = arguments['<directory>']
    output_table = arguments['--table']
    output_list = arguments['--list']
    print_histogram = arguments['--hist']
    text_width = int(arguments['--width'])
    age_bin_size = int(arguments['--size'])
    age_bin_type = arguments['--type']
    follow_links = arguments['--follow_links']

    min_age = int(arguments['--age'])
    logging.info("Looking for files at least %d %s old", min_age, age_bin_type,)
    min_age = min_age * time_spans[age_bin_type]

    user_list = arguments['--user']
    if len(user_list) == 0:
        user_list = None

    # scan the volume
    vol_data, min_date = get_file_sizes_and_dates_by_uid(volume,
                                                         user_list,
                                                         min_age,
                                                         follow_links=follow_links,
                                                        )

    logging.info("Found files for %d users", len(vol_data))
    logging.debug("Users: %s", ", ".join([str(k) for k in vol_data.keys()]))

    #  write file list, if asked
    if output_list:
        with open(output_list, 'wt') as output_handle:
            for user, file_data_list in vol_data.items():
                output_handle.write('# ' + str(user) + "\n")
                # sort files by mtime
                for file_data in sorted(file_data_list,
                                        key=lambda t: t[1],
                                       ):
                    output_handle.write(handle_funky_chars(file_data[2]))
                    output_handle.write("\n")

    # table needed for histogram or table
    if output_table or print_histogram:
        usage_table = get_file_size_table(vol_data,
                                          min_date,
                                          age_bin_size,
                                          age_bin_type,
                                         )

        logging.debug("%r", usage_table)

        # write table to file, if asked
        if output_table:
            usage_table.to_csv(output_table)

        # print histogram if asked
        if print_histogram:
            usage_by_uid = usage_table.sum().to_dict()
            generate_text_table(usage_by_uid,
                                text_width,
                                directory=volume,
                               )



time_spans = {
    'minutes': 60,
    'hours': 3600,
    'days': 3600*24,
    'weeks': 3600*24*7,
    'months': 3600*24*30,
}

def handle_funky_chars(decoded_string):
    return decoded_string.encode('utf8','surrogateescape').decode('utf8','replace')

def generate_text_table(data, max_width,
                        sorted_keys=None,
                        label_width=10,
                        directory='directory',
                        log=False,
                        out_handle=sys.stdout,
                       ):
    if sorted_keys is None:
        sorted_keys = sorted(data.keys(), key=lambda k: str(k))

    # empty directory
    if len(data) == 0:
        sys.exit("ERROR: %s is empty" % (directory))

    # figure out range (may be more efficient to do while parsing,
    #  but not worth it)
    width = max_width - label_width
    tot = sum(data.values())
    maxVal = max(data.values())

    # log
    if log:
        maxVal = np.log(maxVal)

    scale = maxVal/float(width)

    # print histogram
    for key in sorted_keys:
        size = data[key]
        if log and size > 0:
            barSize = np.log(size)
            barString = getLogBar(barSize, scale,width, log)
        else:
            barSize = size
            barString = getBar(barSize, scale, log)
        out_handle.write("%s(%s)|%s\n" % (get13charName(str(key)),
                                          getSizeString(size/1024),
                                          barString))

    # print total
    out_handle.write("Total: %s\n" % (getSizeString(tot/1024)))



def get_bin_bounds_string(bin_index, bin_bounds, to_str=repr, suffix=""):
    return "{} to {} {}".format(to_str(bin_bounds[bin_index]), to_str(bin_bounds[bin_index + 1]), suffix)


def get_file_sizes_and_dates_by_uid(volume, users=None, min_age=0, follow_links=False):
    """ Collect date and size by user id """

    # translate user ids to names
    userid_map = get_user_lookup_table().to_dict()

    # translate userids to names in include list
    if users is not None:
        users = set(userid_map.get(u, u) for u in users)

    usage_data = defaultdict(lambda: [])
    min_date = int(datetime.now().timestamp())
    now = datetime.now().timestamp()
    for root_path, folder_list, file_list in os.walk(volume, followlinks=follow_links):
        for file_name in file_list:
            try:
                file_path = os.path.join(root_path, file_name)
                if not(os.path.isfile(file_path)):
                    # skip broken links
                    continue
                file_stats = os.stat(file_path)

                # filter by owner if user list given
                ownerid = file_stats.st_uid
                owner = userid_map.get(ownerid, ownerid)
                if users is not None and owner not in users:
                    continue

                mtime = max(file_stats.st_mtime, file_stats.st_ctime)
                # keep track of oldest file
                min_date = min(mtime, min_date)
                # filter by age
                file_age = now - mtime
                if file_age < min_age:
                    continue
                usage_data[owner].append((file_stats.st_size,
                                          mtime,
                                          file_path,
                                         ))
            except:
                pass

    return usage_data, min_date


def get_file_size_table(usage_data, min_date,
                        age_bin_size=2,
                        age_bin_type='weeks', min_age=0):
    """ translate files sizes and dates into table """

    now = datetime.now().timestamp()
    if age_bin_type not in time_spans:
        raise Exception("I don't know the time span {}. Please specify one of: {}".format(
            age_bin_type,
            ", ".join(time_spans.keys()),
        ))

    age_bins_step = age_bin_size * time_spans[age_bin_type]
    oldest_age = now - min_date
    age_bin_bounds = numpy.arange(0, oldest_age + age_bins_step, age_bins_step)
    
    counts = {}
    now = datetime.now().timestamp()
    for owner, file_data_list in usage_data.items():
        owner_counts = counts.setdefault(owner, {})
        for file_data in file_data_list:
            size = file_data[0]
            file_age = now - file_data[1]
            if file_age < min_age:
                continue
            age_bin = int(file_age/age_bins_step)
            owner_counts[age_bin] = owner_counts.get(age_bin, 0) + size
            
    
    # make into a data frame
    file_size_table = pandas.DataFrame(counts)
    # headers...
    #users = get_user_lookup_table()
    #file_size_table.columns = [users.get(c,c) for c in file_size_table.columns]
    
    file_size_table.index = \
            [get_bin_bounds_string(i, 
                                   age_bin_bounds, 
                                   lambda b: \
                                       str(int(b/time_spans[age_bin_type])), 
                                   "{} old".format(age_bin_type)) \
             for i in file_size_table.index]
    return file_size_table    
    

def get_user_lookup_table():
    """ returns series mapping user id to user name """
    return pandas.read_table('/etc/passwd', sep=':', names=['user','code','id','group','home','shell'], index_col=2)['user']


def plot_file_sizes(file_size_table, figsize=[4,4], log=False, cmap_name=None):
    plt.figure(figsize=figsize)
    matrix = file_size_table.as_matrix()
    if log:
        matrix = numpy.log10(matrix)
    try:
        if cmap_name is not None:
            cmap = plt.get_cmap(cmap_name)
        else:
            cmap = None
    except:
        print("WARNING: unknown color map: " + cmap_name)
        raise
    p = plt.imshow(matrix, cmap=cmap)
    xticks = plt.xticks(numpy.arange(len(file_size_table.columns)), [c for c in file_size_table.columns], rotation=90)
    yticks = plt.yticks(numpy.arange(len(file_size_table.index)), [y for y in file_size_table.index])
    plt.colorbar(p)




if __name__ == '__main__':
    arguments=docopt(__doc__, version='monitor_filesystem 0.9')
    main(arguments)

