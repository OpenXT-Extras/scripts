#
# Copyright (c) 2014 Citrix Systems, Inc.
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

from os import listdir
from re import compile
from os.path import join, isdir
from sys import stderr
from infrastructure.xt.decode_tag import is_tag
from infrastructure.xt.inspect_build import inspect_build

NOT_FOR_DISTRIBUTION = 'NOT_FOR_DISTRIBUTION'
DATE_REGEXP = compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}-.*')

def scan_releases(releases_directory):
    """Return a sequence of dictionaries describing releases.

    Will not cope with many of these inconsistent releases that predate
    release.py; they are ignored."""
    releases = []
    rnames = {}
    for release in listdir(releases_directory):
        nfd_dir = join(releases_directory, release, NOT_FOR_DISTRIBUTION)
        if isdir(nfd_dir):
            nfd_tags = [f for f in listdir(nfd_dir) if is_tag(f)]
            if len(nfd_tags) == 0:
                # no tags, which happens for manual releases 
                # eg 2014-01-30-XT-3.2.0-SyncXT-Fix
                continue
            if len(nfd_tags) != 1:
                print >>stderr, 'WARNING: found', nfd_tags,
                print >>stderr, 'rather than exactly one tag in', nfd_dir,
                print >>stderr, 'so skipping', release
                continue
            tag = nfd_tags[0]
            builddir = join(nfd_dir, tag)
            name = release
            if DATE_REGEXP.match(name):
                name = name[11:]
            name = name.replace('XT-', '').replace('-Release', '').lower()
            if name in rnames:
                print >>stderr, 'WARNING: name clash on', release, name, 
                print >>stderr, nfd_dir, rnames[name]
            else:
                releases += inspect_build(builddir, tag, 'release', name)
                rnames[name] = nfd_dir
    return releases
