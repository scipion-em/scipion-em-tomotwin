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


def getTomoTwinEnvName(version):
    return "tomotwin-%s" % version


VERSIONS = ['0.1.2', '0.2.1.6']
TOMOTWIN_DEFAULT_VER_NUM = VERSIONS[-1]

DEFAULT_ENV_NAME = getTomoTwinEnvName(TOMOTWIN_DEFAULT_VER_NUM)
DEFAULT_ACTIVATION_CMD = 'conda activate ' + DEFAULT_ENV_NAME
TOMOTWIN_ENV_ACTIVATION = 'TOMOTWIN_ENV_ACTIVATION'
NAPARI_ENV_ACTIVATION = 'NAPARI_ENV_ACTIVATION'

TOMOTWIN_MODEL = 'TOMOTWIN_MODEL'
DEFAULT_MODEL = 'tomotwin_model_p120_052022_loss.pth'
