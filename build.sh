#!/usr/bin/env bash


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



# TODO:
# - further tests
# - make it possible to pass extra arguments to ./configure calls
# - more code reuse (check_gstreamer/check_opus duplicate a lot for example)
# - what if the version number is omitted? Default version? Error?
# - support for more detailed git checkouts (example: gstreamer=git-abc : clone git repo ,
#   use branch "abc" ; gstreamer=git : same, branch defaults to "master")
# - support for building GLib
# - what if the package file itself is present but the checksum one isn't?
# - make use of optflags
# - don't use $(pwd) for getting the root path - try to get the script's location instead


set -e


num_args=$#
root=$(pwd)
optflags="-O0 -g3 -ggdb"
dl_dir="$root/downloads"
staging_dir="$root/staging"
installation_dir="$root/installation"
num_jobs=1


# helper to call a function if it exists and return 1 if it doesn't exist
checked_call_function ()
{
	if declare -f "$1" > /dev/null
	then
		"$1" "${@:2}" # ${@:2} passes all arguments except the first one to the function specified in $1
		retval=$?
		return $retval
	else
		return 1
	fi	
}


# safety wrapper for rm
# it always expects an option - call it like this: checked_rm <opt> <file1> <file2> ..
checked_rm ()
{
	options="$1"
	for arg in ${@:2}
	do
		filename=$(readlink -f "$arg")
		filepath=$(dirname "$filename")
		allowed_filepaths=( \
			$(readlink -f "$dl_dir") \
			$(readlink -f "$staging_dir") \
			$(readlink -f "$installation_dir") \
		)
		error=1
		for allowed_filepath in ${allowed_filepaths[@]}
		do
			if [ "$allowed_filepath" == "$filepath" ]
			then
				error=0
				break
			fi
		done
		if [ $error -eq 1 ]
		then
			echo "!!!!! FATAL: Caught attempt to delete \"$filename\", which is outside of" \
				"the list of directories where deleting is allowed"
			exit -1
		fi
	done
	echo Executing: rm "$options" "${@:2}"
	rm "$options" "${@:2}"
}


mkdir -p "$dl_dir"
mkdir -p "$staging_dir"
mkdir -p "$installation_dir"
mkdir -p "$installation_dir/bin"
mkdir -p "$installation_dir/include"
mkdir -p "$installation_dir/lib/pkgconfig"
mkdir -p "$installation_dir/share/aclocal"


source "$root/env.sh"





########################
#### GSTREAMER-0.10 ####
########################

gst_0_10_pkgs=( \
	"gstreamer" \
	"gst-plugins-base" \
	"gst-plugins-good" \
	"gst-plugins-bad" \
	"gst-plugins-ugly" \
	"gst-ffmpeg" \
)
gst_0_10_pkg_source="http://gstreamer.freedesktop.org/src"
gst_0_10_git_source="git://anongit.freedesktop.org/gstreamer"
gst_0_10_pkg_ext="tar.bz2"
gst_0_10_pkg_checksum_prog="md5sum"
gst_0_10_pkg_checksum_ext="md5"

parse_gstreamer_0_10_version ()
{
	echo "$1" | sed -e 's/^\([^:]*\):\([^:]*\):\([^:]*\):\([^:]*\):\([^:]*\):\([^:]*\)$/\1 \2 \3 \4 \5 \6/'
}

fetch_gstreamer_0_10 ()
{
	gst_0_10_versions=($(parse_gstreamer_0_10_version $1))
	echo "Building GStreamer 0.10 with the following versions:"
	echo "core:   ${gst_0_10_versions[0]}"
	echo "base:   ${gst_0_10_versions[1]}"
	echo "good:   ${gst_0_10_versions[2]}"
	echo "bad:    ${gst_0_10_versions[3]}"
	echo "ugly:   ${gst_0_10_versions[4]}"
	echo "ffmpeg: ${gst_0_10_versions[5]}"

	i=0
	for gst_0_10_pkg in ${gst_0_10_pkgs[@]}
	do
		version=${gst_0_10_versions[$i]}
		i=$(expr "$i" "+" "1")
		gst_0_10_pkg_basename="$gst_0_10_pkg-$version"
		if [ "$version" == "git" ]
		then
			gst_0_10_git_link="$gst_0_10_git_source/$gst_0_10_pkg"
			gst_0_10_git_dest="$staging_dir/$gst_0_10_pkg_basename"
			if [ -d "$gst_0_10_git_dest" ]
			then
				pushd "$gst_0_10_git_dest" >/dev/null
				git pull
				popd >/dev/null
			else
				git clone "$gst_0_10_git_link" "$gst_0_10_git_dest"
				git checkout "0.10"
			fi
		else
			gst_0_10_pkg_filename="$gst_0_10_pkg_basename.$gst_0_10_pkg_ext"
			gst_0_10_pkg_link="$gst_0_10_pkg_source/$gst_0_10_pkg/$gst_0_10_pkg_filename"
			gst_0_10_pkg_dest="$dl_dir/$gst_0_10_pkg_filename"
			if [ -f "$gst_0_10_pkg_dest" ]
			then
				echo "### $gst_0_10_pkg_filename present - downloading skipped"
			else
				echo "### $gst_0_10_pkg_filename not present - downloading from $gst_0_10_pkg_link"
				wget "$gst_0_10_pkg_link" -P "$dl_dir"
				wget "$gst_0_10_pkg_link.$gst_0_10_pkg_checksum_ext" -P "$dl_dir"
			fi
		fi
	done
}

check_gstreamer_0_10 ()
{
	gst_0_10_versions=($(parse_gstreamer_0_10_version $1))
	pushd "$dl_dir" >/dev/null
	i=0
	for gst_0_10_pkg in ${gst_0_10_pkgs[@]}
	do
		version=${gst_0_10_versions[$i]}
		i=$(expr "$i" "+" "1")
		if [ "$version" == "git" ]
		then
			continue
		fi
		gst_0_10_pkg_basename="$gst_0_10_pkg-$version"
		gst_0_10_pkg_filename="$gst_0_10_pkg_basename.$gst_0_10_pkg_ext"
		gst_0_10_pkg_dest="$dl_dir/$gst_0_10_pkg_filename"
		gst_0_10_pkg_dest_checksum="$gst_0_10_pkg_dest.$gst_0_10_pkg_checksum_ext"
		if $gst_0_10_pkg_checksum_prog -c "$gst_0_10_pkg_dest_checksum" --quiet >/dev/null 2>&1
		then
			echo "### $gst_0_10_pkg_basename $gst_0_10_pkg_checksum_ext check : OK"
		else
			echo "### $gst_0_10_pkg_basename $gst_0_10_pkg_checksum_ext check : FAILED"
			echo "Removing downloaded files for $gst_0_10_pkg_basename"
			checked_rm -f "$gst_0_10_pkg_dest" "$gst_0_10_pkg_dest_checksum"
			if [ -d "$staging_dir/$gst_0_10_pkg_basename" ]
			then
				echo "Removing unpacked content in $staging_dir/$gst_0_10_pkg_basename"
				checked_rm -rf "$staging_dir/$gst_0_10_pkg_basename"
			fi
			exit 1
		fi
	done
	popd >/dev/null
}

unpack_gstreamer_0_10 ()
{
	gst_0_10_versions=($(parse_gstreamer_0_10_version $1))
	pushd "$staging_dir" >/dev/null
	i=0
	for gst_0_10_pkg in ${gst_0_10_pkgs[@]}
	do
		version=${gst_0_10_versions[$i]}
		i=$(expr "$i" "+" "1")
		if [ "$version" == "git" ]
		then
			continue
		fi
		gst_0_10_pkg_basename="$gst_0_10_pkg-$version"
		gst_0_10_pkg_filename="$gst_0_10_pkg_basename.$gst_0_10_pkg_ext"
		gst_0_10_pkg_full_filename="$dl_dir/$gst_0_10_pkg_filename"
		if [ -d "$gst_0_10_pkg_basename" ]
		then
			echo "### Directory $staging_dir/$gst_0_10_pkg_basename present - unpacking skipped"
		else
			echo "### Directory $staging_dir/$gst_0_10_pkg_basename no present - unpacking"
			tar xf "$gst_0_10_pkg_full_filename"
		fi
	done
	popd >/dev/null
}

build_gstreamer_0_10 ()
{
	gst_0_10_versions=($(parse_gstreamer_0_10_version $1))
	i=0
	for gst_0_10_pkg in ${gst_0_10_pkgs[@]}
	do
		version=${gst_0_10_versions[$i]}
		i=$(expr "$i" "+" "1")
		gst_0_10_pkg_basename="$gst_0_10_pkg-$version" >/dev/null
		echo "### Building $gst_0_10_pkg_basename in $staging_dir/$gst_0_10_pkg_basename"
		pushd "$staging_dir/$gst_0_10_pkg_basename"
		if [ "$version" == "git" ]
		then
			./autogen.sh --noconfigure
		fi
		./configure "--prefix=$installation_dir"
		make "-j$num_jobs"
		make install
		popd >/dev/null
	done
}






#######################
#### GSTREAMER-1.0 ####
#######################

gst_1_0_pkgs=( \
	"gstreamer" \
	"gst-plugins-base" \
	"gst-plugins-good" \
	"gst-plugins-bad" \
	"gst-plugins-ugly" \
	"gst-libav" \
)
gst_1_0_pkg_source="http://gstreamer.freedesktop.org/src"
gst_1_0_git_source="git://anongit.freedesktop.org/gstreamer"
gst_1_0_pkg_ext="tar.xz"
gst_1_0_pkg_checksum="sha256sum"

fetch_gstreamer_1_0 ()
{
	gst_1_0_version=$1
	for gst_1_0_pkg in ${gst_1_0_pkgs[@]}
	do
		gst_1_0_pkg_basename="$gst_1_0_pkg-$gst_1_0_version"
		if [ "$gst_1_0_version" == "git" ]
		then
			gst_1_0_git_link="$gst_1_0_git_source/$gst_1_0_pkg"
			gst_1_0_git_dest="$staging_dir/$gst_1_0_pkg_basename"
			if [ -d "$gst_1_0_git_dest" ]
			then
				pushd "$gst_1_0_git_dest" >/dev/null
				git pull
				popd >/dev/null
			else
				git clone "$gst_1_0_git_link" "$gst_1_0_git_dest"
			fi
		else
			gst_1_0_pkg_filename="$gst_1_0_pkg_basename.$gst_1_0_pkg_ext"
			gst_1_0_pkg_link="$gst_1_0_pkg_source/$gst_1_0_pkg/$gst_1_0_pkg_filename"
			gst_1_0_pkg_dest="$dl_dir/$gst_1_0_pkg_filename"
			if [ -f "$gst_1_0_pkg_dest" ]
			then
				echo "### $gst_1_0_pkg_filename present - downloading skipped"
			else
				echo "### $gst_1_0_pkg_filename not present - downloading from $gst_1_0_pkg_link"
				wget "$gst_1_0_pkg_link" -P "$dl_dir"
				wget "$gst_1_0_pkg_link.$gst_1_0_pkg_checksum" -P "$dl_dir"
			fi
		fi
	done
}

check_gstreamer_1_0 ()
{
	gst_1_0_version=$1
	if [ "$gst_1_0_version" == "git" ]
	then
		return 0
	fi
	pushd "$dl_dir" >/dev/null
	for gst_1_0_pkg in ${gst_1_0_pkgs[@]}
	do
		gst_1_0_pkg_basename="$gst_1_0_pkg-$gst_1_0_version"
		gst_1_0_pkg_filename="$gst_1_0_pkg_basename.$gst_1_0_pkg_ext"
		gst_1_0_pkg_dest="$dl_dir/$gst_1_0_pkg_filename"
		gst_1_0_pkg_dest_checksum="$gst_1_0_pkg_dest.$gst_1_0_pkg_checksum"
		if $gst_1_0_pkg_checksum -c "$gst_1_0_pkg_dest_checksum" --quiet >/dev/null 2>&1
		then
			echo "### $gst_1_0_pkg_basename $gst_1_0_pkg_checksum check : OK"
		else
			echo "### $gst_1_0_pkg_basename $gst_1_0_pkg_checksum check : FAILED"
			echo "Removing downloaded files for $gst_1_0_pkg_basename"
			checked_rm -f "$gst_1_0_pkg_dest" "$gst_1_0_pkg_dest_checksum"
			if [ -d "$staging_dir/$gst_1_0_pkg_basename" ]
			then
				echo "Removing unpacked content in $staging_dir/$gst_1_0_pkg_basename"
				checked_rm -rf "$staging_dir/$gst_1_0_pkg_basename"
			fi
			exit 1
		fi
	done
	popd >/dev/null
}

unpack_gstreamer_1_0 ()
{
	gst_1_0_version=$1
	if [ "$gst_1_0_version" == "git" ]
	then
		return 0
	fi
	pushd "$staging_dir" >/dev/null
	for gst_1_0_pkg in ${gst_1_0_pkgs[@]}
	do
		gst_1_0_pkg_basename="$gst_1_0_pkg-$gst_1_0_version"
		gst_1_0_pkg_filename="$gst_1_0_pkg_basename.$gst_1_0_pkg_ext"
		gst_1_0_pkg_full_filename="$dl_dir/$gst_1_0_pkg_filename"
		if [ -d "$gst_1_0_pkg_basename" ]
		then
			echo "### Directory $staging_dir/$gst_1_0_pkg_basename present - unpacking skipped"
		else
			echo "### Directory $staging_dir/$gst_1_0_pkg_basename no present - unpacking"
			tar xf "$gst_1_0_pkg_full_filename"
		fi
	done
	popd >/dev/null
}

build_gstreamer_1_0 ()
{
	gst_1_0_version=$1
	for gst_1_0_pkg in ${gst_1_0_pkgs[@]}
	do
		gst_1_0_pkg_basename="$gst_1_0_pkg-$gst_1_0_version" >/dev/null
		echo "### Building $gst_1_0_pkg_basename in $staging_dir/$gst_1_0_pkg_basename"
		pushd "$staging_dir/$gst_1_0_pkg_basename"
		if [ "$gst_1_0_version" == "git" ]
		then
			./autogen.sh --noconfigure
		fi
		./configure "--prefix=$installation_dir"
		make "-j$num_jobs"
		make install
		popd >/dev/null
	done
}





#############
#### EFL ####
#############

efl_pkgs=( \
	"eina" \
	"eet" \
	"evas" \
	"ecore" \
	"eio" \
	"embryo" \
	"edje" \
	"efreet" \
	"e_dbus" \
	"eeze" \
	"elementary" \
	"expedite" \
	"evas_generic_loaders" \
	"emotion" \
)
efl_pkg_source="http://download.enlightenment.org/releases"
efl_pkg_ext="tar.bz2"

fetch_efl ()
{
	efl_version=$1
	for efl_pkg in ${efl_pkgs[@]}
	do
		efl_pkg_basename="$efl_pkg-$efl_version"
		efl_pkg_filename="$efl_pkg_basename.$efl_pkg_ext"
		efl_pkg_link="$efl_pkg_source/$efl_pkg_filename"
		efl_pkg_dest="$dl_dir/$efl_pkg_filename"
		if [ -f "$efl_pkg_dest" ]
		then
			echo "### $efl_pkg_filename present - downloading skipped"
		else
			echo "### $efl_pkg_filename not present - downloading from $efl_pkg_link"
			wget "$efl_pkg_link" -P "$dl_dir"
		fi
	done
}

check_efl ()
{
	return 0
}

unpack_efl ()
{
	efl_version=$1
	pushd "$staging_dir" >/dev/null
	for efl_pkg in ${efl_pkgs[@]}
	do
		efl_pkg_basename="$efl_pkg-$efl_version"
		efl_pkg_filename="$efl_pkg_basename.$efl_pkg_ext"
		efl_pkg_full_filename="$dl_dir/$efl_pkg_filename"
		if [ -d "$efl_pkg_basename" ]
		then
			echo "### Directory $staging_dir/$efl_pkg_basename present - unpacking skipped"
		else
			echo "### Directory $staging_dir/$efl_pkg_basename no present - unpacking"
			tar xf "$efl_pkg_full_filename"
		fi
	done
	popd >/dev/null
}

build_efl ()
{
	efl_version=$1
	for efl_pkg in ${efl_pkgs[@]}
	do
		efl_pkg_basename="$efl_pkg-$efl_version" >/dev/null
		echo "### Building $efl_pkg_basename in $staging_dir/$efl_pkg_basename"
		pushd "$staging_dir/$efl_pkg_basename"
		./configure "--prefix=$installation_dir"
		make "-j$num_jobs"
		make install
		popd >/dev/null
	done
}





##############
#### OPUS ####
##############

opus_source="http://downloads.xiph.org/releases/opus"
opus_ext="tar.gz"
opus_checksum="sha1sum"

fetch_opus ()
{
	opus_version=$1
	opus_basename="opus-$opus_version"
	opus_filename="$opus_basename.$opus_ext"
	opus_link="$opus_source/$opus_filename"
	opus_link_sha1sum="$opus_source/SHA1SUMS"
	opus_dest="$dl_dir/$opus_filename"
	opus_dest_checksum="$opus_dest.$opus_checksum"

	if [ -f "$opus_dest" ]
	then
		echo "### $opus_filename present - downloading skipped"
	else
		echo "### $opus_filename not present - downloading from $opus_link"
		wget "$opus_link" -P "$dl_dir"
		curl -s "$opus_link_sha1sum" | grep "$opus_filename" >"$opus_dest_checksum"
	fi
}

check_opus ()
{
	opus_version=$1
	opus_basename="opus-$opus_version"
	opus_filename="$opus_basename.$opus_ext"
	opus_dest="$dl_dir/$opus_filename"
	opus_dest_checksum="$opus_dest.$opus_checksum"

	pushd "$dl_dir" >/dev/null
	if $opus_checksum -c "$opus_dest_checksum" --quiet >/dev/null 2>&1
	then
		echo "### $opus_basename $opus_checksum check : OK"
	else
		echo "### $opus_basename $opus_checksum check : FAILED"
		echo "Removing downloaded files for $opus_basename"
		checked_rm -f "$opus_dest" "$opus_dest_checksum"
		if [ -d "$staging_dir/$opus_basename" ]
		then
			echo "Removing unpacked content in $staging_dir/$opus_basename"
			checked_rm -rf "$staging_dir/$opus_basename"
		fi
		exit 1
	fi
	popd >/dev/null
}

unpack_opus ()
{
	opus_version=$1
	opus_basename="opus-$opus_version"
	opus_filename="$opus_basename.$opus_ext"
	opus_full_filename="$dl_dir/$opus_filename"
	pushd "$staging_dir" >/dev/null
	if [ -d "$opus_basename" ]
	then
		echo "### Directory $staging_dir/$opus_basename present - unpacking skipped"
	else
		echo "### Directory $staging_dir/$opus_basename no present - unpacking"
		tar xf "$opus_full_filename"
	fi
	popd >/dev/null
}

build_opus ()
{
	opus_version=$1
	opus_basename="opus-$opus_version"
	echo "### Building $opus_basename in $staging_dir/$opus_basename"
	pushd "$staging_dir/$opus_basename" >/dev/null
	./configure "--prefix=$installation_dir"
	make "-j$num_jobs"
	make install
	popd >/dev/null
}





##############
#### MAIN ####
##############

print_help ()
{
        echo "Usage: $0 [OPTION]..."
	echo ""
	echo "Valid options:"
	echo "  -p PACKAGE=VERSION   build and locally install VERSION of PACKAGE"
	echo "                       (set version to \"git\" to build from git upstream)"
	echo "  -j N                 use parallel build, with parallelization factor N"
	echo "  -h                   this help"
        exit -1
}

if [ $num_args -lt 1 ]
then
	print_help
fi


declare -a packages=()


# parse arguments
while getopts ":p:j:" opt
do
	case $opt in
		p)
			package=($(echo "$OPTARG" | sed -e 's/^\([^=]*\)=\(.*\)$/\1 \2/'))
			pkg_name="${package[0]}"
			pkg_version="${package[1]}"
			packages=("${packages[@]}" "$pkg_name" "$pkg_version")
			;;
		j)
			num_jobs="$OPTARG"
			echo "Building with JOBS=$num_jobs"
			;;
		h)
			print_help
			;;
		\?)
			echo "Invalid option: -$OPTARG" >&2
			echo ""
			print_help
			exit 1
			;;
		:)
			echo "Option -$OPTARG requires an argument." >&2
			exit 1
			;;
	esac
done


for func in fetch check unpack build
do
	set ${packages[@]}
	while [ $# -gt 0 ]
	do
		pkg_name="$1"
		pkg_version="$2"
		shift
		shift
		echo "###### calling $func function for $pkg_name version $pkg_version"
		if ! checked_call_function "$func""_""$pkg_name" "$pkg_version"
		then
			echo "No $func function for $pkg_name exists or $func function failed. Stop."
			exit 1
		fi
	done
done

