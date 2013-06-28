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

	def call_with_env(self, cmd):
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

		for func in ['fetch', 'check', 'unpack', 'build', 'install']:
			msg('calling %s function for package %s version %s' % (func, package_name, package_version), 6)
			try:
				m = getattr(package_builder, func)
			except AttributeError:
				error('package builder has no %s function' % func)
				exit(-1)
			if not m(self, package_version):
				error('function %s failed' % func)
				exit(-1)



class opus_builder:
	opus_source="http://downloads.xiph.org/releases/opus"
	opus_ext="tar.gz"

	def fetch(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		archive_filename = basename + '.' + opus_builder.opus_ext
		archive_link = opus_builder.opus_source + '/' + archive_filename
		archive_link_sha1sum = opus_builder.opus_source + '/SHA1SUMS'
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'opus-sha1sums')
		archive_dest_checksum_tmp = os.path.join(ctx.dl_dir, 'opus-sha1sums-tmp')

		if os.path.exists(archive_dest):
			msg('%s present - downloading skipped' % archive_filename)
		else:
			msg('%s not present - downloading from %s' % (archive_filename, archive_link))
			if 0 != subprocess.call('wget -c "%s" -O "%s"' % (archive_link, archive_dest), shell = True):
				return False
			if 0 != subprocess.call('wget -c "%s" -O "%s"' % (archive_link_sha1sum, archive_dest_checksum_tmp), shell = True):
				return False
			subprocess.call('grep "%s" "%s" >"%s"' % (archive_filename, archive_dest_checksum_tmp, archive_dest_checksum), shell = True)
		return True


	def check(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		archive_filename = basename + '.' + opus_builder.opus_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_dest_checksum = os.path.join(ctx.dl_dir, 'opus-sha1sums')

		olddir = os.getcwd()
		os.chdir(ctx.dl_dir)
		retval = subprocess.call('sha1sum -c "%s" --quiet >/dev/null 2>&1' % archive_dest_checksum, shell = True)
		os.chdir(olddir)

		if 0 == retval:
			msg('opus checksum : OK')
		else:
			msg('opus checksum : FAILED - removing downloaded Opus files')
			p = os.path.join(ctx.staging_dir, basename)
			if os.path.exists(p):
				msg('Removing unpacked content in ' + p)
			return False

		return True


	def unpack(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		archive_filename = basename + '.' + opus_builder.opus_ext
		archive_dest = os.path.join(ctx.dl_dir, archive_filename)
		archive_staging = os.path.join(ctx.staging_dir, basename)
		if os.path.exists(archive_staging):
			msg('Directory %s present - unpacking skipped' % archive_staging)
		else:
			msg('Directory %s not present - unpacking' % archive_staging)
			if 0 != subprocess.call('tar xf "%s" -C "%s"' % (archive_dest, ctx.staging_dir), shell = True):
				return False
		return True


	def build(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		staging = os.path.join(ctx.staging_dir, basename)
		olddir = os.getcwd()
		os.chdir(staging)
		success = \
			(0 == ctx.call_with_env('./configure --prefix="%s"' % ctx.inst_dir)) and \
			(0 == ctx.call_with_env('make "-j%d"' % ctx.num_jobs))
		os.chdir(olddir)
		if not success:
			return False
		return True


	def install(self, ctx, package_version):
		basename = 'opus-%s' % package_version
		staging = os.path.join(ctx.staging_dir, basename)
		olddir = os.getcwd()
		os.chdir(staging)
		success = (0 == ctx.call_with_env('make "-j%d" install' % ctx.num_jobs))
		os.chdir(olddir)
		if not success:
			return False
		return True



class gstreamer_1_0_builder:
	pkgs = [ \
		"gstreamer", \
		"gst-plugins-base", \
		"gst-plugins-good", \
		"gst-plugins-bad", \
		"gst-plugins-ugly", \
		"gst-libav" \
	]
	pkg_source = "http://gstreamer.freedesktop.org/src"
	git_source = "git://anongit.freedesktop.org/gstreamer"
	pkg_ext = "tar.xz"
	pkg_checksum = "sha256sum"

	def fetch(self, ctx, package_version):
		for pkg in gstreamer_1_0_builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			if package_version == 'git':
				git_link = gstreamer_1_0_builder.git_source + '/' + pkg
				git_bare = os.path.join(ctx.dl_dir, basename + '.git')
				if os.path.exists(git_bare):
					subprocess.call(' \
						pushd %s >/dev/null ; \
						git pull ; \
						popd >/dev/null \
					' % git_bare, shell = True)
				else:
					subprocess.call('git clone --bare %s %s' % (git_link, git_bare), shell = True)
			else:
				archive_filename = basename + '.' + gstreamer_1_0_builder.pkg_ext
				archive_link = gstreamer_1_0_builder.pkg_source + '/' + pkg + '/' + archive_filename
				archive_dest = os.path.join(ctx.dl_dir, archive_filename)
				if os.path.exists(archive_dest):
					msg('%s present - downloading skipped' % archive_filename)
				else:
					msg('%s not present - downloading from %s' % (archive_filename, archive_link))
					if 0 != subprocess.call('wget -c "%s" -P "%s"' % (archive_link, ctx.dl_dir), shell = True):
						return False
					if 0 != subprocess.call('wget -c "%s.%s" -P "%s"' % (archive_link, gstreamer_1_0_builder.pkg_checksum, ctx.dl_dir), shell = True):
						return False
		return True

	def check(self, ctx, package_version):
		if package_version == 'git':
			return True
		for pkg in gstreamer_1_0_builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			archive_filename = basename + '.' + gstreamer_1_0_builder.pkg_ext
			archive_link = gstreamer_1_0_builder.pkg_source + '/' + pkg + '/' + archive_filename
			archive_dest = os.path.join(ctx.dl_dir, archive_filename)
			archive_dest_checksum = archive_dest + '.' + gstreamer_1_0_builder.pkg_checksum

			olddir = os.getcwd()
			os.chdir(ctx.dl_dir)
			retval = subprocess.call('sha256sum -c "%s" --quiet >/dev/null 2>&1' % archive_dest_checksum, shell = True)
			os.chdir(olddir)
			if 0 == retval:
				msg('%s checksum : OK' % pkg)
			else:
				msg('%s checksum : FAILED - removing downloaded files for this GStreamer package' % pkg)
				p = os.path.join(ctx.staging_dir, basename)
				if os.path.exists(p):
					msg('Removing unpacked content in ' + p)
				return False
		return True
			

	def unpack(self, ctx, package_version):
		for pkg in gstreamer_1_0_builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			if package_version == 'git':
				git_bare = os.path.join(ctx.dl_dir, basename + '.git')
				git_staging = os.path.join(ctx.staging_dir, basename)
				if os.path.exists(git_staging):
					msg('Directory %s present - not cloning anything' % git_staging)
				else:
					msg('Directory %s not present - cloning from local git repo copy' % git_staging)
					if 0 != subprocess.call('git clone "%s" "%s"' % (git_bare, git_staging), shell = True):
						return False
			else:
				archive_filename = basename + '.' + gstreamer_1_0_builder.pkg_ext
				archive_dest = os.path.join(ctx.dl_dir, archive_filename)
				archive_staging = os.path.join(ctx.staging_dir, basename)
				if os.path.exists(archive_staging):
					msg('Directory %s present - unpacking skipped' % archive_staging)
				else:
					msg('Directory %s not present - unpacking' % archive_staging)
					if 0 != subprocess.call('tar xf "%s" -C "%s"' % (archive_dest, ctx.staging_dir), shell = True):
						return False
		return True


	def build(self, ctx, package_version):
		for pkg in gstreamer_1_0_builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			staging = os.path.join(ctx.staging_dir, basename)
			olddir = os.getcwd()
			os.chdir(staging)
			success = True
			if package_version == 'git':
				success = (0 == ctx.call_with_env('./autogen.sh --noconfigure'))
			success = success and \
				(0 == ctx.call_with_env('./configure --prefix="%s"' % ctx.inst_dir)) and \
				(0 == ctx.call_with_env('make "-j%d"' % ctx.num_jobs))
			os.chdir(olddir)
			if not success:
				return False
		return True


	def install(self, ctx, package_version):
		for pkg in gstreamer_1_0_builder.pkgs:
			basename = '%s-%s' % (pkg, package_version)
			staging = os.path.join(ctx.staging_dir, basename)
			olddir = os.getcwd()
			os.chdir(staging)
			success = (0 == ctx.call_with_env('make "-j%d" install' % ctx.num_jobs))
			os.chdir(olddir)
			if not success:
				return False
		return True





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
ctx.package_builders['gstreamer-1.0'] = gstreamer_1_0_builder()
ctx.package_builders['opus'] = opus_builder()


for pkg in packages:
	ctx.build_package(pkg[0], pkg[1])
