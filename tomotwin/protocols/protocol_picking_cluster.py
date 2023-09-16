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
from pyworkflow.utils import yellowStr
from tomo.objects import SetOfCoordinates3D

from .. import Plugin
from .protocol_base import ProtTomoTwinBase


class ProtTomoTwinClusterPicking(ProtTomoTwinBase):
    """ Clustering-based picking with TomoTwin. """

    _label = 'clustering-based picking'
    _devStatus = BETA
    _possibleOutputs = {'output3DCoordinates': SetOfCoordinates3D}

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._createFilenameTemplates()
        self._insertFunctionStep(self.convertInputStep)

        tomoIds = self.inputTomos.get().aggregate(["COUNT"], "_tsId", ["_tsId"])
        tomoIds = set([d['_tsId'] for d in tomoIds])

        for tomoId in tomoIds:
            self._insertFunctionStep(self.embedTomoStep, tomoId)
            self._insertFunctionStep(self.createUmapsStep, tomoId)
            self._insertFunctionStep(self.pickClustersStep, tomoId)
            self._insertFunctionStep(self.pickingStep, tomoId)

        self._insertFunctionStep(self.createOutputStep)

    # --------------------------- STEPS functions -----------------------------
    def createUmapsStep(self, tomoId):
        """ Estimate UMAP manifold and Generate Embedding Mask. """
        self.runProgram(self.getProgram("tomotwin_tools.py"),
                        self._getUmapArgs(tomoId))

    def pickClustersStep(self, tomoId):
        """ Load data for clustering in Napari. """
        maskFn = f"{tomoId}_embeddings_label_mask.mrci"
        if os.path.exists(self._getExtraPath(tomoId, maskFn)):
            self.info("Loading data for clustering in Napari..")
            tomoPath = os.path.relpath(self._getTmpPath(tomoId + ".mrc"),
                                       self._getExtraPath(tomoId))
            args = f"{tomoPath} {maskFn}"

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

            Plugin.runNapariBoxManager(self._getExtraPath(tomoId),
                                       "napari", args)
        else:
            self.info(f"Skipping tomo {tomoId}, no embedding mask file found.")

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

    # --------------------------- UTILS functions ------------------------------
    def _getUmapArgs(self, tomoId):
        return [
            f"umap -i embed/tomos/{tomoId}_embeddings.temb",
            f"-o ../extra/{tomoId}/"
        ]

    def _getMapArgs(self, tomoId):
        clustersFn = self._getExtraPath(tomoId, "cluster_targets.temb")
        if not os.path.exists(clustersFn):
            raise FileNotFoundError(f"Missing file from Napari: {clustersFn}")

        return [
            f"distance -r ../extra/{tomoId}/cluster_targets.temb",
            f"-v embed/tomos/{tomoId}_embeddings.temb",
            f"-o ../extra/{tomoId}/"
        ]
