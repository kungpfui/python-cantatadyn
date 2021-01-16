#!/usr/bin/env python

import os
import sys
import shutil
import subprocess
from distutils.core import setup
from setuptools.command.install import install as _install


_package = 'cantatadyn'
_conf_fn = f'{_package}.conf'

class Prepare(_install):
    def run(self):
        _install.run(self)

        # load my own config file
        from cantatadyn import Config
        conf = Config(_conf_fn)

        shutil.copy(_conf_fn, f'/etc/opt/')
        # create folders
        for folder in (conf.filesDir, conf.logDir):
            if not os.path.exists(folder):
                os.makedirs(folder)
            shutil.chown(folder, 'mpd', 'audio')
            os.chmod(folder, 0o766)

        shutil.copy('cantatadyn.service', '/lib/systemd/system/')
        subprocess.call("systemctl enable cantatadyn.service", shell=True)


with open(os.path.join(_package, '__init__.py')) as fid:
    for line in fid:
        if line.startswith('__version__'):
            VERSION = line.strip().split()[-1][1:-1]
            break

LONG_DESCRIPTION = """
"""

setup(name='cantatadyn',
    version=VERSION,
    author='Stefan Schwendeler',
    author_email='kungpfui@users.noreply.github.com',
    url='https://github.com/kungpfui/python-cantatadyn',
    description='Cantata/MPD Dynamic Playlist Daemon',
    long_description=LONG_DESCRIPTION,
    license='GPL3.0',

    install_requires = [ ],
    packages=[_package],
    cmdclass={'install': Prepare}
    )

