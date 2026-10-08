assert unicode(ExtAPI.DataModel.GetObjectById(1656).Solution.ObjectState)=='Solved'
REPORT_CASE='bolted750_modal';REPORT_ANALYSIS_ID=1656
execfile(PCB670_RUN+r'\export_modal_results.py')
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
p=pref.GetType().GetProperty('ExtraModelDisplay')
System.IO.File.WriteAllText(PCB670_RUN+r'\graphics_edge_options.txt',unicode(list(System.Enum.GetNames(p.PropertyType)))+'\n'+unicode(pref.ExtraModelDisplay))
REPORT_CASE='default_refined';REPORT_ANALYSIS_ID=4182
execfile(PCB670_RUN+r'\export_modal_results.py')
REPORT_CASE='bolted750_modal';REPORT_ANALYSIS_ID=1656
