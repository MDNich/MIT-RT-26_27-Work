if (!wb.hidden)
    Trace("TRACING:DSKeyframeAnimationScript started");

var g_KeyframeAnimationPaneObjects = null;
var g_KeyframeAnimationEventsConnected = false;

function initKeyframeAnimationPane() { instrument_function(arguments);
    initKeyframeAnimationCommandContainer();

    initKeyframeAnimationList();

    connectKeyframeAnimationPaneListEvents();

    doRefreshKeyframeAnimation();
}

function initKeyframeAnimationCommandContainer() { instrument_function(arguments);
    var toolbarNames = new Array();
    toolbarNames.push("ID_KeyframeManagement");
    toolbarNames.push("ID_AnimationControl");
    toolbarNames.push("ID_SubframeCount");
    toolbarNames.push("ID_CurrentFrame");

    getRibbonWrapperHelper().loadToolbars("KeyframeAnimation",
        keyframeAnimationPane.CommandBars,
        keyframeAnimationPane.CommandBarsGlobalSetttings,
        toolbarNames);
    decorateCommandBarsTooltipByName("KeyframeAnimation");
}

function connectKeyframeAnimationPaneListEvents() { instrument_function(arguments);
    if (keyframeAnimationPaneList == null)
    {
        return;
    }

    if (g_KeyframeAnimationPaneObjects != null)
    {
        return;
    }

    Trace("connectKeyframeAnimationPaneListEvents started");

    g_KeyframeAnimationPaneObjects = new KeyframeAnimationPaneObjects();

    var keyframeAnimationKeyDown = keyframeAnimationPaneList.OnKeyDown;
    keyframeAnimationKeyDown.AddCOM(g_KeyframeAnimationPaneObjects, "KeyframeAnimationPaneList_KeyDownDelegate");

    var keyframeAnimationMouseUp = keyframeAnimationPaneList.OnMouseUp;
    keyframeAnimationMouseUp.AddCOM(g_KeyframeAnimationPaneObjects, "KeyframeAnimationPaneList_MouseUpDelegate");

	var keyframeAnimationItemClick = keyframeAnimationPaneList.OnItemClick;
	keyframeAnimationItemClick.AddCOM(g_KeyframeAnimationPaneObjects, "KeyframeAnimationPaneList_ItemClickDelegate");

	Trace("connectKeyframeAnimationPaneListEvents done");
}

function disconnectKeyframeAnimationPaneListEvents() { instrument_function(arguments);
    if (keyframeAnimationPaneList == null)
    {
        return;
    }

    if (g_KeyframeAnimationPaneObjects == null)
    {
        return;
    }

    Trace("disconnectKeyframeAnimationPaneListEvents started");

    disconnectDelegate(keyframeAnimationPaneList.OnKeyDown, g_KeyframeAnimationPaneObjects, "KeyframeAnimationPaneList_KeyDownDelegate");
    disconnectDelegate(keyframeAnimationPaneList.OnMouseUp, g_KeyframeAnimationPaneObjects, "KeyframeAnimationPaneList_MouseUpDelegate");
	disconnectDelegate(keyframeAnimationPaneList.OnItemClick, g_KeyframeAnimationPaneObjects, "KeyframeAnimationPaneList_ItemClickDelegate");

    Trace("disconnectKeyframeAnimationPaneListEvents done");
}

function connectKeyframeAnimationEvents() { instrument_function(arguments);
    if (g_KeyframeAnimationEventsConnected)
        return;

    var cmd = "def OnKeyframeAnimationChangedFwd(sender, args):\n" +
        "    script_function = 'DS.Script.doRefreshKeyframeAnimationWithKeyframeCount(' + str(args.KeyframeCount) + ')'\n" +
        "    ExtAPI.Application.ScriptByName('jscript').ExecuteCommand(script_function)\n" +
        "ExtAPI.Application.EventSource.OnKeyframeAnimationChanged += OnKeyframeAnimationChangedFwd";
    ExecutePythonCommand(cmd);

    g_KeyframeAnimationEventsConnected = true;
}

function initKeyframeAnimationList() { instrument_function(arguments);
    var lvwList = 2;
    var lvwReport = 3;
    keyframeAnimationPaneList.View = lvwReport;
    keyframeAnimationPaneList.Checkboxes = false;
    keyframeAnimationPaneList.GridLines = false;
    keyframeAnimationPaneList.FullRowSelect = true;
    keyframeAnimationPaneList.MultiSelect = false;
    keyframeAnimationPaneList.HideSelection = false;
    keyframeAnimationPaneList.HideColumnHeaders = true;

    var lvwColumnCenter = 2;
    var nameWidth = 100;
    if (0 == keyframeAnimationPaneList.ColumnHeaders.Count)
        keyframeAnimationPaneList.ColumnHeaders.Add(null, null, "", nameWidth, lvwColumnCenter);

    var ccDefault = 0;
    keyframeAnimationPaneList.MousePointer = ccDefault;

    var lvwAutomatic = 0;
    var lvwManual = 1;
    keyframeAnimationPaneList.LabelEdit = lvwManual;

    var ccNone = 0;
    var ccFixedSingle = 1;
    keyframeAnimationPaneList.BorderStyle = ccNone;

    var ccFlat = 0;
    var cc3D = 1;
    keyframeAnimationPaneList.Appearance = ccFlat;
}

function KeyframeAnimationPaneObjects() { instrument_function(arguments);
    this.KeyframeAnimationPaneList_KeyDownDelegate = function keyframeAnimationPaneList_KeyDownDelegate(sender, args) { instrument_function(arguments);
        keyframeAnimationPaneList_KeyDown(args.KeyCode, args.Shift);
    }

    this.KeyframeAnimationPaneList_MouseUpDelegate = function keyframeAnimationPaneList_MouseUpDelegate(sender, args) { instrument_function(arguments);
        keyframeAnimationPaneList_MouseUp(args.Button, args.Modifiers, args.X, args.Y);
    }

	this.KeyframeAnimationPaneList_ItemClickDelegate = function KeyframeAnimationPaneList_ItemClickDelegate(sender, args) { instrument_function(arguments);
        keyframeAnimationPaneList_ItemClick();
    }

	function keyframeAnimationPaneList_MouseUp(Button, Shift, x, y) { instrument_function(arguments);
        if (Button == 1)
        {
            doApplyKeyframeAnimation();
        }
    }
	
    function keyframeAnimationPaneList_KeyDown(KeyCode, Shift) { instrument_function(arguments);
        var Del = 46;
        var Enter = 13;
        if (KeyCode == Del)
            doDeleteKeyframeAnimation();
        if (KeyCode == Enter)
            doApplyKeyframeAnimation();
    }

	function keyframeAnimationPaneList_ItemClick() { instrument_function(arguments);
		Trace("keyframeAnimationPaneList_ItemClick started");

		//Need the UI to be Refreshed for Manual Ribbon Refresh Mode.
		triggerUIRefreshCallback();
	}

}

function doAddKeyframeAnimation() { instrument_function(arguments);
    var paneWidth = keyframeAnimationPane.CommandContainer.Width;
    keyframeAnimationPaneList.ColumnHeaders.Item(1).Width = paneWidth;

    // if no keyframe is selected, add keyframe with default subframecount, if a keyframe is selected, add keyframe with selected keyframe's subframecount
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.AddKeyframe()", id_DS_AppCommandRegionGeneral);
    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex != -1)
        cmd = new DSAppCommand("subframeCount = Graphics.KeyframeAnimationUtility.GetSubframeCount(" + keyFrameIndex + ")\n" +
            "Graphics.KeyframeAnimationUtility.AddKeyframe(subframeCount)", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);

    // select the newly added keyframe (the last one)
    var listIndex = keyframeAnimationPaneList.ListItems.Count;
    var lstItem = keyframeAnimationPaneList.ListItems.Item(listIndex);
    if (lstItem)
    {
        lstItem.Selected = true;
        lstItem.Focused = true;
    }
}

function doInsertKeyframeAnimation() { instrument_function(arguments);
    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex == -1)
        return;

    var subframeCount = getSubframeCountOfSelectedKeyframe();
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.InsertKeyframe(" + keyFrameIndex + ", " + subframeCount + ")", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);

    // select the newly inserted keyframe
    var listIndex = keyFrameIndex + 1;
    var lstItem = keyframeAnimationPaneList.ListItems.Item(listIndex);
    if (lstItem)
    {
        lstItem.Selected = true;
        lstItem.Focused = true;
    }
}

function doDeleteKeyframeAnimation() { instrument_function(arguments);
    var itemCount = keyframeAnimationPaneList.ListItems.Count;
    if (itemCount < 1)
        return;

    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex == -1)
        keyFrameIndex = itemCount - 1; // if no keyframe is selected then delete the last one

    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.RemoveKeyframe(" + keyFrameIndex + ")", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function doApplyKeyframeAnimation() { instrument_function(arguments);
    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex == -1)
        return;

    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.SetCurrentFrame(" + keyFrameIndex + ", 0)", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function doModifyKeyframeAnimation() { instrument_function(arguments);
    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex == -1)
        return;

    var subframeCount = getSubframeCountOfSelectedKeyframe();
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.ReplaceKeyframe(" + keyFrameIndex + ", " + subframeCount + ")", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function doRefreshKeyframeAnimation() { instrument_function(arguments);
    var keyframeCount = 0;
    var command = "ExtAPI.Graphics.KeyframeAnimationUtility.KeyframeCount";
    keyframeCount = wb.AddinManager.Addin("AAPWBAddin").ExecuteCommand("", command);

    doRefreshKeyframeAnimationWithKeyframeCount(keyframeCount);
}

function doRefreshKeyframeAnimationWithKeyframeCount(keyframeCount) { instrument_function(arguments);
    if (keyframeAnimationPaneList == null)
    {
        return;
    }

    var paneWidth = keyframeAnimationPane.CommandContainer.Width;
    keyframeAnimationPaneList.ColumnHeaders.Item(1).Width = paneWidth;
    keyframeAnimationPaneList.ListItems.Clear();
    keyframeAnimationPaneList.Font.Size = ds.Script.GetFontSize();
    keyframeAnimationPaneList.Font.Name = localString("ID_VSFlexGridTahoma")
    keyframeAnimationPaneList.Refresh();

    //use different color based on Mechanical themes
    var colorThemePalatte = getADLColorVariableFromPreference();
    var fontColor = parseInt(colorThemePalatte.fontColor.slice(1), 16);
    var bkgColor = parseInt(colorThemePalatte.bodyColor.slice(1), 16);
    //change the list background
    keyframeAnimationPaneList.BackColor = bkgColor;

    for (var listIndex = 1; listIndex <= keyframeCount; listIndex++)
    {
        var id = keyframeAnimationPaneList.ListItems.Count;
        var lstItem = keyframeAnimationPaneList.ListItems.Add(null, null, localString("ID_Keyframe") + " " + id);
        lstItem.ForeColor = fontColor;
        lstItem.BkgndColor = bkgColor;
    }

    if (CheckKeyFrame())
        UpdateNumberOfFramesText();
}

function doLoadKeyframeAnimation() { instrument_function(arguments);
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.LoadAnimation()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function doSaveKeyframeAnimation() { instrument_function(arguments);
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.SaveAnimation()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function doExportKeyframeAnimation() { instrument_function(arguments);
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.ExportAnimationVideo()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function hasKeyFrameAnimationPaneLoaded() { instrument_function(arguments);
    if (keyframeAnimationPaneList != null)
    {
        return true;
    }

    return false;
}

function isKeyframeAnimationPaneListEmpty() { instrument_function(arguments);
    if (keyframeAnimationPaneList == null)
    {
        return true;
    }

    return keyframeAnimationPaneList.ListItems.Count < 1;
}

function atleastTwoKeyFramesPresent() { instrument_function(arguments);
    if (keyframeAnimationPaneList == null)
    {
        return false;
    }
    return keyframeAnimationPaneList.ListItems.Count > 1;
}

function doPreviousFrameKeyframeAnimation() { instrument_function(arguments);
    if (isKeyframeAnimationPaneListEmpty())
        return;

    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.PreviousFrame()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function isPlaying() { instrument_function(arguments);

    if (ExecutePythonCommand("Graphics.KeyframeAnimationUtility.IsPlaying"))
        return true;
    else
        return false;
}

function getIconForKeyframeAnimationPlayPause() { instrument_function(arguments);
    if (isPlaying())
        return "animate_pause";
    else
        return "animate_play";
}

function doPlayOrPauseKeyframeAnimation() { instrument_function(arguments);
    if (!atleastTwoKeyFramesPresent())
        return;

    if (isPlaying())
        doPauseKeyframeAnimation();
    else
        doPlayKeyframeAnimation();

    triggerUIRefreshCallback();
}

function doPlayKeyframeAnimation() { instrument_function(arguments);
    if (isKeyframeAnimationPaneListEmpty())
        return;

    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.Play()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function doPauseKeyframeAnimation() { instrument_function(arguments);
    if (isKeyframeAnimationPaneListEmpty())
        return;

    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.Pause()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function doStopKeyframeAnimation() { instrument_function(arguments);
    if (isKeyframeAnimationPaneListEmpty())
        return;

    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.Stop()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);

    triggerUIRefreshCallback();
}

function doNextFrameKeyframeAnimation() { instrument_function(arguments);
    if (isKeyframeAnimationPaneListEmpty())
        return;

    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.NextFrame()", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}

function getCurrentKeyframe() { instrument_function(arguments);
    if (!isKeyframeAnimationWindowVisible() || isKeyframeAnimationPaneListEmpty())
        return 0;

    var command = "currentFrame = ExtAPI.Graphics.KeyframeAnimationUtility.CurrentFrame\n" +
        "currentFrame.Item1";
    return wb.AddinManager.Addin("AAPWBAddin").ExecuteCommand("", command);
}

function getCurrentKeyframeText() { instrument_function(arguments);
    var currentKeyframe = getCurrentKeyframe();
    var currentKeyframeText = localString("ID_Keyframe") + ": " + currentKeyframe;
    return currentKeyframeText;
}

function getCurrentSubframe() { instrument_function(arguments);
    if (!isKeyframeAnimationWindowVisible() || isKeyframeAnimationPaneListEmpty())
        return "";

    var command = "currentFrame = ExtAPI.Graphics.KeyframeAnimationUtility.CurrentFrame\n" +
        "currentFrame.Item2";

    return wb.AddinManager.Addin("AAPWBAddin").ExecuteCommand("", command);
}

function getCurrentSubframeText() { instrument_function(arguments);
    var currentSubframe = getCurrentSubframe();
    var currentSubframeText = localString("ID_Subframe") + ": " + currentSubframe;
    return currentSubframeText;
}

function getSelectedKeyframeIndex() { instrument_function(arguments);
    var keyFrameIndex = -1;
    var selectedItem = keyframeAnimationPaneList.SelectedItem;
    if (selectedItem)
    {
        var listIndex = selectedItem.Index;
        keyFrameIndex = listIndex - 1;
    }
    return keyFrameIndex;
}

function isKeyframeSelected() { instrument_function(arguments);
    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex == -1)
        return false;

    return true;
}

function getSubframeCountOfSelectedKeyframe() { instrument_function(arguments);
    if (!isKeyframeAnimationWindowVisible() || isKeyframeAnimationPaneListEmpty())
        return 0;

    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex == -1)
        return 0;

    var subframeCount = 0;
    var command = "ExtAPI.Graphics.KeyframeAnimationUtility.GetSubframeCount(" + keyFrameIndex + ")";
    subframeCount = wb.AddinManager.Addin("AAPWBAddin").ExecuteCommand("", command);

    return subframeCount;
}

function getSubframeCountTextOfSelectedKeyframe() { instrument_function(arguments);
    var subframeCount = getSubframeCountOfSelectedKeyframe();
    var subframeCountText = "" + subframeCount;
    return subframeCountText;
}

function setSubframeCountOfSelectedKeyframe(value) { instrument_function(arguments);
    var keyFrameIndex = getSelectedKeyframeIndex();
    if (keyFrameIndex == -1)
        return;

    var subframeCount = value;
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.ModifySubframeCount(" + keyFrameIndex + ", " + subframeCount + ")", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);

    doRefreshKeyframeAnimation();
}

function getTotalTime() { instrument_function(arguments);
    if (!isKeyframeAnimationWindowVisible() || isKeyframeAnimationPaneListEmpty())
        return 0;

    var totalTime = 0;
    var command = "ExtAPI.Graphics.KeyframeAnimationUtility.GetTotalTime()";
    totalTime = wb.AddinManager.Addin("AAPWBAddin").ExecuteCommand("", command);
    totalTime = Number(totalTime);

    if (totalTime % 1 === 0)
        return Math.round(totalTime);               // keep integer
    else
        return Math.round(totalTime * 100) / 100;   // keep two decimals
}

function getTotalTimeText() { instrument_function(arguments);
    var totalTime = getTotalTime();
    var totalTimeText = "" + totalTime + " s";
    return totalTimeText;
}

function setTotalTime(value) { instrument_function(arguments);

    var strvalue = String(value);
    if (strvalue.length > 2 && strvalue.substr(strvalue.length - 1) == "s")
        strvalue = strvalue.substr(0, strvalue.length - 1); // converts ***s to ***

    if (isNaN(strvalue)) // is Not a Number?
        return;

    var totalTime = Number(strvalue);
    var cmd = new DSAppCommand("Graphics.KeyframeAnimationUtility.ModifyTotalTime(" + totalTime + ")", id_DS_AppCommandRegionGeneral);
    DSAddCommand(cmd, true);
}
if (!wb.hidden)
    Trace("TRACING:DSKeyframeAnimationScript done");
