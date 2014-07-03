#!/bin/sh
#
# bstrap:
#
# $Id: autogen.sh,v 1.1 2011/01/13 17:42:27 root Exp $
#
# $Log: autogen.sh,v $
# Revision 1.1  2011/01/13 17:42:27  root
# *** empty log message ***
#
#
#
#

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

libtoolize -f -c  --automake
aclocal
autoheader
autoconf
automake -a -c 
automake -a -c Makefile
automake -a -c src/Makefile
automake -a -c test/Makefile
automake -a -c app/Makefile
