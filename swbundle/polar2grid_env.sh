#!/usr/bin/env bash
### SWBUNDLE ENVIRONMENT SETUP ###
#
# Copyright (C) 2013 Space Science and Engineering Center (SSEC),
#  University of Wisconsin-Madison.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This file is part of the polar2grid software package. Polar2grid takes
# satellite observation data, remaps it, and writes it to a file format for
# input into another program.
# Documentation: http://www.ssec.wisc.edu/software/polar2grid/
#
#     Written by David Hoese    January 2013
#     University of Wisconsin-Madison 
#     Space Science and Engineering Center
#     1225 West Dayton Street
#     Madison, WI  53706
#     david.hoese@ssec.wisc.edu

# Only load the environment if it hasn't been done already
if [ -z "$POLAR2GRID_REV" ]; then
    if [ -z "$POLAR2GRID_HOME" ]; then 
      export POLAR2GRID_HOME="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"
    fi

    # Add all polar2grid scripts to PATH
    export PATH=$POLAR2GRID_HOME/bin:$PATH
    # Add ShellB3 to PATH
    export PATH=$POLAR2GRID_HOME/ShellB3/bin:$PATH
    # Don't let someone else's PYTHONPATH mess us up
    unset PYTHONPATH
    # Point gdal utilities to the proper data location
    export GDAL_DATA=$POLAR2GRID_HOME/ShellB3/share/gdal

    export POLAR2GRID_REV="$Id$"
fi

