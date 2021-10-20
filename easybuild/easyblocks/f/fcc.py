##
# Copyright 2009-2021 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/easybuilders/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
EasyBuild support for installing FCC compiler toolchain, implemented as an easyblock

@author: Miguel Dias Costa (National University of Singapore)
"""
import os
import stat
import tempfile

from easybuild.easyblocks.generic.toolchain import Toolchain
from easybuild.framework.easyconfig import CUSTOM
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.filetools import adjust_permissions, mkdir, which, write_file
from easybuild.tools.py2vs3 import subprocess_popen_text


class EB_FCC(Toolchain):
    """FCC compiler toolchain easyblock: install compiler wrappers and generate module file."""

    @staticmethod
    def extra_options(extra_vars=None):
        """Easyconfig parameters specific to Fujitsu toolchains."""
        if extra_vars is None:
            extra_vars = {}
        extra_vars.update({
            'wrapper_flags': [[], "Flags to inject in Fujitsu compiler wrappers", CUSTOM],
        })
        return Toolchain.extra_options(extra_vars=extra_vars)

    def install_step(self):
        super(EB_FCC, self).install_step()

        def test_compiler(fcc):
            fd, fn = tempfile.mkstemp(suffix='.c')
            with os.fdopen(fd, 'w') as f:
                f.write("int main(){return 0;}")

            fdx, fnx = tempfile.mkstemp(suffix='.x')
            os.close(fdx)

            proc = subprocess_popen_text([fcc, '-Nclang', fn, '-o', fnx] + self.cfg['wrapper_flags'])
            (stdout, stderr) = proc.communicate()

            proc = subprocess_popen_text([fnx])
            (stdout, stderr) = proc.communicate()

            if proc.returncode == 0:
                return True
            else:
                return False

        fcc = which('fcc')
        if fcc is None:
            raise EasyBuildError("Could not find path to Fujitsu compiler. You may need to edit the FCC easyconfig"
                                 "in order to load the correct module for your system.")

        test = test_compiler(fcc)
        if test:
            self.log.info("Fujitsu compiler was able to compile a working executable.")
        elif '-Knolargepage' not in self.cfg['wrapper_flags']:
            self.log.info("Fujitsu compiler was not able to compile a working executable, trying with -Knolargepage")
            self.cfg.update('wrapper_flags', '-Knolargepage')
            test = test_compiler(fcc)
            if test:
                self.log.info("Fujitsu compiler was able to compile a working executable.")

        if not test:
            raise EasyBuildError("Not able to generate a working executable with the Fujitsu compiler. \
                                  You may need to use the wrapper_flags easyconfig parameter to inject flags.")

        wrapper_template = """#!/bin/bash\n%(cmd)s %(flags)s \"$@\"\n"""

        wrapper_flags = self.cfg['wrapper_flags']

        compilers = [
            {'name': 'fcc', 'cmd': which('fcc'), 'flags': ' '.join(['-Nclang'] + wrapper_flags)},
            {'name': 'FCC', 'cmd': which('FCC'), 'flags': ' '.join(['-Nclang'] + wrapper_flags)},
            {'name': 'frt', 'cmd': which('frt'), 'flags': ' '.join(wrapper_flags)},

            {'name': 'mpifcc', 'cmd': which('mpifcc'), 'flags': ' '.join(['-Nclang'] + wrapper_flags)},
            {'name': 'mpiFCC', 'cmd': which('mpiFCC'), 'flags': ' '.join(['-Nclang'] + wrapper_flags)},
            {'name': 'mpifrt', 'cmd': which('mpifrt'), 'flags': ' '.join(wrapper_flags)},
        ]

        bindir = os.path.join(self.installdir, 'bin')
        mkdir(bindir, parents=True)
        for compiler in compilers:
            cmd_wrapper = os.path.join(bindir, compiler['name'])
            write_file(cmd_wrapper, wrapper_template % compiler)
            adjust_permissions(cmd_wrapper, stat.S_IXUSR)
