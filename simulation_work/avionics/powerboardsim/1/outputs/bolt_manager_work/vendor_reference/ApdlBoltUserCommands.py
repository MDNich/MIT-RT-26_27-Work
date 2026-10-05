"""
Notes:

"""
#region Globals and Initialize
import clr
clr.AddReference("Ans.UI")
from Ansys.UI import *
clr.AddReference("Ans.Utilities"); clr.AddReference('Ans.UI.Toolkit'); clr.AddReference("Ans.UI.Toolkit.Base")
import Ansys.UI.Toolkit; import Ansys.Utilities

MyFont = Ansys.UI.Toolkit.Drawing.Font('Arial', 12)

def Initialize(MyExtAPI, MyAnsys):
    """
    Call this function each time you import the module to set global variables and connect with Mechanical API.
    """
    global ExtAPI; global Ansys; global Enums; global Quantity
    ExtAPI = MyExtAPI; Ansys = MyAnsys
#endregion

#region UI class controls
class ApdlCommandTreeView(Ansys.UI.Toolkit.TreeView):
    def __init__(self):
        self.Snippet = None
        self.InfoPanel = None
        self.ManagerPanel=None

        self.LabelEdit = True

        self.ContextMenu = Ansys.UI.Toolkit.ContextMenu()
        CM = self.ContextMenu
        def CreateItem(Text,Method,Contextmenu):
            MI = Ansys.UI.Toolkit.MenuItem(Text); MI.Clicked+=Method; Contextmenu.Items.Add(MI)
            return MI
        CreateItem("Add Snippet",self.AddSnippetClick,CM)
        CreateItem("Rename Snippet",self.RenameObjects,CM)
        CreateItem("Delete Snippet",self.DeleteNode,CM)
        self.MouseDown+=self.MyMouseDown
        self.SelectionChanged+=self.MySelectionChanged
        self.KeyDown+=self.MyKeyDown

    #region user action methods
    def MyKeyDown(self,Sender,Event):
        if Event.KeyCode == Ansys.UI.Toolkit.Keys.F2:
            self.RenameObjects(None,None)
        Event.SuppressKeyPress = True

    def MySelectionChanged(self,Sender, Event):
        N=None
        try: N = self.SelectedNodes[0]
        except:return
        self.ManagerPanel.NodeSelectionChanged(N)
        if self.InfoPanel!=None:
            self.InfoPanel.LoadSnippet(N.Snippet)

    def MyMouseDown(self,Sender,Event):
        if Event.Button == Ansys.UI.Toolkit.MouseButton.Right:
            self.ContextMenu.Show()
    #endregion
    #region Add/Delete snippets
    def AddSnippetClick(self,Sender,Event):
        self.AddNode("New Snippet")
        self.Save()

    def DeleteNode(self,Sender=None,Event=None):
        N=None
        try: N = self.SelectedNodes[0]
        except:return
        self.Nodes.Remove(N)
        self.Save()

    def AddNode(self, Text, Snippet=None):
        Node = self.TreeNodeEx(self)
        Node.Text = Text
        if Snippet==None:
            Node.Snippet = UserApdlCommandSnippet()
        else: Node.Snippet = Snippet
        Node.Snippet.Name = Text
        self.Nodes.Add(Node)
        self.SelectNodes([Node])
        return Node
    #endregion
    #region Rename or edit snippets
    def RenameObjects(self,Sender,Event):
        Win = RenameWindow()
        Win.RenameObjects=self.SelectedNodes
        Win.AfterRenameMethod=self.RenameBasedOnItemText
        Win.TextBox.Text=self.SelectedNodes[0].Text
        Win.Show()
        Win.TextBox.Focus()

    def RenameBasedOnItemText(self):
        for Node in self.SelectedNodes:
            Node.Snippet.Name=Node.Text
        self.Save()
    #endregion
    def Save(self):
        self.ManagerPanel.Save()

    class TreeNodeEx(Ansys.UI.Toolkit.TreeNode):
        def __init__(self,TreeView):
            self.Snippet = None

class UserSnippetInputPanel(Ansys.UI.Toolkit.TableLayoutPanel):
    """
    Panel to house the controls
    """
    def __init__(self, ManagerPanel = None):

        self.Snippet = None
        self.ManagerPanel=ManagerPanel
        self.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Absolute, 30)
        self.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Absolute, 55)
        self.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Absolute, 55)
        self.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Absolute, 55)
        self.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 100)
        self.Columns.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 100)

        self.OptionControls = []
        def AddOptionsBox(Title, ToolTip, Options, Row):
            GB = Ansys.UI.Toolkit.GroupBox(Title)
            GB.ToolTipText = ToolTip
            GB.Font = MyFont
            Panel = Ansys.UI.Toolkit.TableLayoutPanel()
            Panel.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 100)
            GB.SetControl(Panel)
            c=0
            Buttons = []
            for Text in Options:
                Panel.Columns.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 100)
                Button = Ansys.UI.Toolkit.CheckBox(Text)
                Button.Font = MyFont
                self.OptionControls.append(Button)
                Buttons.append(Button)
                Panel.Controls.Add(Button,0,c)
                c+=1
            self.Controls.Add(GB,Row,0)
            return Buttons
        r = 0
        SaveButton = Ansys.UI.Toolkit.Button("Save Changes")
        SaveButton.Font = MyFont
        SaveButton.Click+=self.SaveSnippet
        self.Controls.Add(SaveButton,r,0); r+=1
        ToolTip="Location in the APDL file where commands will be inserted"+'\n'
        ToolTip+="Pre = Before loads, Solve = Before SOLVE command, Post= After SOLVE command"
        self.LocButtons = AddOptionsBox("Apdl Location", ToolTip, ["Pre", "Solve", "Post"], r); r+=1
        ToolTip="Component for which the commands will be inserted"
        self.CompButtons = AddOptionsBox("Component in Assembly", ToolTip, ["Bolt", "Nut", "Bolt Washer", "Nut Washer"], r); r+=1
        ToolTip="Each component has commands for both 'Part' and 'Assembly' pass"
        ToolTip+="\n"+"Commands will be inserted prior to these pases, or at the end of Assembly pass with 'After' option"
        self.LevelButtons = AddOptionsBox("Level", ToolTip, ["Part", "Assembly", "After"], r); r+=1
        self.CmdBox = Ansys.UI.Toolkit.RichTextBox()
        self.CmdBox.Font = MyFont
        self.Controls.Add(self.CmdBox,r,0); r+=1

    def LoadSnippet(self,Snippet):
        self.Snippet = Snippet
        self.CmdBox.Text = Snippet.Text

        Properties = []
        Properties.extend(Snippet.ApdlLocations)
        Properties.extend(Snippet.ComponentNames)
        Properties.extend(Snippet.Levels)

        for Button in self.OptionControls:
            Button.IsChecked = (Button.Text.replace(" ","") in Properties)

    def SaveSnippet(self, Sender=None, Event=None):
        self.Snippet.Text= self.CmdBox.Text

        self.Snippet.ApdlLocations=[]
        for B in self.LocButtons:
            if B.IsChecked:
                self.Snippet.ApdlLocations.append(B.Text.replace(" ",""))
        self.Snippet.ComponentNames=[]
        for B in self.CompButtons:
            if B.IsChecked:
                self.Snippet.ComponentNames.append(B.Text.replace(" ",""))
        self.Snippet.Levels=[]
        for B in self.LevelButtons:
            if B.IsChecked:
                self.Snippet.Levels.append(B.Text.replace(" ",""))

        #Save all snippets on the manager level
        self.ManagerPanel.Save()

class UserSnippetManagerPanel(Ansys.UI.Toolkit.TableLayoutPanel):
    """
    Panel to house the controls
    """
    def __init__(self):

        self.ActObj=None

        self.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 100)
        self.Columns.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 25)
        self.Columns.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 100)

        self.Tree = ApdlCommandTreeView()
        self.Tree.ManagerPanel = self
        self.Controls.Add(self.Tree,0,0)

    def NodeSelectionChanged(self, SelectedNode):
        self.SnippetPanel = UserSnippetInputPanel()
        self.SnippetPanel.ManagerPanel=self
        self.Tree.InfoPanel = self.SnippetPanel
        self.Controls.Add(self.SnippetPanel,0,1)

    def Load(self, AttribName = "UserCmds"):
        if self.ActObj.Attributes[AttribName]==None: return
        for ObjList in self.ActObj.Attributes[AttribName]:
            Snippet = UserApdlCommandSnippet()
            Snippet.LoadFromList(ObjList)
            self.Tree.AddNode(Snippet.Name, Snippet)

    def Save(self, AttribName = "UserCmds"):
        ActObj = self.ActObj
        ActObj.Attributes[AttribName]=[]
        ActObj.NotifyChange()
        for N in self.Tree.Nodes:
            MyList = N.Snippet.SaveToList()
            ActObj.Attributes[AttribName].append(MyList)
        NumCmds = len(self.Tree.Nodes)
        if NumCmds>0:
            Text = "User Commands: " + str(NumCmds) + " In Use"
        else:
            Text = "Click to Edit"
        ActObj.Properties["Cmds/UserApdlCommands"].Value=Text
#endregion

#region Helper classes
class RenameWindow(Ansys.UI.Toolkit.Window):
    """
    Window used to rename objects
    """
    def __init__(self):
        self.Location = Ansys.UI.Toolkit.Drawing.Point(200,200)
        self.Text = 'Rename Object'
        self.Size = Ansys.UI.Toolkit.Drawing.Size(600,200)

        self.MainPanel = Ansys.UI.Toolkit.TableLayoutPanel()

        self.MainPanel.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Absolute, 25)
        self.MainPanel.Rows.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Absolute, 25)
        self.MainPanel.Columns.Add(Ansys.UI.Toolkit.TableLayoutSizeType.Percent, 50)

        self.Label = Ansys.UI.Toolkit.Label("Give New Name:")
        self.TextBox = Ansys.UI.Toolkit.RichTextBox()
        self.TextBox.KeyDown+=self.SetName
        self.MainPanel.Controls.Add(self.Label,0,0)
        self.MainPanel.Controls.Add(self.TextBox,1,0)

        self.RenameObjects = []
        self.AfterRenameMethod=None

        self.Add(self.MainPanel)
        self.TextBox.Focus()

    def SetName(self,Sender,Event):
        if Event.KeyCode == Ansys.UI.Toolkit.Keys.Enter:
            for Obj in self.RenameObjects:
                Obj.Text = self.TextBox.Text
            if self.AfterRenameMethod!=None:
                self.AfterRenameMethod()

            Event.SuppressKeyPress = True
            self.Hide()
#endregion
class UserApdlCommandSnippet:
    """
    Custom class to store information about user-input command snippets
    Used for APDL Bolt objects
    """
    def __init__(self):
        self.Name=None
        self.Text=None
        self.ApdlLocations = []    #Pre, Solve, Post
        self.ComponentNames = []   #Bolt, Nut, BoltWasher, NutWasher
        self.Levels = []           #Part, Assembly, After

    def SaveToActObjAttribute(self,ActObj,AttribName = "UserCmds"):
        if ActObj.Attributes[AttribName]==None:
            ActObj.Attributes[AttribName]=[]
        MyList = self.SaveToList()
        ActObj.Attributes[AttribName].append(MyList)

    def SaveToList(self):
        MyList = [self.Name, self.Text]
        MyList.append(self.ApdlLocations)
        MyList.append(self.ComponentNames)
        MyList.append(self.Levels)
        return MyList
    def LoadFromList(self, MyList):
        i=0
        self.Name = MyList[i];i+=1
        self.Text = MyList[i];i+=1
        self.ApdlLocations = MyList[i];i+=1
        self.ComponentNames = MyList[i];i+=1
        self.Levels = MyList[i];i+=1

def CreateUserWindow(ActObj):
    Win = Ansys.UI.Toolkit.Window()
    Panel = UserSnippetManagerPanel()
    Panel.ActObj=ActObj
    Panel.Load()
    Win.Add(Panel)
    Win.Location = Ansys.UI.Toolkit.Drawing.Point(50,50)
    Win.Text = 'Snippet Manager'
    Win.Size = Ansys.UI.Toolkit.Drawing.Size(1200,800)
    Win.Show()
