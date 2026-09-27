import java.io.*;import java.nio.file.*;import java.util.*;
import javax.xml.parsers.*;import org.w3c.dom.*;import com.google.inject.Guice;
import info.openrocket.swing.startup.GuiModule;import info.openrocket.core.startup.Application;import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.document.*;import info.openrocket.core.rocketcomponent.*;import info.openrocket.core.rocketcomponent.position.AxialMethod;
import info.openrocket.core.aerodynamics.*;import info.openrocket.core.models.atmosphere.ExtendedISAModel;import info.openrocket.core.logging.WarningSet;
public class CoefficientSweep {
 static final double IN=.0254;
 static Element child(Element e,String tag){var x=e.getElementsByTagName(tag);return x.getLength()==0?null:(Element)x.item(0);}
 static double num(Element e,String tag){return Double.parseDouble(child(e,tag).getTextContent());}
 static String str(Element e,String tag){return child(e,tag).getTextContent();}
 static ExternalComponent.Finish finish(String s){return switch(s){case "Polished"->ExternalComponent.Finish.POLISHED;case "Smooth Paint"->ExternalComponent.Finish.OPTIMUM;case "Rough Camouflage Paint"->ExternalComponent.Finish.SMOOTH;case "Galvanized Metal"->ExternalComponent.Finish.UNFINISHED;default->ExternalComponent.Finish.MIRROR;};}
 public static void main(String[] args)throws Exception{
  Locale.setDefault(Locale.US);Path out=Path.of(args[0]);GuiModule gm=new GuiModule();Application.setInjector(Guice.createInjector(gm,new PluginModule()));gm.startLoader();
  List<Path> paths=new ArrayList<>();for(Path p:Files.newDirectoryStream(out.resolve("models"),"*.CDX1"))paths.add(p);paths.sort(Comparator.naturalOrder());
  for(Path p:paths){
   Element rd=(Element)DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(p.toFile()).getElementsByTagName("RocketDesign").item(0);
   var doc=OpenRocketDocumentFactory.createNewRocket();Rocket rocket=doc.getRocket();var stage=rocket.getStage(0);rocket.setPerfectFinish(!Boolean.parseBoolean(str(rd,"Turbulence")));
   Element nc=child(rd,"NoseCone"),bt=child(rd,"BodyTube"),fe=child(bt,"Fin");double dia=num(nc,"Diameter")*IN,bl=num(bt,"Length")*IN,nl=num(nc,"Length")*IN;
   String shape=str(nc,"Shape");Transition.Shape ns=switch(shape){case "Conical"->Transition.Shape.CONICAL;case "Von Karman Ogive"->Transition.Shape.HAACK;case "Elliptical"->Transition.Shape.ELLIPSOID;case "Tangent Ogive"->Transition.Shape.OGIVE;default->throw new RuntimeException("Unknown shape "+shape);};
   var fn=finish(str(rd,"Surface"));NoseCone nose=new NoseCone(ns,nl,dia/2);nose.setName("nose");if(ns==Transition.Shape.OGIVE)nose.setShapeParameter(1);if(ns==Transition.Shape.HAACK)nose.setShapeParameter(0);nose.setAftRadiusAutomatic(false);nose.setFinish(fn);stage.addChild(nose);
   BodyTube body=new BodyTube(bl,dia/2,.001);body.setName("body");body.setOuterRadiusAutomatic(false);body.setFinish(fn);stage.addChild(body);
   TrapezoidFinSet fins=null;int count=0;double cr=0,tip=0,span=0,thick=0,sweep=0,mac=0;
   if(fe!=null){count=(int)num(fe,"Count");cr=num(fe,"Chord")*IN;tip=num(fe,"TipChord")*IN;span=num(fe,"Span")*IN;thick=num(fe,"Thickness")*IN;sweep=num(fe,"SweepDistance")*IN;
    fins=new TrapezoidFinSet(count,cr,tip,sweep,span);fins.setName("fins");fins.setThickness(thick);fins.setFilletRadius(0);fins.setCantAngle(0);fins.setFinish(fn);
    String profile=str(fe,"AirfoilSection");fins.setCrossSection(switch(profile){case "Square"->FinSet.CrossSection.SQUARE;case "Rounded"->FinSet.CrossSection.ROUNDED;case "Hexagonal Blunt Base"->FinSet.CrossSection.TRIANGULAR;default->throw new RuntimeException("Unknown profile "+profile);});
    if(profile.equals("Hexagonal Blunt Base"))fins.setLeadingEdgeDistance(num(fe,"FX1")*IN);
    body.addChild(fins);fins.setAxialMethod(AxialMethod.BOTTOM);fins.setAxialOffset(cr-num(fe,"Location")*IN);mac=2.0/3*(cr*cr+cr*tip+tip*tip)/(cr+tip);
   }
   rocket.enableEvents();var cfg=rocket.getSelectedConfiguration();String name=p.getFileName().toString().replace(".CDX1","");
   // Additional native-finish curves provide a check on the independent exact-roughness reconstruction.
   var finishes=List.of(fn);if(name.equals("Hbody")||name.equals("Hsq")||name.equals("Hbev"))finishes=Arrays.asList(ExternalComponent.Finish.values());
   for(var fni:finishes){nose.setFinish(fni);body.setFinish(fni);if(fins!=null)fins.setFinish(fni);var calc=new BarrowmanCalculator();var cond=new FlightConditions(cfg);cond.setTheta(0);cond.setRollRate(0);cond.setPitchRate(0);cond.setYawRate(0);cond.setAtmosphericConditions(new ExtendedISAModel().getConditions(0));
    String suffix=(fni==fn?"":"-ORfinish-"+fni.name());
    try(PrintWriter w=new PrintWriter(Files.newBufferedWriter(out.resolve("openrocket/"+name+suffix+".csv")))){
     w.println("mach,alpha_deg,cd0,ca,cn,cd_wind,cl,cp_m,cna_effective,friction,pressure,base,nose_friction,nose_pressure,body_friction,body_pressure,body_base,fin_friction,fin_pressure,area_m2,re_length,re_fin,fin_mac_m,span_m,thickness_m,sweep_m,count,roughness_m,perfect_finish");
     for(double alpha:new double[]{0,2,4}){cond.setAOA(Math.toRadians(alpha));for(int k=1;k<=300;k++){
      double m=k/100.0;cond.setMach(m);var warnings=new WarningSet();var forces=calc.getForceAnalysis(cfg,cond,warnings);var t=forces.get(rocket);var n=forces.get(nose);var b=forces.get(body);var f=fins==null?null:forces.get(fins);double ff=f==null?0:f.getFrictionCD()*count,fp=f==null?0:f.getPressureCD()*count;
      if(Math.abs(n.getCD()+b.getCD()+ff+fp-t.getCD())>1e-8)throw new RuntimeException(name+" component sum mismatch");
      double vel=cond.getVelocity(),nu=cond.getAtmosphericConditions().getKinematicViscosity(),aoa=cond.getAOA(),ca=t.getCDaxial(),cn=t.getCN();double cd=ca*Math.cos(aoa)+cn*Math.sin(aoa),cl=cn*Math.cos(aoa)-ca*Math.sin(aoa);
      double[] vals={m,alpha,t.getCD(),ca,cn,cd,cl,t.getCP().x,t.getCP().weight,t.getFrictionCD(),t.getPressureCD(),t.getBaseCD(),n.getFrictionCD(),n.getPressureCD(),b.getFrictionCD(),b.getPressureCD(),b.getBaseCD(),ff,fp,cond.getRefArea(),vel*cfg.getLengthAerodynamic()/nu,vel*mac/nu,mac,span,thick,sweep,count,fni.getRoughnessSize(),rocket.isPerfectFinish()?1:0};
      for(int j=0;j<vals.length;j++){if(j>0)w.print(',');w.printf(Locale.US,"%.12g",vals[j]);}w.println();
     }}
    }
   }
   System.out.println("SWEPT "+name+"; alpha 0/2/4; component sums checked");
  }System.exit(0);
 }
}
