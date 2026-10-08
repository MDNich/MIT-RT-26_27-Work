"""

"""
#Globals and import
#region

#This is required to get Ansys.Core into the binary extension
import clr
clr.AddReference("Ans.Core")

import TreeOrganizerHelper
TreeOrganizerHelper.Initialize(ExtAPI,Ansys)
import GeneralUtilities.SelectionInfoHelper
GeneralUtilities.SelectionInfoHelper.Initialize(ExtAPI, Ansys)
from GeneralUtilities.SelectionInfoHelper import GeomSelInfo, GetCurrentSelection, SetSelection

#Global Objects
GeoModel = None             #Internal GeoModel created automatically from Geometry
GeoEntityDict = None        #Dictionary for GeoEntities for InstanceFinder Module.
TreeGroupsGeoModel = None   #GeoModel created based on user-editable "Groups" from Instance Manager.

InternalLog = ""            #Used to store information internally and can be printed at user request.
SelectFromTreeGroups=False        #Flag for selecting geom accross instance groups from internal GeoModel or Groups obj in tree

MyGroupManager=None         #Group manager is an object in the tree that holds groups at the model level.  Only 1 allowed per model
MyGroups = {}               #Dictionary of all the ACT Group Objects in the tree.

MyTreeObjManager = None     #Object in the tree at the model level.  Only 1 allowed per model

#Part Library Globals
StandardPartLibrary = None  #Global for a part library of fasteners.
PartLibraryWindow=None      #Display for Part Library manager.
PartLibraryFolderPaths = []

#Used for a database of bolts that are applied via APDL.
import ApdlBoltModule
from ApdlBoltModule import ApdlBolt     #import the class so it is available to bind to the ACT object as controller.
from ApdlBoltModule import ApdlBoltManager     #import the class so it is available to bind to the ACT object as controller.
from ApdlBoltModule import ApplyUserApdlCommands
from ApdlBoltModule import ApdlBolt_GetCommands_Pre
from ApdlBoltModule import ApdlBolt_GetCommands_Solve
from ApdlBoltModule import ApdlBolt_GetCommands_Post

#These are needed to attach to the wizard panel for a bug per 2019R3
#These must be set prior to opening a wizard or object generator to attach correctly.
WizardPanelEnum=None;  WizardPane = None
#endregion

import os
from os.path import *

AppDataDir = os.environ["appdata"]
AppDataPath=join(AppDataDir, ExtAPI.ExtensionManager.CurrentExtension.Name)
def SetupAppDataDir():
    """
    Setup the appdata directory for the app.
    """
    try:
        def MakeDir(Path):
            if not exists(Path):
                os.mkdir(Path)
                ExtAPI.Log.WriteMessage("Created Dir: "+Path)
            InitPath = join(Path,"__init__.py")
            if not exists(InitPath):
                file=open(InitPath,'w');file.close()
        #Make the appdata directory for the app
        LibraryDataPath = join(AppDataPath,"AD_PartLibraryData")
        #Make the directory structure and starting files.
        MakeDir(AppDataPath)
        MakeDir(LibraryDataPath)
        MakeDir(join(LibraryDataPath,"MatchingCriteria"))
        MakeDir(join(LibraryDataPath,"PartScripts"))
        MakeDir(join(LibraryDataPath,"CustomParts"))
    except Exception as e:
        ExtAPI.Log.WriteMessage(e.message)
        return False
    return AppDataPath

#Mechanical Interface Callbacks
#region 
def MechanicalInit(Context):
    global WizardPanelEnum
    WizardPanelEnum=MechanicalPanelEnum.Wizard
    global  WizardPane; WizardPane  = ExtAPI.UserInterface.GetPane(WizardPanelEnum)

    ApdlBoltModule.Initialize(ExtAPI,Ansys)

    AppDataPath = SetupAppDataDir()
    import sys
    if AppDataPath!=False:
        if not AppDataPath in sys.path: sys.path.append(AppDataPath)

def MechanicalBeforeSolve(Analysis):
    ApdlBoltModule.StartApdlInputFileWrite(Analysis)

def MechanicalOnAfterGeometryUpdate():
    """
    Run this after the geometry is updated
    """
    #Clear out these entities to be rebuilt after geometry refresh.
    global GeoModel; global GeoEntityDict
    GeoModel = None             #Internal GeoModel created automatically from Geometry
    GeoEntityDict = None        #Dictionary for GeoEntities for InstanceFinder Module.

    try:
        import ConeOfCompressionImprintGUI; ConeOfCompressionImprintGUI.Initialize(ExtAPI,Ansys)
        ConeOfCompressionImprintGUI.OnAfterGeometryUpdate()
    except Exception as e:
        pass
#endregion

#Mechanical Buttons
#region
#Selection Helpers
    #region 
def SelectInstancesFromSelection(Analysis):
    try: GetGeoModel().SelectInstanceGroupFromSelection()
    except:pass

def SelectInstancePatternFromSelection(Analysis):
    """
    Select bodies that are in the same pattern as the current selection
    """
    try:
        import InstanceFinder
        InstanceFinder.Initialize(ExtAPI,Ansys)
        GeoModel=GetGeoModel()
        IG = GeoModel.SelectInstanceGroupFromSelection(Select=False)
        BodyIds = IG.GetMyBodyIds()
        CurrentSelBodies = [InstanceFinder.GetBodyFromEntity(Ent)[0] for Ent in ExtAPI.SelectionManager.CurrentSelection.Entities]
        CurrentSelBodyIds = [Body.Id for Body in CurrentSelBodies]
        GroupPatterns = InstanceFinder.DetectPatterns(BodyIds)
        SelectionIds = []
        for GroupPattern in GroupPatterns:
            CheckList = list(set(GroupPattern) & set(CurrentSelBodyIds))
            if len(CheckList)>0:
                SelectionIds.extend(GroupPattern)
        SelInfo = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
        SelInfo.Ids = list(set(SelectionIds))
        ExtAPI.SelectionManager.NewSelection(SelInfo)
    except Exception as e:
        pass

def SelectBodiesFromGroups(Analysis=None):
    """
    Select all the bodies in the graphics from the active groups in the tree.
    """
    GroupIds = [G.Controller.GetMechanicalObj().ObjectId for G in MyGroups.values()]
    ActiveIds = [Obj.ObjectId for Obj in ExtAPI.DataModel.Tree.ActiveObjects]
    ActiveGroupIds = list(set(GroupIds) & set(ActiveIds))
    ActiveGroups = []
    for G in MyGroups.values():
        if G.Controller.GetMechanicalObj().ObjectId in ActiveGroupIds:
            ActiveGroups.append(G)

    Ids = []
    for Group in ActiveGroups:
        Ids.extend(Group.Properties["Geometry"].Value.Ids)
    SelInfo = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    SelInfo.Ids = Ids
    ExtAPI.SelectionManager.NewSelection(SelInfo)

def SelectEqualGeomInInstanceGroup(Analysis=None):
    SelEntIds = []

    if not SelectFromTreeGroups:
        try:
            GeoModel=GetGeoModel()
            for Entity in ExtAPI.SelectionManager.CurrentSelection.Entities:
                IG = GeoModel.GetInstanceGroupByGeoEntity(Entity)
                Ids = IG.GetMyBodyIds()
                import InstanceFinder; InstanceFinder.Initialize(ExtAPI,Ansys)
                EqualEntities=InstanceFinder.GetEqualEntitiesFromArrayIndex(Entity,Ids,GeoModel.GeoEntityDict,False,True)
                SelEntIds.extend(EqualEntities)
        except Exception as e:
            pass
    else:
        try:
            import InstanceFinder; InstanceFinder.Initialize(ExtAPI,Ansys)
            GeoModel=GetGeoModel()      #This is needed for the GeoModel.GeoEntityDict
            GeoEntityDict = GeoModel.GeoEntityDict
            
            for Entity in ExtAPI.SelectionManager.CurrentSelection.Entities:
                for Group in MyGroups.values():
                    InGroup = False 
                    try:
                        BodyId = InstanceFinder.GetBodyFromEntity(Entity,True)[0].Id
                        InGroup = (BodyId in Group.Properties["Geometry"].Value.Ids)
                    except:pass
                    if InGroup:
                        Ids = Group.Properties["Geometry"].Value.Ids
                        break

                EqualEntities=InstanceFinder.GetEqualEntitiesFromArrayIndex(Entity,Ids,GeoEntityDict,False,True)
                SelEntIds.extend(EqualEntities)
        except Exception as e:
            pass
    try:
        SelInfo = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
        SelInfo.Ids = SelEntIds
        ExtAPI.SelectionManager.NewSelection(SelInfo)
    except Exception as e:
        pass

def SelectSimilarInBody(Analysis):
    import GeometryRecognizer
    GeometryRecognizer.Initialize(ExtAPI,Ansys)
    GeometryRecognizer.GeomRecognizer().GetSimilarFeatures()

def SelectInstanceGroupFromGraphicSelection(Analysis=None):
    """
    Select the instance group object in the tree from the first selected graphical entity
    """
    try:
        InstGrps=set()
        for Ent in ExtAPI.SelectionManager.CurrentSelection.Entities:
            InstGrp = GetGeoModel().GetInstanceGroupByGeoEntity(Ent)
            if InstGrp!=None: InstGrps.add(InstGrp)
        GrpClasses = set()
        for InstGrp in list(InstGrps):
            for Grp in MyGroups.values():
                GrpClass = Grp.Controller
                if GrpClass.InstanceGroup.Id==InstGrp.Id:
                    GrpClasses.add(GrpClass)
                    break
        GrpObjs = [GrpClass.GetMechanicalObj() for GrpClass in list(GrpClasses)]
        import TreeOrganizerHelper; TreeOrganizerHelper.Initialize(ExtAPI,Ansys)
        TreeOrganizerHelper.ActivateObjects(GrpObjs)
    except Exception as e: pass

def SelectBoltGeom(Analysis=None):
    import BoltGeomSelectorHelper; BoltGeomSelectorHelper.Initialize(ExtAPI,Ansys)
    BoltGeomSelectorHelper.ShowWindow()

def GoToTreeSel(Analysis = None):
    import GeoDataHelper; GeoDataHelper.Initialize(ExtAPI,Ansys)
    Ents = ExtAPI.SelectionManager.CurrentSelection.Entities
    Bodies = GeoDataHelper.ConvertEntitySelectionToBodies(Ents)
    TreeBodies = [ExtAPI.DataModel.Project.Model.Geometry.GetBody(B) for B in Bodies]
    import TreeOrganizerHelper; TreeOrganizerHelper.Initialize(ExtAPI,Ansys)
    TreeOrganizerHelper.ActivateObjects(TreeBodies)
    #endregion
#Contacts
    #region 
def ShowBodiesInContact(Analysis):
    import ConnectionsHelper
    ConnectionsHelper.Initialize(ExtAPI,Ansys)
    ConnectionsHelper.GetBodiesInContact(Entities=None,UpdateGraphics=True)

def ActivateContactsForSelection(Analysis):
    import ConnectionsHelper; ConnectionsHelper.Initialize(ExtAPI,Ansys)
    Contacts=ConnectionsHelper.GetContactsForEntities(SpecificSelection=True)
    import TreeOrganizerHelper; TreeOrganizerHelper.Initialize(ExtAPI,Ansys)
    TreeOrganizerHelper.ActivateObjects(Contacts)

def RemoveEntityFromAllContacts(Analysis):
    import ConnectionsHelper
    ConnectionsHelper.Initialize(ExtAPI,Ansys)
    Contacts=ConnectionsHelper.RemoveEntitiesFromContacts(None,None)

def RemoveEntityFromSelectedContacts(Analysis):
    Contacts = ExtAPI.DataModel.Tree.ActiveObjects
    import ConnectionsHelper
    ConnectionsHelper.Initialize(ExtAPI,Ansys)
    Contacts=ConnectionsHelper.RemoveEntitiesFromContacts(Contacts,None)

def KeepOnlyEntityFromSelectedContactsBySurfaceType(Analysis):
    Contacts = ExtAPI.DataModel.Tree.ActiveObjects
    FaceType = None
    try:FaceType = ExtAPI.SelectionManager.CurrentSelection.Entities[0].SurfaceType
    except:pass
    if FaceType==None: return
    import ConnectionsHelper
    ConnectionsHelper.Initialize(ExtAPI,Ansys)
    Contacts=ConnectionsHelper.KeepContactEntitiesByFaceType(FaceType,Contacts)

def GoToNamedSelectionsScopings(Analysis=None):
    """
    Activate the Named Selections for selected contacts
    """
    import ConnectionsHelper; ConnectionsHelper.Initialize(ExtAPI,Ansys)
    ConnectionsHelper.GetNamedSelForContacts(Contacts=None, Activate=True)

def ShowContactResultsWizard(Analysis):
    """
    Show the main wizard panel to start the process.
    """
    import ContactPostHelperGUI
    ContactPostHelperGUI.Initialize(ExtAPI,Ansys)
    ContactPostHelperGUI.ShowPanel()

def ShowContactStatusWizard(Analysis):
    """
    Show the main wizard panel to start the process.
    """
    import ContactStatusReporterGUI
    ContactStatusReporterGUI.Initialize(ExtAPI,Ansys)
    ContactStatusReporterGUI.ShowPanel()
    #endregion
    #region Meshing
def AddMeshCopy(Analysis):
    CS = ExtAPI.SelectionManager.CurrentSelection
    SourceId =  CS.Ids[0]
    SourceBodyId = CS.Entities[0].Bodies[0].Id
    TargetIds = []
    for Entity in CS.Entities:
        if Entity.Bodies[0].Id!=SourceBodyId:
            TargetIds.append(Entity.Id)
    Source=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    Source.Ids = [SourceId]
    Target=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    Target.Ids = TargetIds
    import BoltMeshingHelper
    BoltMeshingHelper.Initialize(ExtAPI,Ansys)
    MeshCopy = BoltMeshingHelper.CreateMeshCopy(Source,Target)
    #endregion
#Coordinate Systems
    #region 
def AddCsForSel(Analysis):
    import CoordinateSystemHelper; CoordinateSystemHelper.Initialize(ExtAPI,Ansys)
    CoordinateSystemHelper.CreateCoordinateSystemsForEntities(None, Activate=True)

def FlipZAxis(Analysis):
    import CoordinateSystemHelper; CoordinateSystemHelper.Initialize(ExtAPI,Ansys)
    CoordinateSystemHelper.FlipAxis(None,[2],True)

def AddCsForBolt(Analysis):
    """
    Add a coordinate system for a bolt body 
    This is located at the bottom face by threads, is cylindrical,
        and points towards the head of the bolt.
    """
    import CoordinateSystemHelper
    CoordinateSystemHelper.Initialize(ExtAPI,Ansys)
    StartSel = GetCurrentSelection()
    Creator = CoordinateSystemHelper.CoordinateSystemCreator()
    Creator.Group=True
    Creator.Name="Bolt Sys: <BodyName>"
    with Transaction(True):
        CSs = CoordinateSystemHelper.CreateBoltCoordinateSystem(StartSel.Entities, Creator)
    if Creator.Group and Creator.CreatedObjects.GroupingDone==False:
        Creator.DoGrouping()
    SetSelection(StartSel)
    TreeOrganizerHelper.ActivateObjects(Creator.CreatedObjects.CoordinateSystems)
def GetBoltCs(Analysis):
    """
    Gets the coordinate system for a bolt body 
    This CS is located at the bottom face by threads, is cylindrical,
        and points towards the head of the bolt.
    """
    import CoordinateSystemHelper
    CoordinateSystemHelper.Initialize(ExtAPI,Ansys)
    CsDict = CoordinateSystemHelper.GetBoltCoordianteSystems()
    TreeOrganizerHelper.ActivateObjects(CsDict.values())
    #endregion
#Beams
    #region 
def CreateBeamsFromSolids(Analysis=None):
    import BeamHelper
    BeamHelper.Initialize(ExtAPI,Ansys)
    Creator=BeamHelper.BeamFromSolidCreator()
    with Transaction(True):
        Creator.CreateBeams()
    #endregion
# Preloads
    #region
def AssignPreloadCs(Analysis):
    import PretensionHelper; PretensionHelperGUI.Initialize(ExtAPI,Ansys)
    PretensionHelper.AssignPretensionCoordinateSystem()

def MovePreloadsCs(Analysis):
    import PretensionHelperGUI; PretensionHelperGUI.Initialize(ExtAPI,Ansys)
    Win = PretensionHelperGUI.PreloadMoveWindow()
    Win.Show()
    Win.TextBox.Focus()

def GetPreloadsFromCs(Analysis):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.GetPretensionsFromCoordinateSystems(None,True)

def GetCsFromPreloads(Analysis):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.GetCsFromPretensions(None, True)

def GetPreloadsFromSelection(Analysis):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.GetPretensionsFromSelection()

def SetGraphicSelectionFromPreloads(Analysis=None):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.ActivateGraphicsFromPretensions()

def GetPreloadsFromProbes(Analysis):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.GetPretensionsFromProbes(None, True)

def RenamePreloadsBasedOnDef(Analysis):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.RenamePretensionsAndCs()

def ExportPreloadValues(Analysis=None):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.SaveTabularDataToFile()

def ImportPreloadValues(Analysis=None):
    import PretensionHelper; PretensionHelper.Initialize(ExtAPI,Ansys)
    PretensionHelper.LoadTabularDataFromFile()
    #endregion
#Wizard
#region 
def ShowHoleDetectionWizard(Analysis):
    import SurfaceBodyHolesGUI; SurfaceBodyHolesGUI.Initialize(ExtAPI,Ansys)
    SurfaceBodyHolesGUI.ShowHoleDetectionWizardPanel()

def ShowSolidBodyHoleDetectionWizard(Analysis):
    import SolidBodyHolesGUI; SolidBodyHolesGUI.Initialize(ExtAPI,Ansys)
    SolidBodyHolesGUI.ShowWizardPanel()

def ShowSetupWizard(Analysis):
    import SetupWizardGUI; SetupWizardGUI.Initialize(ExtAPI,Ansys)
    SetupWizardGUI.ShowSetupWizardPanel()

def ShowPostWizard(Analysis=None):
    import ConnectionObjPostProcessingGUI
    ConnectionObjPostProcessingGUI.Initialize(ExtAPI,Ansys)
    ConnectionObjPostProcessingGUI.ShowWizardPanel()

def ShowReactionResultsPanel(Analysis):
    """
    Show reaction probes wizard panel
    """
    import ReactionProbesHelperGUI
    ReactionProbesHelperGUI.Initialize(ExtAPI,Ansys)
    ReactionProbesHelperGUI.ShowPanel()

def ShowConeOfCompressionWizard(Analysis=None):
    import ConeOfCompressionImprintGUI
    ConeOfCompressionImprintGUI.Initialize(ExtAPI,Ansys)
    ConeOfCompressionImprintGUI.ShowPanel()

def ShowGeometryRegionSelectorWizard(Analysis=None):
    import InternalGeomSelectorHelperGUI
    InternalGeomSelectorHelperGUI.Initialize(ExtAPI,Ansys)
    InternalGeomSelectorHelperGUI.ShowPanel()

def ShowCompFacesWizard(Analysis=None):
    import CompFacesGeomRecognitionGUI
    CompFacesGeomRecognitionGUI.Initialize(ExtAPI,Ansys)
    CompFacesGeomRecognitionGUI.ShowPanel()
#endregion
#Tree Helpers
    #region 
def ShowObjConnectionTree(Analysis=None):
    import UserMechTree
    UserMechTree.Initialize(ExtAPI,Ansys)
    Objs = [Obj for Obj in ExtAPI.DataModel.Tree.ActiveObjects]
    UserMechTree.ShowObjectRelationTreePanel(Objs)

def ShowTreeHelper(Analysis):
    import TreeFilterHelper
    TreeFilterHelper.Initialize(ExtAPI,Ansys)
    TreeFilterHelper.ShowWindow()

def ShowObjectSelector(Analysis):
    import ObjLocationDataHelperGUI
    ObjLocationDataHelperGUI.Initialize(ExtAPI,Ansys)
    ObjLocationDataHelperGUI.ShowWizardPanel()

def ShowTreeGroupSelector(Analysis):
    import TreeGroupFolderSelectorHelper
    TreeGroupFolderSelectorHelper.Initialize(ExtAPI,Ansys)
    import AttachControlToMechanical
    AttachControlToMechanical.Initialize(ExtAPI,Ansys)
    Control = TreeGroupFolderSelectorHelper.FolderTreePanel()
    ControlFramPanel = AttachControlToMechanical.ControlFramePanel(Control)
    ControlFramPanel.Pane = WizardPane      #Due to bug in mapping wizard to correct panel
    ControlFramPanel.AddPanelToMechanical()

def ShowObjectExtDataViewer(Analysis):
    import ObjectExternalDataTableGUI
    ObjectExternalDataTableGUI.Initialize(ExtAPI,Ansys)
    ObjectExternalDataTableGUI.ShowPanel()
    #endregion
#Post Processing
#region 
def ShowObjSummaryTable(Analysis=None):
    #RunObjSummaryTable()
    import ObjectSummaryTable
    ObjectSummaryTable.Initialize(ExtAPI,Ansys)
    ObjectSummaryTable.RunObjSummaryTable()
#endregion
#endregion

#Standard Parts
#region
def ShowPartsLibrary(Analysis):
    """
    Show the parts library window GUI in the mechanical application.
    """
    try:
        global PartLibraryWindow
        import os
        import PartLibraryGUI; PartLibraryGUI.Initialize(ExtAPI,Ansys)

        #Set global vairables of the module that are used later.
        PartLibraryGUI.Library = GetStandardPartLibrary()
        PartLibraryGUI.GeoModel = GetGeoModel()
        PartLibraryGUI.UpdateMatchPartMethod = MatchStandardPartExternal

        PartLibraryWindow=PartLibraryGUI.ShowWindow()
    except Exception as e:
        ErrorHandle("Error opening Part Library Window...", e)

def RunStandardPartScript(Analysis=None):
    """
    Run the scripts for selected Groups with assocaited standard parts.
    """
    GetTreeGroupsGeoModel()     #Update the GeoModel
    GetStandardPartLibrary(True)

    ActiveIds = [Obj.ObjectId for Obj in ExtAPI.DataModel.Tree.ActiveObjects]
    ActiveGroups = []
    for MyGroup in MyGroups.values():
        Id = MyGroup.Controller.GetMechanicalObj().ObjectId
        if Id in ActiveIds:
            ActiveGroups.append(MyGroup)
    GroupsToRun=[]
    for Group in ActiveGroups:
        if Group.Properties["IsStandardPart"].Value=="Yes":
            GroupsToRun.append(Group)
    for Group in GroupsToRun:
        Part = Group.Controller.GetStandardPart(StandardPartLibrary)
        if Part!=None:
            InstanceGroup = Group.Controller.InstanceGroup
            PyFileName = Group.Properties["StandardPartData/PyFileName"].Value
            Arg1 = Group.Properties["StandardPartData/UserArg1"].Value
            Arg2 = Group.Properties["StandardPartData/UserArg2"].Value
            Arg3 = Group.Properties["StandardPartData/UserArg3"].Value
            RunPartLibraryPart(PyFileName, InstanceGroup, Part, Arg1, Arg2, Arg3)
    return
#endregion

def ShowHelpDoc(Analysis=None):
    """
    Open the documentation
    """
    import webbrowser
    version = str(Ansys.Utilities.ApplicationConfiguration.DefaultConfiguration.VersionInfo.VersionString) 
    hf_url="https://ansyshelp.ansys.com/account/secured?returnurl=/Views/Secured/corp/v"+version+"/en/wb_sim/ds_geo_addon_bolttools.html"  
    webbrowser.open(hf_url)

#GroupManager
#region 
def CanAdd_GroupManager(ParentObj,ObjName):  return (MyGroupManager==None)
def CanDuplicate_GroupManager(Entity,Parent): return False
class GroupManager:
    def __init__(self,ExtAPI,AnsysObj):
        self.AnsysObj = AnsysObj
        self.GeoModel = None     #GeoModel class object that helps to store data.
        return

    def oninit(self,Me):
        global MyGroupManager; MyGroupManager=Me
        global SelectFromTreeGroups; SelectFromTreeGroups = True

    def onremove(self,Me):
        global MyGroupManager; MyGroupManager=None
        global SelectFromTreeGroups; SelectFromTreeGroups = False
        global TreeGroupsGeoModel; TreeGroupsGeoModel = None

    def onshow(self,Me):
        pass

def CreateGroup(Obj):
    ExtAPI.Log.WriteMessage("Create Object...")
    StartSel = ExtAPI.SelectionManager.CurrentSelection
    ExtAPI.SelectionManager.ClearSelection()
    GroupObj = Obj.CreateChild("Group")
    ExtAPI.SelectionManager.NewSelection(StartSel)

def CreateGroupsFromModel(Obj):
    """
    Action callback for GroupManager Object.
    Auto-Creates Groups under the object based on the model and user-preferences
    """

    ExtAPI.Log.WriteMessage("Create Objects...")
    Tolerance = Obj.Properties["AutoCreation/Tolerance"].Value

    UsedBodyIds = []
    for MyGroup in MyGroups.values():
        Ids = []
        try:
            Geom = MyGroup.Properties["Geometry"].Value
            Ids = Geom.Ids
        except:pass
        UsedBodyIds.extend(Ids)

    GeoModel = LoadGeoModel(Tolerance,UsedBodyIds)

    BodyGroupNumMin = Obj.Properties["AutoCreation/MinNumber"].Value
    CreatedGroups = []
    with Transaction():
        for i in range(len(GeoModel.InstanceGroups.values())):
            ActiveGroup =  GeoModel.InstanceGroups.values()[i]
            if len(ActiveGroup.BodyGroups.keys())>BodyGroupNumMin-1:
                GroupObj = Obj.CreateChild("Group")
                CreatedGroups.append(GroupObj)
                GroupObj.Controller.InstanceGroup = ActiveGroup
                SelInfo = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
                SelInfo.Ids = ActiveGroup.GetMyBodyIds()
                GroupObj.Properties["Geometry"].Value = SelInfo
                GroupObj.Controller.GetMechanicalObj().Name = ActiveGroup.Name

    if len(CreatedGroups)==0:
        import GeneralUtilities.UserFeedbackUI as UserFeedbackUI
        Msg = "No groups were created.\nEither all active bodies are in a group or settings are such that no groups are created."
        UserFeedbackUI.GiveUserFeedback("Note:",Msg)

def CanDuplicate_Group(Entity,Parent): return False
#endregion
#Groups
#region 
class Group:
    def __init__(self,ExtAPI,ACTObj):
        self.ExtAPI = ExtAPI
        self.ACTObj = ACTObj

        self.InstanceGroup = None   #GeoModel InstanceGroup auto-assigned when creating GeoModel

    def oninit(self,Me):
        global MyGroups
        MyGroups[Me.Id]=Me

    def onadd(self,Me):
        pass

    def onremove(self,Me):
        global MyGroups
        del MyGroups[Me.Id]

    def onshow(self,Me):
        #Get the display type
        if len(ExtAPI.DataModel.Tree.ActiveObjects)==1:
            DisplayType=""
            if Me.Properties["OnSelection"].Value !="Default":
                DisplayType=Me.Properties["OnSelection"].Value
            else:
                DisplayType=MyGroupManager.Properties["OnSelection"].Value
            #Do the display action
            if DisplayType.startswith("Hide Others"): 
                try:
                    ExtAPI.SelectionManager.NewSelection(Me.Properties["Geometry"].Value)
                    with ExtAPI.Graphics.Suspend():
                        Cmd = "DS.Script.doHideAllOtherPartsFromGeometrySelection();"
                        ExtAPI.Application.ScriptByName("jscript").ExecuteCommand(Cmd)
                    if "Fit" in DisplayType: ExtAPI.Graphics.Camera.SetFit()
                except:pass
            elif DisplayType == "Select Bodies":
                try: ExtAPI.SelectionManager.NewSelection(Me.Properties["Geometry"].Value)
                except Exception as e:
                    pass

    def onhide(self,Me):
        pass

    def GetMechanicalObj(self):
        Id = self.ACTObj.InternalObject.ID
        return ExtAPI.DataModel.GetObjectById(Id)

    def GetStandardPart(self,Library):
        """
        Get the PartLibrary.Part object for the Group by its Standard Part Name property.
        """
        Part = None
        try:
            PartName = self.ACTObj.Properties["StandardPartData/Name"].Value
            Part = Library.Parts[PartName]
        except:pass
        return Part

def RenameAllGroupsFromStandardPart(Analysis=None):
    for MyGroup in MyGroups.values():
        RenameFromStandardPart(MyGroup)

def RenameFromStandardPart(Obj):
    if Obj.Properties["IsStandardPart"].Value == "Yes":
        Name = Obj.Properties["StandardPartData/Name"].Value
        Obj.Controller.GetMechanicalObj().Name = Name
        Obj.NotifyChange()

def RenameTreeBodiesFromGroup(Obj):
    GeoBodies = [ExtAPI.DataModel.GeoData.GeoEntityById(Id) for Id in Obj.Properties["Geometry"].Value.Ids]
    TreeBodies = [ExtAPI.DataModel.Project.Model.Geometry.GetBody(B) for B in GeoBodies]
    Name = Obj.Controller.GetMechanicalObj().Name
    for TreeBody in TreeBodies:
        TreeBody.Name = Name

    #region Group Property Callbacks
def Group_Geometry_OnValidate(Obj,Prop):
    """
    Runs after Geometry Scoping of a Group is changed
    Will ensure bodies are only scoped to a single group.
    """
    if Prop.Value==None: return
    Ids = Prop.Value.Ids
    for MyGroup in MyGroups.values():
        if MyGroup!=Obj:
            Geom = MyGroup.Properties['Geometry'].Value
            if Geom !=None:
                MyGroupIds = Geom.Ids
                OverlapList = list(set(Ids) & set(MyGroupIds))
                if len(OverlapList)>0:
                    #Remove from the group with overlap
                    SelType = Ansys.ACT.Interfaces.Common.SelectionTypeEnum.GeometryEntities
                    SelInfo = ExtAPI.SelectionManager.CreateSelectionInfo(SelType)
                    NewIds = list(set(MyGroupIds)-set(OverlapList))
                    SelInfo.Ids = NewIds
                    MyGroup.Properties['Geometry'].Value=SelInfo

def OnValidate_Group_IsStandardPart(Obj,Prop):
    Visibility = (Prop.Value == "Yes")
    Obj.Properties["StandardPartData"].Visible=Visibility

def OnValidate_Group_StandardPart(Obj,Prop):
    """
    Change the standard part for a Group object
    Other properties about the part are updated as well based on the new selection.
    """
    Name = Prop.Value
    Part = None
    #Get the new part from the internal library
    try:Part = GetStandardPartLibrary().Parts[Name]
    except:pass
    #If you have a part identified then change the other displayed properties.
    if Part!=None:
        #Change the description of the part property
        if Part.Description!="": Description = Part.Description
        else: Description = "NA"
        Obj.Properties["StandardPartData/Description"].Value = Description

        #Set the value and options for the python script files.
        PyFileProp = Obj.Properties["StandardPartData/PyFileName"]
        PyFileProp.Options.Clear()
        for PythonScriptName in Part.PythonScriptNames:
            if PythonScriptName!="":
                PyFileProp.Options.Add(PythonScriptName)
        if len(PyFileProp.Options)==0:
            PyFileProp.Options.Add("NA")
        PyFileProp.Value = PyFileProp.Options[0]
        PyFileProp.ReadOnly=(len(PyFileProp.Options)<2)     #read only if only 1 option.

def MatchStandardPartExternal(StandardOartName, Obj):
    """
    Routine to Update the Standard part from an external module
    Needed to stil get all the callbacks for object update.
    """
    Prop = Obj.Properties["IsStandardPart"]
    Prop.Value = "Yes"
    OnValidate_Group_IsStandardPart(Obj,Prop)

    Prop = Obj.Properties["StandardPartData/Name"]
    Prop.Value = StandardOartName
    OnValidate_Group_StandardPart(Obj,Prop)

    RenameFromStandardPart(Obj)


def OnActivate_Group_StandardPart(Obj,Prop):
    """
    Fill list of options for standard parts.
    """
    Prop.Options.Clear()
    Prop.Options.Add("None")
    Lib = GetStandardPartLibrary()
    for Part in Lib.Parts.values():
        Prop.Options.Add(Part.Name)
    #endregion
#endregion
#ApdlBolt Custom Object
#region 
def CanAdd_ApdlBoltManager(ParentObj,ObjName):  return (ApdlBoltModule.MyApdlBoltManager==None)
def CanDuplicate_ApdlBoltManager(Entity,Parent): return False
def CreateApdlBolt(Obj):
    ExtAPI.Log.WriteMessage("Create APDl Bolt Object...")
    ApdlBoltObj = Obj.CreateChild("ApdlBolt")

def ApdlBoltNameActivate(Obj,Prop):
    """
    Activate Callback for ApdlBolt part selector
    """
    Prop.Options.Clear()
    Bolts = []; Washers=[]; Nuts=[]
    for Data in ApdlBoltModule.ApdlBoltDict.values():
        try:
            if Data.PartType.upper()=="BOLT":
                Bolts.append(Data.Name)
            if Data.PartType.upper()=="Washer".upper():
                Washers.append(Data.Name)
            if Data.PartType.upper()=="Nut".upper():
                Nuts.append(Data.Name)
        except:pass

    Prop.Options.Add("None")
    if Prop.UniqueName == "Parts/BoltName":
        for Bolt in Bolts:
            Prop.Options.Add(Bolt)
    elif Prop.UniqueName == "Parts/BoltWasherName" or Prop.UniqueName == "Parts/NutWasherName":
        for Washer in Washers:
            Prop.Options.Add(Washer)
    elif Prop.UniqueName == "Parts/NutName":
        for Nut in Nuts:
            Prop.Options.Add(Nut)

def ApdlBoltValidate(Obj,Prop):
    """
    Match the mech bolt to the dictionary of the app.
    """
    Obj.Controller.GetData(Obj)

def ApdlBolt_Display_Validate(Obj,Prop):
    Obj.Controller.UpdateGraphics(Obj,FullUpdate=False)

def SelectCoordinateSystems(Obj,Prop):
    """Routine to select coordinate systems for ApdlBolt object"""
    ApdlBoltModule.SelectCoordinateSystems(Obj,Prop)

def ActivateObjCs(Obj):
    """Activate in tree the coordinate systems for ApdlBolt object"""
    import TreeOrganizerHelper
    TreeOrganizerHelper.Initialize(ExtAPI,Ansys)
    Ids = Obj.Attributes["CsIds"]
    TreeOrganizerHelper.ActivateObjects(Ids)
#endregion
#GeoModel Loading and Management
#region 
def LoadGeoModel(InstanceTolerance= 0.001, UsedBodyIds=[]):
    """
    Get the global GeoModel object initialized.
    GeoModel holds information about the identical instances in the model and other helpful info.
    """
    global GeoModel; global InternalLog
    InternalLog+="Getting Ready to Gather Instances \n"
    import InstanceFinder; InstanceFinder.Initialize(ExtAPI,Ansys)
    InternalLog+="Getting Instance Data \n"

    GeoModel = InstanceFinder.GeoModel()
    GeoModel.GetModelData(False,UsedBodyIds,InstanceTolerance)

    InternalLog+="Done Getting Instance Data \n"
    return GeoModel

def GetGeoModel():
    """
    Routine to ensure you have loaded the global GeoModel
    """
    global GeoModel; global TreeGroupsGeoModel
    if not SelectFromTreeGroups:
        if GeoModel==None:
            LoadGeoModel()
        return GeoModel
    else:
        GetTreeGroupsGeoModel()
        return TreeGroupsGeoModel

def GetTreeGroupsGeoModel(RefreshDict=False):
    """
    Get a GeoModel of the Groups in the ModelTree.
    This is stored globally.
    """
    global TreeGroupsGeoModel
    global GeoEntityDict
    import InstanceFinder; InstanceFinder.Initialize(ExtAPI,Ansys)
    if RefreshDict: GeoEntityDict=None
    TreeGroupsGeoModel = InstanceFinder.GeoModel(GeoEntityDict)
    GeoEntityDict = TreeGroupsGeoModel.GeoEntityDict
    for MyGroup in MyGroups.values():
        InstGrp = InstanceFinder.InstanceGroup()
        InstGrp.TreeGroupObj = MyGroup.Controller.GetMechanicalObj()    #Mechanical Object in Tree
        InstGrp.Name = InstGrp.TreeGroupObj.Name      #Name as it appears in the tree
        #Link the Tree ACT Group to the GeoModel Instance Group
        InstGrp.TreeGroupACTObj=MyGroup
        MyGroup.Controller.InstanceGroup=InstGrp

        InstGrp.Id=TreeGroupsGeoModel.GetId()
        TreeGroupsGeoModel.InstanceGroups[InstGrp.Id] = InstGrp  #Add the Instance group to the Model.

        Geom = MyGroup.Properties["Geometry"].Value
        i=1
        for Id in Geom.Ids:
            BodyGroup = InstanceFinder.BodyGroup()
            BodyGroup.Id = i
            BodyGroup.Bodies[Id] = ExtAPI.DataModel.GeoData.GeoEntityById(Id)
            InstGrp.BodyGroups[i] = BodyGroup
            BodyGroup.InstanceGroup = InstGrp
            i+=1
    pass

#endregion
#Part Library Scripts
#region 
def GetStandardPartLibrary(ForceRefresh=False):
    """
    Get the global StandardPartLibrary
    If not initialized, it will read it from extension files and create it.
    """
    global StandardPartLibrary
    if StandardPartLibrary==None or ForceRefresh:
        import PartLibrary #Part Library Module
        PartLibrary.Initialize(ExtAPI,Ansys)
        StandardPartLibrary = PartLibrary.PartLibrary()

        InstallDir = ExtAPI.ExtensionManager.CurrentExtension.InstallDir
        LibraryFolderName='PartLibraryData'
        StandardPartLibrary.FolderPaths.append(join(InstallDir,'PartLibraryData'))
        StandardPartLibrary.FolderPaths.append(join(AppDataPath,'AD_PartLibraryData'))
        StandardPartLibrary.LoadFromFiles()
    return StandardPartLibrary

def RunPartLibraryPart(FileName, InstanceGroup, Part, 
    UserArg1=None, UserArg2=None, UserArg3=None):
    """
    Runs a python file that is mapped to a part in the part library.
        FileName is the name of the python file without .py extension
        Assumption is there is a main routine called "Run" in the file
    """
    if "AD_PartLibraryData" in Part.FilePath:
        exec("import AD_PartLibraryData.PartScripts." + FileName + " as StandardPartModule")
    else:
        exec("import PartLibraryData.PartScripts." + FileName + " as StandardPartModule")
    reload(StandardPartModule)
    StandardPartModule.ExtAPI = ExtAPI

    StandardPartModule.InstanceGroup=InstanceGroup
    StandardPartModule.Part = Part
    StandardPartModule.UserArg1 = UserArg1
    StandardPartModule.UserArg2 = UserArg2
    StandardPartModule.UserArg3 = UserArg3
    StandardPartModule.Run()
#endregion

#Object Summary Table
#region 
def RunObjSummaryTable(FileNameNoExt=None):
    """
    Runs a python file that is mapped to a Object Summary Table.
        Assumption is there is a main routine called "Run" in the file
    """
    if FileNameNoExt==None:
        from os import path
        import FileSelectorGUI; FileSelectorGUI.Initialize(ExtAPI,Ansys)
        FileSel = FileSelectorGUI.FileSelector()
        FileSel.DefaultDir = path.join(ExtAPI.ExtensionManager.CurrentExtension.InstallDir,"SummaryTables")
        FileSel.FilterStr = "Python Files|*.py;*.py|All Files(*.*)|*.*"
        DialogResult = FileSel.GetFiles()
        if DialogResult.UserCancelled: return
        FileName = DialogResult.SelectedPaths[0]
        FileNameNoExt = path.splitext(path.basename(FileName))[0]
    exec("import SummaryTables." + FileNameNoExt + " as ObjTable")
    reload(ObjTable)
    ObjTable.ExtAPI = ExtAPI
    ObjTable.Ansys = Ansys
    ObjTable.AppDir = ExtAPI
    ObjTable.Enums = Ansys.Mechanical.DataModel.Enums
    ObjTable.Quantity=Ansys.Core.Units.Quantity
    ObjTable.Model=ExtAPI.DataModel.Project.Model
    ObjTable.TableObjects = ExtAPI.DataModel.Tree.ActiveObjects
    ObjTable.Pane = WizardPane
    ObjTable.Run()
#endregion
def ErrorHandle(UserMessage, e):
    """
    General routine for errors and printing to the ACT log.
        UserMessage (string): User message for the error
        e (Exception): Exception thrown by error.
    """
    try: ExtAPI.Log.WriteMessage(e.UserMessage)
    except:pass
    try: ExtAPI.Log.WriteError(e.message)
    except:
        try: ExtAPI.Log.WriteError("Unknown error occured.")
        except:pass 

toolTips = {
"Selection":"Selection tools are provided to streamline the selection of geometry across a pattern of bodies or within a body.",
"Select Instance Bodies":"Selects the bodies in the same Instance Group as the bodies associated with the current selection. Only the first active entity is used in the selection.",
"Select Instance Pattern Bodies":"Selects the bodies in the same Instance Group as the bodies associated with the current selection, and attempts to identify separate patterns within the Instance Group. Only the bodies in the identified pattern are selected. Only the first active entity is used in the selection.",
"Select Bodies in Groups Active in Tree":"Selects in the graphics all the bodies scoped to any of the active Instance Groups in the tree.",
"Activate Group from Graphics Selection":"Activates the Instance Groups in the tree based on the currently selected geometry.",
"Select Equal Geom across Instances":"Selects the equivalent geometry entities on each body of the Instance Group. Supports multiple selections.",
"Select Similar Geom on Body":"Attempts to select geometry of the same size and shape within the body associated with the current selection. Only the first active entity is used in the selection.",
"Select Bolt Geometry":"Opens a secondary form to select geometry associated with different parts of a bolt.",
"Go To Selection in Tree":"Activates the tree body objects for the current graphical selection.",
"Contacts":"Contacts are in integral part of bolted joint modeling and can take a significant amount of time to setup correctly for large assemblies. Many features and tools are introduced to simplify and streamline this process.",
"Show Bodies In Contact":"Shows only the selected bodies and bodies that are associated via a contact pair in the tree.",
"Activate Contacts from Selection":"Activates all contacts in the tree that contain the given graphical selection entities. This works on any specific entities such as faces, not just the body.",
"Remove Selection from All Contacts":"Removes the graphical selection entities from all contacts in the tree. Useful for globally cleaning contacts of geometrical entities that should not have contacts, but perhaps were included in auto contact generation.",
"Remove Selection from Active Contacts":"Removes the graphical selection entities from activated contacts in the tree. Contacts that have all entities removed from a scoping by this action will be deleted.",
"Keep Contact Faces By Face Type":"Removes any faces in the activated contacts that are not the same type as the first selected face in the graphics.",
"Activate Named Selection for Contacts":"For contacts scoped to Named Selections this will activate the named selections in the tree for quick reference.",
"Contact Results Wizard":"The purpose of this wizard is to create post processing objects related to contacts and export multiple images to files as well as Microsoft PowerPoint presentations.",
"Contact Status Export Wizard":"This wizard is used to export contact status information for multiple locations and time points.",
"Meshing":"Under Mesh options you can use the 'Add Mesh Copy' capability.",
"Add Mesh Copy":"Add a Mesh Copy control.  This is useful to copy mesh from one bolt to others in the pattern.  Select equal faces of all bolt instances and the mesh copy scoping will be completed on that selection.",
"CoordinateSystems":"Coordinate systems (CS) are important objects that are often used by other objects for definition. Creation and manipulation of multiple CS along a pattern can be done via these menu commands.",
"Add CS for Each in Selection":"Adds a coordinate system for each geometrical entity selected. Each entity will get its own cartesian coordinate system located at its centroid. Z axis will be set to be primary and aligned with the associated geometrical entity.",
"Flip Z Axis":"Add a CS transformation to each activated CS to flip the Z axis.",
"Add Bolt CS":"Adds a CS based on entity selection in the graphics window. Any entity types (Faces, edges, etc.) can be selected, but the routine will work with the associated bodies.",
"Get Bolt CS":"Activate CS for a body that fit the standard convention for a bolt CS.",
"Preloads":"Bolt preloads are an integral part of the bolted joint analysis and simulate the tensioning assembly of the bolt, typically, prior to other loads being applied. The bolt body is cut into two sections and a pilot node is used to apply this modeling practice. Application of a preload can either be to a cylindrical face, or to a body. When scoped to a body, a coordinate system must be identified in order to establish the location of the cut section along the bolt axis.",
"Assign Preload CS":"Attempt to associate the selected preloads with the closest CS to the body centroid.",
"Move Preload CS":"Shows small window for user input to move the coordinate system of all activated preloads in the Z direction. Useful for modifying the location of the cut section in the bolt to avoid any bonded contact in the threaded section.",
"Get Preload From CS":"Select any corresponding preloads from the currently active coordinate systems.",
"Get CS From Preload":"Select any corresponding coordinate systems from the currently active preloads.",
"Get Preloads From Selection":"Select any corresponding preloads from the graphics window selection.",
"Set Selection From Preloads":"Select in the graphics all the scoped entities for the active preload objects in the tree.",
"Get Preloads From Probes":"Activate preload objects under an analysis based on the active Preload Probes under the solution.",
"Rename Preloads Based On Def":"Auto-rename all selected preloads.",
"Export Preload Values":"Export the tabular data load values to an external file (.csv).",
"Import Preload Values":"Import tabular data values from an external file to activated preloads.",
"Beams":"Supports modeling and evaluation of bolts as 1D beam elements.",
"Show Summary Table":"Opens a dialog to select an Object Summary Table for display.",
"Create Beams From Solids":"Creates beam objects with linked remote points, named selections and coordinate systems, for current graphical selection.",
"PostProcessing":"Supports modeling and evaluation of bolts as 1D beam elements.",
"Show Summary Table":"Opens a dialog to select an Object Summary Table for display.",
"Reaction Probes Wizard":"Opens a post processing wizard for viewing time history results for multiple beam, joint, or user-element data. Use in cases where you have exported tabular data from an APDL snippet and want to reference the data back to Mechanical via the APDL element number.",
"Connections Post Wizard":"This wizard is used to display and export data on connection objects.  Beams and Joints are currently supported.  This does not create post objects in the Mechanical tree, but directly accessed the analysis results file and extracts data that is displayed in the interface or exported to a file.",
"Tree Helper":"Contains useful tools for navigating large tree structures and cross referencing of objects.",
"Object Connections Tree":"Opens a secondary object tree with referenced objects underneath it for quick cross referencing.",
"Show Tree Helper":"Opens secondary window of quick key options for filtering the model tree or setting visibility.",
"Tree Group Helper":"Opens a pane for selecting objects based on group or folder in the tree. Useful for selecting grouped objects and modifying properties in the details window in mass updates. Provides for user-filtering tools to get the objects desired quickly.",
"Object External Data Viewers":"Wizard interface to display external .csv files and cross reference rows to objects in the tree. User will specify columns for the object Ids for cross referencing.",
"Object Selector":"Wizard interface to help select objects in the tree based on user criteria.",
"Wizards":"The Bolt Modeling Wizard is a streamlined interface for model setup of typical fastener assemblies. Similar to the main menu items, it is organized into tabs for each category of object, such as: coordinate systems, contacts, meshing, etc. The wizard is created to allow for more complex user inputs to designate how a workflow should perform, as compared to a single button with pre-programmed assumptions.",
"Setup Wizard":"The setup wizard is primarily focused on the setup steps and includes: Coordinate Systems, Mesh, Named Selections, Pretension and Contacts.",
"Surface Body Hole Detection Wizard":"This wizard is used to detect mating holes in surface body assemblies.  Once identified, objects like mesh controls, and connections such as beams can be created to model fasteners.",
"Reaction Probes Wizard":"This tab is used to create post processing reaction probes for forces and moments are various locations and time points.  These can then be easily exported to a summary file in .csv format.",
"Connections Post Wizard":"This wizard is used to display and export data on connection objects.  Beams and Joints are currently supported.  This does not create post objects in the Mechanical tree, but directly accessed the analysis results file and extracts data that is displayed in the interface or exported to a file.",
"Contact Results Wizard":"The purpose of this wizard is to create post processing objects related to contacts and export multiple images to files as well as Microsoft PowerPoint presentations.",
"Contact Status Export Wizard":"This wizard is used to export contact status information for multiple locations and time points.",
"Instances":"The Instance Manager is a custom object that can be inserted into the Mechanical tree. Only one object of this type is allowed, as this applies to the current model geometry. Users can insert Instance Groups under the Instance Manager to designate geometry into groupings and associate it with standard parts from the Part Library.",
"Instance Manager":"The Instance Manager can auto-create Instance groups for the entire model. This consists of identifying bodies with the same volume and material and putting them into a group together.",
"Rename All Groups From Standard Part":"Rename All Groups From Standard Part.",
"Parts Library":"A part library is utilized to automate the modeling of standard parts represented as bodies in the model. With a predefined file that contains part information like material, volume and name, you can uniquely define criteria to identify a specific part. Once identified, this part can be mapped to standard scripts which will control the setup. This can include meshing, loads, material selection, contacts, post objects, or any other modeling setup. More than one script file can be used to account for different modeling approaches taken on the same part based on the analysis context. For example, sometimes you may want to represent a bolt with full solid elements, while other times a beam-representation may be appropriate.",
"Run Standard Part Scripts for Selected":"One of the key features of Instance Groups is the ability to trigger user-defined scripts to fully automate the modeling of these parts.",
"ApdlBolt":"APDL is a language/solver used by Mechanical and for parts that have a standardized method for modeling, an APDL-based setup can greatly reduce the amount of work required in Mechanical. To accommodate this and integrate in Mechanical, a custom object has been created to allow for users to direct user-defined APDL input based on selected coordinate systems in Mechanical and a list of user-defined standard parts.",
"Help": "Open the Bolt Tools Help for further information."
}

def GetToolTips(name):
	if name in toolTips.keys(): return toolTips[name]
	return name