"""
Module will control the ACT objects and methods associated with ApdlBolt implementation.
"""
#region imports and globals
ExtAPI = None; Ansys = None
Enums = None; Quantity=None

#App related paths and data
ApdlDir = None
ApdlPartsDir = None
ApdlScriptsDir=None

ApdlBoltDict = {}

MyApdlBoltManager = None      #ACT object

#globals for APDL input file write tracking.
ActiveAnalysis = None       #Analysis that is currently being solved or input file written.
NodeNum = 0     #Current Ids in Mechanical for solver input file creations
ElemNum = 0
TypeNum = 0
SentFiles = []  #Track all files that are sent to the input stream.
HeaderSent = False
GlobalManager = None

#general imports.
import os
import xml.etree.ElementTree
import units

#App specific module imports.
import Factory3DGraphicsHelper
import FeBlockDataWriter


def Initialize(MyExtAPI, MyAnsys):
    """Call each time you import the module"""
    global ExtAPI; global Ansys; global Enums; global Quantity
    global ApdlDir; global ApdlPartsDir
    global ApdlScriptsDir

    ExtAPI = MyExtAPI; Ansys = MyAnsys

    Factory3DGraphicsHelper.Initialize(ExtAPI,Ansys)
    #FeBlockDataWriter does not need to be Initialized.

    Enums = Ansys.Mechanical.DataModel.Enums
    Quantity=Ansys.Core.Units.Quantity

    ApdlDir = os.path.join(ExtAPI.ExtensionManager.CurrentExtension.InstallDir,"APDL")
    ApdlPartsDir = os.path.join(ApdlDir,"Parts")
    ApdlScriptsDir = os.path.join(ApdlDir,"Scripts")
#endregion

def StartApdlInputFileWrite(Analysis):
    """
    Run this in the "BeforeSolve" callback to clear all values.
    """
    if MyApdlBoltManager==None: return
    global ActiveAnalysis; ActiveAnalysis=Analysis
    global NodeNum; NodeNum = 0
    global ElemNum ; ElemNum = 0
    global TypeNum; TypeNum = 0
    global SentFiles; SentFiles=[]
    global HeaderSent; HeaderSent=False
    global GlobalManager; GlobalManager = GlobalFilesManager()

class ApdlBoltManager:
    """
    Controller object for the ACT custom object
    """
    def __init__(self,ExtAPI,AnsysObj):
        self.AnsysObj = AnsysObj

    def oninit(self,Me):
        global MyApdlBoltManager
        MyApdlBoltManager=Me
        LoadXmlApdlBolts()

    def onremove(self,Me):
        global MyApdlBoltManager; MyApdlBoltManager=None
    def GetMechanicalObj(self):
        Id = self.AnsysObj.InternalObject.ID
        return ExtAPI.DataModel.GetObjectById(Id)

class ApdlBolt:
    """
    Controller object for the ACT custom object
    """
    def __init__(self,ExtAPI,AnsysObj):
        self.AnsysObj = AnsysObj
        self.ApdlBoltData = {}      #Dictionary of BoltData Objects for each selected part.
        self.Graphics = []      #List of all Factory3D graphics entities shown

    #region ACT callbacks
    def onadd(self,Me):
        Me.Attributes["UserCmds"]=[]    #Add an attribute for user commands

    def onshow(self,Me):
        #If you have some graphics in the list then they were "Visible"
        #You don't need to show them again.
        if len(self.Graphics)==0:
            with ExtAPI.Graphics.Suspend():
                self._DisplayGraphics(Me)
                self.UpdateGraphics(Me,FullUpdate=False)

    def onhide(self,Me):
        if Me.Properties["Display/Visible"].Value=="No":    #Check if you need to clear graphics or keep.
            self.ClearGraphics()

    def onsuppress(self,Me):
        self.ClearGraphics()

    def onunsuppress(self,Me):
        pass

    def onremove(self,Me):
        self.ClearGraphics()    #Clear any graphics

    def oninit(self,Me):
        if Me.Properties["Display/Visible"].Value=="Yes":
            with ExtAPI.Graphics.Suspend():
                self._DisplayGraphics(Me)
                self.UpdateGraphics(Me,FullUpdate=False)

    def onterminate(self,Me):
        self.ClearGraphics()    #Clear any graphics
    #endregion

    def ClearGraphics(self):
        """
        Delete all the graphics entities and start with empty list
        """
        with ExtAPI.Graphics.Suspend():
            for G in self.Graphics:
                try: G.Delete()
                except:pass
        self.Graphics=[]

    def UpdateGraphics(self,Me,FullUpdate=True):
        """
        Update the gaphics shown for the object.
        Called by OnShow
        """
        with ExtAPI.Graphics.Suspend():
            if FullUpdate:      #Full update will delete and re-create graphics new.
                self.ClearGraphics(); self.onshow(Me)
            #If not Full, then only update properties of the exisiting garphics.
            for G in self.Graphics:
                try: G.Translucency=Me.Properties["Display/Transparency"].Value
                except:pass
                try: G.DepthTest=Me.Properties["Display/DepthTest"].Value=="Yes"
                except:pass

    def GetMechanicalObj(self):
        Id = self.AnsysObj.InternalObject.ID
        return ExtAPI.DataModel.GetObjectById(Id)

    def _DisplayGraphics(self,Obj):
        """
        Loop through all selected CS.
        """
        #region get CS Ids
        Ids = None
        try:Ids = Obj.Attributes["CsIds"]
        except:pass
        if Ids==None:return
        self.GetData(Obj,False)
        #endregion 
        CadUnits = Factory3DGraphicsHelper.GetCadLengthUnit()
        ModelUnits=Factory3DGraphicsHelper.GetModelLengthUnit()
        for key in self.ApdlBoltData.keys():
            Data = self.ApdlBoltData[key]
            if Data!=None:
                GM = Data.MyGraphicsManager
                for Id in Ids:
                    CS = ExtAPI.DataModel.GetObjectById(Id)
                    GM.Show()
                    Graphics = [Sec.Graphic for Sec in GM.Sections.values()]

                    if key=="Bolt" or key=="BoltWasher":
                        TranslateVal = Obj.Attributes["Bolt_ZLoc"]
                    elif key=="Nut":
                        TranslateVal = Obj.Attributes["Nut_ZLoc"]
                    elif key=="NutWasher":
                        TranslateVal = Obj.Attributes["NutWasher_ZLoc"]
                    if TranslateVal!=0:
                        Factory3DGraphicsHelper.TranslateAlongAxis(Graphics,TranslateVal,[0,0,1],ConvertValue=False)
                    self.Graphics.extend(Graphics)
                    Factory3DGraphicsHelper.MoveGraphicsToCoordSys(Graphics,CS,ModelUnits,CadUnits)

    def GetData(self,Me,UpdateGraphics=True):
        """
        Get the stored data for the bolt object from the database.
        Update graphics if specified.
        """
        MyDict = ApdlBoltDict
        PartDataNames = []
        PropNames = ["Parts/BoltName","Parts/BoltWasherName","Parts/NutName","Parts/NutWasherName"]
        for PropName in PropNames:
            PartDataName = Me.Properties[PropName].Value
            Data = None
            try:
                Data = ApdlBoltDict[PartDataName]
            except Exception as e:pass
            self.ApdlBoltData[PropName.replace("Parts/",'').replace("Name",'')]=Data

        #Figure out Z Locations of all parts
        BoltWasherHeight = Quantity(0,'mm')
        try:BoltWasherHeight = self.ApdlBoltData["BoltWasher"].Inputs["Height"].Value
        except Exception as e: pass
        NutWasherHeight = Quantity(0,'mm')
        try:NutWasherHeight = self.ApdlBoltData["NutWasher"].Inputs["Height"].Value
        except Exception as e: pass

        CadLenUnit = Factory3DGraphicsHelper.GetCadLengthUnit()

        Bolt_ZLoc = units.ConvertUnit(-BoltWasherHeight.Value,BoltWasherHeight.Unit,CadLenUnit,"Length")
        Me.Attributes["Bolt_ZLoc"] = Bolt_ZLoc

        NutLocProp = Me.Properties["Parts/NutLoc"]
        NutLocQuantity = Quantity(NutLocProp.Value,NutLocProp.UnitString)
        NutWasherLoc = units.ConvertUnit(NutLocQuantity.Value,NutLocQuantity.Unit,CadLenUnit,"Length")
        Me.Attributes["NutWasher_ZLoc"] = NutWasherLoc

        NutLocZ = NutLocQuantity + NutWasherHeight
        NutLocZ = units.ConvertUnit(NutLocZ.Value,NutLocZ.Unit,CadLenUnit,"Length")
        Me.Attributes["Nut_ZLoc"] = NutLocZ

        if UpdateGraphics: self.UpdateGraphics(Me)

def ApdlBolt_GetCommands(Obj,SolverData,Stream, ApdlLocation):
    """
    General routine for sending APDL commands.
    """
    #region Send Header
    #Determine if you have sent the starting header for any APDL Bolt objects
    #This is only sent once for the entire input file, so global flag is used to track if input.
    global HeaderSent
    global GlobalManager
    if not HeaderSent:
        Text = "!****** Start sending data for APDL Bolt Manager and Child Objects  ******"+'\n'
        Text += "!Unit system from Mechanical"+'\n'
        Text +="_MechUnitSys = '"+str(ExtAPI.DataModel.Project.UnitSystem)+"'\n\n"
        Stream.Write(Text)

        try:
            GlobalManager.GetGlobalData()
            if GlobalManager.GlobalText!="":
                Stream.Write("!Global file text.  This is at the start of the APDL Bolt Manager inputs and only appears once.")
                Stream.Write(GlobalManager.GlobalText+'\n\n')
        except Exception as e:
            WriteApdlStreamError(Stream,e)

        HeaderSent=True
    #endregion

    #First send all assembly level values from the object
    try:Obj.Controller.GetData(Obj, UpdateGraphics=False)
    except Exception as e:
        WriteApdlStreamError(Stream,e)
    try:
        CsIds = Obj.Attributes["CsIds"]
        if CsIds==None:
            Stream.Write("*MSG,ERROR\nNo CS selected for APDL Bolt.  Run terminated")
            return
    except Exception as e:
        ApdlText+=WriteApdlError(e)

    Id = str(Obj.Controller.AnsysObj.InternalObject.ID)
    Stream.Write("!APDL Bolt Assembly object: "+str(Id)+'\n')
    Stream.Write('_MechObjId = '+Id+'\n')

    Step = str(SolverData.CurrentStep)
    Stream.Write('_MechAnalysisStep = '+Step+'\n')

    ApdlText = ""
    #region write Coordinate Systems Info
    try:
        ApdlText+="!Coordinate System Ids:"+'\n'
        NumCs = len(CsIds)
        ApdlText+="*DIM,_ApdlBoltCsIds,ARRAY,"+str(NumCs)+'\n'
        for i in range(NumCs):
            CS = ExtAPI.DataModel.GetObjectById(CsIds[i])
            #If you have an APDL name use that, otherwise use the CsApdlId
            if CS.APDLName=="": CsIdtext = str(CS.CoordinateSystemID)
            else: CsIdtext = CS.APDLName
            ApdlText+="_ApdlBoltCsIds("+str(i+1)+") = " + CsIdtext +'\n'
        ApdlText+="!End Coordinate System Ids"+'\n'
    except Exception as e: ApdlText+=WriteApdlError(e)
    #endregion

    #region Write local Z locations for parts.
    try:
        FromUnit = Factory3DGraphicsHelper.GetCadLengthUnit()
        def SendZLocToApdl(AttributeName, ApdlName):
            Val= Obj.Attributes[AttributeName]
            ConvertedVal = units.ConvertUnitToSolverConsistentUnit(ExtAPI,Val,FromUnit,"Length",ActiveAnalysis)
            Text = ApdlName+"="+str(ConvertedVal)+'\n'
            return Text

        ApdlText+="!Values for Z location in local CS for parts"+'\n'
        ApdlText+=SendZLocToApdl("Bolt_ZLoc","_BoltZLoc")
        ApdlText+=SendZLocToApdl("NutWasher_ZLoc","_NutWasherZLoc")
        ApdlText+=SendZLocToApdl("Nut_ZLoc","_NutZLoc")
    except Exception as e: ApdlText+=WriteApdlError(e)
    #endregion 
    Stream.Write(ApdlText)

    #Done sendin assembly object information 
    #Start with the part data APDL commands.
    try:
        for Level in ["PART","ASSEMBLY"]:       #Make two passes for Part then Assembly Level.
            for key in Obj.Controller.ApdlBoltData.keys():  #Loop through all parts data
                AssemblyComp = key  #Component of the assembly like Bolt, Nut, Washer etc...

                #Write any user snippet text to the correct part of the file.
                try:
                    Snippets = GetUserSnippets(Obj, ApdlLocation, AssemblyComp, Level)
                    if Snippets!=None:
                        for Snippet in Snippets:
                            ApdlText='\n'+"!User Snippet:" +Snippet.Name +"\n"+Snippet.Text+'\n'
                            Stream.Write(ApdlText)
                except Exception as e:
                    Stream.Write(WriteApdlError(e))
                try:
                    Data=None
                    try:Data = Obj.Controller.ApdlBoltData[key]
                    except:pass
                    if Data!=None:
                        FilesToSend = []
                        for File in Data.ApdlInputFiles:
                            if StringMatch(File.Level,Level) and StringMatch(File.Location, ApdlLocation):
                                FilesToSend.append(File)
                        if len(FilesToSend)==0:
                            ApdlText ='\n'+"!No Files for "+ApdlLocation+" APDL input for "+Data.Name+ " at "+Level+" Level as "+AssemblyComp +'\n'
                        else:
                            ExtAPI.Log.WriteMessage("Write "+ApdlLocation+" APDL input for "+Data.Name+ " at "+Level+" Level as "+AssemblyComp)
                            ApdlText =""
                            ApdlText += '\n' "/COM,****** Sending " + Data.Name+ " at "+Level+" Level as "+AssemblyComp+" ******"
                            ApdlText += '\n'+"PartNameInAssembly = '"+AssemblyComp+"'"+'\n'
                            ApdlText += "InputLevel = '"+Level+"'"+'\n'
                            ApdlText += "PartFileName = '"+ Data.Name +"'"+'\n'
                            #Write any global files for parts
                            try:
                                if GlobalManager.GlobalPartText!="":
                                    ApdlText+='\n'"!User PartGlobal file text.  This is sent at the start of each part."+'\n'
                                    ApdlText+=GlobalManager.GlobalPartText+'\n\n'
                            except Exception as e:
                                ApdlText+=WriteApdlError(e)

                            ApdlText += Data.WriteToApdlInput(Obj, ApdlLocation, SolverData, CsIds,Level,AssemblyComp)+'\n'
                            ApdlText +="/COM,Done Sending " + Data.Name + " at "+Level+" Level as "+AssemblyComp+'\n'
                except Exception as e:
                    ApdlText+=WriteApdlError(e)
                if Data!=None: Stream.Write(ApdlText)
    except Exception as e:
        ApdlText+=WriteApdlError(e)

def ApdlBolt_GetCommands_Pre(Obj,SolverData,Stream):
    """
    Pre commands for the ApdlBolt ACT Object
    """
    ApdlBolt_GetCommands(Obj,SolverData,Stream,"Pre")
    pass

def ApdlBolt_GetCommands_Solve(Obj,SolverData,Stream):
    ApdlBolt_GetCommands(Obj,SolverData,Stream,"Solve")
    pass

def ApdlBolt_GetCommands_Post(Obj,SolverData,Stream):
    ApdlBolt_GetCommands(Obj,SolverData,Stream,"Post")
    pass

class ApdlBoltData:
    """
    class holder of information for a ApdlBolt object
    """
    def __init__(self):
        self.FilePath = None    #Path to xml data file.
        self.LoadErrors = False
        self.LoadErrorMsg=None

        self.Name = None
        self.Description = None
        self.PartType = None
        self.Inputs = {}        #Dictionary of inputs.  keys = Input.ApdlName, values = Input.
        self.ApdlInputFiles = []    #List of Apdl input files
        self.MyGraphicsManager = self.GraphicsManager(self)

    class ApdlInputFile:
        """
        Holder of information about an input file that should be inserted for this part.
        """
        def __init__(self):
            self.Name = None        #Name of APDL input file like 'BoltSetup1.inp'
            self.Location = None    #Its location "Pre", "Solve", "Post"
            #Flag for Part or Assembly level
            #One round of file inputs is sent for Part, then a second for Assembly.
            self.Level = None

            #Options for copying the file rather than inputing the text.
            self.FullPath=None      #Full path to file.
            self.CopyAs = None      #Flag to copy the file to working directory only.
            self.DistKey=0          #Option for copy operation in ADPL
            self.SendOnceOnly = None   #Option to only send the file once to the stream.  tracked with global list.
            self.IterateBlockIds=False      #Option to iterate Ids in NBLOCK EBLOCK and CMBLOCK

            self.Step = None
            #Values for iterating Mechanicals internal Ids for this input file.
            self.IsIterator = False     #Flag for if you iterate internal Ids
            self.IsUpdater = False      #Flag for if you update internal Ids (only once and tracked in python and APDL)
            self.UpdateAttributeName = None
            self.NodeNum= None
            self.ElementNum = None
            self.TypeNum  = None
            self.PerCoordinateSystem = False

        def WriteToXml(self,Indent):
            """Write the input to an XML node."""
            if self.IsIterator:
                XmlText = Indent+"<IterateMechRefIds"
                if self.NodeNum!=None:
                    XmlText += " Node='"+str(self.NodeNum)+"'"
                if self.ElementNum!=None:
                    XmlText += " Element='"+str(self.ElementNum)+"'"
                if self.TypeNum!=None:
                    XmlText += " Type='"+str(self.TypeNum)+"'"
                if self.PerCoordinateSystem!=None:
                    XmlText += " PerCoordinateSystem='"+str(self.PerCoordinateSystem)+"'"
                XmlText += "/>"
            elif self.IsUpdater:
                XmlText = Indent+"<UpdateMechRefIds"
                if self.UpdateAttributeName!=None:
                    XmlText+=" AttributeName='"+str(self.UpdateAttributeName)+"'"
                XmlText += "/>"
            else:
                XmlText=Indent+"<File"
                if self.IterateBlockIds!=None:
                    XmlText+=" IterateBlockIds='"+str(self.IterateBlockIds)+"'"
                if self.Step!=None:
                    XmlText+=" Step='"+str(self.Step)+"'"
                if self.CopyAs!=None:
                    XmlText+=" CopyAs='"+self.CopyAs+"'"
                if self.SendOnceOnly!=None:
                    XmlText+=" SendOnceOnly='"+self.SendOnceOnly+"'"
                XmlText+=">"+self.Name+"</File>"
            return XmlText

        def WriteToApdl(self, SolverData):
            """
            Write to APDL input file at solve time.
            SolverData = Passed from GetCommands Callback
            NumCs = Number of CS assigned to object
            """
            ApdlText=""
            try:
                if self.CopyAs!=None:     #Print APDL commands to copy the file.
                    if self.CopyAs=="": CopyName = self.Name
                    else: CopyName = self.CopyAs
                    FullPath=self.FullPath.replace("/","\\")
                    ApdlText+="/INQUIRE,_FileExists,EXISTS,'"+CopyName+"'"+'\n'
                    ApdlText+="*IF,_FileExists,NE,1,THEN"+'\n'
                    ApdlText+="  /COPY,'"+FullPath+"',,,'"+CopyName+"',,,"+str(self.DistKey)+'\n'
                    ApdlText+="*ENDIF"+'\n'
                    ApdlText+="*SET,_FileExists"+'\n'
                else:       #Put the Text as-is into the APDL
                    SendText = True
                    if self.SendOnceOnly!=None:
                        if self.SendOnceOnly.upper()=='TRUE':
                            if self.Name in SentFiles:
                                SendText=+False
                    if SendText:
                        ApdlText+=self.GetFileText()
                    else:   
                        ApdlText+="!"+self.Name +" send previously and not sent again at user specification."+'\n'
                SentFiles.append(self.Name)
            except Exception as e: ApdlText+=WriteApdlError(e)
            return ApdlText

        def UpdateMechRefIds(self,Obj, PartNameInAssembly, SolverData):
            """
            Iterate the internal Mechanical ref Ids. 
            Send this info to globals for module tracking and iterating file Ids later.
            Write the new values as APDL variables.
            """
            global NodeNum; NodeNum = SolverData.GetNewNodeId()
            global ElemNum; ElemNum = SolverData.GetNewElementId()
            global TypeNum; TypeNum = SolverData.GetNewElementType()
            ApdlText = "!Update of Mechanical input file Ids:"+'\n'
            ApdlText += "_MechNodeId="+str(NodeNum)+'\n'
            ApdlText += "_MechElemId="+str(ElemNum)+'\n'
            ApdlText += "_MechElemTypeId="+str(TypeNum)+'\n'

            if self.UpdateAttributeName!=None:
                Obj.Attributes[PartNameInAssembly+"_"+self.UpdateAttributeName+"_Type"]=TypeNum
                Obj.Attributes[PartNameInAssembly+"_"+self.UpdateAttributeName+"_Node"]=NodeNum
                Obj.Attributes[PartNameInAssembly+"_"+self.UpdateAttributeName+"_Elem"]=ElemNum

            return NodeNum, ElemNum, TypeNum, ApdlText 

        def IterateMechRefIds(self, SolverData, NumCs):
            ApdlText="!New Mechanical internal Ids:"
            if self.PerCoordinateSystem==False: NumCs=1
            #Iterate the Ids and print to variables in APDL.
            global NodeNum; global ElemNum; global TypeNum
            if self.NodeNum!=None:
                NumNewNodes = self.NodeNum*NumCs
                for i in range(NumNewNodes):
                    NodeNum = SolverData.GetNewNodeId()
                ApdlText+="Nodes="+str(NodeNum)+': '
            if self.ElementNum!=None:
                NumNewElems = self.ElementNum*NumCs
                for i in range(NumNewElems):
                    ElemNum = SolverData.GetNewElementId()
                ApdlText+="Elems="+str(ElemNum)+': '
            if self.TypeNum!=None:
                NumNewElemTypes = self.TypeNum*NumCs
                for i in range(NumNewElemTypes):
                    TypeNum = SolverData.GetNewElementType()
                ApdlText+="Types="+str(TypeNum)
            ApdlText+='\n'
            return ApdlText 

        def SetValuesFromXmlNode(self,Node,ApdlLocation, Level):
            self.Location=ApdlLocation
            self.Level = Level

            if Node.tag.upper()=="UpdateMechRefIds".upper():
                self.IsUpdater=True
                self.UpdateAttributeName = TryGetAttribValue(Node,'AttributeName')
            elif Node.tag.upper()=="IterateMechRefIds".upper():
                self.IsIterator=True
                self.NodeNum = TryGetAttribValue(Node,'Node')
                if self.NodeNum!=None:
                    self.NodeNum = int(self.NodeNum)
                self.ElementNum = TryGetAttribValue(Node,'Element')
                if self.ElementNum!=None:
                    self.ElementNum = int(self.ElementNum)
                self.TypeNum = TryGetAttribValue(Node,'Type')
                if self.TypeNum!=None:
                    self.TypeNum = int(self.TypeNum)
                self.PerCoordinateSystem = TryGetAttribValue(Node,'PerCoordinateSystem')
                if self.PerCoordinateSystem == None:
                    self.PerCoordinateSystem =False
                else:
                    self.PerCoordinateSystem=(self.PerCoordinateSystem.upper()=="TRUE")

            else:
                self.Name = Node.text
                self.FullPath = os.path.join(ApdlScriptsDir,Node.text).replace("/","\\")
                self.CopyAs = TryGetAttribValue(Node,"CopyAs")
                self.SendOnceOnly = TryGetAttribValue(Node,"SendOnceOnly")
                self.Step = TryGetAttribValue(Node,"Step")
                self.IterateBlockIds = TryGetAttribValue(Node,"IterateBlockIds")
                if self.IterateBlockIds!=None:
                    self.IterateBlockIds=(self.IterateBlockIds.upper()=="TRUE")

        def GetFileText(self):
            """
            Get Text of the file.
            If self.IterateBlockIds=True: Iterates Ids
            """
            if self.IterateBlockIds:
                if os.path.exists(self.FullPath):
                    DW = FeBlockDataWriter.DataWriter()
                    DW.ReadFilePath = self.FullPath
                    DW.NodeStart = NodeNum-1
                    DW.ElemStart= ElemNum-1
                    DW.ElemTypeStart = TypeNum-1
                    DW.MatStart = TypeNum-1
                    DW.SecIdStart = TypeNum-1
                    DW.RealConstStart = TypeNum-1
                    Text = DW.WriteData()
            else:
                if os.path.exists(self.FullPath):
                    File = open(self.FullPath,'r')
                    Text = File.read()
                    File.close()
                else:
                    Text="*MSG,ERROR"+'\n'
                    Text+="File not found: "+self.FullPath+'\n'
            Text+='\n'
            return Text

    class Input:
        def __init__(self,ApdlName = None, Value = None):
            self.ApdlName=ApdlName              #APDL Variable name to write.
            self.ApdlLocation = "Pre"        #Location in APDL input file to write: Example 'Pre'
            self.Type = None            #Type of value i.e. Float, Quantity etc....
            self.QuantityName = None    #Name of quantity like "Length", "Force"
            self.Value = Value          #Value interpreted based on Type
            self.Description = ""     #user description of the value

        def WriteToApdl(self, MechLenUnit=None):
            """
            Write the input to APDL based on APDL variable name and value
            Quantity values for Length will be converted to solver units.
            """
            ApdlText=""
            try:
                if self.Type=="Quantity":
                    Quantity = self.Value
                    Value = Quantity.Value
                    FromUnit = Quantity.Unit
                    ConvertedValue = units.ConvertUnitToSolverConsistentUnit(ExtAPI,Value,FromUnit,self.QuantityName, ActiveAnalysis)
                    ApdlText += self.ApdlName+" = "+str(ConvertedValue) + "\t!"+self.Description+": "+str(Quantity)+'\n'
                elif self.Type=="Text":
                    ApdlText += self.ApdlName+" = '"+self.Value+ "'\t!"+self.Description+'\n'
                else:
                    ApdlText += self.ApdlName+" = "+str(self.Value) + "\t!"+self.Description+'\n'
            except Exception as e: ApdlText+=WriteApdlError(e)
            return ApdlText

        def WriteToXml(self,Indent):
            """Write the input to an XML node."""
            XmlText=Indent
            XmlText+="<Input ApdlName='"+self.ApdlName+"' Description='"+self.Description+"' "
            XmlText+="Type='"+self.Type+"'"
            if self.QuantityName!=None:
                XmlText+=" QuantityName='" + self.QuantityName+"'"
            XmlText+=">"+str(self.Value)+"</Input>"
            return XmlText

        def SetValuesFromXmlNode(self,Node,ApdlLocation):
            self.ApdlLocation = ApdlLocation
            self.ApdlName = TryGetAttribValue(Node,"ApdlName")
            self.Description = TryGetAttribValue(Node,"Description")
            self.Type = TryGetAttribValue(Node,"Type")
            self.QuantityName = TryGetAttribValue(Node,"QuantityName")

            InputTypeStr = self.Type.upper().strip()
            if InputTypeStr=="QUANTITY":
                self.Value = Quantity(Node.text)
            elif InputTypeStr=="TEXT":
                self.Value = Node.text
            elif InputTypeStr=="FLOAT":
                self.Value = float(Node.text)

    class GraphicsManager:
        """
        Manages how the parts will be displayed in Mechanical with Factory3D graphics.
        """
        def __init__(self, Data):
            self.Data = Data        #Parent Data object
            self.Sections = {}

        class Section:
            def __init__(self, Manager):
                self.Manager = Manager
                self.RadiusInput = None; self.HeightInput = None; self.HeadTypeInput = None
                self.ZLocInput = None
                self.Name = None
                self.DefaultRed = 200; self.DefaultBlue = 200; self.DefaultGreen=200
                self.Red = self.DefaultRed; self.Blue=self.DefaultBlue; self.Green = self.DefaultGreen

                self.Graphic=None       #List of GraphicInstance to track where section is displayed.

            def SetColor(self):
                self.Graphic.Color = (self.Red<<16)+(self.Green<<8)+self.Blue

            def WriteToXml(self,Indent):
                """Write the info to an XML node."""
                def WriteProp(Name,Value,IsColor=False,DefaultValue = None):
                    if IsColor:
                        if Value!=DefaultValue:
                            Out = " "+Name+"='"+str(Value)+"'"
                        else: Out=""
                    else:
                        if Value!=None:Out = " "+Name+"='"+str(Value)+"'"
                        else: Out =""
                    return Out

                Out = Indent+"<"+self.Name
                Out += WriteProp("Radius", self.RadiusInput)
                Out += WriteProp("Height", self.HeightInput)
                Out += WriteProp("ZLoc", self.ZLocInput)
                Out += WriteProp("HeadType", self.HeadTypeInput)
                Out += WriteProp("Red",self.Red,True,self.DefaultRed)
                Out += WriteProp("Green",self.Green,True,self.DefaultGreen)
                Out += WriteProp("Blue",self.Blue,True,self.DefaultBlue)
                Out+="></"+self.Name+">"
                return Out

            def GetRadius(self): return self.Manager.Data.Inputs[self.RadiusInput].Value
            def GetHeight(self): return self.Manager.Data.Inputs[self.HeightInput].Value
            def GetHeadType(self): return self.Manager.Data.Inputs[self.HeadTypeInput].Value
            def GetZLoc(self): return self.Manager.Data.Inputs[self.ZLocInput].Value

        def Show(self):
            """
            General routine to show a part
            Will show specific based on type
            """
            if self.Data.PartType=="Bolt": self._ShowBolt()
            if self.Data.PartType=="Nut": self._ShowNut()
            if self.Data.PartType=="Washer": self._ShowWasher()
            for Sec in self.Sections.values(): Sec.SetColor()

        def _ShowBolt(self):
            MakeCyl = Factory3DGraphicsHelper.CreateCylinderFromQuantities
            Sec = self.Sections["Head"]
            Sec.Graphic=MakeCyl(Sec.GetRadius(),Sec.GetHeight(),-Sec.GetHeight())
            if Sec.GetHeadType()=="Hex": Sec.Graphic.Samples=6
            else: Sec.Graphic.Samples=16
            Sec = self.Sections["Shank"]
            Sec.Graphic=MakeCyl(Sec.GetRadius(),Sec.GetHeight())
            Sec = self.Sections["Thread"]
            Sec.Graphic=MakeCyl(Sec.GetRadius(),Sec.GetHeight(),self.Sections["Shank"].GetHeight())
            #Optional Graphics
            Sec = None
            try: Sec = self.Sections["Preload"]
            except:pass
            if Sec!=None:
                MakeCirc = Factory3DGraphicsHelper.CreateCircleFromQuantities
                Sec.Graphic=MakeCirc(Sec.GetRadius(),Sec.GetZLoc())
            Sec = None
            try: Sec = self.Sections["HeadFlange"]
            except:pass
            if Sec!=None:
                Sec.Graphic=MakeCyl(Sec.GetRadius(),Sec.GetHeight(),-Sec.GetHeight())
        def _ShowNut(self):
            MakeCyl = Factory3DGraphicsHelper.CreateCylinderFromQuantities
            Sec = self.Sections["Nut"]
            Sec.Graphic=MakeCyl(Sec.GetRadius(),Sec.GetHeight())
            if Sec.GetHeadType()=="Hex": Sec.Graphic.Samples=6
            else: Sec.Graphic.Samples=16

        def _ShowWasher(self):
            MakeCyl = Factory3DGraphicsHelper.CreateCylinderFromQuantities
            Sec = self.Sections["Washer"]
            Sec.Graphic=MakeCyl(Sec.GetRadius(),Sec.GetHeight())

    def Clear(self):
        self.__init__()

    def LoadFromFile(self,Path):
        """
        Load data from a source file.
        """
        try:
            self.Clear()
            self.Name = os.path.basename(Path)
            Doc = xml.etree.ElementTree.parse(Path)
            Root = Doc.getroot()

            try: self.PartType = Root.attrib["PartType"]
            except:pass

            for XmlNode in list(Root):
                if XmlNode.tag.upper()=="DESCRIPTION":
                    self.Description= XmlNode.text
                #Do Input Files.
                elif XmlNode.tag.upper()=="APDLINPUTFILES":
                    for LocNode in list(XmlNode):
                        Location = LocNode.tag
                        for LevelNode in list(LocNode):
                            Level = LevelNode.tag
                            for InputNode in list(LevelNode):
                                MyObj= self.ApdlInputFile()
                                MyObj.SetValuesFromXmlNode(InputNode,Location,Level)
                                self.ApdlInputFiles.append(MyObj)

                #Get the inputs
                elif XmlNode.tag.upper()=="INPUTS":
                    for LocNode in list(XmlNode):
                        Location = LocNode.tag
                        for InputNode in list(LocNode):
                            MyInput=self.Input()
                            MyInput.SetValuesFromXmlNode(InputNode,Location)
                            self.Inputs[MyInput.ApdlName]=MyInput

                elif XmlNode.tag.upper()=="GraphicsDisplay".upper():
                    GM = self.MyGraphicsManager
                    for InputNode in list(XmlNode):
                        Section = GM.Section(GM)
                        if InputNode.tag=="Preload":
                            Section.Name = InputNode.tag
                            Section.RadiusInput = InputNode.attrib["Radius"]
                            Section.ZLocInput = InputNode.attrib["ZLoc"]
                        else:
                            Section.Name = InputNode.tag
                            Section.RadiusInput = InputNode.attrib["Radius"]
                            Section.HeightInput = InputNode.attrib["Height"]
                            if Section.Name.upper() in ["HEAD","NUT"]:
                                Section.HeadTypeInput= InputNode.attrib["HeadType"]
                        #Get display inputs.
                        try:
                            if InputNode.attrib["Red"]!=None: Section.Red = int(InputNode.attrib["Red"])
                        except:pass
                        try:
                            if InputNode.attrib["Green"]!=None: Section.Green = int(InputNode.attrib["Green"])
                        except:pass
                        try:
                            if InputNode.attrib["Blue"]!=None: Section.Blue = int(InputNode.attrib["Blue"])
                        except:pass
                        
                        GM.Sections[InputNode.tag]=Section

            self.LoadErrors=False
        except Exception as e:
            try:
                self.LoadErrorMsg = e.message
            except Exception as e:pass
            self.LoadErrors=True

    def WriteToFile(self,FileName):
        """
        Write the information in the part to a file.
        """
        def AddNode(Tag,Text,Indent,Close=True):
            def GetNodeText(Text):
                if Text=="": return Text
                OutStr=Text
                OutStr.replace("\"",'&quot;')
                OutStr=OutStr.replace("'",'&apos;')
                OutStr=OutStr.replace("<",'&lt;')
                OutStr=OutStr.replace(">",'&gt;')
                OutStr=OutStr.replace("&",'&amp;')
                return OutStr
            NodeText = GetNodeText(Text)
            if Close:
                Out = Indent+"<"+Tag
                Out +=">"+NodeText+"</"+Tag+">"+'\n'
            else:
                Out = Indent+"<"+Tag
                Out+=">"+NodeText+'\n'
            return Out
        def CloseNode(Tag,Indent):
            return Indent+"</"+Tag+">"+'\n'
        Text ="<Part PartType='"+self.PartType+"'>"+'\n'
        Text +=AddNode("Description",self.Description,"  ",Close=True)

        #Do Inputs
        Text +=AddNode("Inputs","","  ",Close=False)
        for Location in ["Pre","Solve","Post"]:
            Text+=AddNode(Location,"","    ",False)
            for MyInput in self.Inputs.values():
                if StringMatch(MyInput.ApdlLocation,Location):
                    Text+=MyInput.WriteToXml("      ")+'\n'
            Text += CloseNode(Location,'    ')
        Text += CloseNode("Inputs",'  ')
        #Do graphics display
        Text +=AddNode("GraphicsDisplay","","  ",Close=False)
        for Section in self.MyGraphicsManager.Sections.values():
            Text+=Section.WriteToXml("    ")+'\n'
        Text += CloseNode("GraphicsDisplay",'  ')

        #Do ApdlInput Files
        Text+=AddNode("ApdlInputFiles","","  ",Close=False)
        for Location in ["Pre","Solve","Post"]:
            Text+=AddNode(Location,"","    ",Close=False)
            for Level in ["Part","Assembly"]:
                Text+=AddNode(Level,"","      ",Close=False)
                for MyFile in self.ApdlInputFiles:
                    if StringMatch(MyFile.Location,Location) and StringMatch(MyFile.Level,Level):
                        Text+=MyFile.WriteToXml("        ")+'\n'
                Text+=CloseNode(Level,"      ")
            Text+=CloseNode(Location,"    ")
        Text += CloseNode("ApdlInputFiles",'  ')

        Text += CloseNode("Part",'')
        File = open(os.path.join(ApdlPartsDir,FileName),'w')
        File.write(Text)
        File.close()

    def WriteToApdlInput(self,Obj, Location, SolverData, CsIds, Level, PartNameInAssembly):
        """
        Write data to APDL input format.
        """
        ApdlText=""

        #region Write all APDL input variables
        try: 
            for MyInput in self.Inputs.values():
                if StringMatch(MyInput.ApdlLocation,Location):
                    ApdlText+=MyInput.WriteToApdl()
        except Exception as e: ApdlText+=WriteApdlError(e)
        #endregion

        #region Write all APDL input files from user.
        #Check for correct APDL input file location and level (Part/Assembly)
        try:
            NumCs = len(CsIds)
            for MyFile in self.ApdlInputFiles:
                if StringMatch(MyFile.Location,Location):
                    if StringMatch(MyFile.Level,Level):

                        #Iterate the internal mech ids by given amounts.
                        if MyFile.IsIterator:
                            ApdlText+=MyFile.IterateMechRefIds(SolverData,NumCs)
                        elif MyFile.IsUpdater:
                            #Update the internal trackers for Mech things.
                            #Send new ids text to APDL stream
                            NodeRef,ElemRef,TypeRef,UpdaterApdlText = MyFile.UpdateMechRefIds(Obj, PartNameInAssembly, SolverData)
                            ApdlText+=UpdaterApdlText
                        else:
                            ApdlText+=MyFile.WriteToApdl(SolverData)

        except Exception as e: ApdlText+=WriteApdlError(e)
        #endregion

        return ApdlText

#region Helpers
def WriteApdlError(e, Type="ERROR"):
    """
    Write an error to the APDL input stream
    """
    ErrorText=""
    try:ErrorText += '\n'+"/COM,"+e.message
    except:ErrorText += '\n'+"/COM,Unknown ACT error"
    try:ErrorText +='\n'+"*MSG,"+Type+'\n'+"ACT Object error.  Run Terminated"+'\n'
    except:pass
    return ErrorText

def StringMatch(Str1,Str2):
    return Str1.upper()==Str2.upper()

def TryGetAttribValue(Node,AttribName):
    Val = None
    try: Val = Node.attrib[AttribName].strip()
    except Exception as e:pass
    return Val

def GetPropConvertedValue(Prop, Analysis):
    """
    Convert a property from the ACT .xml definition to an analysis-unit-converted value
    """
    Val = units.ConvertUnitToSolverConsistentUnit(ExtAPI,Prop.Value,Prop.UnitString,Prop.unit, Analysis)
    return Val

def SendPropToApdl(Prop, Analysis, ApdlName):
    ConvertedVal = GetPropConvertedValue(Prop,Analysis)
    return ApdlName+"="+str(NutOffsetVal)+'\n'
#endregion

def LoadXmlApdlBolts(Folder=None):
    global ApdlBoltDict
    BoltDict = {}
    if Folder==None: Folder = ApdlPartsDir
    Files=os.listdir(Folder)
    XmlFiles = list(filter(lambda F: F.upper().endswith(".XML"), Files))
    for F in XmlFiles:
        Data = ApdlBoltData()
        Data.LoadFromFile(os.path.join(Folder,F))
        BoltDict[Data.Name]=Data
    ApdlBoltDict=BoltDict

def SelectCoordinateSystems(Obj,Prop):
    """
    Routine to select coordinate systems for ApdlBolt object
    """
    if Prop.Value == "No": return
    Prop.Value = "No"

    import MechTreeControl
    MechTreeControl.Initialize(ExtAPI,Ansys)
    import AttachControlToMechanical
    AttachControlToMechanical.Initialize(ExtAPI,Ansys)

    Model=ExtAPI.DataModel.Project.Model
    CsNode = MechTreeControl.GetNodeById(Model.CoordinateSystems.ObjectId)
    Nodes = MechTreeControl.GetNodesRecursive(CsNode)

    MTP = MechTreeControl.ModelTreeSelectionPanel()
    MTP.Tree.CreateNodesFromNativeNode(Nodes)
    try:
        MTP.Tree.Nodes[0].Expand()
    except Exception as e:
        pass
    MTP.ActObj = Obj; MTP.ActProp = Prop

    def SelectCsObj():
        MTP.ActObj.Properties["CS/CsIds"].Value = str(len(MTP.Tree.SelectedNodes)) + " CS"
        ControlFramPanel.HidePanel(HidePanel=False)
        Cmd="DS.Script.g_UIHandler.TreeHandler.FillTree();"
        ExtAPI.Application.ScriptByName("jscript").ExecuteCommand(Cmd)
        ObjIds = [N.AnsysObjId for N in MTP.Tree.SelectedNodes]
        MTP.ActObj.Attributes["CsIds"] = ObjIds

        MTP.ActObj.Controller.UpdateGraphics(MTP.ActObj)

    def CancelSelection():
        ControlFramPanel.HidePanel(HidePanel=False)

    MTP.SelectionMethod=SelectCsObj
    MTP.CancelMethod=CancelSelection

    ControlFramPanel = AttachControlToMechanical.ControlFramePanel(MTP,ShowHeader=False)
    ControlFramPanel.MechanicalPanelEnum = Ansys.ACT.Interfaces.Mechanical.MechanicalPanelEnum.Outline
    ControlFramPanel.AddPanelToMechanical()

#Global Files
class GlobalFilesManager:
    def __init__(self):
        self.GlobalFiles=[]
        self.GlobalPartFiles = []
        self.GlobalText = ""
        self.GlobalPartText = ""

    def GetGlobalData(self):
        try:
            self.__init__()
            GlobalPath = os.path.join(ApdlDir,"Global.xml")
            if not os.path.exists(GlobalPath):
                return
            Doc = xml.etree.ElementTree.parse(GlobalPath)
            Root = Doc.getroot()
            for XmlNode in list(Root):
                if XmlNode.tag.upper()=="GLOBAL":
                    for GlobalFileNode in list(XmlNode):
                        FileName = GlobalFileNode.text
                        self.GlobalFiles.append(FileName)
                        FullPath = os.path.join(ApdlScriptsDir,FileName)
                        File = open(FullPath,'r'); Text = File.read(); File.close()
                        self.GlobalText+='\n!****** Text from File: '+FileName+'\n'+Text
                elif XmlNode.tag.upper()=="PARTGLOBAL":
                    for GlobalFileNode in list(XmlNode):
                        FileName = GlobalFileNode.text
                        self.GlobalPartFiles.append(FileName)
                        FullPath = os.path.join(ApdlScriptsDir,FileName)
                        File = open(FullPath,'r'); Text = File.read(); File.close()
                        self.GlobalPartText+='\n!******Text from File: '+FileName+'\n'+Text
        except Exception as e:
            pass

#region User Snippets
#User snippets are APDL command snippets that are stored in the APDL bolt object
#These snippets are able to be input at different points in the object APDL input based on user input.
def ApplyUserApdlCommands(Obj,Prop):
    import ApdlBoltUserCommands; reload(ApdlBoltUserCommands) 
    ApdlBoltUserCommands.Initialize(ExtAPI,Ansys)
    ApdlBoltUserCommands.CreateUserWindow(Obj)
def GetUserSnippets(Obj, ApdlLocation, PartType, Level):
    """
    Get information about the user snippets to know what to send to the input file.
    """
    UserSnippetLists = Obj.Attributes["UserCmds"]
    if UserSnippetLists==None: return
    if len(UserSnippetLists)==0: return []
    import ApdlBoltUserCommands; reload(ApdlBoltUserCommands) 
    ApdlBoltUserCommands.Initialize(ExtAPI,Ansys)
    MySnippets = []
    for UserSnippetList in UserSnippetLists:
        Snippet = ApdlBoltUserCommands.UserApdlCommandSnippet()
        Snippet.LoadFromList(UserSnippetList)
        if ApdlLocation.upper() in [Text.upper() for Text in Snippet.ApdlLocations]:
            if PartType.upper() in [Text.upper() for Text in Snippet.ComponentNames]:
                if Level.upper() in [Text.upper() for Text in Snippet.Levels]:
                    MySnippets.append(Snippet)
    return MySnippets
#endregion
