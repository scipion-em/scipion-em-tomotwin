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


__version__ = '3.4'
_references = ['Rice2022']
_logo = "tomotwin_logo.png"


class Plugin(pwem.Plugin):
    _pathVars = [TOMOTWIN_MODEL]
    _url = "https://github.com/scipion-em/scipion-em-tomotwin"
    _supportedVersions = VERSIONS

    @classmethod
    def _defineVariables(cls):
        cls._defineVar(TOMOTWIN_ENV_ACTIVATION, DEFAULT_ACTIVATION_CMD)
        cls._defineEmVar(TOMOTWIN_MODEL, cls._getTomotwinModel(DEFAULT_MODEL))

    @classmethod
    def _getTomotwinModel(cls, version):
        return os.path.join(f"tomotwin_model-{version}", getModelName(version))

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

        url2022 = "https://ftp.gwdg.de/pub/misc/sphire/TomoTwin/models/tomotwin_model_p120_052022_loss.pth"
        url2023 = "https://zenodo.org/records/8358240/files/tomotwin_latest.pth?download=1"
        for ver, url in zip(MODEL_VERSIONS, [url2022, url2023]):
            env.addPackage("tomotwin_model", version=ver,
                           tar='void.tgz',
                           commands=[(f"wget -O {getModelName(ver)} {url}",
                                      getModelName(ver))],
                           neededProgs=["wget"],
                           default=ver == DEFAULT_MODEL)

    @classmethod
    def addTomoTwinPackage(cls, env, version, default=False):
        ENV_NAME = getTomoTwinEnvName(version)
        git_version = f"v{version}" if version in ['0.6.1', '0.8.0'] else version
        installCmds = [
            f"cd .. && rmdir tomotwin-{version} &&",
            f"git clone -b {git_version} https://github.com/MPI-Dortmund/tomotwin-cryoet.git {ENV_NAME} &&",
            f"cd {ENV_NAME} && {cls.getCondaActivationCmd()}",
            f"conda create -y -n {ENV_NAME} -c nvidia -c pytorch -c rapidsai -c conda-forge",
            "'pytorch>=2.1' torchvision 'pandas<2' scipy numpy matplotlib",
            "pytables cuML=23.04 cudatoolkit=11.8 'protobuf>3.20'",
            "tensorboard optuna mysql-connector-python &&",
            f"conda activate {ENV_NAME} &&",
            "pip install -e .",
        ]

        tomotwinCmds = [(" ".join(installCmds), "setup.py")]

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
        return f'{cls.getCondaActivationCmd()} {cls.getTomoTwinEnvActivation()}'

    @classmethod
    def getProgram(cls, program, gpus=True, useQueue=False):
        """ Create TomoTwin command line. """
        fullProgram = f"{cls.getActivationCmd()} && "
        if gpus and not useQueue:
            fullProgram += "CUDA_VISIBLE_DEVICES=%(GPU)s "

        return fullProgram + program

    @classmethod
    def runNapariBoxManager(cls, tmpDir, program, args):
        """ Run Napari boxmanager from a given protocol. """
        tomoPlugin = pwem.Domain.importFromPlugin('tomo', 'Plugin', doRaise=True)
        tomoPlugin._defineVariables()
        napariVar = tomoPlugin.getVar(NAPARI_ENV_ACTIVATION)
        fullProgram = '%s %s && %s' % (cls.getCondaActivationCmd(),
                                       napariVar, program)
        print(f"Running command: {fullProgram} {args}")
        pwutils.runJob(None, fullProgram, args, env=cls.getEnviron(),
                       cwd=tmpDir, numberOfMpi=1)

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
            raise ValueError("This version of TomoTwin is not supported: ", v1)

        if VERSIONS.index(v1) < VERSIONS.index(version):
            return False
        return True
