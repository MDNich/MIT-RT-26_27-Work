package info.openrocket.core.aerodynamics.barrowman;

import info.openrocket.core.rocketcomponent.*;
import java.util.*;

/** Geometry for the afterbody ablations of the MIT 6.6 research model. Dimensions are SI. */
public final class BodyPlan {
    public record Load(double slope, double station) {}
    public record Center(double length, double endDiameter) {}
    public record Part(Center center, boolean groupedStep, boolean terminal, boolean crossflow) {}

    enum Mode { PREVIOUS, SEGMENTS, CENTER, TAIL, CROSSFLOW, COMBINED, NARROW }
    private static final Mode MODE = Mode.valueOf(System.getProperty("study.afterbody", "narrow").toUpperCase(Locale.ROOT));

    private static boolean enabled(Mode method) { return MODE == Mode.COMBINED || MODE == method; }
    private static double start(SymmetricComponent component) { return component.getComponentLocations()[0].x; }
    private static boolean conical(SymmetricComponent c) {
        return c instanceof Transition t && !(t instanceof NoseCone) && t.getShapeType()==Transition.Shape.CONICAL && t.getLength()>0;
    }

    /** Only active, centerline, nonparallel stage components can receive these changes. */
    public static Map<RocketComponent,Part> identify(FlightConfiguration configuration) {
        Map<RocketComponent,Part> map = new IdentityHashMap<>();
        if (MODE==Mode.PREVIOUS) return map;
        List<SymmetricComponent> spine=new ArrayList<>();
        for (AxialStage stage: configuration.getActiveStages()) {
            if (!(stage.getParent() instanceof Rocket) || stage instanceof ParallelStage) continue;
            for (int i=0;i<stage.getChildCount();i++) {
                if(stage.getChild(i) instanceof SymmetricComponent c && c.getLength()>0) spine.add(c);
            }
        }
        spine.sort(Comparator.comparingDouble(BodyPlan::start));
        for (int i=0;i<spine.size();i++) {
            SymmetricComponent c=spine.get(i);
            boolean tail=(enabled(Mode.TAIL) || (MODE==Mode.NARROW && c.getAftRadius()<c.getForeRadius())) && i==spine.size()-1 && conical(c) && i>0 &&
                spine.get(i-1) instanceof BodyTube && touches(spine.get(i-1),c) &&
                Math.abs(spine.get(i-1).getAftRadius()-c.getForeRadius())<1e-6;
            map.put(c,new Part(null,false,tail,enabled(Mode.CROSSFLOW)));
        }
        boolean equalTubesOnly=MODE==Mode.SEGMENTS || MODE==Mode.NARROW;
        if(!equalTubesOnly && !enabled(Mode.CENTER)) return map;
        for (int i=0;i+1<spine.size();i++) {
            if (!(spine.get(i) instanceof NoseCone nose) || !ChartModel.supports(nose) ||
                !(spine.get(i+1) instanceof BodyTube)) continue;
            double base=2*nose.getAftRadius();
            int lastTube=i; int direction=0; double previous=base;
            for(int j=i+1;j<spine.size();j++){
                var c=spine.get(j);
                if(c.getParent()!=nose.getParent() || !touches(spine.get(j-1),c) ||
                   (!(c instanceof BodyTube) && !conical(c))) break;
                double end=2*c.getAftRadius(), fore=2*c.getForeRadius();
                if(Math.abs(fore-previous)>2e-6) break;
                if(equalTubesOnly && (!(c instanceof BodyTube) || Math.abs(end-base)>2e-6)) break;
                if(Math.max(Math.abs(end/base-1),Math.abs(fore/base-1))>.10+1e-10) break;
                int next=end>previous+1e-7?1:(end<previous-1e-7?-1:0);
                if(direction!=0 && next!=0 && direction!=next) break;
                if(next!=0)direction=next;
                previous=end;
                if(c instanceof BodyTube)lastTube=j;
            }
            if(lastTube<=i+1) continue; // ordinary one-tube fixture uses its original chart calculation
            var end=spine.get(lastTube);
            var center=new Center(start(end)+end.getLength()-start(nose)-nose.getLength(),2*end.getAftRadius());
            map.put(nose,new Part(center,false,false,enabled(Mode.CROSSFLOW)));
            for(int j=i+1;j<=lastTube;j++) if(conical(spine.get(j)))
                map.put(spine.get(j),new Part(null,true,false,enabled(Mode.CROSSFLOW)));
        }
        return map;
    }
    private static boolean touches(SymmetricComponent a,SymmetricComponent b){
        return Math.abs(start(a)+a.getLength()-start(b))<1e-6;
    }
    public static Load center(NoseCone nose,Center center,double mach){
        double ln=nose.getLength(),dn=2*nose.getAftRadius(), d1=center.endDiameter();
        double mean=(dn+d1)/2;
        double f=Math.min(5,center.length()*dn/(ln*mean));
        double u=Math.sqrt(mach*mach-1)*dn/ln;
        boolean cone=nose.getShapeType()==Transition.Shape.CONICAL;
        double n=ChartModel.val(cone?ChartData.D4221B:ChartData.D4221A,cone?ChartData.BNB:ChartData.BNA,u,f);
        double[] table=cone?(u<=1?ChartData.DL218B:ChartData.DR218B):(u<=1?ChartData.DL218A:ChartData.DR218A);
        double fraction=ChartModel.val(table,cone?ChartData.BXB:ChartData.BXA,Math.min(u,1/u),f);
        return new Load(n*d1*d1/(dn*dn),fraction*ln*(1+f*mean/dn));
    }
    /** Local force coefficient on fore-diameter area and local CP measured from the taper start. */
    public static Load terminal(double fore,double aft,double length,double mach) {
        if(!(fore>0 && aft>0 && length>0) || Math.abs(aft/fore-1)<1e-8)return null;
        double beta=Math.sqrt(mach*mach-1), ratio=aft/fore;
        if(ratio<1){
            double axis=beta*(fore-aft)/(2*length);
            if(axis>.5 || length/(fore*beta)>2.5) return null;
            double normal=(1-ratio*ratio)*one(AfterTables.T4222A,AfterTables.D4222A,length/(fore*beta));
            double cp=ChartModel.val(AfterTables.D42119,AfterTables.TAIL_AXES,axis,ratio)*length;
            return new Load(normal,cp);
        }
        double theta=Math.atan((aft-fore)/(2*length)), angle=Math.toDegrees(theta);
        if(ratio>3 || angle<5 || angle>90)return null;
        double normal=one(AfterTables.T4222B,AfterTables.D4222B,ratio)*Math.pow(Math.cos(theta),2);
        double moment=ChartModel.val(AfterTables.FLARE_M,AfterTables.FLARE_AXES,angle,1/ratio);
        return new Load(normal,-moment*fore*ratio*ratio*ratio/normal);
    }
    /** Approach the last boattail chart row continuously before reverting to the existing load. */
    public static double terminalWeight(double fore,double aft,double length,double mach){
        if(aft>=fore)return 1;
        double beta=Math.sqrt(mach*mach-1);
        double corner=beta*(fore-aft)/(2*length);
        double fineness=length/(fore*beta);
        return ChartModel.h((.5-corner)/.05)*ChartModel.h((2.5-fineness)/.25);
    }
    public static double crossflow(double mach,double angle){
        return one(AfterTables.T4217B,AfterTables.D4217B,mach*Math.abs(Math.sin(angle)));
    }
    private static double one(double[] axis,double[] values,double arg){
        return ChartModel.val(values,new double[][]{axis},arg);
    }
}
