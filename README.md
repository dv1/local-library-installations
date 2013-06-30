LOCAL LIBRARY INSTALLATIONS SCRIPT
==================================

2013 by Carlos Rafael Giani (dv AT pseudoterminal DOT org)

Licensed under the GPL v2. See the LICENSE file for details.



What this is
------------

This script is intended for creating local installations of various libraries and frameworks, in case
a system-wide installation is impossible, impractical, or inconvenient. One example is a developer who
needs GStreamer 1.0 up and running, with VP8 support, even when using an older distribution.


Quick setup
-----------

Make sure you have at least Python 2.7 installed in your system. curl and wget are also necessary.

To build Opus and GStreamer with make -j5, run:

    ./build.py -p opus=1.0.2 -p gstreamer-1.0=1.0.7 -j 5

+(the -j X argument is optional ; also, do not forget about the space between -j and the number)

**NOTE**: the order matters. FIRST comes Opus, THEN GStreamer. Otherwise, GStreamer won't find the Opus binaries, and will not build the associated plugins.
Use the version numbers of the packages that you want. In this example, it would build Opus 1.0.2 and GStreamer 1.0.7 (the latter with Opus plugins, since Opus has been built before).


build.py usage
--------------

    usage: build.py [-h] [-j JOBS] [-p [PKG=VERSION [PKG=VERSION ...]]]
    
    supported packages:
        gstreamer-1.0 - GStreamer 1.0
        vpx - libvpx VP8 video codec library
        opus - Opus audio codec library
        bluez - BlueZ
        efl - Enlightenment Foundation Libraries
        orc - ORC Oil Runtime Compiler library
    
    Example call: ./build.py -p orc=0.4.17 gstreamer-1.0=1.1.1
    
    optional arguments:
      -h, --help            show this help message and exit
      -j JOBS               Specifies the number of jobs to run simultaneously when compiling
      -p [PKG=VERSION [PKG=VERSION ...]]
                            Package(s) to build; VERSION is either a valid version number,
			    or "git", in which case sources are fetched from git upstream instead

NOTE: Currently, only GStreamer 1.0 can be built from git.


How to use the built installation
---------------------------------

Run:

    source ./env.sh

Then, gst-inspect-1.0 and friends should be available.


Full GStreamer 1.0 setup using the script
-----------------------------------------

A full GStreamer 1.0.7 setup including GLib can be built by using this example call:

    ./build.py -p orc=0.4.17 opus=1.0.2 vpx=1.2.0 gstreamer-1.0=1.0.7 -j X

where X is the number of jobs that shall run in parallel with make (or equivalent build systems).


How to clean up
---------------

Just delete the staging/ and installation/ directories. downloads/ too if you are sure you don't need the downloaded stuff.
(Deleting the first two but not the last is useful for rebuilding, since it omits the downloading stage.)


Supported packages
------------------

At the moment, the following packages are supported (the package name you pass to -p is written in brackets):

* GStreamer 1.0 (`gstreamer-1.0`)
* Enlightenment Foundation Libraries (`efl`)
* Opus codec (`opus`)
* Opus audio codec (`opus`)
* VP8 video codec (`vpx`)
* ORC Oil Runtime Compiler, important for good GStreamer performance (`orc`)
* BlueZ Linux bluetooth package (`bluez`)
