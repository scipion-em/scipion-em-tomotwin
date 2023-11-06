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

from pyworkflow import BETA
import pyworkflow.protocol.params as params
from pwem.protocols import ProtCreateMask3D

from tomo.objects import SetOfTomoMasks, TomoMask

from .. import Plugin
from ..constants import TOMOTWIN_MODEL
from ..convert import convertToMrc


class ProtTomoTwinCreateMasks(ProtCreateMask3D):
    """ Calculate a 3D mask that excludes areas that probably do not contain any protein. """

    _label = 'create tomo masks'
    _devStatus = BETA
    _possibleOutputs = {'outputMasks': SetOfTomoMasks}

    def __init__(self, **kwargs):
        ProtCreateMask3D.__init__(self, **kwargs)
        self.stepsExecutionMode = params.STEPS_PARALLEL

    # --------------------------- DEFINE param functions ----------------------
    def _defineParams(self, form):
        form.addSection(label='Input')
        form.addHidden(params.GPU_LIST, params.StringParam,
                       default='0', help="Choose GPU IDs")
        form.addParam('inputTomos', params.PointerParam,
                      pointerClass='SetOfTomograms',
                      label="Input tomograms", important=True,
                      help='It is recommended to rescale tomograms to '
                           '10 A/px in advance. Tomograms should be '
                           'without denoising or lowpass filtering.')

        if Plugin.versionGE("0.7.0"):
            form.addParam('roiEstimate', params.EnumParam,
                          choices=['median', 'intensity'],
                          default=0,
                          display=params.EnumParam.DISPLAY_HLIST,
                          label='ROI estimation based on:',
                          help='Estimate potential ROIs based on median '
                               'embedding (default) or intensity values.')

        form.addParallelSection(threads=1)

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        convertStepId = self._insertFunctionStep(self.convertInputStep)
        deps = []
        tomoIds = self.inputTomos.get().aggregate(["COUNT"], "_tsId", ["_tsId"])
        tomoIds = set([d['_tsId'] for d in tomoIds])

        for tomoId in tomoIds:
            stepId = self._insertFunctionStep(self.createMaskStep, tomoId,
                                              prerequisites=convertStepId)
            deps.append(stepId)

        self._insertFunctionStep(self.createOutputStep, prerequisites=deps)

    # --------------------------- STEPS functions -----------------------------
    def convertInputStep(self):
        """ Convert or link input files to mrc format. """
        for tomo in self.inputTomos.get():
            inputFn = tomo.getFileName()
            tomoFn = self._getTmpPath(tomo.getTsId() + ".mrc")
            convertToMrc(inputFn, tomoFn)

    def createMaskStep(self, tomoId):
        """ Create mask for each tomo. """
        args = ["embedding_mask"]

        if Plugin.versionGE("0.7.0"):
            args.extend([
                f"{self.getEnumText('roiEstimate')}",
                f"-m {Plugin.getVar(TOMOTWIN_MODEL)}"
            ])

        args.extend([
            f"-i {tomoId}.mrc",
            "-o ../extra/"
        ])

        self.runJob(self.getProgram("tomotwin_tools.py"), " ".join(args),
                    env=Plugin.getEnviron(),
                    cwd=self._getTmpPath())

    def createOutputStep(self):
        inTomos = self.inputTomos.get()
        outputSet = SetOfTomoMasks.create(self._getPath())
        outputSet.setSamplingRate(inTomos.getSamplingRate())

        for tomo in inTomos.iterItems():
            outTomoMask = TomoMask()
            outTomoMask.copyInfo(tomo)
            outTomoMask.setFileName(self._getExtraPath(f"{tomo.getTsId()}_mask.mrc"))
            outTomoMask.setVolName(os.path.basename(tomo.getFileName()))
            outputSet.append(outTomoMask)

        self._defineOutputs(outputMasks=outputSet)
        self._defineSourceRelation(inTomos, outputSet)

    # --------------------------- UTILS functions ------------------------------
    def getProgram(self, program, gpu=True):
        return Plugin.getProgram(program, gpus=gpu,
                                 useQueue=self.useQueue())
