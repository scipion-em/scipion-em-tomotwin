# **************************************************************************
# *
# * Authors:     David Herreros Calero (dherreros@cnb.csic.es)
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
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
from multiprocessing import Process

import pyworkflow.viewer as pwviewer
from pyworkflow.gui.dialog import ToolbarListDialog
from pyworkflow.gui.tree import TreeProvider
from pyworkflow.gui.browser import FileBrowserWindow
import pyworkflow.utils as pwutils
from pwem.protocols import EMProtocol
from pwem.viewers.views import ObjectView

import tomo.objects

from tomotwin.protocols import ProtTomoTwinRefPicking
from tomotwin import Plugin


class Tomo3DTreeProvider(TreeProvider):
    """ Populate Tree from SetOfTomograms. """

    def __init__(self, tomoList):
        TreeProvider.__init__(self)
        self.tomoList = tomoList

    def getColumns(self):
        return [('Tomogram id', 300), ("# coords", 100)]

    def getObjectInfo(self, tomo):
        tomogramName = pwutils.removeBaseExt(tomo.getFileName())

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

    def __init__(self, parent, coords, **kwargs):
        self.coords = coords
        self.provider = kwargs.get("provider", None)
        msg = """Double click on a tomo to launch Napari viewer.
              If you change the coordinates, click File -> Save selected Layer(s) and save a new {tomo_id}.tloc file for each tomo in the same folder."""
        ToolbarListDialog.__init__(self, parent, "Tomogram List",
                                   itemDoubleClick=self.doubleClickOnTomogram,
                                   cancelButton=True, message=msg,
                                   allowSelect=False, **kwargs)

    def doubleClickOnTomogram(self, tomo=None):
        tomo_path = tomo.getFileName()
        tomo_id = tomo.getTsId()
        prot_path = os.path.dirname(self.coords.getFileName())
        proc = Process(target=self.launchNapari,
                       args=(tomo_path, tomo_id, prot_path))
        proc.start()

    def launchNapari(self, tomoFn, tomoId, protPath, **kwargs):
        program = f"{Plugin.getCondaActivationCmd()} conda activate napari && napari"
        args = f"{tomoFn} {protPath}/extra/{tomoId}/locate/located.tloc -w napari-boxmanager"
        pwutils.runJob(None, program, args, env=Plugin.getEnviron())


class NapariBoxManager(pwviewer.Viewer):
    """ Wrapper to visualize tomo coordinates using napari. """
    _environments = [pwviewer.DESKTOP_TKINTER]
    _targets = [
        tomo.objects.SetOfCoordinates3D,
        #ProtTomoTwinRefPicking
    ]

    def __init__(self, **kwargs):
        pwviewer.Viewer.__init__(self, **kwargs)
        self._views = []

    def _getObjView(self, obj, fn, viewParams={}):
        return ObjectView(
            self._project, obj.strId(), fn, viewParams=viewParams)

    def _visualize(self, obj, **kwargs):
        cls = type(obj)
        if issubclass(cls, tomo.objects.SetOfCoordinates3D):
            outputCoords = obj
        elif issubclass(cls, EMProtocol):
            outputCoords = obj.output3DCoordinates.get()

        tomos = outputCoords.getPrecedents()
        volIds = outputCoords.aggregate(["MAX", "COUNT"], "_volId", ["_volId"])
        volIds = [(d['_volId'], d["COUNT"]) for d in volIds]

        tomoList = []
        for objId in volIds:
            tomogram = tomos[objId[0]].clone()
            tomogram.count = objId[1]
            tomoList.append(tomogram)

        tomoProvider = Tomo3DTreeProvider(tomoList)
        ViewerNapariDialog(self._tkRoot, outputCoords, provider=tomoProvider)

        def _onSelect(self, fileInfo):
            """ Save updated coordinates. """
            print("SELECTED FOLDER:", fileInfo.getPath())
            return
            protocol = self.protocol
            suffix = protocol._getOutputSuffix(tomo.objects.SetOfCoordinates3D)
            updated_set = protocol._createSetOfCoordinates3D(tomos, suffix)
            updated_set.setName("Selected Coordinates")
            updated_set.setPrecedents(tomos)
            updated_set.setSamplingRate(tomos.getSamplingRate())
            updated_set.setBoxSize(outputCoords.getBoxSize())
            for item in tomoList:
                basename = pwutils.removeBaseExt(item.getFileName())
                indices_file = basename + '_indices.txt'
                if os.path.isfile(indices_file):
                    indices = np.loadtxt(indices_file, delimiter=' ')
                    for index in indices:
                        updated_set.append(outputCoords[index].clone())
                    pwutils.cleanPath(indices_file)
            name = protocol.OUTPUT_PREFIX + suffix
            args = {}
            args[name] = updated_set
            protocol._defineOutputs(**args)
            protocol._defineSourceRelation(tomos, updated_set)
            protocol._updateOutputSet(name, updated_set, state=updated_set.STREAM_CLOSED)

        browser = FileBrowserWindow("Select a folder with saved *.tloc files from Napari",
                                    master=self.formWindow,
                                    path=".",
                                    onSelect=_onSelect,
                                    onlyFolders=True)
        browser.show()
        return []
