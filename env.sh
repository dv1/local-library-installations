#!/usr/bin/env sh

installation_dir="$(pwd)/installation"

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
