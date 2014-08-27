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

from infrastructure.xt.decode_tag import extract_kind
from infrastructure.xt.get_build_info import get_build_info
from infrastructure.xt.decode_tag import extract_build_number, extract_branch
from os.path import join, isfile

def inspect_build(build_dir, tag=None, typename='build', alias='build'):
    """Work out information about build_dir which contains a build of tag"""
    variants = []
    branch = extract_branch(tag) if tag else None
    build_info = get_build_info(branch, tag, build_dir=build_dir)
    for kind, dirname in [('plain', 'netboot'), 
                          ('trial', 'netboot-trial'),
                          ('kent', 'netboot-kent')]:
        netboot = build_info.get('netboot' if kind != 'trial' else
                                 'netboot-trial')
        if netboot == dirname:
            pxelinux = join(build_dir, netboot, 'pxelinux.cfg')
            if isfile(pxelinux):
                variants.append({'kind':kind, 'pxelinux':pxelinux,
                                 'netboot':netboot,
                                 'variant_postfix':('-'+kind) if 
                                 kind != 'plain' else ''})
    if variants == []:
        return []
    return [{'type':typename, 
             'build_number': extract_build_number(tag) if tag else None,
             'branch':branch, 'variants': variants, 'alias':alias,
             'kind':extract_kind(tag) if tag else None,
             'tag':tag, 'build_directory':build_dir}]


def populate(build, netboot_url=None, autoinstall_url=None):
    """Adds extra expansion variables to a build record returned by inspect_build,
    given site configuration netboot_url and autoinstall_url"""
    out = dict(build)
    if 'TFTP_PATH' not in out:
        out['TFTP_PATH'] = ('builds/'+build['branch']+'/'+
                            build['tag']+'/@netboot@')
    out.setdefault('netboot_build_path', '/'.join(
            build['build_directory'].split('/')[2:]))
    if netboot_url:
        full_netboot_url = (netboot_url+'/'+out['netboot_build_path']+
                            '/repository@variant_postfix@')
        out.setdefault('NETBOOT_URL', full_netboot_url)
    if autoinstall_url:
        out.setdefault('AUTOINSTALL_URL', autoinstall_url)
    return out

