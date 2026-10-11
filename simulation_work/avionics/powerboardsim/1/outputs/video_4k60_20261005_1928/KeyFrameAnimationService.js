
function OnACTSocketOpen() {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Localization',
        'body': [
            "ID_KeyframeCreateFrame",
            "ID_KeyframeDeleteFrame",
            "ID_KeyframeModifyFrame",
            "ID_KeyframeLoadAnim",
            "ID_KeyframeSaveAnim",
            "ID_ExportAnimationFile",
            "ID_KeyframePrevFrame",
            "ID_KeyframePlay",
            "ID_KeyframePause",
            "ID_Stop",
            "ID_KeyframeNextFrame",
            "ID_KeyframeKeyframe",
            "ID_KeyframeSubframe",
            "ID_KeyframeSubframeCount",
            "ID_KeyframeTotalTime"
        ],
        'onsuccess': function (reply) {
            localizeStrings(JSON.parse(reply));
            initializeToolTips();
            initializeInnerHtmls();
        },
        'onerror': function (reply) {
            window.alert("error getting localized strings - " + reply);
        }
    });

    Refresh(function (totalTimeValue, KeyframeList) {
        RefreshUI(totalTimeValue, KeyframeList);
    });
}

function localizeStrings(localizedStrings) {
    createKeyframe = localizedStrings["ID_KeyframeCreateFrame"];
    deleteKeyframe = localizedStrings["ID_KeyframeDeleteFrame"];
    modifyKeyframe = localizedStrings["ID_KeyframeModifyFrame"];
    loadAnimation = localizedStrings["ID_KeyframeLoadAnim"];
    saveAnimation = localizedStrings["ID_KeyframeSaveAnim"];
    exportAnimationFile = localizedStrings["ID_ExportAnimationFile"];
    prevKeyframe = localizedStrings["ID_KeyframePrevFrame"];
    playKeyframe = localizedStrings["ID_KeyframePlay"];
    pauseKeyframe = localizedStrings["ID_KeyframePause"];
    stopKeyframe = localizedStrings["ID_Stop"];
    nextKeyframe = localizedStrings["ID_KeyframeNextFrame"];
    keyframe = localizedStrings["ID_KeyframeKeyframe"];
    subframe = localizedStrings["ID_KeyframeSubframe"];
    subframeCount = localizedStrings["ID_KeyframeSubframeCount"];
    totalTime = localizedStrings["ID_KeyframeTotalTime"];
}

function initializeToolTips() {
    $("#jqxAddFrame").jqxTooltip({ content: createKeyframe, opacity: 1 });
    $("#jqxDeleteFrame").jqxTooltip({ content: deleteKeyframe, opacity: 1 });
    $("#jqxReplaceFrame").jqxTooltip({ content: modifyKeyframe, opacity: 1 });
    $("#jqxLoadFrames").jqxTooltip({ content: loadAnimation, opacity: 1 });
    $("#jqxSaveFrames").jqxTooltip({ content: saveAnimation, opacity: 1 });
    $("#ExportVideoFile").jqxTooltip({ content: exportAnimationFile, opacity: 1 });
    $("#jqxPrevButton").jqxTooltip({ content: prevKeyframe, opacity: 1 });
    $("#jqxPlayButton").jqxTooltip({ content: playKeyframe, opacity: 1 });
    $("#jqxPauseButton").jqxTooltip({ content: pauseKeyframe, opacity: 1 });
    $("#jqxStopButton").jqxTooltip({ content: stopKeyframe, opacity: 1 });
    $("#jqxNextButton").jqxTooltip({ content: nextKeyframe, opacity: 1 });
}

function initializeInnerHtmls() {
    var kf = document.getElementById("keyframeId");
    kf.innerHTML = keyframe + " " + kf.innerHTML;
    var sf = document.getElementById("subframeId");
    sf.innerHTML = subframe + " " + sf.innerHTML;
    var sfc = document.getElementById("sfcId");
    sfc.innerHTML = subframeCount + " " + sfc.innerHTML;
    var tt = document.getElementById("ttId");
    tt.innerHTML = totalTime + " " + tt.innerHTML;
}

function PlayAnimation() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/Play',
        'onsuccess': function () {
            prevKf = 0;
            prevSf = 0;
            counter = 0;
            played = true;
            totalKeyframeCount = Object.keys(subframeMap).length - 1;
            $("#jqxPlayButton").hide();
            $("#jqxPauseButton").show();
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function PauseAnimation() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/Pause',
        'onsuccess': function () {
            $("#jqxPlayButton").show();
            $("#jqxPauseButton").hide();
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function StopAnimation() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/Stop',
        'onsuccess': function () {
            played = false;
            prevPlay = false;
            $("#jqxPlayButton").show();
            $("#jqxPauseButton").hide();
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function AddKeyFrame() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/AddFrame',
        'onsuccess': function () {
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function ShowPrevFrame() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/PrevFrame',
        'onsuccess': function () {
            prevPlay = false;
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function ShowNextFrame() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/NextFrame',
        'onsuccess': function () {
            prevPlay = false;
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function RemoveKeyframe(keyframeIndex, handleresult) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/RemoveKeyframe',
        'body': {
            keyframeIndex: keyframeIndex
        },
        'onsuccess': function (result) {
            delete subframeMap[keyframeIndex];
            return handleresult();
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function ReplaceKeyframe(keyframe, currSubframeCount) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/ReplaceKeyframe',
        'body': {
            keyframeIndex: keyframe,
            subframeCount: currSubframeCount
        },
        'onsuccess': function (result) {
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function GetSubframeCount(keyframeIndex, handleresult) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/GetSubframeCount',
        'body': {
            keyframeIndex: keyframeIndex
        },
        'onsuccess': function (result) {
            var data = JSON.parse(result);
            return handleresult(data);
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function GetTotalTime(handleresult) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/GetTotalTime',
        'onsuccess': function (result) {
            var data = JSON.parse(result);
            return handleresult(data);
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function ModifySubframeCount(keyframe, newSubframeCount) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/ModifySubframeCount',
        'body': {
            keyframeIndex: keyframe,
            subframeCount: newSubframeCount
        },
        'onsuccess': function () {
            subframeMap[keyframe] = newSubframeCount;
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function ModifyTotalTime(newTotalTime) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/ModifyTotalTime',
        'body': {
            totalTime: newTotalTime
        },
        'onsuccess': function () {
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });

}

function SaveAnimation() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/SaveAnimation',
        'onsuccess': function () {
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function ExportAnimationVideo() {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/ExportAnimationVideo',
        'onsuccess': function () {
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function LoadAnimation(handleresult) {
    AJACTS({
        'type': 'POST',
        'uri': '/app/Graphics/KeyFrameAnimation/LoadAnimation',
        'onsuccess': function () {
            return handleresult();
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function Refresh(handleresult) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/Refresh',
        'onsuccess': function (result) {
            var data = JSON.parse(result);
            return handleresult(data[0],data[1]);
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function getCurrentFrame(handleresult) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/getCurrentFrame',
        'onsuccess': function (result) {
            var data = JSON.parse(result);
            return handleresult(data[0], data[1]);
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}

function SetCurrentFrame(keyframeIndex, subframeIndex) {
    AJACTS({
        'type': 'GET',
        'uri': '/app/Graphics/KeyFrameAnimation/SetCurrentFrame',
        'body': {
            keyframeIndex: keyframeIndex,
            subframeIndex: subframeIndex
        },
        'onsuccess': function (data) {
        },
        'onerror': function (reply) {
            window.alert("problem: " + reply);
        }
    });
}
