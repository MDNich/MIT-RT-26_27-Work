import com.google.inject.Guice;
import info.openrocket.core.aerodynamics.*;
import info.openrocket.core.file.GeneralRocketLoader;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.rocketcomponent.*;
import info.openrocket.core.rocketcomponent.position.AxialMethod;
import info.openrocket.core.startup.Application;
import info.openrocket.swing.startup.GuiModule;
import org.w3c.dom.Element;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.PrintWriter;
import java.nio.file.*;
import java.util.*;

/** Axial stations are from the same nose datum; areas and diameters for each output are explicit. */
public class Loads {
    private static final double IN = 0.0254;

    private static BodyTube tube(AxialStage stage, double length, double radius) {
        BodyTube tube = new BodyTube(length * IN, radius * IN, 0.00001);
        tube.setOuterRadiusAutomatic(false);
        stage.addChild(tube);
        return tube;
    }
    private static void transition(AxialStage stage, double length, double r0, double r1) {
        Transition tr = new Transition();
        tr.setShapeType(Transition.Shape.CONICAL);
        tr.setLength(length*IN);
        tr.setForeRadius(r0*IN); tr.setAftRadius(r1*IN);
        stage.addChild(tr);
    }
    private static double number(Element e,String name) {
        return Double.parseDouble(e.getElementsByTagName(name).item(0).getTextContent());
    }
    private static void fins(BodyTube tube,int count,double root,double tip,double sweep,double span,
                             double thick,double setback) {
        var f = new TrapezoidFinSet(count,root*IN,tip*IN,sweep*IN,span*IN);
        f.setThickness(thick*IN); f.setCantAngle(0); f.setFilletRadius(0);
        tube.addChild(f); f.setAxialMethod(AxialMethod.BOTTOM); f.setAxialOffset(-setback*IN);
    }
    private static FlightConfiguration cdx(Path p) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        var rd = (Element)factory.newDocumentBuilder().parse(p.toFile()).getElementsByTagName("RocketDesign").item(0);
        Rocket rocket = new Rocket(); AxialStage stage = new AxialStage();rocket.addChild(stage);
        double station=0;
        for(var node=rd.getFirstChild();node!=null;node=node.getNextSibling()) {
            if(!(node instanceof Element e)) continue;
            switch(e.getTagName()){
                case "NoseCone" -> {
                    if(!e.getElementsByTagName("Shape").item(0).getTextContent().equals("Von Karman Ogive"))throw new IllegalArgumentException("Unexpected nose");
                    var nose=new NoseCone(Transition.Shape.HAACK,number(e,"Length")*IN,number(e,"Diameter")*IN/2);
                    nose.setShapeParameter(0);nose.setAftRadiusAutomatic(false);stage.addChild(nose);
                }
                case "BodyTube" -> {
                    BodyTube bt=tube(stage,number(e,"Length"),number(e,"Diameter")/2);
                    var f=(Element)e.getElementsByTagName("Fin").item(0);
                    if(f!=null){
                        fins(bt,(int)number(f,"Count"),number(f,"Chord"),number(f,"TipChord"),
                             number(f,"SweepDistance"),number(f,"Span"),number(f,"Thickness"),number(f,"Location")-number(f,"Chord"));
                        var fin=(FinSet)bt.getChild(0); fin.setCrossSection(FinSet.CrossSection.TRIANGULAR);
                        fin.setLeadingEdgeDistance(number(f,"FX1")*IN);
                    }
                }
                case "Transition" -> transition(stage,number(e,"Length"),number(e,"Diameter")/2,number(e,"RearDiameter")/2);
                default -> { continue; }
            }
            if(Math.abs(number(e,"Location")-station)>1e-6)throw new AssertionError("Station mismatch "+p);
            station+=number(e,"Length");
        }
        rocket.enableEvents();return rocket.getSelectedConfiguration();
    }

    // Fig. 1 (printed p.29) uses a 15-deg cone tangent to an R=11.02-in circular fairing.
    private static FlightConfiguration tunnel(int wing,String part,double span,double chord){
        Rocket r=new Rocket();AxialStage stage=new AxialStage();r.addChild(stage);
        BodyTube base;
        if(part.equals("wing")){
            // Radius tends to zero for the isolated triangular wing. Common reference diameter is set explicitly below.
            base=tube(stage,11,Double.parseDouble(System.getProperty("benchmark.carrierIn","0.00001")));
        }else{
            double angle=Math.toRadians(15),radius=11.02,bodyRadius=.75;
            double r0=bodyRadius-radius*(1-Math.cos(angle)), x0=r0/Math.tan(angle);
            NoseCone nose=new NoseCone(Transition.Shape.CONICAL,x0*IN,r0*IN);nose.setAftRadiusAutomatic(false);stage.addChild(nose);
            final int panels=Integer.getInteger("benchmark.fairingPanels",24);
            double end=x0+radius*Math.sin(angle), lastX=x0,lastR=r0;
            for(int i=1;i<=panels;i++){
                double x=x0+(end-x0)*i/panels;
                double y=bodyRadius-radius+Math.sqrt(radius*radius-(x-end)*(x-end));
                transition(stage,x-lastX,lastR,y);lastX=x;lastR=y;
            }
            base=tube(stage,11-end,bodyRadius);
        }
        if(!part.equals("body")){
            boolean alone=part.equals("wing");
            double root=alone?chord:3.0;
            fins(base,2,root,0,root,alone?span:span-.75,.08*root,3.);
            ((FinSet)base.getChild(0)).setCrossSection(FinSet.CrossSection.ROUNDED);
        }
        r.enableEvents();return r.getSelectedConfiguration();
    }

    private static void output(PrintWriter w,String model,String family,String part,int wing,FlightConfiguration cfg,
            double referenceD,double[] machs,double[] angles,boolean experimental,boolean tunnel){
        var solver=new BarrowmanCalculator(experimental);
        var cond=new FlightConditions(cfg);cond.setRefLength(referenceD*IN);
        cond.setTheta(tunnel?Math.PI/2:0);
        for(double deg:angles)for(double mach:machs){
            cond.setAOA(Math.toRadians(deg));cond.setMach(mach);
            if(tunnel){
                var atmosphere=cond.getAtmosphericConditions().clone();
                double bodyRe=cond.getVelocity()*11*IN/atmosphere.getKinematicViscosity();
                atmosphere.setPressure(atmosphere.getPressure()*5.5e6/bodyRe);
                cond.setAtmosphericConditions(atmosphere);
                if(Math.abs(cond.getVelocity()*11*IN/atmosphere.getKinematicViscosity()-5.5e6)>1)
                    throw new AssertionError("Tunnel Reynolds number");
            }
            var cp=solver.getCP(cfg,cond,null);
            double ca=tunnel?solver.getAerodynamicForces(cfg,cond,null).getCDaxial():Double.NaN;
            if(!Double.isFinite(cp.x+cp.weight) || (tunnel && !Double.isFinite(ca)))throw new AssertionError(family);
            w.printf(Locale.ROOT,"%s,%s,%s,%d,%.9f,%.4f,%.12f,%.12f,%.12f%n",model,family,part,wing,mach,deg,cp.x/IN,cp.weight,ca);
        }
    }
    public static void main(String[] args)throws Exception{
        String model=args[0];Path root=Path.of(args[1]);
        System.setProperty("openrocket.bypass.presets","true");System.setProperty("openrocket.bypass.motors","true");
        GuiModule gui=new GuiModule();Application.setInjector(Guice.createInjector(gui,new PluginModule()));gui.startLoader();
        boolean experimental=!model.equals("legacy");
        try(var w=new PrintWriter(Files.newBufferedWriter(root.resolve("results/followup/"+model+"-loads.csv")))){
            w.println("model,family,part,wing,mach,alpha_deg,cp_in,cna_per_rad,ca0");
            var machs=new TreeSet<Double>();for(int i=1500;i<=3000;i+=5)machs.add(i/1000.);
            for(double edge:new double[]{1,1.15,1.30}){
                double boundary=edge*Math.hypot(3.5,5)/3.5;
                for(double step:new double[]{-2e-5,-1e-5,0,1e-5,2e-5})machs.add(boundary+step);
            }
            double[] irisGrid=machs.stream().mapToDouble(Double::doubleValue).toArray();
            if(!Boolean.getBoolean("benchmark.tunnelOnly")) for(String part:List.of("forebody","finless","finned")){
                var cfg=cdx(root.resolve("inputs/iris-components/models/"+part+".CDX1"));
                output(w,model,"cdx",part,0,cfg,4.20,irisGrid,new double[]{0,2,4},experimental,false);
                var doc=new GeneralRocketLoader(Path.of(System.getenv().getOrDefault("CP_WORK",root.resolve("work").toString())).resolve("handover/"+part+".ork").toFile()).load();
                output(w,model,"ork",part,0,doc.getRocket().getSelectedConfiguration(),4.20,irisGrid,new double[]{0,2,4},experimental,false);
                if(!part.equals("forebody")){
                    Path fixture=Path.of(System.getenv().getOrDefault("CP_WORK",root.resolve("work").toString()))
                            .resolve("handover/"+part+"-nocamera.ork");
                    var withoutPods=new GeneralRocketLoader(fixture.toFile()).load();
                    output(w,model,"ork-no-camera",part,0,withoutPods.getRocket().getSelectedConfiguration(),
                            4.20,irisGrid,new double[]{0,2,4},experimental,false);
                }

            }
            for(String row:Files.readAllLines(root.resolve("followup/tn3795.csv")).subList(1,7)){
                String[] v=row.split(",");int wing=Integer.parseInt(v[0]);
                for(String part:List.of("body","wing","combined")){
                    var cfg=tunnel(wing,part,Double.parseDouble(v[2]),Double.parseDouble(v[3]));
                    output(w,model,"TN3795",part,wing,cfg,1.50,new double[]{1.50,2.02},new double[]{0},experimental,true);
                }
            }
            if(w.checkError())throw new java.io.IOException("Write failed");
        }
        System.exit(0);
    }
}
