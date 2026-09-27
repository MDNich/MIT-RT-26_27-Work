import java.io.*;import java.nio.file.*;import java.util.*;
import javax.xml.parsers.*;import org.w3c.dom.*;
import com.google.inject.Guice;
import info.openrocket.swing.startup.GuiModule;
import info.openrocket.core.startup.Application;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.document.*;
import info.openrocket.core.rocketcomponent.*;
import info.openrocket.core.rocketcomponent.position.AxialMethod;
import info.openrocket.core.aerodynamics.*;
import info.openrocket.core.aerodynamics.barrowman.FinSetCalc;
import info.openrocket.core.models.atmosphere.ExtendedISAModel;
import info.openrocket.core.logging.WarningSet;
public class AeroSweep {
 static final double IN=.0254;
 static Element child(Element e,String tag){var x=e.getElementsByTagName(tag);return x.getLength()==0?null:(Element)x.item(0);}
 static double num(Element e,String tag){return Double.parseDouble(child(e,tag).getTextContent());}
 static double cf(double re,double mach){double f=re<1e4?.0148:1/Math.pow(1.5*Math.log(re)-5.6,2);double c1=1-.1*mach*mach,c2=1/Math.pow(1+.15*mach*mach,.58);return f*(mach<.9?c1:mach>1.1?c2:(c2*(mach-.9)/.2+c1*(1.1-mach)/.2));}
 public static void main(String[] args)throws Exception{
  Locale.setDefault(Locale.US);Path out=Path.of(args[0]);GuiModule gm=new GuiModule();Application.setInjector(Guice.createInjector(gm,new PluginModule()));gm.startLoader();
  for(Path p:Files.newDirectoryStream(out.resolve("models"),"*.CDX1")){
   Element rd=(Element)DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(p.toFile()).getElementsByTagName("RocketDesign").item(0);
   var doc=OpenRocketDocumentFactory.createNewRocket();Rocket rocket=doc.getRocket();var stage=rocket.getStage(0);
   Element nc=child(rd,"NoseCone"),bt=child(rd,"BodyTube"),fe=child(bt,"Fin");
   double dia=num(nc,"Diameter")*IN,bl=num(bt,"Length")*IN,nl=num(nc,"Length")*IN;
   NoseCone nose=new NoseCone(Transition.Shape.OGIVE,nl,dia/2);nose.setName("nose");nose.setShapeParameter(1);nose.setAftRadiusAutomatic(false);nose.setFinish(ExternalComponent.Finish.MIRROR);stage.addChild(nose);
   BodyTube body=new BodyTube(bl,dia/2,.001);body.setName("body");body.setOuterRadiusAutomatic(false);body.setFinish(ExternalComponent.Finish.MIRROR);stage.addChild(body);
   TrapezoidFinSet fins=null;int count=0;double root=0,tip=0,span=0,thick=0,sweep=0,mac=0,finArea=0;
   if(fe!=null){count=(int)num(fe,"Count");root=num(fe,"Chord")*IN;tip=num(fe,"TipChord")*IN;span=num(fe,"Span")*IN;thick=num(fe,"Thickness")*IN;sweep=num(fe,"SweepDistance")*IN;
    fins=new TrapezoidFinSet(count,root,tip,sweep,span);fins.setName("fins");fins.setThickness(thick);fins.setFilletRadius(0);fins.setCantAngle(0);fins.setFinish(ExternalComponent.Finish.MIRROR);
    String profile=child(fe,"AirfoilSection").getTextContent();fins.setCrossSection(profile.equals("Square")?FinSet.CrossSection.SQUARE:FinSet.CrossSection.TRIANGULAR);
    if(!profile.equals("Square"))fins.setLeadingEdgeDistance(num(fe,"FX1")*IN);
    body.addChild(fins);fins.setAxialMethod(AxialMethod.BOTTOM);fins.setAxialOffset(root-num(fe,"Location")*IN);
    mac=2.0/3*(root*root+root*tip+tip*tip)/(root+tip);finArea=(root+tip)*span/2;
   }
   rocket.enableEvents();var cfg=rocket.getSelectedConfiguration();var calc=new BarrowmanCalculator();var cond=new FlightConditions(cfg);cond.setAOA(0);cond.setTheta(0);cond.setRollRate(0);cond.setPitchRate(0);cond.setYawRate(0);cond.setAtmosphericConditions(new ExtendedISAModel().getConditions(0));
   String name=p.getFileName().toString().replace(".CDX1","");
   try(PrintWriter w=new PrintWriter(Files.newBufferedWriter(out.resolve("openrocket/"+name+".csv")))){
    w.println("mach,cd,friction,pressure,base,nose_friction,nose_pressure,body_friction,body_pressure,body_base,fin_friction,fin_pressure,area_m2,re_length,re_fin,fin_local_re_delta,fin_mean_chord_m,span_m,thickness_m,sweep_m,count");
    for(int k=1;k<=300;k++){
     double m=k/100.0;cond.setMach(m);var forces=calc.getForceAnalysis(cfg,cond,new WarningSet());var total=forces.get(rocket);var n=forces.get(nose);var b=forces.get(body);var f=fins==null?null:forces.get(fins);
     double ff=f==null?0:f.getFrictionCD()*count,fp=f==null?0:f.getPressureCD()*count;
     double sum=n.getCD()+b.getCD()+ff+fp;
     if(Math.abs(sum-total.getCD())>1e-8)throw new RuntimeException(name+" component sum mismatch "+sum+" != "+total.getCD());
     double vel=cond.getVelocity(),nu=cond.getAtmosphericConditions().getKinematicViscosity(),re=vel*cfg.getLengthAerodynamic()/nu,refin=vel*mac/nu;
     double localDelta=fins==null?0:(cf(refin,m)-cf(re,m))*(1+2*thick/mac)*2*finArea*count/cond.getRefArea();
     w.printf(Locale.US,"%.9g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%d%n",m,total.getCD(),total.getFrictionCD(),total.getPressureCD(),total.getBaseCD(),n.getFrictionCD(),n.getPressureCD(),b.getFrictionCD(),b.getPressureCD(),b.getBaseCD(),ff,fp,cond.getRefArea(),re,refin,localDelta,mac,span,thick,sweep,count);
    }
   }
   System.out.println("Swept "+name+"; component sums validated");
  }
  System.exit(0);
 }
}
