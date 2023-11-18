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

from pyworkflow import BETA
import pyworkflow.protocol.params as params
from tomo.objects import SetOfCoordinates3D

from .. import Plugin
from ..constants import TOMOTWIN_MODEL
from .protocol_base import ProtTomoTwinBase


class ProtTomoTwinRefPicking(ProtTomoTwinBase):
    """ Reference-based picking with TomoTwin. """

    _label = 'reference-based picking'
    _devStatus = BETA
    _possibleOutputs = {'output3DCoordinates': SetOfCoordinates3D}
    _requiresRefs = True

    def __init__(self, **kwargs):
        ProtTomoTwinBase.__init__(self, **kwargs)
        self.stepsExecutionMode = params.STEPS_PARALLEL

    # --------------------------- DEFINE param functions ----------------------
    def _defineParams(self, form):
        self._defineInputParams(form)
        self._defineEmbedParams(form)
        self._definePickingParams(form)

        form.addParallelSection(threads=1)

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._createFilenameTemplates()
        convertStepId = self._insertFunctionStep(self.convertInputStep)
        deps = []
        embedRefStepId = self._insertFunctionStep(self.embedRefsStep,
                                                  prerequisites=convertStepId)
        deps.append(embedRefStepId)

        tomoIds = self._getInputTomos().aggregate(["COUNT"], "_tsId", ["_tsId"])
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
    def embedRefsStep(self):
        """ Embed the references. """
        self.runProgram(self.getProgram("tomotwin_embed.py"),
                        self._getEmbedRefsArgs())

    # --------------------------- INFO functions ------------------------------
    def _validate(self):
        errors = []

        refs = self.inputRefs.get()
        scale = refs.getSamplingRate() / self._getInputTomos().getSamplingRate()
        doScale = abs(scale - 1.0) > 0.001
        if doScale:
            errors.append("Tomograms and references must have the same pixel size!")

        return errors

    def _warningsExtra(self):
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

        return warnings

    # --------------------------- UTILS functions ------------------------------
    def _getEmbedRefsArgs(self):
        return [
            f"subvolumes -m {Plugin.getVar(TOMOTWIN_MODEL)}",
            "-v ../tmp/input_refs/*.mrc",
            f"-b {self.batchRefs.get()}",
            "-o embed/refs"
        ]

    def _getMapArgs(self, tomoId):
        return [
            "distance -r embed/refs/embeddings.temb",
            f"-v embed/tomos/{tomoId}_embeddings.temb",
            f"-o {tomoId}/"
        ]
