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
	def __init__(self, rootdir, num_jobs):
		self.rootdir = os.path.abspath(os.path.expanduser(rootdir))
		self.dl_dir = os.path.join(self.rootdir, 'downloads')
		self.staging_dir = os.path.join(self.rootdir, 'staging')
		self.inst_dir = os.path.join(self.rootdir, 'installation')
		self.allowed_paths = [self.dl_dir, self.staging_dir, self.inst_dir]
		self.num_jobs = num_jobs
		self.package_builders = {}
		mkdir_p(self.dl_dir)
		mkdir_p(self.staging_dir)
		mkdir_p(self.inst_dir)
		mkdir_p(os.path.join(self.inst_dir, 'bin'))
		mkdir_p(os.path.join(self.inst_dir, 'include'))
		mkdir_p(os.path.join(self.inst_dir, 'lib', 'pkgconfig'))
		mkdir_p(os.path.join(self.inst_dir, 'share', 'aclocal'))

	def call_with_env(self, cmd, extra_cmds = None):
		if extra_cmds:
			retval = subprocess.call('source "%s/env.sh" "%s" ; %s ; %s' % (self.rootdir, self.rootdir, extra_cmds, cmd), shell = True)
		else:
			retval = subprocess.call('source "%s/env.sh" "%s" ; %s' % (self.rootdir, self.rootdir, cmd), shell = True)
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

	def fetch_package_git(self, link, bare):
		if not os.path.exists(bare):
			return 0 == subprocess.call('git clone --bare %s %s' % (link, bare), shell = True)
		return True

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

	def check_package(self, name, basename, hashcall, dest_hash):
		olddir = os.getcwd()
		os.chdir(self.ctx.dl_dir)
		retval = subprocess.call('%s -c "%s" --quiet >/dev/null 2>&1' % (hashcall, dest_hash), shell = True)
		os.chdir(olddir)

		if 0 == retval:
			msg('%s checksum : OK' % name)
		else:
			msg('%s checksum : FAILED - removing downloaded files' % name)
			p = os.path.join(self.ctx.staging_dir, basename)
			if os.path.exists(p):
				msg('Removing unpacked content in ' + p)
			return False

		return True

	def clone_local_git_repo(self, bare_repo, basename, checkout = None):
		staging = os.path.join(self.ctx.staging_dir, basename)
		if os.path.exists(staging):
			msg('Directory %s present - not cloning anything' % staging)
		else:
			msg('Directory %s not present - cloning from local git repo copy' % staging)
			if checkout:
				if 0 != subprocess.call('git clone -b "%s" "%s" "%s"' % (checkout, bare_repo, staging), shell = True):
					return False
			else:
				if 0 != subprocess.call('git clone "%s" "%s"' % (bare_repo, staging), shell = True):
					return False
		return True

	def unpack_package(self, basename, dest):
		staging = os.path.join(self.ctx.staging_dir, basename)
		if os.path.exists(staging):
			msg('Directory %s present - unpacking skipped' % staging)
		else:
			msg('Directory %s not present - unpacking' % staging)
			if 0 != subprocess.call('tar xf "%s" -C "%s"' % (dest, self.ctx.staging_dir), shell = True):
				return False
		return True

	def do_config_make_build(self, basename, is_git, extra_config = '', extra_cflags = '', extra_cxxflags = ''):
		staging = os.path.join(ctx.staging_dir, basename)
		olddir = os.getcwd()
		os.chdir(staging)
		success = True
		if is_git:
			success = (0 == ctx.call_with_env('./autogen.sh --noconfigure'))
		success = success and \
			(0 == ctx.call_with_env('./configure --prefix="%s" %s' % (ctx.inst_dir, extra_config), 'export CFLAGS="$CFLAGS %s" ; export CXXFLAGS="$CXXFLAGS %s" ' % (extra_cxxflags, extra_cxxflags))) and \
			(0 == ctx.call_with_env('make "-j%d"' % ctx.num_jobs))
		os.chdir(olddir)
		return success

	def do_make_install(self, basename, parallel = True):
		staging = os.path.join(ctx.staging_dir, basename)
		olddir = os.getcwd()
		os.chdir(staging)
		if parallel:
			success = (0 == ctx.call_with_env('make "-j%d" install' % ctx.num_jobs))
		else:
			success = (0 == ctx.call_with_env('make install'))
		os.chdir(olddir)
		return success



class OpusBuilder(Builder):
	opus_source="http://downloads.xiph.org/releases/opus"
	opus_ext="tar.gz"

	def __init__(self, ctx):
		super(OpusBuilder, self).__init__(ctx)

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
		return self.check_package('opus', basename, 'sha1sum', archive_dest_checksum)

	def unpack(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		archive_filename = basename + '.' + OpusBuilder.opus_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		return self.do_config_make_build(basename, False) and self.do_make_install(basename)



class GStreamer10Builder(Builder):
	pkgs = [ \
		"gstreamer", \
		"gst-plugins-base", \
		"gst-plugins-good", \
		"gst-plugins-bad", \
		"gst-plugins-ugly", \
		"gst-libav", \
	]
	pkg_source = "http://gstreamer.freedesktop.org/src"
	git_source = "git://anongit.freedesktop.org/gstreamer"
	pkg_ext = "tar.xz"
	pkg_checksum = "sha256sum"

	def __init__(self, ctx):
		super(GStreamer10Builder, self).__init__(ctx)

	def fetch(self, ctx, package_version):
		for pkg in GStreamer10Builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			if package_version == 'git':
				git_link = GStreamer10Builder.git_source + '/' + pkg
				git_bare = os.path.join(ctx.dl_dir, basename + '.git')
				if not self.fetch_package_git(git_link, git_bare):
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
			archive_filename = basename + '.' + GStreamer10Builder.pkg_ext
			archive_link = GStreamer10Builder.pkg_source + '/' + pkg + '/' + archive_filename
			archive_dest = os.path.join(ctx.dl_dir, archive_filename)
			archive_dest_checksum = archive_dest + '.' + GStreamer10Builder.pkg_checksum

			if not self.check_package(pkg, basename, 'sha256sum', archive_dest_checksum):
				return False
		return True	

	def unpack(self, ctx, package_version):
		for pkg in GStreamer10Builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			if package_version == 'git':
				git_bare = os.path.join(ctx.dl_dir, basename + '.git')
				if not self.clone_local_git_repo(git_bare, basename):
					return False
			else:
				archive_filename = basename + '.' + GStreamer10Builder.pkg_ext
				archive_dest = os.path.join(ctx.dl_dir, archive_filename)
				if not self.unpack_package(basename, archive_dest):
					return False
		return True

	def build(self, ctx, package_version):
		for pkg in GStreamer10Builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			if not self.do_config_make_build(basename, package_version == 'git'):
				return False
			if not self.do_make_install(basename):
				return False
		return True



class EFLBuilder(Builder):
	pkgs = [ \
		"eina", \
		"eet", \
		"evas", \
		"ecore", \
		"eio", \
		"embryo", \
		"edje", \
		"efreet", \
		"e_dbus", \
		"eeze", \
		"elementary", \
		"expedite", \
		"evas_generic_loaders", \
		"emotion", \
	] # ethumb, evil
	efl_source = 'http://download.enlightenment.org/releases'
	pkg_ext = 'tar.bz2'

	def __init__(self, ctx):
		super(EFLBuilder, self).__init__(ctx)

	def fetch(self, ctx, package_version):
		for pkg in EFLBuilder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			archive_filename = basename + '.' + EFLBuilder.pkg_ext
			archive_link = EFLBuilder.efl_source + '/' + archive_filename
			archive_dest = os.path.join(ctx.dl_dir, archive_filename)
			if not self.fetch_package_file(archive_filename, archive_dest, None, archive_link, None):
				return False
		return True

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		for pkg in EFLBuilder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			archive_filename = basename + '.' + EFLBuilder.pkg_ext
			archive_dest = os.path.join(ctx.dl_dir, archive_filename)
			if not self.unpack_package(basename, archive_dest):
				return False
		return True

	def build(self, ctx, package_version):
		for pkg in EFLBuilder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			if not self.do_config_make_build(basename, False):
				return False
			if not self.do_make_install(basename):
				return False
		return True



class VPXBuilder(Builder):
	git_source = "http://git.chromium.org/webm/libvpx.git"

	def __init__(self, ctx):
		super(VPXBuilder, self).__init__(ctx)

	def fetch(self, ctx, package_version):
		basename = 'libvpx-%s' % package_version
		git_bare = os.path.join(ctx.dl_dir, basename + '.git')
		return self.fetch_package_git(VPXBuilder.git_source, git_bare)

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		basename = 'libvpx-%s' % package_version
		git_bare = os.path.join(ctx.dl_dir, basename + '.git')
		return self.clone_local_git_repo(git_bare, basename, 'v' + package_version)

	def build(self, ctx, package_version):
		basename = 'libvpx-%s' % package_version
		return self.do_config_make_build(basename, False, extra_cflags = '-fPIC -DPIC', extra_cxxflags = '-fPIC -DPIC') and self.do_make_install(basename)



class OrcBuilder(Builder):
	orc_source="http://code.entropywave.com/download/orc"
	orc_ext="tar.gz"

	def __init__(self, ctx):
		super(OrcBuilder, self).__init__(ctx)

	def fetch(self, ctx, package_version):
		basename = 'orc-%s' % package_version
		archive_filename = basename + '.' + OrcBuilder.orc_ext
		archive_link = OrcBuilder.orc_source + '/' + archive_filename
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)

		return self.fetch_package_file(archive_filename, archive_dest, None, archive_link, None)

	def check(self, ctx, package_version):
		return True

	def unpack(self, ctx, package_version):
		basename = 'orc-%s' % package_version
		archive_filename = basename + '.' + OrcBuilder.orc_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'orc-%s' % package_version
		return self.do_config_make_build(basename, False) and self.do_make_install(basename)



class BlueZBuilder(Builder):
#	bluez_source="https://www.kernel.org/pub/linux/bluetooth/bluez-4.101.tar.xz"
	bluez_source="https://www.kernel.org/pub/linux/bluetooth"
	bluez_ext="tar.xz"

	def __init__(self, ctx):
		super(BlueZBuilder, self).__init__(ctx)

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
		return self.check_package('opus', basename, 'sha256sum', archive_dest_checksum)

	def unpack(self, ctx, package_version):
		basename = 'bluez-%s' % package_version
		archive_filename = basename + '.' + BlueZBuilder.bluez_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		return self.unpack_package(basename, archive_dest)

	def build(self, ctx, package_version):
		basename = 'bluez-%s' % package_version
		return self.do_config_make_build(basename, False, extra_config = '--with-systemdunitdir="%s"' % os.path.join(ctx.inst_dir, 'lib', 'systemd', 'system')) and self.do_make_install(basename)




parser = argparse.ArgumentParser()
parser.add_argument('-j', dest = 'num_jobs', metavar = 'JOBS', type = int, action = 'store', default = 1, help = 'Specifies the number of jobs to run simultaneously when compiling')
parser.add_argument('-p', dest = 'pkgs_to_build', metavar = 'PKG=VERSION', type = str, action = 'store', default = [], nargs = '*', help = 'Package(s) to build; VERSION is either a valid version number, or "git", in which case sources are fetched from git upstream instead')

args = parser.parse_args()

print(args.num_jobs)
print(args.pkgs_to_build)

packages = []

for s in args.pkgs_to_build:
	delimiter_pos = s.find('=')
	if delimiter_pos == -1:
		error('invalid package specified: "%s" (must be in format <PKG>=<VERSION>', s)
		exit(-1)
	pkg = s[0:delimiter_pos]
	version = s[delimiter_pos+1:]
	packages += [[pkg, version]]
	print('package: "%s" version: "%s"' % (pkg, version))


rootdir = os.path.dirname(os.path.realpath(__file__))
ctx = Context(rootdir, args.num_jobs)
ctx.package_builders['gstreamer-1.0'] = GStreamer10Builder(ctx)
ctx.package_builders['opus'] = OpusBuilder(ctx)
ctx.package_builders['efl'] = EFLBuilder(ctx)
ctx.package_builders['vpx'] = VPXBuilder(ctx)
ctx.package_builders['orc'] = OrcBuilder(ctx)
ctx.package_builders['bluez'] = BlueZBuilder(ctx)


for pkg in packages:
	ctx.build_package(pkg[0], pkg[1])
