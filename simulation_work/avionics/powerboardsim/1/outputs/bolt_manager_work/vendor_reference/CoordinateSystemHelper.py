"""
Notes:
Helpful routines for coordinate systems and manipulations.

Example:
import CoordinateSystemHelper; reload(CoordinateSystemHelper)
CoordinateSystemHelper.Initialize(ExtAPI,Ansys)

"""

#Imports Globals and Initialize
#region
ExtAPI = None; Ansys = None

from module_base import *

import Vectors              #Custom vector helper.
import TreeOrganizerHelper
import GeoConnectivityHelper
import GeneralUtilities.SelectionInfoHelper
from GeneralUtilities.SelectionInfoHelper import GeomSelInfo
from GeneralUtilities.QuantityHelper import IsZero
from GeneralUtilities.UnitsHelper import ConvertQuantityToActiveUnit
import StringMatcher
import GeoDataHelper
from GeoDataHelper import GetBodyFromEntity
import BoltGeometryRecognition

#Globals taken from Mechanical session

#Custom globals
AxisDict={}
AxisDict[0] = CoordinateSystemAxisType.PositiveXAxis
AxisDict[1] = CoordinateSystemAxisType.PositiveYAxis
AxisDict[2] = CoordinateSystemAxisType.PositiveZAxis

Cartesian=CoordinateSystemTypeEnum.Cartesian
Cylindrical=CoordinateSystemTypeEnum.Cylindrical

CsTypeList = ["Cartesian","Cylindrical","Cylindrical And Cartesian"]
CsTypeDict={}
CsTypeDict["Cartesian"]=[Cartesian]
CsTypeDict["Cylindrical"]=[Cylindrical]
CsTypeDict["Cylindrical And Cartesian"]=[Cylindrical, Cartesian]

CsObjType=Ansys.ACT.Automation.Mechanical.CoordinateSystem


def Initialize(MyExtAPI, MyAnsys):
    """
    Call this each time you import this module to pass variables for ExtAPI, Ansys and any others needed.
    """

    #Set global values for module
    global ExtAPI; global Ansys
    ExtAPI = MyExtAPI; Ansys = MyAnsys

    TreeOrganizerHelper.Initialize(ExtAPI,Ansys)
    Vectors.Initialize(ExtAPI,Ansys)
    GeoConnectivityHelper.Initialize(ExtAPI, Ansys)
    GeoDataHelper.Initialize(ExtAPI, Ansys)
    GeneralUtilities.SelectionInfoHelper.Initialize(ExtAPI, Ansys)
    BoltGeometryRecognition.Initialize(ExtAPI, Ansys)
#endregion

class CoordinateSystemCreator():
    def __init__(self):
        self.Entities=[]

        self.Group=True

        self.CsType="Cartesian"

        self.Name="<BodyName> <TypeName>"
        self.GroupName="<BaseName>"

        self.ConsiderConnectivity=False  #Options to create based on connected Zones

        self.IterateNames=False
        self.Activate=False

        self.RestoreGraphicsSelection=False

        self.CreatedObjects = CreatedObjects()

    def CreateCoordinateSystems(self):
        """
        """
        #Figure out the location lists to use
        IsZones=False
        if self.ConsiderConnectivity:
            Map = GeoConnectivityHelper.GetEntityMap(self.Entities)
            if Map!=None:
                Zones=Map.GetZones()
                EntLists = [GeoConnectivityHelper.GetZoneEntities(Zone) for Zone in Zones]
                IsZones=True
        if not IsZones:  #Do it individually
            EntLists=[[Ent] for Ent in self.Entities]
        CsTypes=CsTypeDict[self.CsType]
        CurrentSel=ExtAPI.SelectionManager.CurrentSelection
        ExtAPI.SelectionManager.ClearSelection()  #Do this for a clean start.
        for EntList in EntLists:
            for CsType in CsTypes:
                ##Make associative for Origin and assign it.
                SelInfo = GeomSelInfo(Entities=EntList)
                CS=ExtAPI.DataModel.Project.Model.CoordinateSystems.AddCoordinateSystem()
                CS.CoordinateSystemType=CsType
                CS.OriginLocation=SelInfo
                CS.PrimaryAxisDefineBy=CoordinateSystemAlignmentType.Associative
                CS.PrimaryAxis=CoordinateSystemAxisType.PositiveZAxis
                CS.PrimaryAxisLocation=SelInfo
                CS.APDLName="CS_"+str(CS.ObjectId)
                self.CreatedObjects.CoordinateSystems.append(CS)
                self.CreatedObjects.SysByEntDict[EntList[0].Id]=CS
        self.DoNaming()
        self.DoGrouping()
        #Clean up.
        if self.RestoreGraphicsSelection:
            ExtAPI.SelectionManager.NewSelection(CurrentSel)
        if self.Activate:
            TreeOrganizerHelper.ActivateObjects(self.CreatedObjects.CoordinateSystems)

    def DoGrouping(self):
        if not (self.Group): return
        Folder = TreeOrganizerHelper.GroupObjects(self.CreatedObjects.CoordinateSystems,ReturnId=False)
        if Folder==None:
            return
        Name = self.GroupName
        Flag="<BaseName>"
        if Flag in Name:
            BaseName = StringMatcher.LongestCommonStrInList([Obj.Name for Obj in self.CreatedObjects.CoordinateSystems])
            Name = Name.replace(Flag, BaseName)
        Folder.Name = Name
        self.CreatedObjects.GroupingDone=True

    def DoNaming(self):
        i=1
        for CS in self.CreatedObjects.CoordinateSystems:
            Name = self.Name
            Flag="<BodyName>"
            if Flag in Name:
                FirstEnt = CS.OriginLocation.Entities[0]
                Name = Name.replace(Flag, GetBodyFromEntity(FirstEnt)[0].Name)
            Flag = "<TypeName>"
            if Flag in Name:
                Name = Name.replace(Flag, str(CS.CoordinateSystemType))
            if self.IterateNames:
                Name+=" "+str(i)
            CS.Name = Name
            i+=1
class CreatedObjects():
    def __init__(self):
        self.CoordinateSystems=[]
        self.SysByEntDict={}

        self.GroupingDone=False #Track if grouping is done correctly.

def CreateBoltCoordinateSystem(Entities=None, SystemCreator=None):
    """
    Creates a coordinate system for a bolt that is cylindrical and at the bottom face (by thread)
        This can be used to reference other measurements and do named selections.
    Args:
        Entities (list of GeoEntity): Entities to work with.
            Will be converted to list of bodies.
        SystemCreator (CoordinateSystemCreator): See class documentation for details.
    Returns:
        Dict: key = BodyId, Value = CS Obj
    """
    #Get a list of the bodies from entities.
    if Entities==None:
        Entities=ExtAPI.SelectionManager.CurrentSelection.Entities
    Bodies = GeoDataHelper.ConvertEntitySelectionToBodies(Entities,SharedTopology=False)
    Faces = [BoltGeometryRecognition.GetMaxMinFaces(B)[0] for B in Bodies]
    #use the creator to create the systems.
    if SystemCreator==None:
        Creator = CoordinateSystemCreator()
    else:
        Creator = SystemCreator

    Creator.Entities=Faces
    Creator.CsType="Cylindrical"
    Creator.CreateCoordinateSystems()

    CSs = Creator.CreatedObjects.SysByEntDict

    BoltBodyCsDict = {}
    for CS in CSs.values():
        OriginId=ExtAPI.DataModel.GeoData.GeoEntityById(CS.OriginLocation.Ids[0])
        Body = GeoDataHelper.GetBodyFromEntity(OriginId)[0]
        CS.Name = "Bolt Sys: "+Body.Name
        BoltBodyCsDict[Body.Id]=CS
        #Flip the Z axis if they are 180 degrees apart.
        Axis = BoltGeometryRecognition.GetBodyAxis(Body,AsUnit=True)
        Dot = Vectors.DotProduct([CS.ZAxis, Axis])
        if Dot < 0:
            FlipAxis([CS], [2], False)
    return BoltBodyCsDict
def GetBoltCoordianteSystems(Entities=None):
    #Get a list of the bodies from entities.
    if Entities==None:
        Entities=ExtAPI.SelectionManager.CurrentSelection.Entities
    Bodies = GeoDataHelper.ConvertEntitySelectionToBodies(Entities,SharedTopology=False)
    Faces = {B.Id:BoltGeometryRecognition.GetMaxMinFaces(B)[0] for B in Bodies}
    CSs=_GetPotentialBoltCSs()
    OutDict={}
    for B in Bodies:
        MinFace = Faces[B.Id]
        if CSs.has_key(MinFace.Id):
            CS=CSs[MinFace.Id]
            #Check Z orientation to the bolt axis.
            Axis = BoltGeometryRecognition.GetBodyAxis(B,AsUnit=True)
            Dot = Vectors.DotProduct([CS.ZAxis, Axis])
            if Dot>0:
                OutDict[B.Id]=CS
    return OutDict

def CreateCoordinateSystemsForEntities(Entities=None, Activate=True):
    """
    Quick function to create CS for entities.
    """
    #Initial args interpretation
    if Entities==None:
        Entities = ExtAPI.SelectionManager.CurrentSelection.Entities
    if Entities==None: return
    if len(Entities)<1:return
    #Do the creation
    Creator = CoordinateSystemCreator()
    Creator.Entities=Entities
    with Transaction():
        Creator.CreateCoordinateSystems()
    if Creator.Group and not Creator.CreatedObjects.GroupingDone:
        Creator.DoGrouping()
    CSs=Creator.CreatedObjects.CoordinateSystems
    if Activate:
        TreeOrganizerHelper.ActivateObjects(CSs)
    return CSs

def IsBoltSys(CS):
    """
    Check to see if a CS is a potential bolt CS with the proper conventions.
    """
    if CS.Suppressed: return False
    if CS.CoordinateSystemType!=CoordinateSystemTypeEnum.Cylindrical: return False
    if CS.OriginLocation==None: return False
    if len(CS.OriginLocation.Ids)!=1:return False
    if CS.PrimaryAxisDefineBy!=CoordinateSystemAlignmentType.Associative: return False
    if CS.PrimaryAxis!=CoordinateSystemAxisType.PositiveZAxis: return False
    for i in range(CS.TransformationCount):
        if CS.GetTransformationValue(1)!=6:return False
    return True
def _GetPotentialBoltCSs():
    CSs=GetAllCs()
    CSs=filter(lambda CS:IsBoltSys(CS), CSs)
    CSs={CS.OriginLocation.Ids[0]:CS for CS in CSs}
    return CSs

def FlipAxis(CoordinateSystems, AxisIndex, RedrawGraphics=True):
    """
    Add transformations to CS list to flip an axis.
    CoordinateSystems (list of CoordinateSystem)
    AxisIndex (list of integer 0-2), Based on the global AxisDict
    """
    if CoordinateSystems==None:
        CoordinateSystems=GetActiveCs()
    for CS in CoordinateSystems:
        for i in AxisIndex:
            try:
                CS.AddTransformation(TransformationType.Flip,AxisDict[i])
            except Exception as e:
                pass
    if RedrawGraphics: ExtAPI.Graphics.Redraw()

def MoveCoordinateSystems(CSs=None, Offsets=[0,0,0], RedrawGraphics=True):
    """
    Move a CS based on adding transformations to it.
    Args:
        Objects (list of Objects): Objects for moving CS
            If None->Active Objects in the tree
        Offset (list of float or Quantity): Offset [X,Y,Z].  0 for no offset.
    """
    if CSs==None: CSs=GetActiveCs()
    for CS in CSs:
        for i in range(3):
            Val = Offsets[i]
            if not IsZero(Val):
                if isinstance(Val, Quantity):
                    ConvQuant = ConvertQuantityToActiveUnit(Val, ExtAPI)
                    Val = ConvQuant.Value
                CS.AddTransformation(TransformationType.Offset,AxisDict[i])
                CS.SetTransformationValue(CS.TransformationCount,Val)
    if RedrawGraphics: ExtAPI.Graphics.Redraw()

def GetClosestCoordinateSystem(Point, CsList=None, MaxDist=None):
    """
    Gets the closest CS to a point [x,y,z]
    Args:
        Point (list of float): [x,y,z] list of point
        CsList (list of CoordinateSystem objects): List of CS that you want to search through.
    """
    #Get the list of CS: if None set to all in model.
    if CsList==None:
        ObjType = DataModelObjectCategory.CoordinateSystem
        CsList = ExtAPI.DataModel.GetObjectsByType(ObjType)

    #Determine the closest system
    ActiveLengUnit = ExtAPI.DataModel.CurrentUnitFromQuantityName("Length")
    CADUnits = ExtAPI.DataModel.GeoData.Unit
    MinDist = 1E15; MyCs = None
    for CS in CsList:
        Origin = [Ansys.Core.Units.UnitsManager.ConvertUnit(Val,ActiveLengUnit,CADUnits) for Val in CS.Origin]
        Vect=Vectors.VectorFromPoints([Point,Origin])
        Mag = Vectors.Magnitude(Vect)
        if Mag<MinDist: 
            MinDist=Mag
            MyCs = CS
    if MaxDist!=None:
        if MinDist > MaxDist: MyCs=None
    return MyCs

def GetGeomAssociativeCoordinateSytems(GeoIds,CsList=None):
    """
    Return a list of CS with origin associativity to the given GeoIds.
    Returned CS are for ANY match with the given GeoId list
    Args:
        GeoId (list of int): list of integers for GeoIds to check against
        CsList (list of CS): list of CS to check.  If None: all in model.
    """
    #Get the list of CS: if None set to all in model.
    if CsList==None:
        CsList = list(GetAllCs())
    AttachedSystems=[]
    for CS in CsList:
        try:
            if CS.OriginLocation!=None:
                if len(set(CS.OriginLocation.Ids) & set(GeoIds)) > 0:
                    AttachedSystems.append(CS)
        except Exception as e:
            pass
    return AttachedSystems

def GetAllClosestCoordinateSystems(Entities=None, CsSearchRange = None, Activate=False):
    if CsSearchRange==None: CsSearchRange = ExtAPI.DataModel.Tree.ActiveObjects
    if Entities==None: Entities = ExtAPI.SelectionManager.CurrentSelection.Entities
    CsList=[]
    for Entity in Entities:
        CS = GetClosestCoordinateSystem(Entity.Centroid,CsSearchRange)
        if CS!=None:
            CsList.append(CS)
    CsList = [ExtAPI.DataModel.GetObjectById(Id) for Id in list(set([Obj.ObjectId for Obj in CsList]))]
    if Activate:
        TreeOrganizerHelper.ActivateObjects(CsList)
    return CsList

def GetCsGeomRefs(CsList):
    """
    Gets all the GeoIds of the system's reference geometry.
    """
    Ids = set()
    for CS in ValidateIsCs(CsList):
        try:Ids.update(CS.OriginLocation.Ids)
        except:pass
        try:Ids.update(CS.PrimaryAxisLocation.Ids)
        except:pass
        try:Ids.update(CS.SecondaryAxisLocation.Ids)
        except:pass
    return list(Ids)

def ValidateIsCs(Objs):
    """
    Filter a list of objects so they are only CS types
    """
    return filter(lambda Obj: Obj.GetType()==CsObjType, Objs)

def VectorFromAxis(Axis):
    return Ansys.ACT.Math.Vector3D(Axis[0],Axis[1],Axis[2])

def GetAllCs():
    return ExtAPI.DataModel.GetObjectsByType(DataModelObjectCategory.CoordinateSystem)

def GetActiveCs():
    return ValidateIsCs(ExtAPI.DataModel.Tree.ActiveObjects)

def SetCameraFromCsAxis(Axis):
    """
    Set the camera graphics to the orientation of the given CS axis
    """
    ExtAPI.Graphics.Camera.ViewVector = VectorFromAxis(Axis)