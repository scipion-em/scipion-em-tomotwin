# **************************************************************************
# *
# * Authors:     Grigory Sharov (gsharov@mrc-lmb.cam.ac.uk)
# *
# * MRC Laboratory of Molecular Biology (MRC-LMB)
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 3 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307  USA
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************

import os
import pwem
import pyworkflow.utils as pwutils
from pyworkflow import Config

from .constants import *


__version__ = '3.0a1'
_references = ['Rice2022']
_logo = "tomotwin_logo.png"


class Plugin(pwem.Plugin):
    _url = "https://github.com/scipion-em/scipion-em-tomotwin"
    _supportedVersions = VERSIONS

    @classmethod
    def _defineVariables(cls):
        cls._defineVar(TOMOTWIN_ENV_ACTIVATION, DEFAULT_ACTIVATION_CMD)
        cls._defineVar(NAPARI_ENV_ACTIVATION, "conda activate napari")
        cls._defineEmVar(TOMOTWIN_MODEL, DEFAULT_MODEL)

    @classmethod
    def getTomoTwinEnvActivation(cls):
        """ Remove the scipion home and activate the conda environment. """
        activation = cls.getVar(TOMOTWIN_ENV_ACTIVATION)
        scipionHome = Config.SCIPION_HOME + os.path.sep

        return activation.replace(scipionHome, "", 1)

    @classmethod
    def getEnviron(cls):
        """ Setup the environment variables needed to launch TomoTwin. """
        environ = pwutils.Environ(os.environ)
        if 'PYTHONPATH' in environ:
            # this is required for python virtual env to work
            del environ['PYTHONPATH']
        return environ

    @classmethod
    def getDependencies(cls):
        """ Return a list of dependencies. Include conda if
        activation command was not found. """
        condaActivationCmd = cls.getCondaActivationCmd()
        neededProgs = []
        if not condaActivationCmd:
            neededProgs.append('conda')

        return neededProgs

    @classmethod
    def defineBinaries(cls, env):
        for ver in VERSIONS:
            cls.addTomoTwinPackage(env, ver,
                                   default=ver == TOMOTWIN_DEFAULT_VER_NUM)

        url = "https://owncloud.gwdg.de/index.php/s/vfjKoBZc4YtPaGT/download"
        env.addPackage(TOMOTWIN_MODEL, version="052022",
                       tar='void.tgz',
                       commands=[(f"wget -O {DEFAULT_MODEL} {url}",
                                  DEFAULT_MODEL)],
                       neededProgs=["wget"],
                       default=True)

        env.addPackage("napari", version="latest", tar="void.tgz",
                       commands=[(f"{cls.getCondaActivationCmd()} "
                                  f"conda create -y -n napari -c conda-forge "
                                  f"python=3.9 napari && touch installed",
                                  "./installed")],
                       default=False)

    @classmethod
    def addTomoTwinPackage(cls, env, version, default=False):
        ENV_NAME = getTomoTwinEnvName(version)
        installCmds = [
            f"cd .. && rmdir tomotwin-{version} &&",
            f"git clone -b dev https://github.com/MPI-Dortmund/tomotwin-cryoet.git tomotwin-{version} &&",
            f"cd tomotwin-{version} && git rev-parse --short HEAD > VERSION.txt && ",
            cls.getCondaActivationCmd(),
            f"conda create -y -n {ENV_NAME} -c pytorch -c rapidsai -c nvidia",
            f"-c conda-forge python=3.9 pytorch==1.12 torchvision pandas scipy",
            f"numpy matplotlib pytables cuML=22.06 cudatoolkit=11.6 'protobuf>3.20' tensorboard &&",
            f"conda activate tomotwin-{version} &&",
            f"pip install -e . && conda remove -y --force cupy",
        ]

        tomotwinCmds = [(" ".join(installCmds), "VERSION.txt")]

        envPath = os.environ.get('PATH', "")
        # keep path since conda likely in there
        installEnvVars = {'PATH': envPath} if envPath else None
        env.addPackage('tomotwin', version=version,
                       tar='void.tgz',
                       commands=tomotwinCmds,
                       neededProgs=cls.getDependencies(),
                       default=default,
                       vars=installEnvVars)

    @classmethod
    def getActivationCmd(cls):
        """ Return the activation command. """
        return '%s %s' % (cls.getCondaActivationCmd(),
                          cls.getTomoTwinEnvActivation())

    @classmethod
    def getProgram(cls, program, gpus='0'):
        """ Create TomoTwin command line. """
        fullProgram = '%s && CUDA_VISIBLE_DEVICES=%s %s' % (
            cls.getActivationCmd(), gpus, program)

        return fullProgram

    @classmethod
    def getActiveVersion(cls, *args):
        """ Return the env name that is currently active. """
        envVar = cls.getVar(TOMOTWIN_ENV_ACTIVATION)
        return envVar.split()[-1].split("-")[-1]

    @classmethod
    def versionGE(cls, version):
        """ Return True if current version of TomoTwin is newer
         or equal than the input argument.
         Params:
            version: string version (semantic version, e.g 0.3.3b)
        """
        v1 = cls.getActiveVersion()
        if v1 not in VERSIONS:
            raise Exception("This version of TomoTwin is not supported: ", v1)

        if VERSIONS.index(v1) < VERSIONS.index(version):
            return False
        return True
