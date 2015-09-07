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
# input into another program.
# Documentation: http://www.ssec.wisc.edu/software/polar2grid/
#
# Written by David Hoese    November 2014
# University of Wisconsin-Madison
# Space Science and Engineering Center
# 1225 West Dayton Street
# Madison, WI  53706
# david.hoese@ssec.wisc.edu
"""Script for installing the polar2grid package. See the documentation site for more information:

http://www.ssec.wisc.edu/software/polar2grid/

:author:       David Hoese (davidh)
:contact:      david.hoese@ssec.wisc.edu
:organization: Space Science and Engineering Center (SSEC)
:copyright:    Copyright (c) 2014 University of Wisconsin SSEC. All rights reserved.
:date:         Nov 2014
:license:      GNU GPLv3
"""
__docformat__ = "restructuredtext en"
import os
from setuptools import setup, find_packages, Command
from distutils.extension import Extension
import numpy

extensions = [
    Extension("polar2grid.remap._ll2cr", sources=["polar2grid/remap/_ll2cr.pyx"], extra_compile_args=["-O3", "-Wno-unused-function"]),
    Extension("polar2grid.remap._fornav", sources=["polar2grid/remap/_fornav.pyx", "polar2grid/remap/_fornav_templates.cpp"], language="c++", extra_compile_args=["-O3", "-Wno-unused-function"])
]

try:
    from Cython.Build import cythonize
except ImportError:
    cythonize = None

if not os.getenv("USE_CYTHON", False) or cythonize is None:
    print("Cython will not be used. Use environment variable 'USE_CYTHON=True' to use it")
    def cythonize(extensions, **_ignore):
        """Fake function to compile from C/C++ files instead of compiling .pyx files with cython.
        """
        for extension in extensions:
            sources = []
            for sfile in extension.sources:
                path, ext = os.path.splitext(sfile)
                if ext in ('.pyx', '.py'):
                    if extension.language == 'c++':
                        ext = '.cpp'
                    else:
                        ext = '.c'
                    sfile = path + ext
                sources.append(sfile)
            extension.sources[:] = sources
        return extensions

version = '2.0.0'


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess
        import sys
        errno = subprocess.call([sys.executable, 'runtests.py'])
        raise SystemExit(errno)


def readme():
    with open("README.rst", "r") as f:
        return f.read()


classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 2 :: Only",  # Working on it, I swear
    "Programming Language :: Python :: Implementation :: CPython",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "Operating System :: POSIX :: Linux",  # Not sure if it works on Windows, since we don't normally support it, needs testing
    "Operating System :: MacOS :: MacOS X",
    "Intended Audience :: Science/Research",
    "Topic :: Scientific/Engineering",
    "Topic :: Scientific/Engineering :: Atmospheric Science",
    "Topic :: Scientific/Engineering :: GIS",
]

extras_require = {
    # Backends:
    "awips": ["netCDF4"],
    "gtiff": ["gdal"],
    "ninjo": ["pylibtiff"],
    "hdf5": ["h5py"],
    # Frontends (included separately):
    # Other:
    # FIXME: technically polar2grid.core.meta uses this through the polar2grid.proj module
    "remap": ["pyproj", "scipy"],
    "utils": ["matplotlib"],
}
extras_require["all"] = [x for y in extras_require.values() for x in y]

entry_points = {
    'console_scripts': [
        'p2g_glue=polar2grid.glue:main',
        'p2g_frontend=polar2grid.glue:main_frontend',
        'p2g_backend=polar2grid.glue:main_backend',
        'p2g_remap=polar2grid.remap.__main__:main',
        'p2g_composite=polar2grid.compositors:main',
    ],
    'polar2grid.backend_class': [
        'gtiff=polar2grid.gtiff_backend:Backend',
        'awips=polar2grid.awips.awips_netcdf:Backend',
        'binary=polar2grid.binary:Backend',
        'ninjo=polar2grid.ninjo:Backend',
        'hdf5=polar2grid.hdf5_backend:Backend',
        ],
    'polar2grid.backend_arguments': [
        'gtiff=polar2grid.gtiff_backend:add_backend_argument_groups',
        'awips=polar2grid.awips.awips_netcdf:add_backend_argument_groups',
        'binary=polar2grid.binary:add_backend_argument_groups',
        'ninjo=polar2grid.ninjo:add_backend_argument_groups',
        'hdf5=polar2grid.hdf5_backend:add_backend_argument_groups',
        ],
    'polar2grid.compositor_class': [
        'rgb=polar2grid.compositors.rgb:RGBCompositor',
        'true_color=polar2grid.compositors.rgb:TrueColorCompositor',
        'false_color=polar2grid.compositors.rgb:FalseColorCompositor',
        'crefl_sharpen=polar2grid.compositors.rgb:CreflRGBSharpenCompositor',
        ],
    }

setup(
    name='polar2grid',
    version=version,
    author='David Hoese, SSEC',
    author_email='david.hoese@ssec.wisc.edu',
    license='GPLv3',
    description="Library and scripts to remap satellite data to a grid",
    long_description=readme(),
    classifiers=classifiers,
    keywords='',
    url="http://www.ssec.wisc.edu/software/polar2grid/",
    download_url="http://larch.ssec.wisc.edu/simple/polar2grid",
    ext_modules=cythonize(extensions),
    include_dirs=[numpy.get_include()],
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=["polar2grid"],
    include_package_data=True,
    package_data={'polar2grid': ["compositors/*.ini", "awips/*.ini", "grids/*.conf", "ninjo/*.ini"]},
    zip_safe=True,
    tests_require=['py.test'],
    cmdclass={'test': PyTest},
    install_requires=[
        'setuptools',       # reading configuration files
        'numpy',
        'polar2grid.core[all]',  # Almost everything touches this in some way
        ],
    extras_require=extras_require,
    entry_points=entry_points
)

