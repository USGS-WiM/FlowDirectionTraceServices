#------------------------------------------------------------------------------
#----- FlowDirectionTrace.py --------------------------------------------------
#------------------------------------------------------------------------------
#
#  copyright:  2017 WiM - USGS
#
#    authors:  Jeremy K. Newson - USGS Web Informatics and Mapping (WiM)
#              
#    purpose:  traverses FDR grid.
#
#      usage:  THIS SECTION NEEDS TO BE UPDATED
#
# discussion:  use flow direction to find any neighbor cell flowing 
#              to the current cell then record col,row of cell
#
#              using recorded row,col get Flow direction pixel value between
#              neighbor cell and current cell
#
#              neighborhood   _NNRowArray(n) _NNColArray(n) _LengthArray(n)     flow
#               numbering       offsets         offsets        x cell size    direction
#            
#             | 6 | 7 | 8 |   |-1 |-1 |-1 |  |-1 | 0 | 1 |  |1.4| 0 |1.4|   | 32| 64|128|
#             | 5 | x | 1 |   | 0 | x | 0 |  |-1 | x | 1 |  | 1 | x | 1 |   | 16| x | 1 |
#             | 4 | 3 | 2 |   | 1 | 1 | 1 |  |-1 | 0 | 1 |  |1.4| 0 |1.4|   | 8 | 4 | 2 |
#
#   https://community.esri.com/docs/DOC-2954
#
#      dates:   29 SEPT 2017 jkn - Created
#
#------------------------------------------------------------------------------
import traceback
import os
import arcpy
from arcpy import env
import json
from WiMPy.SpatialOps import SpatialOps
from WiMPy.MapLayer import *
from WiMPy.Config import Config

class FlowDirectionTrace(SpatialOps):
    #region Constructor and Dispose
    def __init__(self, workspacePath):     
        SpatialOps.__init__(self, workspacePath)
        arcpy.ResetEnvironments()   
        self._initialize()        
        self._sm("initialized flow trace")
        arcpy.AddMessage("init flow trace")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        SpatialOps.__exit__(self, exc_type, exc_value, traceback) 
    #endregion   

    #region Methods
    def Trace(self, startpoint, inmask):
        temp = None
        array = arcpy.Array()
        try:
            fdr = MapLayer(MapLayerDef("fdr"), "", startpoint)
            if not fdr.Activated:
                raise Exception("Flow direction could not be activated.")
            
            cellsize = self._getRasterCellSize(fdr.Dataset)
            sr = fdr.spatialreference
          
            point = self.ProjectFeature(startpoint, sr)
            mask = self.ProjectFeature(inmask,sr)

            maskGeom = self._getFirstFeature(mask)

            maskExtent = self._getExtent(mask) if mask else self._getExtent(fdr.Dataset)
            rasterExtent = self._setRasterExtent(maskExtent,fdr.Dataset, cellsize)

            fdrArray = self._createNumpyArray(fdr.Dataset, rasterExtent, cellsize)  
            location = self._getFirstFeature(point)[0]
            featList = []
            while (location):
                if(maskGeom.contains(location)):
                    array.add(location)
                row,col = self._getRowColOfPoint(rasterExtent, location,cellsize) 
                try:
                    if(row < 0 or col < 0): raise Exception("")
                    pixVal = fdrArray.item(row,col) 
                except:
                    location = None
                    break
                location = self._nextPoint(pixVal,location,cellsize)
            #next point

            polyline = arcpy.Polyline(array,sr)
            array.removeAll()

            return polyline

        except:
            tb = traceback.format_exc()
            self._sm("Trace Error "+tb, "ERROR")
        finally:
            #local cleanup
            temp = None

    #endregion
    #region Helper Methods
    def _fdRowCol(self, fd, row,col):
        return row + self._NNRow[fd],col+self._NNCol[fd]
    
    def _nextPoint(self, fd, point, cellsize):
        try:
            #Shift row/col directions 
            newpoint = arcpy.Point()
            if(fd == 0): 
                self._sm("Flow direction cell = 0, possible sink hole.")
                return None
            newpoint.X = point.X + self._NNCol[fd]*cellsize
            newpoint.Y = point.Y - self._NNRow[fd]* cellsize
            print (newpoint.X, newpoint.Y)
            return newpoint
        except :
            return None      
 
        
    def _getRowColOfPoint(self, ext, pnt, cellsize): 
        col = int(((pnt.X - ext.XMin) - ((pnt.X - ext.XMin) % cellsize)) / cellsize)  
        row = int(((ext.YMax - pnt.Y) - ((ext.YMax - pnt.Y) % cellsize)) / cellsize)  
        return row, col  

    def _getRasterCellSize(self, raster):  
        desc = arcpy.Describe(raster)  
        return (desc.meanCellHeight + desc.meanCellWidth) / 2

    def _getExtent(self, dataset):
        return arcpy.Describe(dataset).extent

    def _setRasterExtent(self, ext, raster, cellsize):
        ras_ext = arcpy.Describe(raster).extent  
        xmin = ext.XMin - ((ext.XMin - ras_ext.XMin) % cellsize)  
        ymin = ext.YMin - ((ext.YMin - ras_ext.YMin) % cellsize)  
        xmax = ext.XMax + ((ras_ext.XMax - ext.XMax) % cellsize)  
        ymax = ext.YMax + ((ras_ext.YMax - ext.YMax) % cellsize)  
        return arcpy.Extent(xmin, ymin, xmax, ymax) 

    def _createNumpyArray(self, raster, extent, cellsize):  
        lowerLeft = arcpy.Point(extent.XMin, extent.YMin)  
        ncols = int(extent.width / cellsize)  
        nrows = int(extent.height / cellsize)  
        return arcpy.RasterToNumPyArray(raster, lowerLeft, ncols, nrows, nodata_to_value=9999)
    
    def _getFirstFeature(self, fc):  
        geom = arcpy.da.SearchCursor(fc, ("SHAPE@",)).next()[0]
        return geom
    
    def _initialize(self):
        try:
        #  neighborhood   _NNRowArray(n)    _NNColArray(n)      flow
        #   numbering       offsets             offsets       direction
        #
        # | 6 | 7 | 8 |   |-1 |-1 |-1 |     |-1 | 0 | 1 |    | 32| 64|128|
        # | 5 | x | 1 |   | 0 | x | 0 |     |-1 | x | 1 |    | 16| x | 1 |
        # | 4 | 3 | 2 |   | 1 | 1 | 1 |     |-1 | 0 | 1 |    | 8 | 4 | 2 |
            #self._NNRowArray =[0,0,1,1,1,0,-1,-1,-1]            
            #self._NNColArray =[0,1,1,0,-1,-1,-1,0,1]

            self._NNRow ={
                    0:0,
                    1:0,
                    2:1,
                    4:1,
                    8:1,
                    16:0,
                    32:-1,
                    64:-1,
                    128:-1
                }
            self._NNCol ={
                    0:0,
                    1:1,
                    2:1,
                    4:0,
                    8:-1,
                    16:-1,
                    32:-1,
                    64:0,
                    128:1
                }

            self.isInit = True

        except:    
            self.isInit = True

   
    #endregion
