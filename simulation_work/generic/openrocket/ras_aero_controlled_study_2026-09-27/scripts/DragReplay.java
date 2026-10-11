import java.io.*;import java.nio.file.*;import java.util.*;
import com.google.inject.Guice;
import info.openrocket.swing.startup.GuiModule;
import info.openrocket.core.startup.Application;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.file.GeneralRocketLoader;
import info.openrocket.core.file.motor.RASPMotorLoader;
import info.openrocket.core.database.motor.ThrustCurveMotorSetDatabase;
import info.openrocket.core.aerodynamics.*;
import info.openrocket.core.simulation.*;
import info.openrocket.core.simulation.listeners.AbstractSimulationListener;

public class DragReplay {
 static class Curve {
  TreeMap<Double,Double> values=new TreeMap<>();
  double at(double x){var lo=values.floorEntry(x);var hi=values.ceilingEntry(x);if(lo==null)return values.firstEntry().getValue();if(hi==null)return values.lastEntry().getValue();if(lo.getKey().equals(hi.getKey()))return lo.getValue();double a=(x-lo.getKey())/(hi.getKey()-lo.getKey());return lo.getValue()*(1-a)+hi.getValue()*a;}
 }
 static class Replay extends AbstractSimulationListener {
  Curve power=new Curve(),coast=new Curve();double mach=0,burnout;
  Replay(Path p,double b)throws Exception{burnout=b;List<String> lines=Files.readAllLines(p);for(String line:lines.subList(1,lines.size())){String[] a=line.split(",");if(Double.parseDouble(a[18])<0)break;double m=Double.parseDouble(a[3]),cd=Double.parseDouble(a[5]);if(m<=0||cd<=0)continue;(Double.parseDouble(a[7])>0?power:coast).values.put(m,cd);}}
  @Override public FlightConditions postFlightConditions(SimulationStatus s,FlightConditions f){mach=f.getMach();return null;}
  @Override public AerodynamicForces postAerodynamicCalculation(SimulationStatus s,AerodynamicForces f){double cd=(s.getSimulationTime()<burnout?power:coast).at(mach);var g=f.clone();g.setCD(cd);g.setCDaxial(cd);return g;}
 }
 public static void main(String[] args)throws Exception{
  Locale.setDefault(Locale.US);Path out=Path.of(args[0]);GuiModule gm=new GuiModule();Application.setInjector(Guice.createInjector(gm,new PluginModule()));gm.startLoader();
  var db=Application.getInjector().getInstance(ThrustCurveMotorSetDatabase.class);for(var m:new RASPMotorLoader().load(Files.newInputStream(out.resolve("models/study-motors.eng")),"study-motors.eng",false))db.addMotor(m.build());
  for(Path p:Files.newDirectoryStream(out.resolve("rasaero"),"*-turbulent-*.csv")){
   String fn=p.getFileName().toString(),base=fn.split("-turbulent-")[0];if(base.startsWith("B02"))continue;
   var load=new GeneralRocketLoader(out.resolve("models/"+base+".ork").toFile());var doc=load.load();int index=fn.contains("I500")?0:1;var sim=doc.getSimulation(index);
   sim.simulate(new Replay(p,index==0?1.335:2.052));var d=sim.getSimulatedData();
   ControlledStudy.csv(d.getBranch(0),out.resolve("openrocket/"+fn.replace("-turbulent-","-").replace(".csv","-ras-cd-replay.csv")));
   System.out.println(fn+" REPLAY apogee="+d.getMaxAltitude()+" vmax="+d.getMaxVelocity()+" warnings="+d.getWarningSet());
  }
  System.exit(0);
 }
}
