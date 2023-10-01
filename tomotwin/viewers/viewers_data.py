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
import os.path
import threading

import pyworkflow.viewer as pwviewer
from pyworkflow.gui.browser import FileBrowserWindow
from pyworkflow.gui.dialog import askYesNo
from pyworkflow.utils.properties import Message
import pyworkflow.utils as pwutils
from pwem.viewers.views import ObjectView

from ..protocols import ProtTomoTwinRefPicking, ProtTomoTwinClusterPicking
from .views_tkinter_tree import TomoTreeProvider, ViewerNapariDialog


class NapariBoxManager(pwviewer.Viewer):
    """ Wrapper to visualize tomo coordinates using napari. """
    _environments = [pwviewer.DESKTOP_TKINTER]
    _targets = [ProtTomoTwinRefPicking, ProtTomoTwinClusterPicking]

    def __init__(self, **kwargs):
        pwviewer.Viewer.__init__(self, **kwargs)
        self._views = []

    def _getObjView(self, obj, fn, viewParams={}):
        return ObjectView(
            self._project, obj.strId(), fn, viewParams=viewParams)

    def _visualize(self, obj, **kwargs):
        outputCoords = obj.output3DCoordinates
        tomos = outputCoords.getPrecedents()
        volIds = outputCoords.aggregate(["COUNT"], "_volId", ["_volId"])
        volIds = [(d['_volId'], d["COUNT"]) for d in volIds]

        tomoList = []
        for objId in volIds:
            tomogram = tomos[objId[0]].clone()
            tomogram.count = objId[1]
            tomoList.append(tomogram)

        tomoProvider = TomoTreeProvider(tomoList, path=None, mode=None)
        ViewerNapariDialog(self._tkRoot, tomoProvider, self.protocol)

        import tkinter as tk
        frame = tk.Frame()
        if askYesNo(Message.TITLE_SAVE_OUTPUT, "Save modified output?", frame):
            def _onSelect(fileInfo):
                """ Convert and save updated coordinates. """
                if fileInfo is None:
                    return
                proc = threading.Thread(target=self._createTmpOutput,
                                        args=(fileInfo, tomoList))
                proc.start()

            browser = FileBrowserWindow("Select a FOLDER with saved *.tloc files from Napari",
                                        master=self.formWindow,
                                        path=self.protocol.getPath(),
                                        onSelect=_onSelect,
                                        selectionType=2,  # FOLDERS
                                        onlyFolders=False)
            browser.show()
        return []

    def _createTmpOutput(self, fileInfo, tomoList):
        from tomotwin import Plugin
        tlocPath = fileInfo.getPath()
        flag = False
        for tomo in tomoList:
            tomoId = tomo.getTsId()
            tlocFn = os.path.join(tlocPath, f"{tomoId}.tloc")
            if os.path.exists(tlocFn):
                tmpDir = self._getTmpPath(tomoId)
                pwutils.cleanPath(tmpDir)
                pwutils.makePath(tmpDir)
                program = Plugin.getProgram("tomotwin_pick.py", gpus=False)
                args = f"-l {os.path.abspath(tlocFn)} -o Tmp/{tomoId}"
                pwutils.runJob(None, program, args, env=Plugin.getEnviron())
                flag = True
            else:
                print(f"Could not find {tlocFn}, skipping...")

        if flag:
            self.protocol.createOutputStep(fromViewer=True)
