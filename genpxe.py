#! /usr/bin/env python
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

"""
generate pxe config infrastructure; incomplete port
"""

from sys import stderr, exit
from time import asctime
from os import mkdir, listdir
from os.path import isdir, join, isfile
from urllib2 import urlopen, URLError
from argparse import ArgumentParser
from subprocess import check_call, check_output, CalledProcessError
from socket import gethostname, timeout
from time import asctime
from infrastructure.xt.decode_tag import extract_branch
from infrastructure.xt.decode_tag import is_tag
from infrastructure.xt.inspect_build import inspect_build, populate
from infrastructure.xt.generate_pxe_files import write_netboot, atomic_write
from infrastructure.xt.generate_pxe_files import generate_pxelinux_cfg
from infrastructure.xt.releases import scan_releases

RELEASE_LINES = 6
MENU_HEADER = """PXE Boot made %20s *Default is local boot after 30 seconds*

3.2.0, 3.1.4 (altogether %s XT releases and %d builds - try tab completion)
labeler, local, r(ecovery)?s?, dos, local, memtest, 
xenserver-[6.0.0|6.2.0|6.2.0-sp1], [amd64-][lenny|squeeze|wheezy]-install,
[lucid|natty|oneiric|precise|quantal][-live][-64], centos-6.[2|3|4|5]-64[-text]

__/~~XenClient XT recent builds~~\_____________________________________________
<ver>   - auto install     <ver>-w  - auto install, download windows isos
<ver>-m - manual install   <ver>-mw - manual install, download windows isos
<ver>-u - upgrade          <ver>-trial[-m|-u|-w|-mw] - trial version
-------------------------------------------------------------------------------
"""

def generate_menu(menuset, nreleases, nbuilds, branch_menus,
                  bvt_results_url=None,
                  columns=2, width=79, menulen=5):
    """Generate menu with menuset, in a certain number of
    columns and width"""
    menus = [reversed(menuset.get(br, [])[-5:]) for br in branch_menus]
    grid = {}
    labels = {}
    nrows = 0
    for i, menu in enumerate(menus):
        for j, build in enumerate(menu):
            if bvt_results_url is None:
                bvtr = ''
            else:
                try:
                    stream = urlopen(bvt_results_url+build['tag'], timeout=10)
                    bvtr = stream.read()
                    if stream.getcode() != 200:
                        bvtr = 'code '+str(stream.getcode())
                except URLError:
                    bvtr = '?/?'
                except timeout:
                    bvtr = '[timeout]'
            count = 1 + j + i * menulen
            # store a copy of build with alias replaced
            labels[count] = dict(build, alias=str(count))
            column = i % columns
            row = j + (menulen+1)*(i/2)
            nrows = max(nrows, row)
            alias = build['alias'].split('-', 2)[-1]
            grid[(column, row)] = ('%2d: %s [%s]' % (
                count, alias, bvtr))[:38]

    out = ''

    for row in range(nrows+1):
        line = ''
        for column in range(columns):
            field = grid.get((column, row), '')
            line += field.ljust((width-1)/columns)
        if line.split() == []:
            line = '.'*79
        out += line+'\n'
    out += '-'*79+'\n'
    return (MENU_HEADER %(asctime(), nreleases, nbuilds)) + out, labels

def scan_builds(branch_parent_directories, verbose=True):
    """Return a sequence of dictionaries describing builds in
    branch_parent_directories."""
    builds = []
    for branch_parent_directory in branch_parent_directories: 
        for branch in listdir(branch_parent_directory):
            # 23 is experimentally shown to be safe
            if len(branch) > 23:
                if verbose:
                    # this warning is going to happen but better not to spam cron email
                    # so the warning is only produced in verbose mode
                    print 'WARNING: skipping', branch, 'since the labels may crash pxelinux'
                continue
            if branch == 'netboots':
                continue
            branchd = join(branch_parent_directory, branch)
            if isfile(branchd):
                continue
            try:
                tagfiles = listdir(branchd)
            except OSError:
                print 'WARNING: unable to access', branchd
                continue
            for tag in tagfiles:
                if not is_tag(tag):
                    continue
                branch_from_tag = extract_branch(tag)
                if branch_from_tag != branch:
                    print 'WARNING: branch/tag confusion in',
                    print join(branchd, tag),
                    print 'so leaving that build out'
                    continue
                root = join(branchd, tag)
                builds += inspect_build(root, tag, 'build', tag)
    return builds

def order_by(name, sequence):
    """Return a list of sequences sorted by key 'name'"""
    olist = [(x[name], x) for x in sequence]
    return [x for _, x in sorted(olist)]

def classify_builds(builds, interesting_branches):
    """Split builds into interesting branches.
    Returns a dictionary mapping branch (or None for the fallback)
    to a list of builds"""
    menuset = {}
    for build in builds:
        key = (build['branch'] if build['branch'] in interesting_branches else
               None)
        menuset.setdefault(key, list())
        menuset[key].append(build)
    for key in menuset:
        menuset[key] = order_by('build_number', [b for b in menuset[key] if
                                                 b['kind'] == 'cam-oeprod'])
    return menuset

def generate_pxelinux_includes(output_directory, builds, releases, args,
                               verbose=False):
    """Generate files in output_directory for builds and releases"""
    menuset = classify_builds(builds, args.branch_menu)
    latestdir = join(output_directory, 'latestbuilds')
    if not isdir(latestdir):
        mkdir(latestdir)
    menu, labels = generate_menu(menuset, len(releases), len(builds),
                                 args.branch_menu, args.bvt_results_url)
    atomic_write(join(latestdir, 'automenu.inc'), menu)
    buildseq = releases + [labels[label] for label in sorted(labels.keys())
                           ] + list(reversed(builds))
    seen = {}
    buildsequ = []
    for pbuild in buildseq:
        build = populate(pbuild, args.netboot_url, args.autoinstall_url)
        if build['alias'] in seen:
            print 'WARNING: found', build['alias'], 'at',
            print build['build_directory'], 'and',
            print seen[build['alias']]['build_directory'],
            print 'so ignoring new location'
            continue
        assert build['alias'] not in seen, (build, seen[build['alias']])
        seen[build['alias']] = build
        buildsequ.append(build)
    if verbose:
        print 'INFO: autogen.inc will have', len(buildseq),
        print 'sections'
    atomic_write(join(latestdir, 'autogen.inc'),
                 ('# autogenerated on %s at %s by genpxe; do not edit!\n' % (
                   gethostname(), asctime()))+
                 (''.join(generate_pxelinux_cfg(build) for build in buildsequ)))

def get_args():
    """Parse arguments or exit if used incorrectly"""
    parser = ArgumentParser(description='Check builds and releases and '
                            'optionally generate material for PXE '
                            'booting.')
    parser.add_argument('output_directory', metavar='OUTPUT_DIRECTORY',
                        help='Generate menu, pxelinux.cfg and rsync '
                        'material into OUTPUT_DIRECTORY.')
    parser.add_argument('netboot_url', action='store', metavar='NETBOOT_URL',
                        help='Netboot URLs begin with NETBOOT_URL')
    parser.add_argument('autoinstall_url', action='store',
                        metavar='AUTOINSTALL_URL',
                        help='Autoinstall URLs being with AUTOINSTALL_URL')
    parser.add_argument('releases_directory', action='store',
                        metavar='RELEASES_DIRECTORY',
                        help='Releases can be found in RELEASES_DIRECTORY')
    parser.add_argument('-s', '--scan-directory', metavar='DIRECTORY',
                        action='append',
                        help='Scan DIRECTORY for builds')
    parser.add_argument('-b', '--build-output', action='store',
                        metavar='DIRECTORY',
                        help='Generate files that boots the OpenXT build '
                        'output at DIRECTORY instead of looking at all builds.')
    parser.add_argument('-n', '--generate-netboots', action='store_true',
                        help='Generate netboot* directories')
    parser.add_argument('-c', '--clean-old-netboots', action='store_true',
                        help='Remove netboot directories for deleted builds')
    parser.add_argument('-i', '--generate-pxelinux-includes', help='Generate '
                        'autogenerated.cfg and automenu.inc for use from '
                        'pxelinux.cfg', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Increase verbosity')
    parser.add_argument('-a', '--apply', action='store_true',
                        help='Apply destructive actions rather than list them')
    parser.add_argument('-m', '--branch-menu', action='append',
                        metavar='BRANCH',
                        help='Create a branch menu for BRANCH')
    parser.add_argument('-r', '--bvt-results-url', metavar='URL',
                        help='Base URL for BVT results service is URL')
    return parser.parse_args()

def clean_old_netboots(output_directory, builds, verbose=False, pretend=False):
    """Delete content of builds which isn't referenced"""
    havetags = [x['tag'] for x in builds]
    for branch in listdir(join(output_directory, 'builds')):
        branchd = join(output_directory, 'builds', branch)
        if not isdir(branchd):
            continue
        for tag in listdir(branchd):
            tagd = join(branchd, tag)
            if not isdir(tagd):
                continue
            if tag not in havetags:
                if verbose:
                    print 'INFO: want to delete', tagd
                if not pretend:
                    check_call(['rm', '-r', tagd])
            else:
                if verbose:
                    print 'INFO: KEEP          ', tagd
        tags = listdir(branchd)
        if len(tags) == 0:
            check_call(['rmdir', branchd])

def main():
    """Entry point"""
    args = get_args()
    if args.build_output:
        if not isdir(args.build_output):
            print 'ERROR:', args.build_output, 'not found'
            exit(1)
        build = populate(inspect_build(args.build_output, None)[0],
                         args.netboot_url, args.autoinstall_url)

        write_netboot(build, args.output_directory,
                      pretend=not args.apply) 
        check_call(['rsync', '-raP', args.build_output+'/repository/',
                    args.output_directory])
        atomic_write(join(args.output_directory, 'pxelinux.cfg'),
                     ('#autogenerated by genpxe at %s\n' % (asctime()))+
                     generate_pxelinux_cfg(build) +
                     '\nlabel local\n  localboot 0\ndefault=build\nprompt 1\n')
        return
    if args.verbose:
        print 'INFO: scanning builds'
    builds = order_by('build_number', scan_builds(args.scan_directory,
                                                  verbose=args.verbose))
    if args.verbose:
        print 'INFO: found', len(builds), 'builds'
    if args.verbose:
        print 'INFO: scanning releases'

    releases = order_by('alias', scan_releases(args.releases_directory))
    if args.clean_old_netboots:
        clean_old_netboots(args.output_directory, builds+releases,
                           verbose=args.verbose, pretend=not args.apply)
    if args.generate_netboots:
        count = len(releases+builds)
        if args.verbose:
            print 'INFO: updating netboot material for', count,
            print 'builds'
        for build in releases + builds:
            write_netboot(populate(build, args.netboot_url,
                                   args.autoinstall_url),
                          join(args.output_directory, 'builds',
                               build['branch'], build['tag']),
                          pretend=not args.apply)
    if args.generate_pxelinux_includes:
        generate_pxelinux_includes(args.output_directory, builds, releases,
                                   args, verbose=args.verbose)

if __name__ == '__main__':
    main()


