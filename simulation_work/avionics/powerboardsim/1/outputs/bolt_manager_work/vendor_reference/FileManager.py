"""
Module Notes:
Perform basic file operations and get information about file paths
"""
#region import
import os
import shutil
from glob import glob
#endregion

Log = ""

#region Direcotry inspection and modification
def DirExists(Path):return os.path.isdir(Path)

def MoveDir(SrcPath,DstPath,OverWrite=False):
    """
    Move a directory to a new location
    Args: (SrcPath,DstPath,OverWrite=False)
        SrcPath (string): Source directory 
        DstPath (string): Destination directory
        OverWrite (bool): Delete original destination directory and contents if it exists prior to move
    Returns (bool): True is successful, False if error.
    """
    try:
        DstExists = DirExists(DstPath)
        if DstExists and OverWrite==False:
            ReportStatus("Directory exists.  Did not move items. Dir: "+DstPath)
            return
        #Try to delete the directory before moving.
        if DstExists: 
            IsDeleted = DeleteDir(DstPath)
        else:
            IsDeleted=True
        if IsDeleted==False:
            ReportStatus("Destination Directory could not be deleted.  Move operation aborted.")
            return False
        shutil.move(SrcPath,DstPath)
        return True
    except Exception as e:
        ReportError(e)
        return False

def DeleteDir(Path):
    """
    Delete directory and contents.
    Args: (Path)
        Path (string): Path to directory to be deleted
    Returns (bool): True is successful, False if error.
    """
    try:
        shutil.rmtree(Path)
        return True
    except Exception as e:
        ReportError(e)
        return False

def GetSubDir(Path):
    """
    Get all subdirectories directly under the given path
    Args: (Path)
        Path (string): Path to get subdirectories
    Returns: List of string
    """
    SubDirs = []
    DirObjs = os.listdir(Path)
    for DirObj in DirObjs:
        if os.path.isdir(os.path.join(Path,DirObj)): SubDirs.append(DirObj)
    return SubDirs
#endregion

def GetFilesByExt(DirPath,ExtList,ReturnFullPaths = True):
    """
    
    """
    MyFiles = []
    MyExts = []
    if not isinstance(ExtList,list):ExtList=[ExtList]
    for Ext in ExtList: 
        if Ext.startswith("."):MyExts.append(Ext.upper())
        else:MyExts.append("."+Ext.upper())
    try:
        AllItems = os.listdir(DirPath)
        for Item in AllItems:
            FullPath = os.path.join(DirPath,Item)
            if os.path.isfile(FullPath):
                if GetExtension(FullPath).upper() in MyExts:
                    if ReturnFullPaths: MyFiles.append(FullPath)
                    else: MyFiles.append(Item)
    except Exception as e:
        ReportError(e)
        pass
    return MyFiles

def GetRecursiveFiles(Path,ExtFilter='*',NameFilter=None):
    """
    Gets all the files in a directory path including everything in all subdirectories
    Args: (Path,ExtFilter='*',NameFilter=None)
        Path
        ExtFilter (string): filter used for extensions to only get a certain file type.
            Has no '.' at start and use '*' to get all files
        NameFilter
    """
    if NameFilter==None:
        if not ExtFilter.startswith('.'): MyExtFilter='.'+ExtFilter
        else: MyExtFilter=ExtFilter
        result = [y for x in os.walk(Path) for y in glob(os.path.join(x[0], '*'+MyExtFilter))]
    else: result = [y for x in os.walk(Path) for y in glob(os.path.join(x[0], NameFilter))]
    return result

#region Get Files Names, Ext, directories etc...
def FileNameWithoutExtension(Path):return os.path.splitext(os.path.basename(Path))[0]
def GetExtension(Path): return os.path.splitext(os.path.basename(Path))[1]
#endregion

#region read/write text files
def GetFileText(Path,Mode='r',ReturnLines=False):
    """
    Get the text of a file.
    Args: (Path,Mode='r',ReturnLines=False)
        Path: Path to file to read
        Mode (string): 'r'=read (default), 'w'=write 'a'=append
        ReturnLines (bool): Option to return a list of lines rather than the text as a single string
    Returns: string or (list of string)
    """
    try:
        MyFile = open(Path,Mode)
        if ReturnLines: MyOut=MyFile.readlines()
        else: MyOut=MyFile.read()
        MyFile.close()
        return MyOut
    except Exception as e:
        ReportError(e)
        return None

def WriteTextToFile(Text,FilePath):
    """
    Write a string to a file.
    Args: (FilePath)
        FilePath: Path to file to write.
            If path directory does not exist then create it.
    Returns: True is successful, False if error.
    """
    try:
        DirName = os.path.dirname(FilePath)
        if not os.path.exists(DirName): os.mkdir(DirName)
        MyFile=open(FilePath,'w');MyFile.write(Text);MyFile.close()
        return True
    except Exception as e:
        ReportError(e)
        return False
#endregion

def GetValidPath(Path, InvalidChars="!@#$%^&*", ReplaceChar="_"):
    ValidPath = Path
    for C in InvalidChars:
        ValidPath =ValidPath.replace(C,ReplaceChar)

def ReplaceSlashes(Path, ReplaceChar="_"):
    return GetValidPath(Path,"\\/",ReplaceChar)

def ReportError(e):
    """
    General internal function to report errors
    """
    global Log; 
    try: 
        if not e.message=="":Log+='\n'+"Error: "+e.message
        else:Log+='\n'+"Error: "+e.strerror
    except Exception as e:
        Log+='\n'+"Error: "+"Could Not determine error message"

def ReportStatus(Status):
    """
    General internal function to report status
    """
    global Log; Log+='\n'+Status