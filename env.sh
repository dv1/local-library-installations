#!/usr/bin/env sh


# BASH shell script for building local library installations
# Copyright (C) 2013  Carlos Rafael Giani
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


num_args=$#

if [ $num_args -lt 1 ]
then
	installation_dir="$(pwd)/installation"
else
	installation_dir="$1/installation"
fi


export PATH="$installation_dir/bin:$PATH"
export CFLAGS="-I$installation_dir/include"
export CCFLAGS="-I$installation_dir/include"
export CXXFLAGS="-I$installation_dir/include"
export LDFLAGS="-L$installation_dir/lib"
export PKG_CONFIG_PATH="$installation_dir/lib/pkgconfig"
export ACLOCAL_FLAGS="-I $installation_dir/share/aclocal"
export GST_PLUGINS_DIR="$installation_dir/lib/gstreamer-1.0"
export GST_PLUGIN_PATH="$GST_PLUGINS_DIR"
export GST_REGISTRY="$installation_dir/gst-registry.bin"
export GST_PLUGIN_SYSTEM_PATH="$installation_dir/lib/gstreamer-1.0"
export LD_LIBRARY_PATH="$installation_dir/lib"
