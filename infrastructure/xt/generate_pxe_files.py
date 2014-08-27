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

from glob import glob
from subprocess import check_call
from sys import stderr
from os.path import isdir, join, split, exists
from os import makedirs

class NothingDone(Exception):
    """Kind not found"""

def expand_variables(build, variant, text):
    """Expand some variables of the form @VAR@ in whom"""
    stext = text
    for var, value in build.items() + variant.items():
        target = '@'+var+'@'
        if target in stext:
            stext = stext.replace(target, value)
    return stext

def generate_pxelinux_cfg(build):
    """Return the text of a set of pxelinux.cfg menu entries"""
    out = []
    for variant in build['variants']:
        orig = file(variant['pxelinux'], 'r')
        section = None
        orig_labels = {}
        for line in orig.readlines():
            spl = line.split()
            if len(spl) >= 2:
                if spl[0] == 'label':
                    section = spl[1]
                elif section:
                    orig_labels.setdefault(section, list())
                    sline = expand_variables(build, variant, line)
                    orig_labels[section].append(sline.replace('\n', ''))

        for orig, new in [('xc-installer', ''),
                          ('xc-installer-download-win', '-w'),
                          ('xc-installer-manual', '-m'),
                          ('xc-installer-manual-download-win', '-mw'),
                          ('xc-installer-upgrade', '-u')]:
            if orig not in orig_labels:
                print >>stderr, 'WARNING: no', orig, 'section in', \
                    variant['kind'], variant['pxelinux'], 'so leaving it out'
                continue
            out.append('label '+build['alias']+(
                    '-trial' if variant['kind'] == 'trial' else '')+new)
            out += orig_labels[orig]+['']
    return '\n'.join(out)+'\n\n'

def write_netboot(build, destd, ansfile_filter=None, kind=None,
                  ansfile_glob='*.ans', verbose=False, pretend=False):
    """rsync netboot answer files to destd"""
    if not isdir(destd):
        if verbose:
            print 'INFO: make directory', destd
        if not pretend:
            makedirs(destd)
    work = False
    for variantd in build['variants']:
        if kind and kind != variantd['kind']:
            continue
        work = True
        if verbose:
            print 'INFO: writing netboot', kind, build, 'to', destd
        source = glob(build['build_directory']+'/'+variantd['netboot'])
        if verbose:
            print 'INFO: syncing', source, 'except netboot.tar.gz and *.ans to', destd
        if not pretend:
            check_call(['rsync', '--exclude', 'netboot.tar.gz', '--exclude', '*.ans']+ source + ['-a', destd])
        destnet = join(destd, variantd['netboot'])
        if not isdir(destnet):
            if verbose:
                print 'INFO: make directory', destnet
            if not pretend:
                makedirs(destnet)
        for ansfile in glob(join(build['build_directory'], variantd['netboot'],
                                 ansfile_glob)):
            with file(ansfile, 'r') as fin:
                content = fin.read()
            scontent = expand_variables(build, variantd, content)
            if ansfile_filter:
                scontent = ansfile_filter(scontent)
            ansfile = join(destnet, split(ansfile)[1])
            if verbose:
                print 'INFO: writing', ansfile
            atomic_write(ansfile, scontent, pretend=pretend)
    if not work:
        raise NothingDone(kind)

def atomic_write(filename, content, verbose=False, pretend=False):
    """Write content to filename with ACID transactional properties"""
    if exists(filename):
        with file(filename, 'r') as readf:
            ccontent = readf.read()
        if ccontent == content:
            return
    directory, _ = split(filename)
    if not isdir(directory):
        if verbose:
            print 'INFO: mkdir', directory
        if not pretend:
            makedirs(directory)
    if not pretend:
        with file(filename+'.new', 'w') as writef:
            writef.write(content)
        check_call(['mv', '-f', filename+'.new', filename])
    if verbose:
        print 'INFO: generated', len(content), 'byte', filename
