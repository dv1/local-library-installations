#!/usr/bin/env python


import os, subprocess, sys, hashlib, argparse


def mkdir_p(path):
	if not os.path.exists(path):
		os.makedirs(path)

def msg(text, level = 3):
	sys.stdout.write(('#' * level) + ' ' + text + '\n')
def error(text):
	sys.stderr.write('!!!!!! ' + text + '\n')


def hashfile_blk(afile, hasher, blocksize=65536):
	buf = afile.read(blocksize)
	while len(buf) > 0:
		hasher.update(buf)
		buf = afile.read(blocksize)
	return hasher.hexdigest()

def hashfile(fname, hashfuncname):
	hashfunc = getattr(globals()['hashlib'], hashfuncname)
	with open(fname, 'rb') as f:
		return hashfile_blk(f, hashfunc())



class Context:
	def __init__(self, rootdir):
		self.rootdir = os.path.abspath(os.path.expanduser(rootdir))
		self.dl_dir = os.path.join(self.rootdir, 'downloads')
		self.staging_dir = os.path.join(self.rootdir, 'staging')
		self.inst_dir = os.path.join(self.rootdir, 'installation')
		self.allowed_paths = [self.dl_dir, self.staging_dir, self.inst_dir]
		self.num_jobs = 1
		self.package_builders = {}
		mkdir_p(self.dl_dir)
		mkdir_p(self.staging_dir)
		mkdir_p(self.inst_dir)
		mkdir_p(os.path.join(self.inst_dir, 'bin'))
		mkdir_p(os.path.join(self.inst_dir, 'include'))
		mkdir_p(os.path.join(self.inst_dir, 'lib', 'pkgconfig'))
		mkdir_p(os.path.join(self.inst_dir, 'share', 'aclocal'))

	def call_with_env(self, cmd, extra_cmds = None):
		# Avoid bashisms:
		# * Use "." , not "source"
		# * Use environment variable to pass on the rootdir
		#   instead of script arguments
		if extra_cmds:
			retval = subprocess.call('ROOTDIR="%s" . "%s/env.sh" ; %s ; %s' % (self.rootdir, self.rootdir, extra_cmds, cmd), shell = True)
		else:
			retval = subprocess.call('ROOTDIR="%s" . "%s/env.sh" ; %s' % (self.rootdir, self.rootdir, cmd), shell = True)
		return retval

	def checked_rm(self, options, filelist):
		# first check if all entries in the filelist are OK
		for f in filelist:
			path = os.path.dirname(f)
			for allowed_path in self.allowed_paths:
				if path != allowed_path:
					raise IOError('Caught attempt to delete %s, which is not located in a path where deleting is allowed' % f)
		# then actually delete
		subprocess.call('rm %s %s' % (options, ' '.join(filelist)), shell = False)

	def build_package(self, package_name, package_version):
		try:
			package_builder = self.package_builders[package_name]
		except KeyError:
			error('invalid package "%s"' % package_name)
			return

		for func in ['fetch', 'check', 'unpack', 'build']:
			print('')
			msg('calling %s function for package %s version %s' % (func, package_name, package_version), 6)
			try:
				m = getattr(package_builder, func)
			except AttributeError:
				error('package builder has no %s function' % func)
				exit(-1)
			if not m(self, package_version):
				error('function %s failed' % func)
				exit(-1)



class Builder(object):
	def __init__(self, ctx):
		self.ctx = ctx

	def get_staging_dir(self, basename, staging_subdir):
		if staging_subdir:
			return os.path.join(ctx.staging_dir, staging_subdir, basename)
		else:
			return os.path.join(ctx.staging_dir, basename)

	def fetch_package_file(self, filename, dest, dest_hash, link, link_hash):
		if os.path.exists(dest):
			msg('%s present - downloading skipped' % filename)
		else:
			msg('%s not present - downloading from %s' % (filename, link))
			if 0 != subprocess.call('wget -c "%s" -O "%s"' % (link, dest), shell = True):
				return False
			if (dest_hash != None) and (link_hash != None):
				if 0 != subprocess.call('wget -c "%s" -O "%s"' % (link_hash, dest_hash), shell = True):
					return False
		return True

	def check_package(self, name, basename, hashcall, dest_hash, staging_subdir = ''):
		olddir = os.getcwd()
		os.chdir(self.ctx.dl_dir)
		retval = subprocess.call('%s -c "%s" --quiet >/dev/null 2>&1' % (hashcall, dest_hash), shell = True)
		os.chdir(olddir)

		if 0 == retval:
			msg('%s checksum : OK' % name)
		else:
			msg('%s checksum : FAILED' % name)
			return False

		return True

	def clone_git_repo(self, link, basename, checkout = None, staging_subdir = ''):
		staging = self.get_staging_dir(basename, staging_subdir)
		if os.path.exists(staging):
			msg('Directory %s present - not cloning anything' % staging)
		else:
			msg('Directory %s not present - cloning from %s' % (staging, link))
			if checkout:
				if 0 != subprocess.call('git clone -b "%s" "%s" "%s"' % (checkout, link, staging), shell = True):
					return False
			else:
				if 0 != subprocess.call('git clone "%s" "%s"' % (link, staging), shell = True):
					return False
		return True

	def unpack_package(self, basename, dest, staging_subdir = ''):
		staging = self.get_staging_dir(basename, staging_subdir)
		if os.path.exists(staging):
			msg('Directory %s present - unpacking skipped' % staging)
		else:
			msg('Directory %s not present - unpacking' % staging)
			unpack_rootdir = self.get_staging_dir('', staging_subdir)
			mkdir_p(unpack_rootdir)
			if 0 != subprocess.call('tar xf "%s" -C "%s"' % (dest, unpack_rootdir), shell = True):
				return False
		return True

	def do_config_make_build(self, basename, use_autogen, extra_config = '', extra_cflags = '', extra_cxxflags = '', staging_subdir = '', noconfigure = True, use_noconfig_env = False):
		staging = self.get_staging_dir(basename, staging_subdir)
		olddir = os.getcwd()
		os.chdir(staging)
		success = True
		if use_autogen:
			if noconfigure:
				if use_noconfig_env:
					success = success and (0 == ctx.call_with_env('NOCONFIGURE=1 ./autogen.sh'))
				else:
					success = success and (0 == ctx.call_with_env('./autogen.sh --noconfigure'))
			else:
				success = success and (0 == ctx.call_with_env('./autogen.sh --prefix="%s" %s' % (ctx.inst_dir, extra_config), 'export CFLAGS="$CFLAGS %s" ; export CXXFLAGS="$CXXFLAGS %s" ' % (extra_cxxflags, extra_cxxflags)))
		if (not use_autogen) or (use_autogen and noconfigure):
				success = success and (0 == ctx.call_with_env('./configure --prefix="%s" %s' % (ctx.inst_dir, extra_config), 'export CFLAGS="$CFLAGS %s" ; export CXXFLAGS="$CXXFLAGS %s" ' % (extra_cxxflags, extra_cxxflags)))

		success = success and (0 == ctx.call_with_env('make "-j%d"' % ctx.num_jobs))
		os.chdir(olddir)
		return success

	def do_make_install(self, basename, parallel = True, staging_subdir = ''):
		staging = self.get_staging_dir(basename, staging_subdir)
		olddir = os.getcwd()
		os.chdir(staging)
		if parallel:
			success = (0 == ctx.call_with_env('make "-j%d" install' % ctx.num_jobs))
		else:
			success = (0 == ctx.call_with_env('make install'))
		os.chdir(olddir)
		return success

	def do_meson_ninja_build(self, basename, extra_config = '', extra_cflags = '', extra_cxxflags = '', staging_subdir = '', build_subdir = 'build'):
		staging = self.get_staging_dir(basename, staging_subdir)
		builddir = os.path.join(staging, build_subdir)
		olddir = os.getcwd()
		mkdir_p(builddir)
		os.chdir(builddir)
		success = True
		success = success and (0 == ctx.call_with_env('meson -Dprefix="%s" %s' % (ctx.inst_dir, extra_config), 'export CFLAGS="$CFLAGS %s" ; export CXXFLAGS="$CXXFLAGS %s" ' % (extra_cxxflags, extra_cxxflags)))
		success = success and (0 == ctx.call_with_env('ninja "-j%d"' % ctx.num_jobs))
		success = success and (0 == ctx.call_with_env('ninja install "-j%d"' % ctx.num_jobs))
		os.chdir(olddir)
		return success



class OpusBuilder(Builder):
	opus_source="http://downloads.xiph.org/releases/opus"
	opus_ext="tar.gz"

	def __init__(self, ctx):
		super(OpusBuilder, self).__init__(ctx)

	def desc(self):
		return "Opus audio codec library"

	def fetch(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		archive_filename = basename + '.' + OpusBuilder.opus_ext
		archive_link = OpusBuilder.opus_source + '/' + archive_filename
		archive_link_sha1sum = OpusBuilder.opus_source + '/SHA1SUMS'
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'opus-sha1sums')
		archive_dest_checksum_tmp = os.path.join(ctx.dl_dir, 'opus-sha1sums-tmp')

		if not self.fetch_package_file(archive_filename, archive_dest, archive_dest_checksum_tmp, archive_link, archive_link_sha1sum):
			return False

		subprocess.call('grep "%s" "%s" >"%s"' % (archive_filename, archive_dest_checksum_tmp, archive_dest_checksum), shell = True)
		return True

	def check(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		archive_filename = basename + '.' + OpusBuilder.opus_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'opus-sha1sums')
		return self.check_package(name = 'opus', basename = basename, hashcall = 'sha1sum', dest_hash = archive_dest_checksum)

	def unpack(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		archive_filename = basename + '.' + OpusBuilder.opus_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		return self.do_config_make_build(basename = basename, use_autogen = False) and self.do_make_install(basename)



class GStreamer10Builder(Builder):
	pkgs = [ \
		"gstreamer", \
		"gst-plugins-base", \
		"gst-plugins-good", \
		"gst-plugins-bad", \
		"gst-plugins-ugly", \
		"gst-libav", \
		"gst-rtsp-server", \
	]
	pkg_source = "http://gstreamer.freedesktop.org/src"
	git_source = "git://anongit.freedesktop.org/gstreamer"
	pkg_ext = "tar.xz"
	pkg_checksum = "sha256sum"

	def __init__(self, ctx):
		super(GStreamer10Builder, self).__init__(ctx)

	def desc(self):
		return "GStreamer 1.0"

	def fetch(self, ctx, package_version):
		for pkg in GStreamer10Builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			msg('GStreamer 1.0: fetching ' + basename, 4)
			if package_version == 'git':
				git_link = GStreamer10Builder.git_source + '/' + pkg
				if not self.clone_git_repo(git_link, basename, staging_subdir = 'gstreamer1.0'):
					return False
			else:
				archive_filename = basename + '.' + GStreamer10Builder.pkg_ext
				archive_link = GStreamer10Builder.pkg_source + '/' + pkg + '/' + archive_filename
				archive_dest = os.path.join(ctx.dl_dir, archive_filename)
				if not self.fetch_package_file(archive_filename, archive_dest, archive_dest + ".sha256sum", archive_link, archive_link + ".sha256sum"):
					return False
		return True

	def check(self, ctx, package_version):
		if package_version == 'git':
			return True
		for pkg in GStreamer10Builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			msg('GStreamer 1.0: checking ' + basename, 4)
			archive_filename = basename + '.' + GStreamer10Builder.pkg_ext
			archive_link = GStreamer10Builder.pkg_source + '/' + pkg + '/' + archive_filename
			archive_dest = os.path.join(ctx.dl_dir, archive_filename)
			archive_dest_checksum = archive_dest + '.' + GStreamer10Builder.pkg_checksum

			if not self.check_package(name = pkg, basename = basename, hashcall = 'sha256sum', dest_hash = archive_dest_checksum, staging_subdir = 'gstreamer1.0'):
				return False
		return True

	def unpack(self, ctx, package_version):
		for pkg in GStreamer10Builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			msg('GStreamer 1.0: unpacking ' + basename, 4)
			if package_version != 'git':
				archive_filename = basename + '.' + GStreamer10Builder.pkg_ext
				archive_dest = os.path.join(ctx.dl_dir, archive_filename)
				if not self.unpack_package(basename, archive_dest, staging_subdir = 'gstreamer1.0'):
					return False
		return True

	def build(self, ctx, package_version):
		for pkg in GStreamer10Builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			msg('GStreamer 1.0: building ' + basename, 4)
			extra_config = '--disable-examples'
			if pkg == 'gst-plugins-bad':
				extra_config += ' --disable-directfb --disable-modplug'
			elif pkg == 'gstreamer':
				extra_config += ' --with-bash-completion-dir=' + ctx.inst_dir

			if not self.do_config_make_build(basename = basename, use_autogen = (package_version == 'git'), extra_config = extra_config, staging_subdir = 'gstreamer1.0'):
				return False
			if not self.do_make_install(basename, staging_subdir = 'gstreamer1.0'):
				return False
		return True



class EFLBuilder(Builder):
	pkgs = [ \
		("efl", "libs", "1.17.0", ""),\
		("emotion_generic_players", "libs", "1.17.0", ""),\
		("evas_generic_loaders", "libs", "1.17.0", ""),\
		("elementary", "libs", "1.17.0", ""),\
		("terminology", "apps", "0.9.1", ""),\
		("rage", "apps", "0.1.4", ""),\
		("enventor", "apps", "0.7.0", ""), \
	]
	pkg_ext = 'tar.gz'
	efl_source = 'http://download.enlightenment.org/rel'
	git_source = "git://git.enlightenment.org"
	git_repos = [
		("core/efl.git", "efl"),
		("core/emotion_generic_players.git", "emotion_generic_players"),
		("core/evas_generic_loaders.git", "evas_generic_loaders"),
		("core/elementary.git", "elementary"),
		("apps/empc.git", "empc"),
		("apps/ephoto.git", "ephoto"),
		("apps/equate.git", "equate"),
		("apps/eruler.git", "eruler"),
		("apps/express.git", "express"),
		("apps/terminology.git", "terminology"),
		("apps/rage.git", "rage"),
		("tools/edi.git", "edi"),
		("tools/edje_list.git", "edje_list"),
		("tools/edje_smart_thumb.git", "edje_smart_thumb"),
		("tools/eflete.git", "eflete"),
		("tools/elm-theme-viewer.git", "elm-theme-viewer"),
		("tools/exactness.git", "exactness"),
		("tools/expedite.git", "expedite"),
	]

	def __init__(self, ctx):
		super(EFLBuilder, self).__init__(ctx)

	def desc(self):
		return "Enlightenment Foundation Libraries version 1.8 or newer"
		
	def fetch(self, ctx, package_version):
		if package_version == 'git':
			for repo in EFLBuilder.git_repos:
				basename = repo[1] + "-git"
				msg('EFL: fetching ' + basename, 4)
				git_link = EFLBuilder.git_source + '/' + repo[0]
				if not self.clone_git_repo(git_link, basename, staging_subdir = 'efl'):
					return False
		else:
			for pkg in EFLBuilder.pkgs:
				basename = '%s-%s' % (pkg[0], pkg[2])
				msg('EFL: fetching ' + basename, 4)
				archive_filename = basename + '.' + EFLBuilder.pkg_ext
				archive_link = EFLBuilder.efl_source + ('/%s/%s/%s' % (pkg[1], pkg[0], archive_filename))
				archive_dest = os.path.join(ctx.dl_dir, archive_filename)
				if not self.fetch_package_file(archive_filename, archive_dest, None, archive_link, None):
					return False
		return True

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		if package_version != 'git':
			for pkg in EFLBuilder.pkgs:
				basename = '%s-%s' % (pkg[0], pkg[2])
				msg('EFL: unpacking ' + basename, 4)
				archive_filename = basename + '.' + EFLBuilder.pkg_ext
				archive_dest = os.path.join(ctx.dl_dir, archive_filename)
				if not self.unpack_package(basename, archive_dest, staging_subdir = 'efl'):
					return False
		return True

	def build(self, ctx, package_version):
		if package_version == 'git':
			for repo in EFLBuilder.git_repos:
				basename = repo[1] + "-git"
				msg('EFL: building ' + basename, 4)
				if not self.do_config_make_build(basename = basename, use_autogen = True, staging_subdir = 'efl', use_noconfig_env = True):
					return False
				if not self.do_make_install(basename, staging_subdir = 'efl'):
					return False
		else:
			for pkg in EFLBuilder.pkgs:
				if pkg[3]:
					ver = pkg[3]
				else:
					ver = pkg[2]
				basename = '%s-%s' % (pkg[0], ver)
				msg('EFL: building ' + basename, 4)
				if not self.do_config_make_build(basename = basename, use_autogen = False, staging_subdir = 'efl', use_noconfig_env = True):
					return False
				if not self.do_make_install(basename, staging_subdir = 'efl'):
					return False
		return True


class Qt5Builder(Builder):
	qt5_source = "http://download.qt.io/official_releases/qt"
	pkg_ext = 'tar.xz'

	def __init__(self, ctx):
		super(Qt5Builder, self).__init__(ctx)

	def desc(self):
		return "Qt 5"

	def fetch(self, ctx, package_version):
		short_version = package_version[:package_version.rfind('.')]
		basename = 'qt-everywhere-opensource-src-' + package_version
		archive_filename = basename + '.' + Qt5Builder.pkg_ext
		archive_link_base = Qt5Builder.qt5_source + ('/%s/%s/single' % (short_version, package_version))
		archive_link = archive_link_base + "/" + archive_filename
		archive_link_md5sums = archive_link_base + '/md5sums.txt'
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'qt5-md5sums')
		archive_dest_checksum_tmp = os.path.join(ctx.dl_dir, 'qt5-md5sums-tmp')
		if not self.fetch_package_file(archive_filename, archive_dest, archive_dest_checksum_tmp, archive_link, archive_link_md5sums):
			return False

		subprocess.call('grep "%s" "%s" >"%s"' % (archive_filename, archive_dest_checksum_tmp, archive_dest_checksum), shell = True)
		return True

	def check(self, ctx, package_version):
		basename = 'qt-everywhere-opensource-src-' + package_version
		archive_filename = basename + '.' + Qt5Builder.pkg_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'qt5-md5sums')
		return self.check_package(name = 'qt5', basename = basename, hashcall = 'md5sum', dest_hash = archive_dest_checksum)

	def unpack(self, ctx, package_version):
		basename = 'qt-everywhere-opensource-src-' + package_version
		archive_filename = basename + '.' + Qt5Builder.pkg_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'qt-everywhere-opensource-src-' + package_version

		staging = os.path.join(ctx.staging_dir, basename)
		olddir = os.getcwd()
		os.chdir(staging)

		success = True
		success = success and (0 == ctx.call_with_env('./configure -opensource -confirm-license -prefix "%s"' % ctx.inst_dir))
		success = success and (0 == ctx.call_with_env('make "-j%d"' % ctx.num_jobs))
		success = success and (0 == ctx.call_with_env('make install "-j%d"' % ctx.num_jobs))

		os.chdir(olddir)

		return True


class DaalaBuilder(Builder):
	git_source = "https://git.xiph.org/daala.git"

	def __init__(self, ctx):
		super(DaalaBuilder, self).__init__(ctx)

	def desc(self):
		return "Daala video codec library"

	def fetch(self, ctx, package_version):
		basename = 'daala-%s' % package_version
		return self.clone_git_repo(DaalaBuilder.git_source, basename, 'master')

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		return True

	def build(self, ctx, package_version):
		basename = 'daala-%s' % package_version
		return self.do_config_make_build(basename = basename, use_autogen = True) and self.do_make_install(basename)


class VPXBuilder(Builder):
	git_source = "https://chromium.googlesource.com/webm/libvpx"

	def __init__(self, ctx):
		super(VPXBuilder, self).__init__(ctx)

	def desc(self):
		return "libvpx VP8/VP9 video codec library"

	def fetch(self, ctx, package_version):
		basename = 'libvpx-%s' % package_version
		if package_version == 'git':
			checkout = 'master'
		else:
			checkout = 'v' + package_version
		return self.clone_git_repo(VPXBuilder.git_source, basename, checkout)

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		return True

	def build(self, ctx, package_version):
		basename = 'libvpx-%s' % package_version
		return self.do_config_make_build(basename = basename, use_autogen = False, extra_cflags = '-fPIC -DPIC', extra_cxxflags = '-fPIC -DPIC') and self.do_make_install(basename)



class OrcBuilder(Builder):
	# Beginning with version 0.4.23, Orc uses
	# xz instead of gzip for the tarballs
	orc_source="http://gstreamer.freedesktop.org/src/orc"
	orc_ext_old="tar.gz"
	orc_ext_new="tar.xz"

	def __init__(self, ctx):
		super(OrcBuilder, self).__init__(ctx)

	def desc(self):
		return "ORC Oil Runtime Compiler library"

	def fetch(self, ctx, package_version):
		orc_ext = self.get_orc_ext(package_version)
		if not orc_ext:
			return False

		msg('Using ORC package extension %s' % orc_ext)

		basename = 'orc-%s' % package_version
		archive_filename = basename + '.' + orc_ext
		archive_link = OrcBuilder.orc_source + '/' + archive_filename
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)

		return self.fetch_package_file(archive_filename, archive_dest, None, archive_link, None)

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		orc_ext = self.get_orc_ext(package_version)
		if not orc_ext:
			return False

		basename = 'orc-%s' % package_version
		archive_filename = basename + '.' + orc_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'orc-%s' % package_version
		orc_version = self.get_orc_version(package_version)
		if (orc_version['major'] >= 0) and (orc_version['minor'] >= 4) and (orc_version['rev'] >= 29):
			return self.do_meson_ninja_build(basename = basename)
		else:
			return self.do_config_make_build(basename = basename, use_autogen = False) and self.do_make_install(basename)

	def get_orc_version(self, package_version):
		import re
		ver_match = re.match('(\d*)\.(\d*)\.(\d*)', package_version)
		if not ver_match:
			error('Version "%s" did not match the pattern "X.Y.Z"' % package_version)
			return None
		return { 'major': int(ver_match.group(1)), 'minor': int(ver_match.group(2)), 'rev': int(ver_match.group(3)) }

	def get_orc_ext(self, package_version):
		orc_version = self.get_orc_version(package_version)
		if (orc_version['major'] >= 0) and (orc_version['minor'] >= 4) and (orc_version['rev'] >= 20):
			return OrcBuilder.orc_ext_new
		else:
			return OrcBuilder.orc_ext_old



class GLibBuilder(Builder):
	glib_source="http://ftp.gnome.org/pub/gnome/sources/glib"
	glib_ext="tar.xz"

	def __init__(self, ctx):
		super(GLibBuilder, self).__init__(ctx)

	def desc(self):
		return "GLib library"

	def fetch(self, ctx, package_version):
		# truncate version: x.yy.z -> x.yy
		# necessary for the source path
		truncated_version = package_version[:package_version.rfind('.')]

		basename = 'glib-%s' % package_version
		archive_filename = basename + '.' + GLibBuilder.glib_ext
		archive_link = GLibBuilder.glib_source + '/' + truncated_version + '/' + archive_filename
		archive_link_checksum = GLibBuilder.glib_source + '/' + truncated_version + '/' + basename + '.sha256sum'
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = archive_dest + ".sha256sum"
		archive_dest_checksum_tmp = archive_dest + ".sha256sum-tmp"

		if not self.fetch_package_file(archive_filename, archive_dest, archive_dest_checksum_tmp, archive_link, archive_link_checksum):
			return False
		subprocess.call('grep "%s" "%s" >"%s"' % (archive_filename, archive_dest_checksum_tmp, archive_dest_checksum), shell = True)
		return True

	def check(self, ctx, package_version):
		basename = 'glib-%s' % package_version
		archive_filename = basename + '.' + GLibBuilder.glib_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = archive_dest + '.sha256sum'

		return self.check_package(name = pkg, basename = basename, hashcall = 'sha256sum', dest_hash = archive_dest_checksum)

	def unpack(self, ctx, package_version):
		basename = 'glib-%s' % package_version
		archive_filename = basename + '.' + GLibBuilder.glib_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'glib-%s' % package_version
		return self.do_config_make_build(basename = basename, use_autogen = False) and self.do_make_install(basename)



class BlueZBuilder(Builder):
	bluez_source="https://www.kernel.org/pub/linux/bluetooth"
	bluez_ext="tar.xz"

	def __init__(self, ctx):
		super(BlueZBuilder, self).__init__(ctx)

	def desc(self):
		return "BlueZ"

	def fetch(self, ctx, package_version):
		basename = 'bluez-%s' % package_version
		archive_filename = basename + '.' + BlueZBuilder.bluez_ext
		archive_link = BlueZBuilder.bluez_source + '/' + archive_filename
		archive_link_sha256sum = BlueZBuilder.bluez_source + '/sha256sums.asc'
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'bluez-sha256sums')
		archive_dest_checksum_tmp = os.path.join(ctx.dl_dir, 'bluez-sha256sums-tmp')

		if not self.fetch_package_file(archive_filename, archive_dest, archive_dest_checksum_tmp, archive_link, archive_link_sha256sum):
			return False

		subprocess.call('grep "%s" "%s" >"%s"' % (archive_filename, archive_dest_checksum_tmp, archive_dest_checksum), shell = True)
		return True

	def check(self, ctx, package_version):
		basename = 'bluez-%s' % package_version
		archive_filename = basename + '.' + BlueZBuilder.bluez_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'bluez-sha256sums')
		return self.check_package(name = 'opus', basename = basename, hashcall = 'sha256sum', dest_hash = archive_dest_checksum)

	def unpack(self, ctx, package_version):
		basename = 'bluez-%s' % package_version
		archive_filename = basename + '.' + BlueZBuilder.bluez_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'bluez-%s' % package_version
		return self.do_config_make_build(basename = basename, use_autogen = False, extra_config = '--with-systemdunitdir="%s"' % os.path.join(ctx.inst_dir, 'lib', 'systemd', 'system')) and self.do_make_install(basename)


class X265Builder(Builder):
	x265_source="http://ftp.videolan.org/pub/videolan/x265"
	x265_ext="tar.gz"

	def __init__(self, ctx):
		super(X265Builder, self).__init__(ctx)

	def desc(self):
		return "x265 HEVC encoder"

	def fetch(self, ctx, package_version):
		basename = 'x265_%s' % package_version
		archive_filename = basename + '.' + X265Builder.x265_ext
		archive_link = X265Builder.x265_source + '/' + archive_filename
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)

		return self.fetch_package_file(archive_filename, archive_dest, None, archive_link, None)

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		basename = 'x265_%s' % package_version
		archive_filename = basename + '.' + X265Builder.x265_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'x265_%s' % package_version

		olddir = os.getcwd()
		staging = os.path.join(ctx.staging_dir, basename, 'build')
		os.chdir(staging)

		success = True
		success = success and (0 == ctx.call_with_env('cmake ../source -DCMAKE_INSTALL_PREFIX="%s"' % ctx.inst_dir))
		success = success and (0 == ctx.call_with_env('make'))
		success = success and (0 == ctx.call_with_env('make install'))

		os.chdir(olddir)

		return success



class SoupBuilder(Builder):
	soup_source="http://ftp.gnome.org/pub/GNOME/sources/libsoup"
	git_source="https://gitlab.gnome.org/GNOME/libsoup.git"
	soup_ext="tar.xz"

	def __init__(self, ctx):
		super(SoupBuilder, self).__init__(ctx)

	def desc(self):
		return "An HTTP client/server library for GNOME"

	def fetch(self, ctx, package_version):
		basename = 'libsoup-%s' % package_version
		if package_version == 'git':
			if not self.clone_git_repo(SoupBuilder.git_source, basename):
				return False
		else:
			split_version = package_version.split('.')
			short_version = split_version[0] + '.' + split_version[1]
			archive_filename = basename + '.' + SoupBuilder.soup_ext
			archive_link = SoupBuilder.soup_source + '/' + short_version + '/' + archive_filename
			archive_link_checksum = SoupBuilder.soup_source + '/' + short_version + '/' + basename + '.sha256sum'
			archive_dest = os.path.join(ctx.dl_dir, archive_filename)
			archive_dest_checksum = archive_dest + ".sha256sum"
			archive_dest_checksum_tmp = archive_dest_checksum + '.tmp'
			if not self.fetch_package_file(archive_filename, archive_dest, archive_dest_checksum_tmp, archive_link, archive_link_checksum):
				return False
			subprocess.call('grep "%s" "%s" >"%s"' % (archive_filename, archive_dest_checksum_tmp, archive_dest_checksum), shell = True)
		return True

	def check(self, ctx, package_version):
		if package_version == 'git':
			return True
		basename = 'libsoup-%s' % package_version
		archive_filename = basename + '.' + SoupBuilder.soup_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = archive_dest + ".sha256sum"

		return self.check_package(name = pkg, basename = basename, hashcall = 'sha256sum', dest_hash = archive_dest_checksum)

	def unpack(self, ctx, package_version):
		if package_version == 'git':
			return True
		basename = 'libsoup-%s' % package_version
		archive_filename = basename + '.' + SoupBuilder.soup_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'libsoup-%s' % package_version
		return self.do_config_make_build(basename = basename, use_autogen = (package_version == 'git'), extra_config = '--enable-introspection=no --enable-vala=no') and self.do_make_install(basename)


class BoostBuilder(Builder):
	boost_source="https://sourceforge.net/projects/boost/files/boost"
	boost_ext="tar.bz2"

	def __init__(self, ctx):
		super(BoostBuilder, self).__init__(ctx)

	def desc(self):
		return "The Boost c++ libraries"

	def fetch(self, ctx, package_version):
		basename = 'boost_%s' % package_version.replace('.', '_')
		archive_filename = basename + '.' + BoostBuilder.boost_ext
		archive_link = BoostBuilder.boost_source + '/' + package_version + '/' + archive_filename + '/download';
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)

		return self.fetch_package_file(archive_filename, archive_dest, None, archive_link, None)

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		basename = 'boost_%s' % package_version.replace('.', '_')
		archive_filename = basename + '.' + BoostBuilder.boost_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'boost_%s' % package_version.replace('.', '_')

		olddir = os.getcwd()
		staging = self.get_staging_dir(basename, None)
		os.chdir(staging)

		print(staging)
		success = True
		success = success and (0 == ctx.call_with_env('./bootstrap.sh --prefix=%s' % ctx.inst_dir))
		success = success and (0 == ctx.call_with_env('./b2 install -j%d' % self.ctx.num_jobs))

		os.chdir(olddir)
		return success


class LibniceBuilder(Builder):
	libnice_source="https://nice.freedesktop.org/releases"
	libnice_ext="tar.gz"

	def __init__(self, ctx):
		super(LibniceBuilder, self).__init__(ctx)

	def desc(self):
		return "An implementation of the IETF's Interactive Connectivity Establishment (ICE) standard (RFC 5245)"

	def fetch(self, ctx, package_version):
		basename = 'libnice-%s' % package_version
		archive_filename = basename + '.' + LibniceBuilder.libnice_ext
		archive_link = LibniceBuilder.libnice_source + '/' + archive_filename
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)

		if not self.fetch_package_file(archive_filename, archive_dest, None, archive_link, None):
			return False

		return True

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		basename = 'libnice-%s' % package_version
		archive_filename = basename + '.' + LibniceBuilder.libnice_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'libnice-%s' % package_version
		return self.do_config_make_build(basename = basename, use_autogen = False, extra_config = '--enable-introspection=no --with-gstreamer') and self.do_make_install(basename)


class PipewireBuilder(Builder):
	git_source="https://github.com/PipeWire/pipewire.git"

	def __init__(self, ctx):
		super(PipewireBuilder, self).__init__(ctx)

	def desc(self):
		return "Multimedia processing graphs"

	def fetch(self, ctx, package_version):
		basename = 'pipewire-%s' % package_version
		if package_version == 'git':
			if not self.clone_git_repo(PipewireBuilder.git_source, basename):
				return False
		else:
			error('Only git-based pipewire builds are currently supported')
			return
		return True

	def check(self, ctx, package_version):
		if package_version == 'git':
			return True

	def unpack(self, ctx, package_version):
		if package_version == 'git':
			return True

	def build(self, ctx, package_version):
		basename = 'pipewire-%s' % package_version

		olddir = os.getcwd()
		staging = os.path.join(ctx.staging_dir, basename, 'build')
		mkdir_p(staging)
		os.chdir(staging)

		success = True
		success = success and (0 == ctx.call_with_env('meson .. -Dsystemd=false -Dprefix="%s" -Dlibdir=lib' % ctx.inst_dir))
		success = success and (0 == ctx.call_with_env('ninja'))
		success = success and (0 == ctx.call_with_env('ninja install'))

		os.chdir(olddir)

		return success




rootdir = os.path.dirname(os.path.realpath(__file__))
ctx = Context(rootdir)
ctx.package_builders['gstreamer-1.0'] = GStreamer10Builder(ctx)
ctx.package_builders['opus'] = OpusBuilder(ctx)
ctx.package_builders['efl'] = EFLBuilder(ctx)
ctx.package_builders['qt5'] = Qt5Builder(ctx)
ctx.package_builders['daala'] = DaalaBuilder(ctx)
ctx.package_builders['vpx'] = VPXBuilder(ctx)
ctx.package_builders['orc'] = OrcBuilder(ctx)
ctx.package_builders['glib'] = GLibBuilder(ctx)
ctx.package_builders['bluez'] = BlueZBuilder(ctx)
ctx.package_builders['x265'] = X265Builder(ctx)
ctx.package_builders['soup'] = SoupBuilder(ctx)
ctx.package_builders['boost'] = BoostBuilder(ctx)
ctx.package_builders['libnice'] = LibniceBuilder(ctx)
ctx.package_builders['pipewire'] = PipewireBuilder(ctx)


desc_lines = ['supported packages:']
for i in ctx.package_builders.keys():
	line = '    %s - %s' % (i, ctx.package_builders[i].desc())
	desc_lines += [line]
desc_lines += ['', 'Example call: %s -p orc=0.4.17 gstreamer-1.0=1.1.1' % sys.argv[0]]

parser = argparse.ArgumentParser(description = '\n'.join(desc_lines), formatter_class = argparse.RawTextHelpFormatter)
parser.add_argument('-j', dest = 'num_jobs', metavar = 'JOBS', type = int, action = 'store', default = 1, help = 'Specifies the number of jobs to run simultaneously when compiling')
parser.add_argument('-p', dest = 'pkgs_to_build', metavar = 'PKG=VERSION', type = str, action = 'store', default = [], nargs = '*', help = 'Package(s) to build; VERSION is either a valid version number, or "git", in which case sources are fetched from git upstream instead')

if len(sys.argv) == 1:
	parser.print_help()
	sys.exit(1)
args = parser.parse_args()

ctx.num_jobs = args.num_jobs

packages = []

for s in args.pkgs_to_build:
	delimiter_pos = s.find('=')
	if delimiter_pos == -1:
		error('invalid package specified: "%s" (must be in format <PKG>=<VERSION>', s)
		exit(-1)
	pkg = s[0:delimiter_pos]
	version = s[delimiter_pos+1:]
	packages += [[pkg, version]]

invalid_packages_found = False
for pkg in packages:
	package_name = pkg[0]
	package_version = pkg[1]
	try:
		package_builder = ctx.package_builders[package_name]
		print('package: "%s" version: "%s"' % (package_name, package_version))
	except KeyError:
		error('invalid package "%s"' % package_name)
		invalid_packages_found = True
if invalid_packages_found:
	error('invalid packages specified - cannot continue')
	sys.exit(1)

for pkg in packages:
	ctx.build_package(pkg[0], pkg[1])
