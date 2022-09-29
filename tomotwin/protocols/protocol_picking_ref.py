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
from glob import glob

from pyworkflow import BETA
from pyworkflow import utils as pwutils
import pyworkflow.protocol.params as params
from pwem import emlib, Domain

from tomo.protocols import ProtTomoPicking
from tomo.objects import SetOfCoordinates3D
from tomo.constants import BOTTOM_LEFT_CORNER

from .. import Plugin
from ..constants import TOMOTWIN_MODEL
from ..convert import readSetOfCoordinates3D


class ProtTomoTwinRefPicking(ProtTomoPicking):
    """ Reference-based picking with TomoTwin. """

    _label = 'reference-based picking'
    _devStatus = BETA
    _possibleOutputs = {'output3DCoordinates': SetOfCoordinates3D}

    def __init__(self, **kwargs):
        ProtTomoPicking.__init__(self, **kwargs)
        self.stepsExecutionMode = params.STEPS_PARALLEL

    def _createFilenameTemplates(self):
        """ Centralize how files are called. """
        self._updateFilenamesDict({
            'output_tloc': self._getExtraPath("%(tomoId)s/locate/located.tloc")
        })

    # --------------------------- DEFINE param functions ----------------------
    def _defineParams(self, form):
        form.addSection(label='Input')
        form.addHidden(params.GPU_LIST, params.StringParam,
                       default='0', help="Choose GPU IDs")
        form.addParam('inputTomos', params.PointerParam,
                      pointerClass='SetOfTomograms',
                      label="Input tomograms", important=True,
                      help='Specify tomograms containing reference-like '
                           'particles to be extracted. It is recommended '
                           'to rescale tomograms to 10 A/px in advance. '
                           'Tomograms should be without denoising or '
                           'lowpass filtering.')
        form.addParam('inputRefs', params.PointerParam,
                      pointerClass="SetOfVolumes",
                      label='Reference volumes', important=True,
                      help='Specify a set of 3D volumes. They will be '
                           'rescaled to match the tomograms pixel size.')
        form.addParam('boxSize', params.IntParam, default=37,
                      label="Box size (px)",
                      help="The box size only influences the non-maximum "
                           "suppression. The ideal box size is a tight box "
                           "size around the protein.")
        form.addParam('numCpus', params.IntParam, default=4,
                      label="Number of CPUs",
                      help="*Important!* This is different from number of threads "
                           "above as threads are used for GPU parallelization. "
                           "Provide here the number of *CPU cores* for tomotwin locate "
                           "process.")

        form.addSection(label="Advanced params")
        line = form.addLine("Batch size for embedding")
        line.addParam('batchTomos', params.IntParam, default=64,
                      label="Tomograms")
        line.addParam('batchRefs', params.IntParam, default=128,
                      label="References")

        line = form.addLine("Z-range for sliding (px)")
        line.addParam('zMin', params.IntParam, default=0,
                      label="Min")
        line.addParam('zMax', params.IntParam, default=0,
                      label="Max")

        form.addParam('tolerance', params.FloatParam,
                      default=0.2,
                      label="Tolerance value")
        form.addParam('globalMin', params.FloatParam,
                      default=0.5,
                      label="Global minimum",
                      help="Global minimum of the find max procedure. "
                           "Maximums below this value will be ignored. "
                           "Higher values will give faster runtime.")

        form.addParallelSection(threads=1, mpi=1)

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._createFilenameTemplates()
        convertStepId = self._insertFunctionStep(self.convertInputStep)
        deps = []
        embedRef = self._insertFunctionStep(self.embedRefsStep,
                                            prerequisites=convertStepId)
        deps.append(embedRef)

        for tomo in self.inputTomos.get():
            stepId = self._insertFunctionStep(self.embedTomoStep, tomo.getTsId(),
                                              prerequisites=convertStepId)
            deps.append(stepId)

        pickStepId = self._insertFunctionStep(self.pickingStep,
                                              prerequisites=deps)
        self._insertFunctionStep(self.createOutputStep, prerequisites=pickStepId)

    # --------------------------- STEPS functions -----------------------------
    def convertInputStep(self):
        """ Copy inputs to tmp and rescale references. """
        pwutils.makePath(self._getTmpPath("input_refs"))
        scale = self.inputRefs.get().getSamplingRate() / self.inputTomos.get().getSamplingRate()
        doScale = abs(scale - 1.0) > 0.00001
        xmippPlugin = Domain.importFromPlugin('xmipp3', 'Plugin', doRaise=True)

        for vol in self.inputRefs.get():
            refFn = pwutils.removeBaseExt(vol.getFileName()) + '.mrc'
            refFn = self._getTmpPath(f"input_refs/{refFn}")

            if doScale:
                params = f' -i {os.path.abspath(vol.getFileName())}'
                params += f' -o {refFn} --factor {scale}'
                self.runJob("xmipp_image_resize", params, env=xmippPlugin.getEnviron())
            else:
                pwutils.createAbsLink(os.path.abspath(vol.getFileName()), refFn)

        ih = emlib.image.ImageHandler()
        for tomo in self.inputTomos.get():
            inputFn = tomo.getFileName()
            tomoFn = self._getTmpPath(tomo.getTsId() + ".mrc")
            if pwutils.getExt(inputFn) == '.mrc':
                pwutils.createAbsLink(os.path.abspath(inputFn), tomoFn)
            else:
                ih.convert(inputFn, tomoFn, emlib.DT_FLOAT)

    def embedRefsStep(self):
        """ Embed the references. """
        self.runProgram(self.getProgram("tomotwin_embed.py"),
                        self._getEmbedRefsArgs())

    def embedTomoStep(self, tomoId):
        """ Embed each tomo. """
        self.runProgram(self.getProgram("tomotwin_embed.py"),
                        self._getEmbedTomoArgs(tomoId))

    def pickingStep(self):
        """ Localize potential particles.  """
        for tomo in self.inputTomos.get():
            tomoId = tomo.getTsId()
            # map tomo
            self.runProgram(self.getProgram("tomotwin_map.py", gpu=False),
                            self._getMapArgs(tomoId))

            # locate particles
            self.runProgram(self.getProgram("tomotwin_locate.py", gpu=False),
                            self._getLocateArgs(tomoId))

            # output coords
            self.runProgram(self.getProgram("tomotwin_pick.py", gpu=False),
                            self._getPickArgs(tomoId))

    def createOutputStep(self, fromViewer=False):
        setOfTomograms = self.inputTomos.get()
        suffix = self._getOutputSuffix(SetOfCoordinates3D)
        coord3DSetDict = {}
        setOfCoord3D = self._createSetOfCoordinates3D(setOfTomograms, suffix)
        setOfCoord3D.setName("tomoCoord")
        setOfCoord3D.setPrecedents(setOfTomograms)
        setOfCoord3D.setSamplingRate(setOfTomograms.getSamplingRate())
        setOfCoord3D.setBoxSize(self.boxSize.get())

        for tomo in setOfTomograms.iterItems():
            tomoId = tomo.getTsId()
            files = glob(f"{self.getOutputDir(fromViewer)}/{tomoId}/*.cbox")
            if not files:
                continue
            else:
                coord3DSetDict[tomo.getObjId()] = setOfCoord3D
                for index, fn in enumerate(files):
                    readSetOfCoordinates3D(fn, setOfCoord3D, tomo.clone(),
                                           origin=BOTTOM_LEFT_CORNER,
                                           groupId=index)

        name = self.OUTPUT_PREFIX + suffix
        self._defineOutputs(**{name: setOfCoord3D})
        self._defineSourceRelation(setOfTomograms, setOfCoord3D)

        for tomoObjId, coord3DSet in coord3DSetDict.items():
            self._updateOutputSet(name, coord3DSet,
                                  state=coord3DSet.STREAM_CLOSED)

    # --------------------------- INFO functions ------------------------------
    def _validate(self):
        errors = []
        return errors

    def getSummary(self, coord3DSet):
        summary = list()
        summary.append("Number of particles picked: %s" % coord3DSet.getSize())
        summary.append("Particle size: %s" % coord3DSet.getBoxSize())
        return "\n".join(summary)

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
            f"-v {tomoId}.mrc",
            f"-b {self.batchTomos.get()}",
            f"-o embed/tomos"
        ]

        if self.zMin > 0 and self.zMax > 0:
            args.append(f"-z {self.zMin} {self.zMax}")

        return args

    def _getEmbedRefsArgs(self):
        return [
            f"subvolumes -m {Plugin.getVar(TOMOTWIN_MODEL)}",
            f"-v input_refs/*.mrc",
            f"-b {self.batchRefs.get()}",
            f"-o embed/refs"
        ]

    def _getMapArgs(self, tomoId):
        return [
            f"distance -r embed/refs/embeddings.temb",
            f"-v embed/tomos/{tomoId}_embeddings.temb",
            f"-o ../extra/{tomoId}/"
        ]

    def _getLocateArgs(self, tomoId):
        return [
            f"findmax -m ../extra/{tomoId}/map.tmap",
            f"-o ../extra/{tomoId}/locate",
            f"-t {self.tolerance.get()}",
            f"-b {self.boxSize.get()}",
            f"-g {self.globalMin.get()}",
            f"--processes {self.numCpus.get()}"
        ]

    def _getPickArgs(self, tomoId):
        return [
            f"-l ../extra/{tomoId}/locate/located.tloc",
            f"-o ../extra/{tomoId}/"
        ]

    def getProgram(self, program, gpu=True):
        return Plugin.getProgram(program, gpus=gpu,
                                 useQueue=self.useQueue())

    def runProgram(self, program, args):
        """ Execute runJob in tmpDir. """
        self.runJob(program, " ".join(args),
                    env=Plugin.getEnviron(),
                    cwd=self._getTmpPath())

    def getOutputDir(self, fromViewer=False):
        """ Results from the viewer will be in the project Tmp folder. """
        if fromViewer:
            return self.getProject().getTmpPath()
        else:
            return self._getExtraPath()
