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
import java.nio.file.*;
import java.util.*;
import java.io.PrintWriter;

/** Reconstruct outside geometry on the native model's axial stations (inches at the file boundary). */
public final class AirframeSweep {
    static final double IN=.0254;
    static double num(Element e,String key) {return Sweep.inch(e,key)/IN;}
    static AxialStage stage(){
        var rocket=new Rocket();var stage=new AxialStage();rocket.addChild(stage);return stage;
    }
    static BodyTube tube(AxialStage stage,double length,double d){
        var b=new BodyTube(length*IN,d*IN/2,.0001);b.setOuterRadiusAutomatic(false);stage.addChild(b);return b;
    }
    static void taper(AxialStage stage,double length,double fore,double aft){
        var t=new Transition();t.setShapeType(Transition.Shape.CONICAL);
        t.setLength(length*IN);t.setForeRadius(fore*IN/2);t.setAftRadius(aft*IN/2);stage.addChild(t);
    }
    static void nose(AxialStage stage,String name,double length,double dia){
        var shape=switch(name){
            case "Conical" -> Transition.Shape.CONICAL; case "Tangent Ogive" -> Transition.Shape.OGIVE;
            case "Von Karman Ogive" -> Transition.Shape.HAACK; default -> throw new IllegalArgumentException(name);
        };
        var n=new NoseCone(shape,length*IN,dia*IN/2);
        if(shape==Transition.Shape.HAACK)n.setShapeParameter(0);
        if(shape==Transition.Shape.OGIVE)n.setShapeParameter(1);
        n.setAftRadiusAutomatic(false);stage.addChild(n);
    }
    static void addFins(BodyTube body,Element item){
        double root=num(item,"Chord");
        var f=new TrapezoidFinSet(Integer.parseInt(Sweep.field(item,"Count")),root*IN,
            num(item,"TipChord")*IN,num(item,"SweepDistance")*IN,num(item,"Span")*IN);
        f.setFilletRadius(0);f.setCantAngle(0);f.setThickness(num(item,"Thickness")*IN);
        f.setCrossSection(switch(Sweep.field(item,"AirfoilSection")){
            case "Square"->FinSet.CrossSection.SQUARE;case "Rounded"->FinSet.CrossSection.ROUNDED;
            case "Hexagonal Blunt Base"->FinSet.CrossSection.TRIANGULAR;
            default->throw new IllegalArgumentException(Sweep.field(item,"AirfoilSection"));});
        if(f.getCrossSection()==FinSet.CrossSection.TRIANGULAR)f.setLeadingEdgeDistance(num(item,"FX1")*IN);
        body.addChild(f);f.setAxialMethod(AxialMethod.BOTTOM);f.setAxialOffset(IN*(root-num(item,"Location")));
    }
    static FlightConfiguration finish(AxialStage stage){
        stage.getRocket().enableEvents();return stage.getRocket().getSelectedConfiguration();
    }
    static FlightConfiguration read(Path p)throws Exception{
        var xml=DocumentBuilderFactory.newInstance();xml.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        var design=(Element)xml.newDocumentBuilder().parse(p.toFile()).getElementsByTagName("RocketDesign").item(0);
        var stage=stage();double location=0,lastDia=0;double promisedTail=0;
        for(var n=design.getFirstChild();n!=null;n=n.getNextSibling()){
            if(!(n instanceof Element e))continue;
            switch(e.getTagName()){
            case "NoseCone" -> {lastDia=num(e,"Diameter");nose(stage,Sweep.field(e,"Shape"),num(e,"Length"),lastDia);}
            case "BodyTube" -> {
                var b=tube(stage,num(e,"Length"),num(e,"Diameter"));lastDia=num(e,"Diameter");
                var f=(Element)e.getElementsByTagName("Fin").item(0);if(f!=null)addFins(b,f);
                promisedTail=num(e,"BoattailLength");
            }
            case "Transition","BoatTail" -> {
                if(!(lastDia>0))throw new IllegalArgumentException("No inherited diameter at "+p);
                if(e.getTagName().equals("BoatTail")){
                    if(promisedTail>0 && Math.abs(promisedTail-num(e,"Length"))>1e-4)throw new IllegalArgumentException("Conflicting tail lengths "+p);
                    promisedTail=0;
                }
                double aft=num(e,"RearDiameter");taper(stage,num(e,"Length"),lastDia,aft);lastDia=aft;
            }
            default -> {if(e.getElementsByTagName("Length").getLength()>0)throw new IllegalArgumentException("Unhandled "+e.getTagName());continue;}
            }
            if(Math.abs(num(e,"Location")-location)>1e-3)throw new IllegalArgumentException("Noncontiguous native geometry "+p);
            location+=num(e,"Length");
        }
        if(promisedTail>0)throw new IllegalArgumentException("Missing BoatTail geometry in "+p);
        return finish(stage);
    }
    static FlightConfiguration nasa(boolean flare){
        final double d=1.25,tip=.25*d,angle=Math.toRadians(14.+2./60),xt=tip*(1-Math.sin(angle));
        var st=stage();double prevX=0,prevD=0;
        for(int j=1;j<=40;j++){
            double x=xt*j/40, dia=2*Math.sqrt(2*tip*x-x*x);
            if(j==1)nose(st,"Conical",x,dia);else taper(st,x-prevX,prevD,dia);
            prevX=x;prevD=dia;
        }
        taper(st,1.22*d-prevX,prevD,d);tube(st,2*d,d);
        if(flare)taper(st,1.37*d,d,1.48*d);else tube(st,1.37*d,d);
        return finish(st);
    }
    static void sweep(PrintWriter w,String name,FlightConfiguration cfg,double[] machs,int[] angles){
        var solver=new BarrowmanCalculator(true);var c=new FlightConditions(cfg);
        for(int a:angles){
            c.setAOA(Math.toRadians(a));
            for(double m:machs){
                c.setMach(m);var cp=solver.getCP(cfg,c,null);
                if(!Double.isFinite(cp.x+cp.weight)||cp.weight<=0)throw new AssertionError(name+" "+m);
                w.printf(Locale.ROOT,"%s,%.4f,%d,%.10f,%.12f,%.12f%n",name,m,a,c.getRefLength()/IN,cp.x/IN,cp.weight);
            }
        }
    }
    public static void main(String[] arg)throws Exception{
        System.setProperty("openrocket.bypass.presets","true");System.setProperty("openrocket.bypass.motors","true");
        var gui=new GuiModule();Application.setInjector(Guice.createInjector(gui,new PluginModule()));gui.startLoader();
        Path root=Path.of(arg[0]);double[] grid=new double[151];
        for(int i=0;i<grid.length;i++)grid[i]=(150+i)/100.;
        try(var w=new PrintWriter(Files.newBufferedWriter(Path.of(arg[1])))){
            w.println("geometry,mach,alpha_deg,D_in,cp_in,n_rad");
            for(var dir:List.of(root.resolve("inputs/native-afterbody/models"),root.resolve("inputs/iris-components/models"))){
                try(var files=Files.list(dir)){
                    for(var file:files.filter(f->f.toString().endsWith(".CDX1")).sorted().toList()){
                        String n=file.getFileName().toString().replace(".CDX1","");
                        sweep(w,n,read(file),grid,new int[]{0,2,4});
                    }
                }
            }
            for(int count:new int[]{1,2,4}){
                var st=stage();nose(st,"Tangent Ogive",12,4);
                for(int i=0;i<count;i++)tube(st,48./count,4);
                sweep(w,"split-"+count,finish(st),grid,new int[]{0,2,4});
            }
            for(boolean flare:new boolean[]{false,true})sweep(w,flare?"blunt-flare10":"blunt-straight",nasa(flare),
                    new double[]{1.97,2.94,4.06},new int[]{0});
            if(w.checkError())throw new java.io.IOException("Failed to write sweep");
        }
        System.exit(0);
    }
}
