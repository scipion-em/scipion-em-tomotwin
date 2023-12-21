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
import glob

from pyworkflow import BETA
from pyworkflow.utils import yellowStr, makePath, createAbsLink
import pyworkflow.protocol.params as params
from tomo.objects import SetOfCoordinates3D

from .. import Plugin
from ..convert import convertToMrc
from .protocol_base import ProtTomoTwinBase


class ProtTomoTwinClusterPicking(ProtTomoTwinBase):
    """ Clustering-based picking with TomoTwin (step 2).

    The second step includes interactive clustering of UMAP embeddings and
    creating output coordinates.
    """

    _label = 'clustering-based picking (step 2)'
    _devStatus = BETA
    _possibleOutputs = {'output3DCoordinates': SetOfCoordinates3D}

    # --------------------------- DEFINE param functions ----------------------
    def _defineParams(self, form):
        form.addSection(label='Input')
        form.addParam("inputUmaps", params.PointerParam,
                      pointerClass="ProtTomoTwinClusterCreateUmaps",
                      label="Previous cluster picking protocol (step 1)")

        self._definePickingParams(form)

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._createFilenameTemplates()
        self._insertFunctionStep(self.convertInputStep)

        tomoIds = self._getInputTomos().aggregate(["COUNT"], "_tsId", ["_tsId"])
        tomoIds = set([d['_tsId'] for d in tomoIds])

        for tomoId in tomoIds:
            makePath(self._getExtraPath(tomoId))
            self._insertFunctionStep(self.pickClustersStep, tomoId)
            self._insertFunctionStep(self.pickingStep, tomoId)

        self._insertFunctionStep(self.createOutputStep)

    # --------------------------- STEPS functions -----------------------------
    def convertInputStep(self):
        """ Copy or link inputs to tmp. """
        for tomo in self._getInputTomos():
            inputFn = tomo.getFileName()
            tomoFn = self._getTmpPath(tomo.getTsId() + ".mrc")
            convertToMrc(inputFn, tomoFn)

    def pickClustersStep(self, tomoId):
        """ Link embeddings from the previous protocol and
        load data for clustering in Napari. """
        inputUmapsProt = self._getInputProt()
        srcDir = inputUmapsProt._getExtraPath(tomoId)
        targetFn = lambda fn: self._getExtraPath(tomoId, os.path.basename(fn))
        files = glob.glob(os.path.join(srcDir, f"{tomoId}_embeddings*"))
        for f in files:
            self.info(f"Linking {f} -> {targetFn(f)}")
            createAbsLink(os.path.abspath(f), targetFn(f))

        self.info("Loading data for clustering in Napari..")
        tomoPath = os.path.relpath(self._getTmpPath(tomoId + ".mrc"),
                                   self._getExtraPath(tomoId))
        args = f"{tomoPath}"

        if not Plugin.versionGE("0.8.0"):
            maskFn = f"{tomoId}_embeddings_label_mask.mrci"
            if os.path.exists(self._getExtraPath(tomoId, maskFn)):
                args += f" {maskFn}"

        text = [
            "Next open the napari-tomotwin clustering tool ",
            "via Plugins -> napari-tomotwin -> Cluster UMAP embeddings. ",
            "Then choose the Path to UMAP by clicking on Select file ",
            "and provide the path to your_tomo_embeddings.tumap. ",
            "Click Load and after a second, a 2D plot of the umap embeddings ",
            "should appear in the plugin window. ",
            "Continue by following https://tomotwin-cryoet.readthedocs.io/en/latest/tutorials/tutorials_overview.html#find-target-clusters ",
            "In the end, save cluster targets in the cluster_targets.temb file inside extra/tomoId folder."
        ]
        text = "".join(text)
        self.info(yellowStr(text))

        Plugin.runNapariBoxManager(self._getExtraPath(tomoId), "napari", args)

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

    # --------------------------- INFO functions ------------------------------
    def _warnings(self):
        return []

    def _methods(self):
        return []

    # --------------------------- UTILS functions ------------------------------
    def _getMapArgs(self, tomoId):
        clustersFn = self._getExtraPath(tomoId, "cluster_targets.temb")
        if not os.path.exists(clustersFn):
            raise FileNotFoundError(f"Missing file from Napari: {clustersFn}")

        tomoEmbedded = self._getInputProt()._getExtraPath(f"embed/tomos/{tomoId}_embeddings.temb")

        return [
            f"distance -r {tomoId}/cluster_targets.temb",
            f"-v {os.path.abspath(tomoEmbedded)}",
            f"-o {tomoId}/"
        ]

    def _getInputProt(self):
        return self.inputUmaps.get()

    def _getInputTomos(self):
        """ Override base class. """
        return self._getInputProt().inputTomos.get()
