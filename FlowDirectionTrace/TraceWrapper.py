
#------------------------------------------------------------------------------
#----- TraceWrapper.py ----------------------------------------------------
#------------------------------------------------------------------------------

#-------1---------2---------3---------4---------5---------6---------7---------8
#       01234567890123456789012345678901234567890123456789012345678901234567890
#-------+---------+---------+---------+---------+---------+---------+---------+

# copyright:   2017 WiM - USGS

#    authors:  Jeremy K. Newson USGS Web Informatics and Mapping
# 
#   purpose:  Wrapper to delineate watershed using split catchement methods
#          
#discussion:  
#       

#region "Comments"
#09.20.2017 jkn - Created
#endregion

#region "Imports"
import traceback
import datetime
import time
import os
import argparse
import arcpy
from arcpy import env
from arcpy.sa import *
from WiMPy import WiMLogging
from WiMPy import Shared
from WiMPy import GeoJsonHandler
from WiMPy.MapLayer import *
from WiMPy.Config import Config
import json
import numpy as np
from FlowDirectionTrace import FlowDirectionTrace

#endregion

##-------1---------2---------3---------4---------5---------6---------7---------8
##       Main
##-------+---------+---------+---------+---------+---------+---------+---------+

#http://stackoverflow.com/questions/13653991/passing-quotes-in-process-start-arguments
class TraceWrapper(object):
    #region Constructor
    def __init__(self):
        try:
            mask = None
            spoint = None
            traceline = None

            parser = argparse.ArgumentParser()
            #For project ID
            parser.add_argument("-startpoint", help="specifies pourpoint geojson feature ", type=json.loads, 
                                default = '{"type":"Feature","geometry":{"type":"Point","coordinates":[-84.088548,39.79728106]}}')
            #Within this EPSG code
            parser.add_argument("-outsrid", help="specifies the spatial reference of pourpoint ", type=int, 
                                default = '4326')
            parser.add_argument("-maskjson", help="specifies the mask of the procedure", type=json.loads, 
                                default = '{"type":"FeatureCollection","totalFeatures":1,"features":[{"type":"Feature","id":"catchmentsp.703512","geometry":{"type":"MultiPolygon","coordinates":[[[[-84.08813991299998,39.79658515107204],[-84.08884139299994,39.79665208807208],[-84.08903151899995,39.79678090607203],[-84.08954422799998,39.797530772072065],[-84.09148228099998,39.79863164407205],[-84.09160042799994,39.79934385907207],[-84.08937138899995,39.79873698507204],[-84.08909568599995,39.79841976007204],[-84.08892698099999,39.79827928407203],[-84.08897117399994,39.79801366307205],[-84.08862042699997,39.79798019507202],[-84.08826967999994,39.79794672607206],[-84.08831378499998,39.79696223007207],[-84.08813991299998,39.79658515107204]]]]},"geometry_name":"the_geom","properties":{"ogc_fid":703512,"gridcode":198363,"featureid":3986396,"sourcefc":"NHDFlowline","areasqkm":0.035182,"shape_length":0.0101182230763888,"shape_area":3.69980109402137E-6}}],"crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::4326"}}}')
                           
            args = parser.parse_args()

            startTime = time.time()
            
            config = Config(json.load(open(os.path.join(os.path.dirname(__file__), 'config.json'))))  
            workingDir = Shared.GetWorkspaceDirectory(config["workingdirectory"],"fdrtrace") 
            
            WiMLogging.init(os.path.join(workingDir,"Temp"),"fldr.log")
            self._sm("Start routine")
            
            sr = arcpy.SpatialReference(args.outsrid)           
            spoint = arcpy.CreateFeatureclass_management("in_memory", "ppointFC", "POINT", spatial_reference=sr) 
            if (args.startpoint["type"].lower() =="feature"):
                GeoJsonHandler.read_feature(args.startpoint,spoint,sr)
            else:
                GeoJsonHandler.read_feature_collection(args.pourpoint,spoint,sr)  

            if(args.maskjson):
                mask = arcpy.CreateFeatureclass_management("in_memory", "maskFC", "POLYGON", spatial_reference=sr) 
                if (args.maskjson["type"].lower() =="feature"):
                    GeoJsonHandler.read_feature(args.maskjson, mask,sr)
                else:
                    GeoJsonHandler.read_feature_collection(args.maskjson,mask,sr)             
            
            with FlowDirectionTrace(workingDir) as fdrTrace:
                if (not fdrTrace.isInit): raise Exception('FlowDirectionTrace failed to initialize')
                traceline = fdrTrace.Trace(spoint, mask)
            #end with
            
            if(not traceline): raise Exception ("TraceFailed")

            resulttrace = traceline.projectAs(sr)


            self._sm('Finished.  Total time elapsed:'+ str(round((time.time()- startTime)/60, 2))+ 'minutes')

            Results = {
                       "trace": self.geometry_to_struct( resulttrace),
                       "Message": ';'.join(WiMLogging.LogMessages).replace('\n',' ')
                      }
        except:
             tb = traceback.format_exc()
             self._sm( "Error executing wrapper "+tb,"Error")
             Results = {
                       "error": {"message": ';'.join(WiMLogging.LogMessages).replace('\n',' ')}
                       }

        finally:
            print("Results="+json.dumps(Results))    
    
    def geometry_to_struct(self, in_geometry):
        if in_geometry is None:
            return None
        elif isinstance(in_geometry, arcpy.PointGeometry):
            pt = in_geometry.getPart(0)
            return {
                        'type': "Point",
                        'coordinates': (pt.X, pt.Y)
                   }
        elif isinstance(in_geometry, arcpy.Polyline):
            parts = [[(point.X, point.Y) for point in in_geometry.getPart(part)]
                     for part in xrange(in_geometry.partCount)]
            if len(parts) == 1:
                return {
                            'type': "LineString",
                            'coordinates': parts[0]
                       }
            else:
                return {
                            'type': "MultiLineString",
                            'coordinates': parts
                       }
        elif isinstance(in_geometry, arcpy.Polygon):
            parts = [list(part_split_at_nones(in_geometry.getPart(part)))
                     for part in xrange(in_geometry.partCount)]
            if len(parts) == 1:
                return {
                            'type': "Polygon",
                            'coordinates': parts[0]
                       }
            else:
                return {
                            'type': "MultiPolygon",
                            'coordinates': parts
                       }
        else:
            raise ValueError(in_geometry)
    def _sm(self,msg,type="INFO", errorID=0):        
        WiMLogging.sm(msg,type="INFO", errorID=0)

if __name__ == '__main__':
    TraceWrapper()

