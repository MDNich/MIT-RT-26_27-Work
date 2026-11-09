package info.openrocket.core.aerodynamics.barrowman;
import info.openrocket.core.rocketcomponent.*;
/** Study-only port of selected thin-wing and body charts, not the full Digital DATCOM program. */
final class ChartModel {
    static double h(double x){x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);}
    static double envelope(double m,double a){return h((m-1.1)/.4)*h((5-m)/.35)*h((8-Math.abs(Math.toDegrees(a)))/5);}
    // Multilinear interpolant; each first axis is contiguous (Fortran order). Saturate to chart limits.
    static double val(double[] tab,double[][] axes,double... coords){
        int ix=0,stride=1; int[] steps=new int[axes.length];double[] f=new double[axes.length];
        for(int k=0;k<axes.length;k++){
            double[] ax=axes[k];double x=Math.max(ax[0],Math.min(ax[ax.length-1],coords[k]));int j=0;
            while(j<ax.length-2&&ax[j+1]<x)j++;
            ix+=j*stride; steps[k]=stride;stride*=ax.length;f[k]=(x-ax[j])/(ax[j+1]-ax[j]);
        }
        double sum=0;for(int mask=0;mask<(1<<axes.length);mask++){
            int i=ix;double w=1;for(int k=0;k<axes.length;k++){if((mask&(1<<k))!=0){i+=steps[k];w*=f[k];}else w*=1-f[k];}
            sum+=w*tab[i];
        }return sum;
    }
    static double slope(double m,double cr,double ct,double s,double sweep){
        double beta=Math.sqrt(m*m-1), ar=4*s/(cr+ct), b=ar*beta, tan=sweep/s, arTan=ar*tan;
        double rect=b>1?(4-2/b)/beta:ar*val(ChartData.DG3246,new double[][]{ChartData.G13246},b);
        if(tan<=0 || arTan<=0)return rect;
        double ratio=beta/tan, z=val(ChartData.W,ChartData.WAX,ratio,arTan,ct/cr)/(ratio>=1?beta:tan);
        // Below the first tabulated AR*tan(sweep), approach the rectangular solution at the same AR.
        return rect+(z-rect)*h(arTan/.25);
    }
    static boolean supports(NoseCone n){return n.getParent() instanceof AxialStage && n.getForeRadius()<1e-8 &&
        (n.getShapeType()==Transition.Shape.CONICAL || n.getShapeType()==Transition.Shape.OGIVE && Math.abs(n.getShapeParameter()-1)<1e-7 ||
         n.getShapeType()==Transition.Shape.HAACK && Math.abs(n.getShapeParameter())<1e-7) &&
         n.getNextSymmetricComponent() instanceof BodyTube b && b.getParent()==n.getParent() && Math.abs(b.getOuterRadius()-n.getAftRadius())<1e-5;}
    // Return normal slope based on nose area and CP from the tip in metres for this pair.
    static double[] nose(NoseCone n,double m){
        double ln=n.getLength(), d=2*n.getAftRadius(), body=n.getNextSymmetricComponent().getLength();
        double f=Math.min(5.,body/ln),u=Math.sqrt(m*m-1)*d/ln;boolean cone=n.getShapeType()==Transition.Shape.CONICAL;
        double normal=val(cone?ChartData.D4221B:ChartData.D4221A,cone?ChartData.BNB:ChartData.BNA,u,f);
        double[] tab=cone?(u<=1?ChartData.DL218B:ChartData.DR218B):(u<=1?ChartData.DL218A:ChartData.DR218A);
        double pos=val(tab,cone?ChartData.BXB:ChartData.BXA,u<=1?u:1/u,f)*ln*(1+f);
        return new double[]{normal,pos};
    }
}
