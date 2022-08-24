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


def readSetOfCoordinates3D(coordsFn, coord3DSet, inputTomo, origin=BOTTOM_LEFT_CORNER,
                           scale=1, groupId=None):

    table = Table(filename=coordsFn, tableName="cryolo")
    for row in table:
        coord3DSet.enableAppend()
        newCoord = readCoordinate3D(row, inputTomo, origin=origin, scale=scale)
        if groupId is not None:
            newCoord.setGroupId(groupId)

        coord3DSet.append(newCoord)


def readCoordinate3D(row, inputTomo, origin=BOTTOM_LEFT_CORNER, scale=1):
    x, y, z = row.CoordinateX, row.CoordinateY, row.CoordinateZ
    coord = Coordinate3D()
    coord.setVolume(inputTomo)
    coord.scale(scale)
    coord.setPosition(x, y, z, origin)

    if not hasattr(coord, '_confidence'):
        coord._confidence = Float()

    coord._confidence.set(row.Confidence)

    return coord
