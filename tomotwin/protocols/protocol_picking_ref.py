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
from pwem import emlib
from pwem.objects import Volume

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
                      pointerClass="SetOfVolumes, Volume",
                      label='Reference volumes', important=True,
                      help='Specify a set of 3D volumes. They *must have '
                           'the same pixel size as tomograms and 37 px dimensions*.')

        if Plugin.versionGE("0.5.1"):
            form.addParam('inputMasks', params.PointerParam,
                          pointerClass='SetOfTomoMasks',
                          label='Input masks', allowsNull=True,
                          help='With TomoTwin >=0.5, the embedding command supports the '
                               'use of masks. With masks you can define which regions '
                               'of your tomogram get actually embedded and therefore '
                               'speedup the embedding.')
        form.addParam('numCpus', params.IntParam, default=4,
                      label="Number of CPUs",
                      help="*Important!* This is different from number of threads "
                           "above as threads are used for GPU parallelization. "
                           "Provide here the number of *CPU cores* for tomotwin locate "
                           "process.")

        form.addSection(label="Advanced params")
        line = form.addLine("Batch size for embedding",
                            help="To have your tomograms embedded as quick "
                                 "as possible, you should choose a batch size that "
                                 "utilize your GPU memory as much as possible. "
                                 "However, if you choose it too big, you might "
                                 "run into memory problems. In those cases play "
                                 "around with different batch sizes and check "
                                 "the memory usage with nvidia-smi.")
        line.addParam('batchTomos', params.IntParam, default=256,
                      label="Tomograms")
        line.addParam('batchRefs', params.IntParam, default=12,
                      label="References")

        line = form.addLine("Z-range for sliding (px)")
        line.addParam('zMin', params.IntParam, default=0,
                      label="Min")
        line.addParam('zMax', params.IntParam, default=0,
                      label="Max")

        form.addParam('boxSize', params.IntParam, default=37,
                      label="Box size (px)",
                      help="The box size only influences the non-maximum "
                           "suppression. The ideal box size is a tight box "
                           "size around the protein.")
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
        embedRefStepId = self._insertFunctionStep(self.embedRefsStep,
                                                  prerequisites=convertStepId)
        deps.append(embedRefStepId)

        tomoIds = self.inputTomos.get().aggregate(["COUNT"], "_tsId", ["_tsId"])
        tomoIds = set([d['_tsId'] for d in tomoIds])

        for tomoId in tomoIds:
            embedTomoStepId = self._insertFunctionStep(self.embedTomoStep,
                                                       tomoId,
                                                       prerequisites=convertStepId)
            deps.append(embedTomoStepId)
            self._insertFunctionStep(self.pickingStep, tomoId,
                                     prerequisites=deps)

        self._insertFunctionStep(self.createOutputStep)

    # --------------------------- STEPS functions -----------------------------
    def convertInputStep(self):
        """ Copy or link inputs to tmp. """
        pwutils.makePath(self._getTmpPath("input_refs"))
        pwutils.makePath(self._getTmpPath("input_masks"))
        refs = self.inputRefs.get()
        if isinstance(refs, Volume):
            refs = [refs]

        ih = emlib.image.ImageHandler()

        def _convert(inputFn, outputFn):
            if pwutils.getExt(inputFn) == '.mrc':
                pwutils.createAbsLink(os.path.abspath(inputFn), outputFn)
            else:
                ih.convert(inputFn, outputFn, emlib.DT_FLOAT)

        for vol in refs:
            inputFn = vol.getFileName()
            refFn = pwutils.removeBaseExt(inputFn) + '.mrc'
            refFn = self._getTmpPath(f"input_refs/{refFn}")
            _convert(inputFn, refFn)

        for tomo in self.inputTomos.get():
            inputFn = tomo.getFileName()
            tomoFn = self._getTmpPath(tomo.getTsId() + ".mrc")
            _convert(inputFn, tomoFn)

            if self._hasMasks():
                for mask in self.inputMasks.get():
                    if os.path.basename(mask.getVolName()) == os.path.basename(inputFn):
                        maskFn = self._getTmpPath(f"input_masks/{tomo.getTsId()}_mask.mrc")
                        _convert(mask.getFileName(), maskFn)
                        break

    def embedRefsStep(self):
        """ Embed the references. """
        self.runProgram(self.getProgram("tomotwin_embed.py"),
                        self._getEmbedRefsArgs())

    def embedTomoStep(self, tomoId):
        """ Embed each tomo. """
        self.runProgram(self.getProgram("tomotwin_embed.py"),
                        self._getEmbedTomoArgs(tomoId))

    def pickingStep(self, tomoId):
        """ Localize potential particles.  """
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
            files = glob(f"{self.getOutputDir(fromViewer)}/{tomoId}/*_relion3.star")
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

        refs = self.inputRefs.get()
        scale = refs.getSamplingRate() / self.inputTomos.get().getSamplingRate()
        doScale = abs(scale - 1.0) > 0.001
        if doScale:
            errors.append("Tomograms and references must have the same pixel size!")

        return errors

    def _warnings(self):
        warnings = []

        refs = self.inputRefs.get()
        if refs.getXDim() != 37:
            warnings.append("Because TomoTwin was trained on many proteins at "
                            "once, we needed to find a box size that worked "
                            "for all proteins. Therefore, all proteins were "
                            "used with a pixel size of 10Å and a box size of "
                            "37 pixels. Because of this, you must extract your "
                            "reference with a box size of 37 pixels. If your "
                            "protein is too large for this box at 10Å/pix (much "
                            "larger than a ribosome) then you should scale the "
                            "pixel size of your tomogram until it fits rather "
                            "than changing the box size. Likewise if your "
                            "protein is so small that at 10Å/pix it only fills "
                            "one to two pixels of the box, you should scale "
                            "your tomogram pixel size until the particle is "
                            "bigger, however we’ve found that for proteins down "
                            "to 100 kDa, 10Å/pix is sufficient for the 37 box.")

        if self.inputTomos.get().getSamplingRate() - 10.0 > 0.5:
            warnings.append("TomoTwin was trained on tomograms with a "
                            "pixel size of 10A. While in practice we've used "
                            "it with pixel sizes ranging from 9.2A to 25.0A, "
                            "it is probably ideal to run it at a pixel size "
                            "close to 10A.")

        return warnings

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
            f"-s 2 -o embed/tomos"
        ]

        if self.zMin > 0 and self.zMax > 0:
            args.append(f"-z {self.zMin} {self.zMax}")

        if self._hasMasks():
            maskFn = f"input_masks/{tomoId}_mask.mrc"
            if os.path.exists(self._getTmpPath(maskFn)):
                args.append(f"--mask {maskFn}")

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

    def _hasMasks(self):
        return Plugin.versionGE("0.5.1") and self.inputMasks.hasValue()
