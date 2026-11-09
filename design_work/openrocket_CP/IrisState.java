import com.google.inject.AbstractModule;
import com.google.inject.Guice;
import com.google.inject.util.Modules;
import info.openrocket.core.database.motor.MotorDatabase;
import info.openrocket.core.database.motor.ThrustCurveMotorSetDatabase;
import info.openrocket.core.document.Simulation;
import info.openrocket.core.file.GeneralRocketLoader;
import info.openrocket.core.file.GeneralRocketSaver;
import info.openrocket.core.file.motor.RASPMotorLoader;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.models.wind.PinkNoiseWindModel;
import info.openrocket.core.models.wind.MultiLevelPinkNoiseWindModel;
import info.openrocket.core.simulation.SimulationStatus;
import info.openrocket.core.simulation.listeners.AbstractSimulationListener;
import info.openrocket.core.simulation.FlightDataType;
import info.openrocket.core.startup.Application;
import info.openrocket.swing.startup.GuiModule;
import java.nio.file.*;
import java.io.PrintWriter;
import static info.openrocket.core.simulation.FlightDataType.*;

/** Compare the first simulation in an .ork with identical inputs and wind realization. */
public final class IrisState {
    public static void main(String[] args) throws Exception {
        if (args.length < 3) throw new IllegalArgumentException("Usage: CompareFlights rocket.ork output-directory motor.eng ...");
        Path source = Path.of(args[0]), output = Path.of(args[1]);

        var database = new ThrustCurveMotorSetDatabase();
        System.setProperty("openrocket.bypass.presets", "true");
        System.setProperty("openrocket.bypass.motors", "true");
        var gui = new GuiModule();
        Application.setInjector(Guice.createInjector(Modules.override(gui).with(new AbstractModule() {
            @Override protected void configure() {
                bind(ThrustCurveMotorSetDatabase.class).toInstance(database);
                bind(MotorDatabase.class).toInstance(database);
            }
        }), new PluginModule()));
        gui.startLoader();
        for (int i = 2; i < args.length; i++) {
            Path curve = Path.of(args[i]);
            try (var stream = Files.newInputStream(curve)) {
                for (var definition : new RASPMotorLoader().load(stream, curve.getFileName().toString())) {
                    var motor = definition.build();
                    database.addMotor(motor);
                    System.out.println("MOTOR " + motor.getDesignation() + " " + motor.getDigest());
                }
            }
        }
        var loader = new GeneralRocketLoader(source.toFile());
        var document = loader.load();
        System.out.println("LOAD " + loader.getWarnings());

        var cfg=document.getSimulation(0).getActiveConfiguration();
        for (boolean full : new boolean[]{true,false}) {
            if(full)cfg.setAllStages();else cfg.setOnlyStage(0);
            var mass=info.openrocket.core.masscalc.MassCalculator.calculateLaunch(cfg);
            System.out.printf(java.util.Locale.ROOT,"%s mass=%.9f kg CG=%.9f m (%.7f in), diameter=%.6f%n",full?"full":"sustainer",mass.getMass(),mass.getCM().x,mass.getCM().x/.0254,cfg.getReferenceLength());
        }
        if(!output.toString().equals("-")){
            var all=Files.readAllLines(output);
            try(var w=new PrintWriter(Files.newBufferedWriter(Path.of(output.toString()+".out.csv")))){
                w.println("time_s,stage,mach,alpha_deg,D_m,x0_D,n0,x1_D,n1");
                String previous="";
                var legacy=new info.openrocket.core.aerodynamics.BarrowmanCalculator(false);
                var finite=new info.openrocket.core.aerodynamics.BarrowmanCalculator(true);
                for(String row:all.subList(1,all.size())){
                    var v=row.split(",");String stage=v[1];
                    if(!previous.equals(stage)){
                        cfg=document.getSimulation(0).getActiveConfiguration().clone();
                        if(stage.equals("B"))cfg.setAllStages();else if(stage.equals("S"))cfg.setOnlyStage(0);else throw new IllegalArgumentException(stage);
                        cfg=cfg.clone(); // Clear cached reference dimensions after changing active stages.
                        legacy=new info.openrocket.core.aerodynamics.BarrowmanCalculator(false);
                        finite=new info.openrocket.core.aerodynamics.BarrowmanCalculator(true);
                        previous=stage;
                    }
                    var c=new info.openrocket.core.aerodynamics.FlightConditions(cfg);
                    c.setTheta(0);c.setMach(Double.parseDouble(v[2]));c.setAOA(Math.toRadians(Double.parseDouble(v[3])));
                    double d=c.getRefLength();var a=legacy.getCP(cfg,c,null);var b=finite.getCP(cfg,c,null);
                    w.printf(java.util.Locale.ROOT,"%s,%s,%s,%s,%.10f,%.12f,%.12f,%.12f,%.12f%n",v[0],stage,v[2],v[3],d,a.x/d,a.weight,b.x/d,b.weight);
                }
                if(w.checkError())throw new java.io.IOException("Cannot write static states");
            }
        }
        System.exit(0);
    }
}
