LOCAL LIBRARY INSTALLATIONS SCRIPT
==================================

2013 by Carlos Rafael Giani (dv AT pseudoterminal DOT org)

Licensed under the GPL v2. See the LICENSE file for details.



Quick setup
-----------

To build Opus and GStreamer with make -j5, run:

    ./build.sh -p opus=1.0.1 -p gstreamer_1_0=1.0.2 -j 5

(the -j X argument is optional)

**NOTE**: the order MATTERS. FIRST comes Opus, THEN GStreamer. Otherwise, GStreamer won't find the Opus binaries, and will not build the associated plugins.
Use the version numbers of the packages that you want. In this example, it would build GStreamer 1.0.2 and Opus 1.0.1.


build.sh usage
--------------

    Usage: ./build.sh [OPTION]...

    Valid options:

      -p PACKAGE=VERSION   build and locally install VERSION of PACKAGE
                         (set version to "git" to build from git upstream)
      -j N                 use parallel build, with parallelization factor N
      -h                   this help


How to use the built installation
---------------------------------

Run:

    source ./env.sh

Then, gst-inspect-1.0 and friends should be available.


How to clean up
---------------

Just delete the staging/ and installation/ directories. downloads/ too if you are sure you don't need the downloaded stuff.
(Deleting the first two but not the last is useful for rebuilding, since it omits the downloading stage.)


Supported packages
------------------

At the moment, the following packages are supported (the package name you pass to -p is written in brackets):

* GStreamer 1.0 (`gstreamer_1_0`)
* Enlightenment Foundation Libraries (`efl`)
* Opus codec (`opus`)

Also:

* GStreamer 0.10 (`gstreamer_0_10`)

but this one isn't very well tested at the moment, and probably collides with GStreamer 1.0 (because of the registry etc.)