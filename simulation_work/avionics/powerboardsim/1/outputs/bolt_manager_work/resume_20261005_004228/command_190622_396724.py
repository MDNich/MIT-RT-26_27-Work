import System
s=[]
for a in Model.Analyses:
 s.append(str(a.ObjectId)+'\t'+a.Name+'\t'+str(a.AnalysisType))
System.IO.File.WriteAllText(PULLROOT+r'\audit\preserved_analyses.tsv','\n'.join(s))
