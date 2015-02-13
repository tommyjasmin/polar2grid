#!/usr/bin/env python# encoding: utf-8
"""
dibs.py
$Id: dibs.py 85 2012-04-25 21:11:09Z rayg $

Purpose: Emulate direct broadcast using IDPS ops data stored in the PEATE

Reference:
http://peate.ssec.wisc.edu/flo/api#api_find

Created by rayg on 23 Apr 2012.
Copyright (c) 2012 University of Wisconsin SSEC. All rights reserved.
"""

import logging
import os, sys, re
from urllib2 import urlopen
from subprocess import call
from collections import defaultdict
from glob import glob
from datetime import date, timedelta, datetime
import ftplib

LOG = logging.getLogger(__name__)

# FUTURE: generate FLO_FMT using PRODUCT_LIST
PRODUCT_LIST = 'GITCO GDNBO SVDNB SVI01 SVI02 SVI03 SVI04 SVI05'.split(' ')

FLO_FMT = """http://peate.ssec.wisc.edu/flo/api/find?
            start=%(start)s&end=%(end)s
            %(file_types)s
            &loc=%(lat)s,%(lon)s
            &radius=%(radius)s
            &output=txt
"""
FLO_HOSTNAME = "peate.ssec.wisc.edu"
# if we are in the building, use this instead for faster download
FLO_INSIDE_HOSTNAME = "peate02.ssec.wisc.edu"

re_npp_pattern = r'(?P<kind>[A-Z\-]+)(?P<band>[0-9]*)_(?P<sat>[A-Za-z0-9]+)_d(?P<date>\d+)_t(?P<start_time>\d+)_e(?P<end_time>\d+)_b(?P<orbit>\d+)_c(?P<created_time>\d+)_(?P<site>[a-zA-Z0-9]+)_(?P<domain>[a-zA-Z0-9]+)\.h5'
RE_NPP = re.compile(re_npp_pattern)


FLO_FMT = re.sub(r'\n\s+', '', FLO_FMT)

ONE_DAY = timedelta(days=1)
TWO_DAY = timedelta(days=2)
THREE_DAY = timedelta(days=3)
FOUR_DAY = timedelta(days=4)
FIVE_DAY = timedelta(days=5)

def flo_find(lat, lon, radius, start, end, file_types, use_inside_hostname=True):
    "return shell script and filename list"
    start = start.strftime('%Y-%m-%d')
    end = end.strftime('%Y-%m-%d')
    file_types=''.join(('&file_type=%s' % ft) for ft in file_types)
    req_url = FLO_FMT % locals()
    LOG.debug('accessing %s' % req_url)
    wp = urlopen(req_url)
    for url in wp:
        url = url.strip()
        if not url:
            continue
        match = RE_NPP.search(url)
        if not match:
            continue
        if use_inside_hostname:
            LOG.debug("replacing flo hostname (%s) with direct hostname (%s)", FLO_HOSTNAME, FLO_INSIDE_HOSTNAME)
            url = url.replace(FLO_HOSTNAME, FLO_INSIDE_HOSTNAME)
        LOG.debug('found %s @ %s' % (match.group(0), url))
        yield match, url
    wp.close()


FLO_RVIRS_RE = re.compile(r'ftp://(?P<host>[^/]+)/ingest/(?P<inst_url>[^/]+)/(?P<sat_url>[^/]+)/(?P<year>\d{4})/(?P<jul_day>\d{3})/(?P<ftype>[^/]+)/' + re_npp_pattern)


def ll_find(lat, lon, radius, start, end, file_types, use_inside_hostname=True, flo_product="RVIRS"):
    """Create a file list for low latency products (separate FTP from flo search) by searching
    flo for `flo_product` and replacing parts of the URL to create FTP URLs for each file type.
    """
    # Example Original URL:
    # ftp://sips.ssec.wisc.edu/ingest/viirs/npp/2015/037/RVIRS/RNSCA-RVIRS_npp_d20150206_t0144453_e0146107_b16978_c20150206034121195445_noaa_ops.h5
    # Example New URL (different day):
    # ftp://sips.ssec.wisc.edu/viirs/npp/cspp_2_0/2015/011/SVI03/SVI03_npp_d20150111_t0000438_e0002080_b16608_c20150111022206530669_ssec_dev.h5
    orig_inventory = flo_find(lat, lon, radius, start, end, [flo_product], use_inside_hostname=use_inside_hostname)
    for orig_nfo, orig_url in orig_inventory:
        new_nfo = FLO_RVIRS_RE.match(orig_url)
        if not new_nfo:
            LOG.error("URL for file does not match expected regular expression")
            continue

        for ft in file_types:
            # needs wildcard to be processed by lftp
            new_url = "ftp://{host}/{inst_url}/{sat_url}/cspp_2_0/{year}/{jul_day}/{file_type}/{file_type}_{sat}_d{date}_t{start_time}_e{end_time}_b{orbit}_c*_ssec_dev.h5".format(file_type=ft, **new_nfo.groupdict())
            yield new_nfo, new_url


def _test_flo_find(args, use_inside_hostname=True):
    start = date(2011, 12, 13)
    end = date(2011, 12, 14)
    for nfo, url in flo_find(43.07, -89.41, 1000, start, end, file_types=args or PRODUCT_LIST, use_inside_hostname=use_inside_hostname):
        print nfo.group(0), url # print filename and url

def _all_products_present(key, file_nfos, products):
    "given the set of files we downloaded, and the work-directory waiting room of files, see if all products are present"
    needs = set(products)
    # go through the files we just downloaded
    for nfo in file_nfos:
        product = '%(kind)s%(band)s' % nfo.groupdict()
        if product in needs:
            needs.remove(product)
        else:
            LOG.error('unknown product type %s was downloaded, how?' % product)

    # check for other products in the directory. alternately file_nfos could be augmented with current directory contents
    hunt_for_these = set(needs)
    date, start_time, end_time = key
    for subtype in hunt_for_these:
        globby = '%(subtype)s*%(date)s*%(start_time)s*%(end_time)s*.h5' % locals()
        LOG.debug('checking current directory for %s' % globby)
        filenames = tuple(glob(globby))
        howmany = len(filenames)
        if howmany>0:
            if howmany>1:
                LOG.warning('found %d files! (%r) huh??' % (howmany, filenames))
            LOG.debug('found %s' % repr(filenames))
            needs.remove(subtype)

    if needs:
        LOG.info('%s is missing %s, skipping for now' % (repr(key), repr(needs)))
        return False
    return True


def curl(filename, url):
    return call(['curl', '-s', '-o', filename, url])


def get_ftp(filename, url):
    # Note: ignores filename
    # Could use ftplib, but this is simpler
    return call(['lftp', '-c', 'mget', url])


def _key(nfo):
    nfo = nfo.groupdict()
    return (nfo['date'], nfo['start_time'], nfo['end_time'])


def sync(lat, lon, radius, start=None, end=None, file_types=None, use_inside_hostname=True, low_latency=False):
    "synchronize current working directory to include all the files available"
    if end is None:
        end = date.today() + ONE_DAY
    if start is None:
        start = end - THREE_DAY
    file_types = file_types or PRODUCT_LIST
    bad = list()
    good = list()
    new_files = defaultdict(list)
    if low_latency:
        inventory = list(ll_find(lat, lon, radius, start, end, file_types, use_inside_hostname=use_inside_hostname))
    else:
        inventory = list(flo_find(lat, lon, radius, start, end, file_types, use_inside_hostname=use_inside_hostname))
    for n, (nfo, url) in enumerate(inventory):
        filename = os.path.basename(url)
        LOG.debug('checking %s @ %s' % (filename, url))
        if os.path.isfile(filename):
            LOG.debug('%s is already present' % filename)
        else:
            LOG.info('downloading %d/%d : %s' % (n+1, len(inventory), url))
            if low_latency:
                rc = get_ftp(filename, url)
            else:
                rc = curl(filename, url)

            if rc!=0:
                bad.append(nfo)
                LOG.warning('download of %s failed' % url)
            else:
                good.append(nfo)
                LOG.info('ok!')
    # return a dictionary of date+time combinations which had no failed file transfers
    badset = set(_key(nfo) for nfo in bad)
    LOG.debug('these keys had transfer failures: %s' % repr(badset))
    for nfo in good:
        key = _key(nfo)
        if key not in badset:
            LOG.debug('adding %s to %s' % (nfo.group(0), key))
            new_files[key].append(nfo)
    fully_intact_sets = dict((k,v) for k,v in new_files.items() if _all_products_present(k, v, file_types))
    return fully_intact_sets


def mainsync(name, lat, lon, radius, start=None, end=None, file_types=None, use_inside_hostname=True,
             low_latency=False):
    "write a .nfo file with 'date start_time end_time when we complete a transfer"
    lat = int(lat)
    lon = int(lon)
    radius = int(radius)
    if start:
        start = datetime.strptime(start, '%Y-%m-%d').date()
    if end:
        end = datetime.strptime(end, '%Y-%m-%d').date()

    fp = file(name+'.nfo', 'at')
    for key in sync(lat, lon, radius, start, end, file_types, use_inside_hostname=use_inside_hostname, low_latency=low_latency).keys():
        LOG.info('%s is ready' % repr(key))
        print >>fp, '%s %s %s' % key
        fp.flush()
    fp.close()




hmst = lambda s: tuple(map(int, [s[0:2], s[2:4], s[4:6], s[6]+'00000']))
ymd = lambda s: tuple(map(int, [s[0:4], s[4:6], s[6:8]]))

def _key2dts(k):
    "convert (yyyymmdd, hhmmsst, hhmmsst) string key tuple into start and end datetime objects"
    d,s,e = k
    d = ymd(d)
    s = hmst(s)
    e = hmst(e)
    ds = datetime(*(d+s))
    de = datetime(*(d+e))
    if de < ds:
        de += timedelta(days=1)
    return ds,de

def _dts2key(s,e):
    "convert datetime object into key tuple"
    horus = lambda x: '%02d%02d%02d%d' % (x.hour, x.minute, x.second, x.microsecond/100000)
    return s.strftime('%Y%m%d'), horus(s), horus(e)

def _outcome_cg(seq):
    "given a sequence of (start,end) ordered datetime objects representing contiguous granules, return new outer key and list of granules"
    if not seq: return None
    grans = [seq[0][0]] + [x[1] for x in seq]
    # build new key
    s = grans[0][0]
    e = grans[-1][1]
    return (_dts2key(s,e), [_dts2key(*x) for x in grans])

def contiguous_groups(keyset, tolerance=timedelta(seconds=5)):
    "sort a set of keys into contiguous groups; yield (newkey, list-of-subkeys) sequence"
    granlist = list(sorted(map(_key2dts, keyset)))

    # pair off in start-time order
    # build a set containing contiguous granules
    # when we find a break in sequence, yield the set as an ordered tuple and start over
    seq = []
    for ((sa,ea),(sb,eb)) in zip(granlist[:-1], granlist[1:]):
        delta = sb-ea
        if delta < tolerance:
            seq.append(((sa,ea),(sb,eb)))
        else:
            if seq:
                yield _outcome_cg(seq)
            seq = []
    if seq:
        yield _outcome_cg(seq)

def read_nfo(filename=None, fobj=None):
    if fobj is None:
        fobj = file(filename, 'rt')
    for line in fobj:
        k = map(str.strip, line.split(' '))
        if len(k)==3:
            yield k

STAMP_FMT = 'd%s_t%s_e%s'

def pass_build(key, subkeys):
    "link all files belonging to subkeys to an pass directory"
    name = STAMP_FMT % key
    final_name = name + '.pass'
    if os.path.isdir(name) or os.path.isdir(final_name):
        LOG.warning('%s already has been processed' % name)
        return None
    os.mkdir(name)
    for piece in subkeys:
        pat = '*' + STAMP_FMT % piece + '*.h5'
        LOG.debug('looking for %s' % pat)
        for filename in glob(pat):
            LOG.debug('linking %s to %s' % (filename, name))
            os.symlink(os.path.join('..', filename), os.path.join(name, filename))
    os.rename(name, final_name)
    LOG.info('created %s' % final_name)



def mainpass(nfo_filename):
    "consume nfo file and link granule groups to their own .pass directories"
    fobj = file(nfo_filename, 'rt')
    stowname = '.' + nfo_filename
    if os.path.isfile(stowname):
        LOG.warning('removing old %s' % stowname)
        os.unlink(stowname)
    os.rename(nfo_filename, stowname)
    nfo = list(read_nfo(fobj=fobj))
    fobj.close()
    passes = contiguous_groups(nfo)
    for eve in passes:
        pass_build(*eve)


def main():
    import optparse
    usage = """
%prog domain-name --lat=latitude --lon=longitude --radius=radius-in-km {--start=YYYY-MM-DD} {--end=YYYY-MM-DD}
appends domain.nfo with "day start end" lines as complete sets of VIIRS files arrive
files are downloaded to current directory
files which have already been downloaded will not be re-downloaded
default start and end is yesterday~today
default file types can be overridden by giving prefixes (SVDNB, GITCO) as a list of arguments
Note that file type arguments should be the same between download (non-pass) run and pass generation run.
example:
%prog madison --lat=43 --lon=-89 --radius=1000
%prog madison --lat=43.07 --lon=-89.41 --radius=1000 GMTCO SVM02 SVM04 SVM05
%prog madison --pass GMTCO SVM02 SVM04 SVM05

"""
    parser = optparse.OptionParser(usage)
    parser.add_option('-t', '--test', dest="self_test",
                    action="store_true", default=False, help="run self-tests")
    parser.add_option('-v', '--verbose', dest='verbosity', action="count", default=0,
                    help='each occurrence increases verbosity 1 level through ERROR-WARNING-INFO-DEBUG')
    parser.add_option('-a', '--lat', dest='lat', help='central latitude', type='float')
    parser.add_option('-o', '--lon', dest='lon', help='central longitude', type='float')
    parser.add_option('-r', '--radius', dest='radius', help='radius in km', type='int', default=0)
    parser.add_option('-s', '--start', dest='start', help='yyyy-mm-dd start dateoptional', default=None)
    parser.add_option('-e', '--end', dest='end', help='yyyy-mm-dd end date optional', default=None)
    parser.add_option('-p', '--pass', dest='passes', help='post-process .nfo file (consuming it) and create .pass directories', default=False, action="store_true")
    parser.add_option('--outside-host', dest='use_inside_hostname', action='store_false', default=True,
                      help='Download data from %s instead of %s' % (FLO_HOSTNAME, FLO_INSIDE_HOSTNAME))
    parser.add_option('--low-latency', dest='low_latency', action='store_true', default=False,
                      help='Download data from the SIPS low-latency FTP location')
    # parser.add_option('-o', '--output', dest='output',
    #                 help='location to store output')
    # parser.add_option('-I', '--include-path', dest="includes",
    #                 action="append", help="include path to append to GCCXML call")
    (options, args) = parser.parse_args()

    # make options a globally accessible structure, e.g. OPTS.
    global OPTS
    OPTS = options

    if options.self_test:
        from pprint import pprint
        logging.basicConfig(level=logging.DEBUG)
        pprint(_test_flo_find(args, use_inside_hostname=options.use_inside_hostname))
        # FIXME - run any self-tests
        # import doctest
        # doctest.testmod()
        sys.exit(2)

    levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    logging.basicConfig(level = levels[min(3,options.verbosity)])

    if not args:
        parser.error( 'incorrect arguments, try -h or --help.' )
        return 9

    if options.radius:
        mainsync(args[0], options.lat, options.lon, options.radius, options.start, options.end,
                 args[1:] or PRODUCT_LIST, use_inside_hostname=options.use_inside_hostname,
                 low_latency=options.low_latency)

    if options.passes:
        mainpass(args[0]+'.nfo')
        return 0


    return 0


if __name__=='__main__':
    sys.exit(main())
