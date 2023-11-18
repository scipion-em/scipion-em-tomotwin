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
from pyworkflow.utils import magentaStr
from pwem.protocols import ProtImportVolumes

from tomo.protocols import ProtImportTomograms
from tomo.tests import DataSet

from ..protocols import (ProtTomoTwinCreateMasks, ProtTomoTwinRefPicking,
                         ProtTomoTwinClusterCreateUmaps)


class TestTomoTwinBase(BaseTest):
    @classmethod
    def setUpClass(cls):
        setupTestProject(cls)
        cls.dataset = DataSet.getDataSet("emd_10439")
        cls.tomo = cls.dataset.getFile('tomoEmd10439')
        cls.subtomos = cls.dataset.getFile('subtomograms/emd_10439-01*.mrc')

    def runImportTomos(self):
        print(magentaStr("\n==> Importing data - tomograms:"))
        protImportTomo = self.newProtocol(ProtImportTomograms,
                                          filesPath=self.tomo,
                                          samplingRate=10)
        self.launchProtocol(protImportTomo)
        self.assertIsNotNone(protImportTomo.Tomograms,
                             msg="There was a problem with tomogram import")

        return protImportTomo

    def runImportVolumes(self):
        print(magentaStr("\n==> Importing data - volumes:"))
        protImportVols = self.newProtocol(ProtImportVolumes,
                                          filesPath=self.subtomos, samplingRate=10)
        self.launchProtocol(protImportVols)
        self.assertIsNotNone(protImportVols.outputVolumes,
                             "There was a problem with volumes import")

        return protImportVols


class TestTomoTwinRefBased(TestTomoTwinBase):
    def test_run(self):
        protImportTomo = self.runImportTomos()
        protImportVols = self.runImportVolumes()

        print(magentaStr("\n==> Testing tomotwin - create tomo masks:"))
        protCreateMasks = self.newProtocol(ProtTomoTwinCreateMasks,
                                           inputTomos=protImportTomo.Tomograms)
        self.launchProtocol(protCreateMasks)
        self.assertIsNotNone(protCreateMasks.outputMasks,
                             "Tomo mask creation has failed")

        print(magentaStr("\n==> Testing tomotwin - reference-based picking:"))
        protPicking = self.newProtocol(ProtTomoTwinRefPicking,
                                       inputTomos=protImportTomo.Tomograms,
                                       inputRefs=protImportVols.outputVolumes,
                                       inputMasks=protCreateMasks.outputMasks,
                                       batchTomos=128,
                                       batchRefs=12,
                                       boxSize=44,
                                       zMin=200, zMax=204)
        self.launchProtocol(protPicking)
        outputCoords = protPicking.output3DCoordinates
        self.assertIsNotNone(outputCoords, "Tomotwin reference-based picking has failed")
        self.assertAlmostEqual(outputCoords.getSize(), 2250, delta=100)
        self.assertEqual(outputCoords.getBoxSize(), 44)


class TestTomoTwinClusterBased(TestTomoTwinBase):
    def test_run(self):
        protImportTomo = self.runImportTomos()

        print(magentaStr("\n==> Testing tomotwin - clustering-based picking (step 1):"))
        protPicking = self.newProtocol(ProtTomoTwinClusterCreateUmaps,
                                       inputTomos=protImportTomo.Tomograms,
                                       batchTomos=128,
                                       zMin=200, zMax=204)
        self.launchProtocol(protPicking)
        self.assertTrue(protPicking.isFinished(),
                        "Tomotwin cluster-based embedding has failed")
