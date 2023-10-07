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
from .protocol_base import ProtTomoTwinBase


class ProtTomoTwinClusterCreateUmaps(ProtTomoTwinBase):
    """ Clustering-based picking with TomoTwin (step 1).

    The first step includes tomograms embedding and creating UMAPs.
    """

    _label = 'clustering-based picking (step 1)'
    _devStatus = BETA

    def __init__(self, **kwargs):
        ProtTomoTwinBase.__init__(self, **kwargs)
        self.stepsExecutionMode = params.STEPS_PARALLEL

    # --------------------------- DEFINE param functions ----------------------
    def _defineParams(self, form):
        self._defineInputParams(form)
        self._defineEmbedParams(form)

        form.addParallelSection(threads=1)

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._createFilenameTemplates()
        convertStepId = self._insertFunctionStep(self.convertInputStep)

        tomoIds = self._getInputTomos().aggregate(["COUNT"], "_tsId", ["_tsId"])
        tomoIds = set([d['_tsId'] for d in tomoIds])

        for tomoId in tomoIds:
            tomoStep = self._insertFunctionStep(self.embedTomoStep, tomoId,
                                                prerequisites=convertStepId)
            self._insertFunctionStep(self.createUmapsStep, tomoId,
                                     prerequisites=tomoStep)

    # --------------------------- STEPS functions -----------------------------
    def createUmapsStep(self, tomoId):
        """ Estimate UMAP manifold and Generate Embedding Mask. """
        self.runProgram(self.getProgram("tomotwin_tools.py"),
                        self._getUmapArgs(tomoId))

    # --------------------------- INFO functions ------------------------------
    def _summary(self):
        if self.isFinished():
            return ["UMAP embeddings created for input tomograms."]

    # --------------------------- UTILS functions ------------------------------
    def _getUmapArgs(self, tomoId):
        return [
            f"umap -i embed/tomos/{tomoId}_embeddings.temb",
            f"-o {tomoId}/",
            f"--fit_sample_size {self.fitSampleSize.get()}",
            f"--chunk_size {self.chunkSize.get()}"
        ]
