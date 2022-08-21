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
from pyworkflow.utils.properties import Message
from pyworkflow import utils as pwutils
import pyworkflow.protocol.params as params

from tomo.protocols import ProtTomoPicking
from tomo.objects import SetOfCoordinates3D

from .. import Plugin
from ..constants import TOMOTWIN_MODEL


class ProtTomoTwinRefPicking(ProtTomoPicking):
    """ Reference-based picking with TomoTwin. """

    _label = 'reference-based picking'
    _devStatus = BETA
    _possibleOutputs = {}

    def _createFilenameTemplates(self):
        """ Centralize how files are called. """

        myDict = {
        }

        self._updateFilenamesDict(myDict)

    def __int__(self, **kwargs):
        ProtTomoPicking.__init__(self, **kwargs)

    # --------------------------- DEFINE param functions ----------------------
    def _defineParams(self, form):
        form.addSection(label='Input')
        form.addHidden(params.GPU_LIST, params.StringParam,
                       default='0', label="Choose GPU IDs")
        form.addParam('inputTomos', params.PointerParam,
                      pointerClass='SetOfTomograms',
                      label="Input tomograms", important=True,
                      help='Specify tomograms containing reference-like '
                           'particles to be extracted.')
        form.addParam('inputRefs', params.PointerParam,
                      pointerClass="SetOfVolumes",
                      label='Reference volumes', important=True,
                      help='Specify a set of 3D volumes.')
        form.addParam('boxSize', params.IntParam, default=37,
                      label="Box size (px)")

        form.addSection(label="Embedding")
        line = form.addLine("Batch size for embedding")
        line.addParam('batchTomos', params.IntParam, default=64,
                      label="Tomograms")
        line.addParam('batchRefs', params.IntParam, default=128,
                      label="References")

        group = form.addGroup('Sliding window')
        group.addParam('windowSize', params.IntParam, default=37,
                       label="Window size")
        group.addParam('strideSize', params.IntParam, default=2,
                       label="Stride of sliding window")

        line = group.addLine("Z-range for sliding")
        line.addParam('zMin', params.IntParam, default=0,
                      label="Min")
        line.addParam('zMax', params.IntParam, default=0,
                      label="Max")

        form.addSection(label="Locate particles")
        form.addParam('tolerance', params.FloatParam,
                      default=0.2,
                      label="Tolerance value")
        form.addParam('globalMin', params.FloatParam,
                      default=0.5,
                      label="Global minimum",
                      help="Global minimum of the find max procedure. "
                           "Maximums below value will be ignored. "
                           "Higher values give faster runtime.")

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._insertFunctionStep('convertInputStep')
        self._insertFunctionStep('pickingStep')
        self._insertFunctionStep("createOutputStep")

    # --------------------------- STEPS functions -----------------------------
    def convertInputStep(self):
        pwutils.makePath(self._getTmpPath("refs"))

        for vol in self.inputRefs.get():
            refFn = pwutils.removeBaseExt(vol.getFileName()) + '.mrc'
            refFn = self._getTmpPath(f"refs/{refFn}")

            pwutils.createAbsLink(os.path.abspath(vol.getFileName()),
                                  refFn)

        for tomo in self.inputTomos.get():
            tomoFn = self._getTmpPath(tomo.getTsId() + ".mrc")
            pwutils.createAbsLink(os.path.abspath(tomo.getFileName()),
                                  tomoFn)

    def pickingStep(self):
        # embed refs
        self.runProgram(self.getProgram("tomotwin_embed.py"),
                        self._getEmbedRefsArgs())

        for tomo in self.inputTomos.get():
            tomoId = tomo.getTsId()
            # embed tomo
            self.runProgram(self.getProgram("tomotwin_embed.py"),
                            self._getEmbedTomoArgs(tomoId))

            # map tomo
            self.runProgram(self.getProgram("tomotwin_map.py"),
                            self._getMapArgs())

            # locate particles
            self.runProgram(self.getProgram("tomotwin_locate.py"),
                            self._getLocateArgs())

    def createOutputStep(self):
        pass

    # --------------------------- INFO functions ------------------------------
    def _validate(self):
        errors = []
        return errors

    def getSummary(self, coord3DSet):
        summary = []
        summary.append("Number of particles picked: %s" % coord3DSet.getSize())
        summary.append("Particle size: %s" % coord3DSet.getBoxSize())
        return "\n".join(summary)

    def _summary(self):
        summary = []
        if not self.isFinished():
            summary.append("Output 3D Coordinates not ready yet.")

        if self.getOutputsSize() >= 1:
            for key, output in self.iterOutputAttributes():
                summary.append("*%s:* \n %s " % (key, output.getObjComment()))
        else:
            summary.append(Message.TEXT_NO_OUTPUT_CO)
        return summary

    def _methods(self):
        tomos = self.inputTomos.get()
        return [
            "Subtomogram coordinates obtained with TomoTwin picker",
            "A total of %d tomograms of dimensions %s were used"
            % (tomos.getSize(), tomos.getDimensions()),
        ]

    # --------------------------- UTILS functions ------------------------------
    def _getEmbedTomoArgs(self, tomoId):
        args = [
            f"tomogram -m {Plugin.getVar(TOMOTWIN_MODEL)}",
            f"-v {tomoId + '.mrc'}",
            f"-b {self.batchTomos.get()}",
            f"-o embed/tomos",
            f"-w {self.windowSize.get()}",
            f"-s {self.strideSize.get()}"
        ]

        if self.zMin > 0 and self.zMax > 0:
            args.append(f"-z {self.zMin} {self.zMax}")

        return args

    def _getEmbedRefsArgs(self):
        return [
            f"subvolumes -m {Plugin.getVar(TOMOTWIN_MODEL)}",
            f"-v refs/*.mrc",
            f"-b {self.batchRefs.get()}",
            f"-o embed/refs"
        ]

    def _getMapArgs(self):
        return [
            f"distance -r embed/refs_embeddings.temb",
            f"-v embed/tomos_embeddings.temb",
            f"-o ./"
        ]

    def _getLocateArgs(self):
        return [
            "findmax -m map.tmap",
            "-o locate/",
            f"-t {self.tolerance.get()}",
            f"-b {self.boxSize.get()}",
            f"-g {self.globalMin.get()}"
        ]

    def getProgram(self, program):
        return Plugin.getProgram(program,
                                 gpus=self.gpuList.get().replace(" ", ","))

    def runProgram(self, program, args):
        """ Execute runJob in tmpDir. """
        self.runJob(program, " ".join(args),
                    env=Plugin.getEnviron(),
                    cwd=self._getTmpPath(),
                    numberOfThreads=1)
