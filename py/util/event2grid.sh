#!/usr/bin/env bash
#Script to chain together the process of retrieving data from PEATE (via dibs), processing that data (via CREFL and polar2grid), and pushing that data to FTP.
#Usage: event2grid.sh event_name_id /base/data/directory/ /base/work/directory <dibs and polar2grid command line options>

EVENT_ID=$1
BASE_DATA_DIR=$2
BASE_WORK_DIR=$3
DIBS_FLAGS=$4
P2G_FLAGS=$5

EXIT_NO_DATA=1
EXIT_SUCCESS=0

export PYTHONPATH=/data1/users/davidh/event2grid_env/python:$PYTHONPATH
# Add CREFL and other binaries to the path for execution
export PATH=/data1/users/davidh/event2grid_env/bin:$PATH
DIBS_VIIRS=/data1/users/davidh/event2grid_env/polar2grid/py/util/dibs_viirs.py
CREFL_RUN=/data1/users/davidh/event2grid_env/viirs_crefl/run_viirs_crefl.bash
PYTHON_EXEC=/data1/users/davidh/event2grid_env/ShellB3/bin/python
CREFL2GTIFF="$PYTHON_EXEC -m polar2grid.glue crefl gtiff true_color"
VIIRS2GTIFF="$PYTHON_EXEC -m polar2grid.glue viirs gtiff"
FTP_BASE_PATH=/pub/ssec/davidh/event2grid

# This event's download directory
EVENT_DL_DIR=$BASE_DATA_DIR/$EVENT_ID
mkdir -p $EVENT_DL_DIR
EVENT_WORK_DIR=$BASE_WORK_DIR/$EVENT_ID
mkdir -p $EVENT_WORK_DIR

# Turn on debugging
set -x

# Have dibs get what we need
echo "Calling dibs to download any data..."
cd $EVENT_DL_DIR
python $DIBS_VIIRS $EVENT_ID -vvv $DIBS_FLAGS
echo "Calling dibs to sort data into passes..."
python $DIBS_VIIRS $EVENT_ID -vvv --pass

# Get a list of passes we should process
for pass_dir in `ls -d $EVENT_DL_DIR/*.pass`; do
    # Get the name of the pass (without the state information)
    pass_dirname=$(basename $pass_dir)
    pass_dirname=${pass_dirname%.pass}
    ftp_data_path=$FTP_BASE_PATH/$EVENT_ID
    echo "Processing pass $pass_dir"

    # Move the pass directory to processing so we know we are done with it
    data_dir=${pass_dir%.pass}.processing
    mv $pass_dir $data_dir

    # FIXME: Make sure all of the necessary files made it or at least log what is missing

    # Create the working directory that CREFL files and Polar2Grid files will be created in
    work_dir=$EVENT_WORK_DIR/$pass_dirname
    mkdir -p $work_dir
    cd $work_dir
    
    # Remap using polar2grid (working dir has the crefl files)
    echo "Running crefl2gtiff..."
    $CREFL2GTIFF -vvv $P2G_FLAGS -f $data_dir
    echo "Running viirs2gtiff..."
    $VIIRS2GTIFF -vvv $P2G_FLAGS -f $data_dir

    # FIXME: This only sends true colors
    for gtiff_file in $work_dir/*.tif; do
        if [ -f $gtiff_file ]; then
            # FTP to a location
            echo "Pushing $gtiff_file to FTP server ($ftp_data_path)"
            ncftpput -m -u ftp -p david.hoese@ssec.wisc.edu ftp.ssec.wisc.edu $ftp_data_path $gtiff_file
        fi
    done
done

echo "Done with $EVENT_ID"
