# **************************************************************************
# *
# * Authors:     David Herreros Calero (dherreros@cnb.csic.es) [1]
# *              Grigory Sharov (gsharov@mrc-lmb.cam.ac.uk) [2]
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC [1]
# * MRC Laboratory of Molecular Biology (MRC-LMB) [2]
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 2 of the License, or
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
import os.path
import threading

from pyworkflow.gui.dialog import ToolbarListDialog, showError
from pyworkflow.gui.tree import TreeProvider
import pyworkflow.utils as pwutils

from tomotwin import Plugin


class Tomo3DTreeProvider(TreeProvider):
    """ Populate Tree from SetOfTomograms. """

    def __init__(self, tomoList):
        TreeProvider.__init__(self)
        self.tomoList = tomoList

    def getColumns(self):
        return [('Tomogram id', 300), ("# coords", 100)]

    def getObjectInfo(self, tomo):
        tomogramName = tomo.getTsId()

        return {'key': tomogramName, 'parent': None,
                'text': tomogramName,
                'values': (tomo.count),
                'tags': ("done")}

    def getObjectPreview(self, obj):
        return (None, None)

    def getObjectActions(self, obj):
        return []

    def _getObjectList(self):
        """Retrieve the object list"""
        return self.tomoList

    def getObjects(self):
        objList = self._getObjectList()
        return objList

    def configureTags(self, tree):
        tree.tag_configure("done", foreground="black")


class ViewerNapariDialog(ToolbarListDialog):
    """
    This class extends ListDialog to allow calling
    a Napari viewer subprocess from a list of Tomograms.
    """

    def __init__(self, parent, **kwargs):
        self.provider = kwargs.get("provider", None)
        self.prot = kwargs.get("protocol", None)

        msg = """Double click on a tomo to launch Napari viewer.
              If you change the coordinates, click File -> Save selected Layer(s) and save a new {tomo_id}.tloc file for each tomo in the same folder."""
        ToolbarListDialog.__init__(self, parent, "Tomogram List",
                                   itemDoubleClick=self.doubleClickOnTomogram,
                                   cancelButton=True, message=msg,
                                   allowSelect=False, **kwargs)

    def doubleClickOnTomogram(self, tomo=None):
        tomo_path = tomo.getFileName()
        self.prot._createFilenameTemplates()
        tloc_fn = self.prot._getFileName("output_tloc", tomoId=tomo.getTsId())
        if not os.path.exists(tloc_fn):
            showError("Error", f"File not found: {tloc_fn}", self)
        else:
            proc = threading.Thread(target=self.launchNapari,
                                    args=(tomo_path, tloc_fn,))
            proc.start()

    def launchNapari(self, tomoFn, tlocFn):
        program = f"{Plugin.getCondaActivationCmd()} conda activate napari && napari"
        args = f"{tomoFn} {tlocFn} -w napari-boxmanager"
        pwutils.runJob(None, program, args, env=Plugin.getEnviron())
