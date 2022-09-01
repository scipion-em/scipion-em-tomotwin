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

from pwem.wizards.wizard import EmWizard

from .protocols import ProtTomoTwinRefPicking


class TomoTwinPickingWizard(EmWizard):
    _targets = [(ProtTomoTwinRefPicking, ['boxSize'])]

    def show(self, form, *params):
        prot = form.protocol
        inputRefs = prot.inputRefs.get()

        if not inputRefs:
            print('You must specify input references')
            return

        size = inputRefs.getXDim()
        form.setVar('boxSize', size)
