import com.google.inject.Guice;
import info.openrocket.core.aerodynamics.*;
import info.openrocket.core.models.atmosphere.ExtendedISAModel;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.rocketcomponent.*;
import info.openrocket.core.rocketcomponent.position.AxialMethod;
import info.openrocket.core.startup.Application;
import info.openrocket.swing.startup.GuiModule;
import org.w3c.dom.Element;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPOutputStream;

/** Reconstruct the single-stage external geometry from the as-run RASAero CDX1. */
public final class Sweep {
    static final double IN = .0254;
    static String field(Element e, String name) { return ((Element)e.getElementsByTagName(name).item(0)).getTextContent(); }
    static double inch(Element e, String s) { return Double.parseDouble(field(e,s))*IN; }
    static Rocket read(Path p) throws Exception {
        var factory=DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        var rd=(Element)factory.newDocumentBuilder().parse(p.toFile()).getElementsByTagName("RocketDesign").item(0);
        if(rd.getElementsByTagName("BodyTube").getLength()!=1 || rd.getElementsByTagName("Fin").getLength()>1 ||
            rd.getElementsByTagName("Booster").getLength()!=0 || rd.getElementsByTagName("Transition").getLength()!=0)
            throw new IllegalArgumentException("Unsupported fixture: "+p);
        var n=(Element)rd.getElementsByTagName("NoseCone").item(0);
        var b=(Element)rd.getElementsByTagName("BodyTube").item(0);
        var fe=(Element)b.getElementsByTagName("Fin").item(0);
        var sh=switch(field(n,"Shape")){
            case "Tangent Ogive" -> Transition.Shape.OGIVE; case "Conical" -> Transition.Shape.CONICAL;
            case "Von Karman Ogive" -> Transition.Shape.HAACK; case "Elliptical" -> Transition.Shape.ELLIPSOID;
            default -> throw new IllegalArgumentException(field(n,"Shape")); };
        var r=new Rocket(); var stage=new AxialStage(); r.addChild(stage);
        var nose=new NoseCone(sh,inch(n,"Length"),inch(n,"Diameter")/2);
        if(sh==Transition.Shape.OGIVE) nose.setShapeParameter(1);
        if(sh==Transition.Shape.HAACK) nose.setShapeParameter(0);
        nose.setAftRadiusAutomatic(false);stage.addChild(nose);
        var tube=new BodyTube(inch(b,"Length"),inch(b,"Diameter")/2,.001);
        tube.setOuterRadiusAutomatic(false);stage.addChild(tube);
        if(fe!=null) {
            double root=inch(fe,"Chord");
            var f=new TrapezoidFinSet(Integer.parseInt(field(fe,"Count")),root,inch(fe,"TipChord"),inch(fe,"SweepDistance"),inch(fe,"Span"));
            f.setThickness(inch(fe,"Thickness")); f.setCantAngle(0); f.setFilletRadius(0);
            f.setCrossSection(switch(field(fe,"AirfoilSection")){
                case "Square" -> FinSet.CrossSection.SQUARE; case "Rounded" -> FinSet.CrossSection.ROUNDED;
                case "Hexagonal Blunt Base" -> FinSet.CrossSection.TRIANGULAR;
                default -> throw new IllegalArgumentException(field(fe,"AirfoilSection"));});
            if(f.getCrossSection()==FinSet.CrossSection.TRIANGULAR) f.setLeadingEdgeDistance(inch(fe,"FX1"));
            tube.addChild(f); f.setAxialMethod(AxialMethod.BOTTOM); f.setAxialOffset(root-inch(fe,"Location"));
        }
        r.enableEvents(); return r;
    }
    public static void main(String[] args) throws Exception {
        System.setProperty("openrocket.bypass.presets","true");System.setProperty("openrocket.bypass.motors","true");
        var gui=new GuiModule();Application.setInjector(Guice.createInjector(gui,new PluginModule()));gui.startLoader();
        try(var paths=Files.list(Path.of(args[0]));var w=new PrintWriter(new GZIPOutputStream(Files.newOutputStream(Path.of(args[1]))))){
            w.println("case,mach,alpha_deg,D_m,x0_D,n0,x1_D,n1");
            for(var path:paths.filter(p->p.toString().endsWith(".CDX1")).sorted().toList()){
                var rocket=read(path); var cfg=rocket.getSelectedConfiguration();
                var c=new FlightConditions(cfg); c.setAtmosphericConditions(new ExtendedISAModel().getConditions(0));
                c.setTheta(0); c.setPitchRate(0);c.setRollRate(0);c.setYawRate(0);
                var l=new BarrowmanCalculator(false); var f=new BarrowmanCalculator(true);
                var name=path.getFileName().toString().replace(".CDX1","");
                for(int alpha:new int[]{0,2,4}) {c.setAOA(Math.toRadians(alpha));
                    for(int i=10;i<=500;i++){
                        c.setMach(i/100.);var a=l.getCP(cfg,c,null);var b=f.getCP(cfg,c,null);double d=c.getRefLength();
                        if(!(a.weight>0 && b.weight>0 && Double.isFinite(a.x+b.x))) throw new AssertionError(name);
                        w.printf(Locale.ROOT,"%s,%.2f,%d,%.10f,%.12f,%.12f,%.12f,%.12f%n",name,i/100.,alpha,d,a.x/d,a.weight,b.x/d,b.weight);
                    }
                }
            }
            if(w.checkError())throw new IOException("Cannot write sweep");
        }
        System.exit(0);
    }
}
