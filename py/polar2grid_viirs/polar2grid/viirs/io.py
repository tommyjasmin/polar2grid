#!/usr/bin/env python
# encoding: utf-8
# Copyright (C) 2014 Space Science and Engineering Center (SSEC),
# University of Wisconsin-Madison.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This file is part of the polar2grid software package. Polar2grid takes
# satellite observation data, remaps it, and writes it to a file format for
#     input into another program.
# Documentation: http://www.ssec.wisc.edu/software/polar2grid/
#
# Written by David Hoese    October 2014
# University of Wisconsin-Madison
# Space Science and Engineering Center
# 1225 West Dayton Street
# Madison, WI  53706
# david.hoese@ssec.wisc.edu
"""
Simple objects to assist in reading VIIRS data from hdf5 (.h5) files.

:author:       David Hoese (davidh)
:contact:      david.hoese@ssec.wisc.edu
:organization: Space Science and Engineering Center (SSEC)
:copyright:    Copyright (c) 2014 University of Wisconsin SSEC. All rights reserved.
:date:         Oct 2014
:license:      GNU GPLv3

"""
__docformat__ = "restructuredtext en"

import h5py
import numpy

from polar2grid.viirs import guidebook
from polar2grid.core.fbf import FileAppender
from polar2grid.core.frontend_utils import BaseMultiFileReader, BaseFileReader
from polar2grid.viirs.guidebook import K_DATA_PATH, K_MOONILLUM

import os
import sys
import re
import logging
from datetime import datetime, timedelta

LOG = logging.getLogger(__name__)
ORBIT_TRANSITION_THRESHOLD = timedelta(seconds=10)


class HDF5Reader(object):
    """Generic HDF5 reading class.
    """
    def __init__(self, filename):
        self.filename = os.path.basename(filename)
        self.filepath = os.path.realpath(filename)
        self._h5_handle = h5py.File(filename, 'r')
        self.file_items = {}
        self._h5_handle.visititems(self._visit_items)
        # Also add the global attributes
        for attr_name, attr_val in self._h5_handle.attrs.items():
            self.file_items["." + attr_name] = attr_val[0][0]

    def _visit_items(self, name, obj):
        """Look at each variable in the HDF file and record its attributes.

        We also store the variable name because sometimes h5py gives you an
        unhelpful/weird KeyError if it doesn't have that key.
        """
        self.file_items[name] = obj
        for attr_name, attr_obj in obj.attrs.items():
            self.file_items[name + "." + attr_name] = attr_obj

    def __contains__(self, key):
        if key.startswith("/"):
            key = key[1:]

        return key in self.file_items

    def __getitem__(self, key):
        """Get HDF5 variable, making it easier to access attributes.
        """
        if key.startswith("/"):
            key = key[1:]

        return self.file_items[key]


def file_time_to_datetime(file_time):
    """Convert a VIIRS StartTime which is in microseconds since 1958-01-01 to
    a datetime object.
    """
    base = datetime(1958, 1, 1, 0, 0, 0)
    return base + timedelta(microseconds=int(file_time))


def time_attr_to_datetime(d, st):
    # The last character is a Z (as in Zulu/UTC)
    whole_sec, s_us = st[:-1].split(".")
    s_us = int(s_us)
    s_dt = datetime.strptime(d + whole_sec, "%Y%m%d%H%M%S").replace(microsecond=s_us)
    return s_dt


class VIIRSSDRReader(BaseFileReader):
    """VIIRS Data SDR hdf5 reader.

    Handles all the difficulties of reading SDR data (masking, scaling, etc.)
    """
    def __init__(self, file_handle, file_type_info):
        """Initialize VIIRS SDR Reader and get information that we can derive by the file name.

        :param filename: HDF5 filename for a VIIRS data SDR file.
        :param file_type_info: Dictionary mapping file key constants to the variable path in the file
        :param instrument: Name of the instrument that recorded the data in the file. Defaults to 'viirs'.
        """
        super(VIIRSSDRReader, self).__init__(file_handle, file_type_info)

        self.satellite = self[guidebook.K_SATELLITE].lower()
        self.instrument = "viirs"

        # begin time
        sd = self[guidebook.K_AGGR_STARTDATE][0][0]
        LOG.info("READING START DATE...")
        st = self[guidebook.K_AGGR_STARTTIME][0][0]
        self.begin_time = time_attr_to_datetime(sd, st)

        # end time
        ed = self[guidebook.K_AGGR_ENDDATE][0][0]
        et = self[guidebook.K_AGGR_ENDTIME][0][0]
        self.end_time = time_attr_to_datetime(ed, et)

        # G-Ring lon
        # TJJ Dateline test - mix of neg and pos lons
        # try:
        #     num_lons = len(self[guidebook.K_LON_G_RING])
        #     neg_lons = False
        #     pos_lons = False
        #     for i in range(num_lons):
        #         LOG.info("GRINGLON: %d", self[guidebook.K_LON_G_RING][i][0])
        #         tmp_lon = self[guidebook.K_LON_G_RING][i][0]
        #         if (tmp_lon > 100):
        #             pos_lons = True
        #         if (tmp_lon < 100):
        #             neg_lons = True
        #     if (neg_lons and pos_lons):
        #         LOG.error("CROSSES DATELINE! Skipping...")
        #         sys.exit(1)
        # except KeyError:
        #     LOG.debug("Not a GEO file, no G-Ring test needed, error is ok...")

        # lat min, max
        lat_min = self[guidebook.K_LAT_MIN][0][0]
        lat_max = self[guidebook.K_LAT_MAX][0][0]
        LOG.info("READING LAT MIN: %d", lat_min)
        LOG.info("READING LAT MAX: %d", lat_max)

        # TJJ - throw out granules above 70 and below lat -65
        if (int(lat_max) > 70):
            LOG.error("Granule out of Latitude upper bounds, skipping...")
            sys.exit(1)
        if (int(lat_min) < -65):
            LOG.error("Granule out of Latitude lower bounds, skipping...")
            sys.exit(1)

    def __getitem__(self, item):
        known_item = self.file_type_info.get(item, item)
        if known_item is None:
            raise KeyError("Key 'None' was not found")

        if not isinstance(known_item, (str, unicode)):
            # Using FileVar class
            known_item = known_item.var_path
        LOG.debug("Loading %s from %s", known_item, self.filename)
        return self.file_handle[known_item]

    def scale_swath_data(self, data, scaling_factors):
        num_grans = len(scaling_factors)/2
        gran_size = data.shape[0]/num_grans
        scaling_mask = numpy.zeros(data.shape)
        for i in range(num_grans):
            start_idx = i * gran_size
            end_idx = start_idx + gran_size
            m = scaling_factors[i*2]
            b = scaling_factors[i*2 + 1]
            if m <= -999 or b <= -999:
                scaling_mask[start_idx:end_idx] = 1
            else:
                data[start_idx:end_idx] = m * data[start_idx:end_idx] + b

        scaling_mask = scaling_mask.astype(numpy.bool)
        return data, scaling_mask

    # TJJ - muck with quality flags here?
    # XXX might hack it up...

    def get_swath_data(self, item, dtype=numpy.float32, fill=numpy.nan):
        """Retrieve the item asked for then set it to the specified data type, scale it, and mask it.
        """
        LOG.debug("TJJ Getting swath data for item: %s", item)
        var_info = self.file_type_info.get(item)
        LOG.debug("TJJ var_info.var_path %s", var_info.var_path)

        bit_mask = None
        if (item == 'qf1_viirscmip'):
            LOG.error("TJJ EXTRACTING CM FROM QF1...")
            dtype = numpy.float32
            fill = numpy.nan
            data = self[var_info.var_path].value
            mask = (data & 0x03) == 0
            data &= 0x0C
            data = data.astype(dtype)
        else:
            data = self[var_info.var_path].value.astype(dtype)

        # if (item == 'qf1_viirscmip'):
            # mask off all but the two cloud confidence bits
            # numpy.bitwise_and(data, 0x0C, out=data)
            # numpy.right_shift(data, 2, out=data)
            # data = (data & 0x0C)
            # data = (data / 4)

        # Get the scaling factors
        scaling_factors = None
        try:
            scaling_factors = list(self[var_info.scaling_path][:])
        except KeyError:
            LOG.debug("TJJ No scaling factors for %s", item)

        # Get the mask for the data (based on unscaled data)
        if item == "qf1_viirscmip":
            pass
            #mask = None  # np.zeros_like(data, dtype=numpy.bool)
        elif scaling_factors is not None and var_info.scaling_mask_func is not None:
            mask = var_info.scaling_mask_func(data)
        elif scaling_factors is None and var_info.nonscaling_mask_func is not None:
            mask = var_info.nonscaling_mask_func(data)
        else:
            mask = None

        # Scale the data
        scaling_mask = None
        if scaling_factors is not None:
            LOG.info("SCALE FACTORS NOT NONE")
            data, scaling_mask = self.scale_swath_data(data, scaling_factors)

        if mask is not None:
            LOG.info("MASK NOT NONE")
            if scaling_factors is not None:
                mask |= scaling_mask
            data[mask] = fill

        # cloud mask seems to have bow-tie errors at swath edge 
        # try zeroing out until I can find a better solution
        # turned off for now
        # if (item == 'wonthappen'):
        # if (item == 'qf1_viirscmip'):
        #    LOG.debug("TJJ BITMASK HACK FOR CM...")
        #    # numpy.bitwise_and(data, 12)
        #    # numpy.divide(data, 4)
        #    # for x in numpy.nditer(data):
        #    #    if (x > 4):
        #    #       LOG.debug(x)
        #    cmH = data.shape[0]
        #    cmW = data.shape[1]
        #    # loCut = cmW / 3
        #    loCut = 1280
        #    # hiCut = loCut * 2
        #    hiCut = 1920
        #    data[0:3, 0:loCut] = 3
        #    data[0:3, hiCut:cmW] = 3
        #    data[cmH-3:cmH, 0:loCut] = 3
        #    data[cmH-3:cmH, hiCut:cmW] = 3

        # mask off all but the two cloud confidence bits
        # if (item == 'qf1_viirscmip'):
            # numpy.bitwise_and(data, 0x0C, out=data)
            # LOG.info("TOT SIZE: %d", data.size)
            # mask off the Cloud Mask Quality Pixel, where zero, we don't use CM
            # LOG.info("ZERO COUNT BEF: %d", data.size - numpy.count_nonzero(data))
            # cmqp = numpy.copy(data)
            # badcm = numpy.where((cmqp & 0x03) == 0)
            # goodcm = numpy.where((cmqp & 0x03) != 0)
            # LOG.info("BADCM SIZE: %d", len(badcm))
            # cmqp = (numpy.invert(cmqp & 0x03))
            # cmqp = (cmqp * 16)
            # cmqp = numpy.invert(cmqp)
            # cmqp = cmqp & 0x03
            # numpy.bitwise_and(cmqp, 0x03, out=cmqp)
            # cmqp = (cmqp * 4)
            # LOG.info("ZERO COUNT AFT: %d", cmqp.size - numpy.count_nonzero(cmqp))

            # mask off the actual Cloud Mask bits
            # bowtie = numpy.where(data == 0)
            # LOG.info("BOWTIE SIZE: %d", len(bowtie))
            # this is the one line that usually works
            # numpy.bitwise_and(data, 0x0C, out=data)
            # data[bowtie] = 0x0C
            # data[badcm] = 255
            # data[goodcm] = 5
            # numpy.bitwise_or(cmqp, data, out=data)
            # numpy.bitwise_or((data & 0x0C), cmqp, out=data)
            # so each flag is easier to visualize
            # data = data * 16
            # LOG.info("unique: %s", numpy.unique(data))

        return data


class VIIRSSDRMultiReader(BaseMultiFileReader):
    """Helper class to wrap multiple VIIRS SDR Files and assist in reading them.
    """
    SINGLE_FILE_CLASS = VIIRSSDRReader

    def __init__(self, file_type_info):
        """Load multiple HDF5 files, sorting by start time if necessary.
        """
        super(VIIRSSDRMultiReader, self).__init__(file_type_info, VIIRSSDRReader)

    def get_orbit_rows(self, data_key):
        """List of number of rows for each orbit being processed.

        In the common case the returned list will only have one element. In the future, this shouldn't be needed
        because multiple orbits should be processed as separate scenes.
        """
        if hasattr(self, "_orbit_scans"):
            return self._orbit_scans

        orbit_rows = []
        begin_times = [fr.begin_time for fr in self.file_readers]
        end_times = [fr.end_time for fr in self.file_readers]
        num_rows = [fr[data_key].shape[0] for fr in self.file_readers]
        prev_end = end_times[0]
        current_num_rows = num_rows[0]
        for idx in range(1, len(begin_times)):
            if begin_times[idx] - prev_end > ORBIT_TRANSITION_THRESHOLD:
                orbit_rows.append(current_num_rows)
                current_num_rows = 0
            current_num_rows += num_rows[idx]
            prev_end = end_times[idx]
        else:
            # on the last file
            orbit_rows.append(current_num_rows)

        return orbit_rows

    def __getitem__(self, item):
        val = super(VIIRSSDRMultiReader, self).__getitem__(item)
        if item == K_MOONILLUM:
            # special case for handling moon illumination fraction
            if isinstance(val, (list, tuple)) and isinstance(val[0], numpy.ndarray):
                # flatten out the structure if the VIIRS file had multiple granules
                val = [single_val for file_vals in val for single_val in file_vals]
        return val
