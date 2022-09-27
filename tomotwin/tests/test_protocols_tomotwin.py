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

from pyworkflow.tests import BaseTest, setupTestProject
from pwem.protocols import ProtImportVolumes

from tomo.protocols import ProtImportTomograms
from tomo.tests import DataSet

from ..protocols.protocol_picking_ref import ProtTomoTwinRefPicking


class TestTomoTwinRefPicking(BaseTest):
    @classmethod
    def setUpClass(cls):
        setupTestProject(cls)
        cls.dataset = DataSet.getDataSet("emd_10439")
        cls.tomo = cls.dataset.getFile('tomoEmd10439')
        cls.subtomos = cls.dataset.getFile('subtomograms/emd_10439-01*.mrc')

    def test_run(self):
        protImportTomo = self.newProtocol(ProtImportTomograms,
                                          filesPath=self.tomo,
                                          samplingRate=13.68)
        self.launchProtocol(protImportTomo)
        self.assertIsNotNone(protImportTomo.outputTomograms,
                             msg="There was a problem with tomogram import")

        protImportVols = self.newProtocol(ProtImportVolumes,
                                          filesPath=self.subtomos, samplingRate=13.68)
        self.launchProtocol(protImportVols)
        self.assertIsNotNone(protImportVols.outputVolumes,
                             "There was a problem with volumes import")

        protPicking = self.newProtocol(ProtTomoTwinRefPicking,
                                       inputTomos=protImportTomo.outputTomograms,
                                       inputRefs=protImportVols.outputVolumes,
                                       boxSize=37,
                                       batchTomos=128,
                                       batchRefs=12,
                                       zMin=200, zMax=210)
        self.launchProtocol(protPicking)
        outputCoords = protPicking.output3DCoordinates
        self.assertIsNotNone(outputCoords, "Tomotwin reference-based picking has failed")
        self.assertAlmostEqual(outputCoords.getSize(), 3192, delta=30)
        self.assertEqual(outputCoords.getBoxSize(), 37)
