#!/usr/bin/env bash
### Run simple tests to verify viirs2geotiff will run properly ###
# Should be renamed run.sh in the corresponding test tarball
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


oops() {
    echo "OOPS: $*"
    echo "FAILURE"
    exit 1
}

run_test() {
    echo "Running test for data in $2..."
    set -x
    viirs2gtiff.sh -g $1 -d $2
    set +x
    if [ $? -ne 0 ]; then
        echo "ERROR: viirs2awips.sh did not complete test $2 successfully"
        echo "ERROR: Won't remove test directory, check it for more information"
        echo "FAILURE"
        exit 2
    fi
}

# Setup viirs2awips environment
if [ -z "$POLAR2GRID_HOME" ]; then
    oops "POLAR2GRID_HOME needs to be defined"
fi
if [ ! -d "$POLAR2GRID_HOME" ]; then
    oops "POLAR2GRID_HOME does not exist: $POLAR2GRID_HOME"
fi

source $POLAR2GRID_HOME/bin/polar2grid_env.sh || oops "Could not find 'bin/polar2grid_env.sh' in POLAR2GRID_HOME"

# Find out where the tests are relative to this script
TEST_BASE="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Base directory for all test cases is $TEST_BASE"

# Make sure we can call viirs2awips.sh before making any test directories
which viirs2gtiff.sh || oops "viirs2gtiff.sh is not in PATH"

# Check if they specified a different working directory
if [ $# -ne 1 ]; then
    WORK_DIR=./p2g-v2g-basic-tests-$$
else
    echo "Will use $1 directory, but won't delete it"
    WORK_DIR=$1
fi

echo "Making temporary test directory $WORK_DIR"
mkdir -p $WORK_DIR || oops "Could not create test directory '$WORK_DIR'"
cd $WORK_DIR

# Run tests for each test data directory in the base directory
for DDIR in $TEST_BASE/*; do
    if [ -d $DDIR ] && [ `basename $DDIR` != "verify" ]; then
        # Make a unique working test directory
        TDIR=`basename $DDIR`-$$
        echo "Making temporary working directory $TDIR"
        mkdir -p $TDIR || oops "Couldn't make $TDIR test directory"
        pushd $TDIR

        run_test wgs84_fit $DDIR
        # Move all NetCDF files here
        mv npp_viirs_*.tif ../ || oops "No geotiff files created for $DDIR in $TDIR"

        popd
        echo "Removing test dir $TDIR"
        rm -r $TDIR || oops "Couldn't remove $TDIR test directory"
    fi
done

# End of all tests
echo "SUCCESS"

