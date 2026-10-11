import java.io.*; import java.nio.file.*; import java.util.*;
import com.google.inject.Guice;
import info.openrocket.swing.startup.GuiModule;
import info.openrocket.core.startup.Application;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.rocketcomponent.*;
import info.openrocket.core.rocketcomponent.position.AxialMethod;
import info.openrocket.core.motor.*;
import info.openrocket.core.file.motor.RASPMotorLoader;
import info.openrocket.core.file.GeneralRocketSaver;
import info.openrocket.core.file.rasaero.export.RASAeroSaver;
import info.openrocket.core.document.*;
import info.openrocket.core.simulation.*;
import info.openrocket.core.logging.*;
import info.openrocket.core.util.GeodeticComputationStrategy;

public class ControlledStudy {
 static final double IN=.0254; static Path out;
 static void csv(FlightDataBranch b,Path dest)throws Exception{
  FlightDataType[] types=b.getTypes();
  try(PrintWriter w=new PrintWriter(Files.newBufferedWriter(dest))){
   for(int j=0;j<types.length;j++){if(j>0)w.print(',');w.print('"'+types[j].getName()+'"');}w.println();
   for(int i=0;i<b.getLength();i++){for(int j=0;j<types.length;j++){if(j>0)w.print(',');w.print(b.get(types[j]).get(i));}w.println();}
  }
 }
 static Simulation sim(OpenRocketDocument doc,FlightConfigurationId id,String name,double dt)throws Exception {
  Simulation sim=new Simulation(doc.getRocket());sim.setName(name);sim.setFlightConfigurationId(id);
  var o=sim.getOptions();o.setISAAtmosphere(true);o.setLaunchAltitude(0);o.setLaunchLatitude(45);o.setLaunchLongitude(0);
  o.setGeodeticComputation(GeodeticComputationStrategy.FLAT);o.setLaunchRodLength(2);o.setLaunchRodAngle(0);o.setLaunchRodDirection(0);o.setLaunchIntoWind(false);
  o.setWindSpeedAverage(0);o.setWindSpeedDeviation(0);o.setWindTurbulenceIntensity(0);o.setWindDirection(0);o.setRandomSeed(12345);o.setTimeStep(dt);o.setMaxSimulationTime(400);
  sim.simulate();var data=sim.getSimulatedData();var b=data.getBranch(0);
  csv(b,out.resolve("openrocket/"+name+".csv"));
  try(PrintWriter w=new PrintWriter(Files.newBufferedWriter(out.resolve("openrocket/"+name+"-events.txt")))){for(var e:b.getEvents())w.println(e);w.println("WARNINGS: "+data.getWarningSet());}
  System.out.println(name+" altitude="+data.getMaxAltitude()+" velocity="+data.getMaxVelocity()+" mach="+data.getMaxMachNumber()+" apogee="+data.getTimeToApogee()+" warnings="+data.getWarningSet());
  return sim;
 }
 public static void main(String[] args)throws Exception {
  Locale.setDefault(Locale.US);out=Path.of(args[0]);
  boolean diagnostic=Arrays.asList(args).contains("diagnostic");
  if(diagnostic){info.openrocket.core.simulation.listeners.MidControlStepLauncher.theTimeStep=.00125;info.openrocket.core.simulation.listeners.MidControlStepLauncher.wantedTimeStep=.00125;}
  GuiModule gm=new GuiModule();Application.setInjector(Guice.createInjector(gm,new PluginModule()));gm.startLoader();
  List<ThrustCurveMotor> motors=new ArrayList<>();
  for(var builder:new RASPMotorLoader().load(Files.newInputStream(out.resolve("models/study-motors.eng")),"study-motors.eng",false))motors.add(builder.build());
  motors.sort(Comparator.comparing(Motor::getDesignation));
  for(int test=0;test<5;test++) {
   if(Arrays.asList(args).contains("only5") && test<4)continue;
   boolean slender=test>=3,bevel=test==2||test==4;String name=new String[]{"B01-smooth-square","B02-rough-square","B03-smooth-bevel","B04-slender-square","B05-slender-bevel"}[test];
   var doc=OpenRocketDocumentFactory.createNewRocket();var rocket=doc.getRocket();rocket.setName(name);rocket.setDesigner("Controlled MIT OR / RASAero study");
   var stage=rocket.getStage(0);stage.setName("Sustainer");
   double dia=(slender?2.26:4.0)*IN,noseLen=(slender?10:12)*IN,bodyLen=(slender?40:48)*IN;
   var finish=test==1?ExternalComponent.Finish.NORMAL:ExternalComponent.Finish.MIRROR;
   NoseCone nose=new NoseCone(Transition.Shape.OGIVE,noseLen,dia/2);nose.setName("Tangent ogive");nose.setShapeParameter(1);nose.setAftRadiusAutomatic(false);nose.setFinish(finish);stage.addChild(nose);
   BodyTube body=new BodyTube(bodyLen,dia/2,.001);body.setName("Constant diameter airframe");body.setOuterRadiusAutomatic(false);body.setFinish(finish);stage.addChild(body);body.setMotorMount(true);body.setMotorOverhang(0);
   TrapezoidFinSet fins=new TrapezoidFinSet(slender?3:4,(slender?5:6)*IN,2*IN,(slender?2.5:4)*IN,(slender?2.5:3.25)*IN);fins.setName("Fixed fins");fins.setThickness(.125*IN);fins.setCrossSection(bevel?FinSet.CrossSection.TRIANGULAR:FinSet.CrossSection.SQUARE);fins.setLeadingEdgeDistance(.25*IN);fins.setFilletRadius(0);fins.setCantAngle(0);fins.setFinish(finish);body.addChild(fins);fins.setAxialMethod(AxialMethod.BOTTOM);fins.setAxialOffset(-.5*IN);
   Parachute chute=new Parachute();chute.setName("Apogee chute");chute.setDiameter(24*IN);chute.setCDAutomatic(false);chute.setCD(.8);chute.getDeploymentConfigurations().getDefault().setDeployEvent(DeploymentConfiguration.DeployEvent.APOGEE);chute.getDeploymentConfigurations().getDefault().setDeployDelay(0);body.addChild(chute);
   stage.setOverrideMass(slender?1.0:6.0);stage.setMassOverridden(true);stage.setSubcomponentsOverriddenMass(true);stage.setOverrideCGX((slender?27:33)*IN);stage.setCGOverridden(true);stage.setSubcomponentsOverriddenCG(true);
   rocket.enableEvents();
   List<FlightConfigurationId> ids=new ArrayList<>();
   for(ThrustCurveMotor m:motors){
    var id=new FlightConfigurationId();ids.add(id);rocket.createFlightConfiguration(id);var cfg=new MotorConfiguration(body,id);cfg.setMotor(m);cfg.setEjectionDelay(Motor.PLUGGED_DELAY);body.setMotorConfig(cfg,id);
    var s=sim(doc,id,name+"-"+m.getDesignation()+(diagnostic?"-actual-h00125":""),diagnostic?.00125:.01);doc.addSimulation(s);
   }
   if(diagnostic)continue;
   doc.getDefaultStorageOptions().setSaveSimulationData(true);new GeneralRocketSaver().save(out.resolve("models/"+name+".ork").toFile(),doc);
   var warnings=new WarningSet();var errors=new ErrorSet();String export=new RASAeroSaver().marshalToRASAero(doc,warnings,errors);Files.writeString(out.resolve("models/"+name+"-raw.CDX1"),export);
   Files.writeString(out.resolve("evidence/"+name+"-export.txt"),"WARNINGS: "+warnings+"\nERRORS: "+errors+"\n");
   for(int i=0;i<motors.size();i++)sim(doc,ids.get(i),name+"-"+motors.get(i).getDesignation()+"-dt005",.005);
  }
  System.exit(0);
 }
}
