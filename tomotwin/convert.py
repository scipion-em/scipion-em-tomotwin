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

from emtable import Table

from pyworkflow.object import Float
from tomo.objects import Coordinate3D
from tomo.constants import BOTTOM_LEFT_CORNER


def readSetOfCoordinates3D(coordsFn, coord3DSet, inputTomo,
                           origin=BOTTOM_LEFT_CORNER, scale=1, groupId=None):
    coord3DSet.enableAppend()
    coord = Coordinate3D()
    coord._confidence = Float()
    for row in Table.iterRows(fileName="cryolo@"+coordsFn):
        readCoordinate3D(coord, row, inputTomo, origin=origin,
                         scale=scale, groupId=groupId)
        coord3DSet.append(coord)


def readCoordinate3D(coord, row, inputTomo, origin=BOTTOM_LEFT_CORNER,
                     scale=1, groupId=None):
    x, y, z = row.CoordinateX, row.CoordinateY, row.CoordinateZ
    coord.setObjId(None)
    coord.setVolume(inputTomo)
    coord.setPosition(x, y, z, origin)
    coord.scale(scale)
    coord._confidence.set(row.Confidence)
    if groupId is not None:
        coord.setGroupId(groupId)
