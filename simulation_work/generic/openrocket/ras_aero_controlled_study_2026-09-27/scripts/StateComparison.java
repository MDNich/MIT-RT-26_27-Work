import java.io.*;import java.nio.file.*;import java.util.*;
import com.google.inject.Guice;
import info.openrocket.swing.startup.GuiModule;
import info.openrocket.core.startup.Application;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.file.GeneralRocketLoader;
import info.openrocket.core.file.motor.RASPMotorLoader;
import info.openrocket.core.database.motor.ThrustCurveMotorSetDatabase;
import info.openrocket.core.aerodynamics.*;
import info.openrocket.core.models.atmosphere.ExtendedISAModel;
import info.openrocket.core.logging.WarningSet;
public class StateComparison {
 public static void main(String[] args)throws Exception{
  Locale.setDefault(Locale.US);Path out=Path.of(args[0]);GuiModule gm=new GuiModule();Application.setInjector(Guice.createInjector(gm,new PluginModule()));gm.startLoader();
  var db=Application.getInjector().getInstance(ThrustCurveMotorSetDatabase.class);
  for(var m:new RASPMotorLoader().load(Files.newInputStream(out.resolve("models/study-motors.eng")),"study-motors.eng",false))db.addMotor(m.build());
  for(Path csv:Files.newDirectoryStream(out.resolve("rasaero"),"*-turbulent-*.csv")){
   String base=csv.getFileName().toString().split("-turbulent-")[0];
   var loader=new GeneralRocketLoader(out.resolve("models/"+base+".ork").toFile());var doc=loader.load();System.out.println(base+" load warnings="+loader.getWarnings());
   var config=doc.getRocket().getSelectedConfiguration();var calc=new BarrowmanCalculator();var atm=new ExtendedISAModel();var conditions=new FlightConditions(config);conditions.setAOA(0);conditions.setTheta(0);conditions.setRollRate(0);conditions.setPitchRate(0);conditions.setYawRate(0);
   List<String> lines=Files.readAllLines(csv);
   try(PrintWriter w=new PrintWriter(Files.newBufferedWriter(out.resolve("evidence/"+csv.getFileName().toString().replace(".csv","-same-state.csv"))))){
    w.println("time,altitude_m,velocity_m_s,ras_mach,or_mach,ras_cd,or_cd,or_friction_cd,or_pressure_cd,or_base_cd,or_cp_m,or_density,ras_drag_N,ras_mass_kg,ras_vertical_accel,ras_thrust_N,ras_aoa_deg");
    for(int i=1;i<lines.size();i++){
     String[] a=lines.get(i).split(",");double t=Double.parseDouble(a[0]),h=Double.parseDouble(a[22])*.3048,v=Double.parseDouble(a[17])*.3048;
     if(Double.parseDouble(a[18])<0)break;if(v<10)continue;
     // RASAero's exported Mach and velocity can be offset by a sample.
     // Match its reported Mach explicitly rather than reconstruct it from velocity.
     conditions.setAtmosphericConditions(atm.getConditions(h));conditions.setMach(Double.parseDouble(a[3]));
     var f=calc.getAerodynamicForces(config,conditions,new WarningSet());
     w.printf(Locale.US,"%.9g,%.9g,%.9g,%s,%.9g,%s,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%s%n",t,h,v,a[3],conditions.getMach(),a[5],f.getCD(),f.getFrictionCD(),f.getPressureCD(),f.getBaseCD(),f.getCP().x,conditions.getAtmosphericConditions().getDensity(),Double.parseDouble(a[9])*4.4482216152605,Double.parseDouble(a[8])*.45359237,Double.parseDouble(a[15])*.3048,Double.parseDouble(a[7])*4.4482216152605,a[4]);
    }
   }
  }
  System.exit(0);
 }
}
