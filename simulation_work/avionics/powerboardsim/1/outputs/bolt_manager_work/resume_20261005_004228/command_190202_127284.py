import System
System.IO.File.WriteAllText(PULLROOT+r'\audit\english_session.txt', 'UI culture: '+System.Threading.Thread.CurrentThread.CurrentUICulture.Name+'\nGeometry display name: '+Model.Geometry.Name+'\nBodies: '+str(len(Model.Geometry.GetChildren(DataModelObjectCategory.Body,True))))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
