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

from pyworkflow.gui.dialog import ToolbarListDialog, showError
from tomo.viewers.views_tkinter_tree import TomogramsTreeProvider


class TomoTreeProvider(TomogramsTreeProvider):
    def getObjectInfo(self, tomo):
        tomogramName = tomo.getTsId()

        return {'key': tomogramName, 'parent': None,
                'text': tomogramName,
                'values': (tomo.count, 'Done'),
                'tags': ("done")}


class ViewerNapariDialog(ToolbarListDialog):
    def __init__(self, parent, provider, protocol, **kwargs):
        self.provider = provider
        self.prot = protocol

        msg = """Double click on a tomo to launch Napari viewer.
              If you change the coordinates, click File -> Save selected Layer(s) and save {tomoId}.tloc file for every tomo in the same folder."""
        ToolbarListDialog.__init__(self, parent, "Tomogram List",
                                   self.provider, allowsEmptySelection=False,
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
        from tomotwin import Plugin, NAPARI_BOXMANAGER
        args = f"{tomoFn} {tlocFn}"
        Plugin.runNapariBoxManager(self.prot.getProject().getPath(), NAPARI_BOXMANAGER, args)
