# Match the previously successful model's contact splitting control.
baseline.AnalysisSettings.ContactSplit=bolted.AnalysisSettings.ContactSplit
case=PCB670_RUN+r'\default\bounded_10k'
e.GetModule().ApdlBoltModule.StartApdlInputFileWrite(baseline)
baseline.WriteInputFile(case+r'\modal_input.dat')
