import com.google.inject.*;
import com.google.inject.util.Modules;
import info.openrocket.core.database.MotorDatabaseLoader;
import info.openrocket.core.database.motor.*;
import info.openrocket.core.document.*;
import info.openrocket.core.file.*;
import info.openrocket.core.models.wind.*;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.simulation.*;
import info.openrocket.core.simulation.listeners.AbstractSimulationListener;
import info.openrocket.core.startup.Application;
import info.openrocket.swing.startup.GuiModule;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Run the MIT OpenRocket engine on explicit, reproducible wind cases. */
public class RecoveryBatch {
    public static void main(String[] args) throws Exception {
        if (args.length != 6) throw new IllegalArgumentException("ORK CASES.csv RESULTS.csv LAT LON ELEVATION_M");
        Locale.setDefault(Locale.US);
        System.setProperty("openrocket.bypass.presets", "true");
        System.setProperty("openrocket.bypass.motors", "true");
        var motorLoader = new MotorDatabaseLoader();
        var module = new GuiModule();
        Application.setInjector(Guice.createInjector(Modules.override(module).with(new AbstractModule() {
            @Override protected void configure() {
                bind(ThrustCurveMotorSetDatabase.class).toProvider(motorLoader::getDatabase).in(Scopes.SINGLETON);
                bind(MotorDatabase.class).toProvider(motorLoader::getDatabase).in(Scopes.SINGLETON);
            }
        }), new PluginModule()));
        module.startLoader(); motorLoader.startLoading(); motorLoader.blockUntilLoaded();
        var loader = new GeneralRocketLoader(Path.of(args[0]).toFile());
        var doc = loader.load();
        System.out.println("Loader warnings: " + loader.getWarnings());
        var cases = Files.readAllLines(Path.of(args[1]));
        try (var out = new PrintWriter(Files.newBufferedWriter(Path.of(args[2])))) {
            out.println("case_id,simulation_index,ground_wind_mps,cloud_wind_mps,wind_from_deg,turbulence,seed,elevation_m,apogee_m,flight_time_s,east_m,north_m,radius_m,vertical_landing_mps,apogee_time_s,launch_mass_kg,landing_mass_kg,rail_speed_mps,deployment_time_s,deployment_speed_mps,ground_hit,warnings");
            for (int row = 1; row < cases.size(); row++) {
                var c = cases.get(row).split(",");
                int simIndex = Integer.parseInt(c[1]);
                var simulation = doc.getSimulation(simIndex);
                // The two non-FC source simulations are used without design or recovery edits.
                if (!simulation.getSimulationExtensions().isEmpty())
                    throw new IllegalArgumentException("Use an unextended source simulation");
                if (!simulation.getActiveConfiguration().hasMotors())
                    throw new IllegalStateException("Unresolved motor in " + simulation.getName());
                var opts = simulation.getOptions();
                opts.setLaunchLatitude(Double.parseDouble(args[3]));
                opts.setLaunchLongitude(Double.parseDouble(args[4]));
                double elevation = c.length > 7 ? Double.parseDouble(c[7]) : Double.parseDouble(args[5]);
                opts.setLaunchAltitude(elevation);
                opts.setISAAtmosphere(true);
                double ground = Double.parseDouble(c[2]), cloud = Double.parseDouble(c[3]);
                double direction = Math.toRadians(Double.parseDouble(c[4]));
                double turbulence = Double.parseDouble(c[5]);
                final int seed = Integer.parseInt(c[6]);
                opts.setRandomSeed(seed);
                WindModel configuredWind;
                if (ground == cloud) {
                    opts.setWindModelType(WindModelType.AVERAGE);
                    var wind = opts.getAverageWindModel();
                    wind.setAverage(ground);
                    wind.setDirection(direction);
                    wind.setStandardDeviation(turbulence * ground);
                    configuredWind = wind.withSeed(seed);
                } else {
                    opts.setWindModelType(WindModelType.MULTI_LEVEL);
                    var wind = opts.getMultiLevelWindModel();
                    wind.clearLevels();
                    wind.setAltitudeReference(WindModel.AltitudeReference.AGL);
                    wind.addWindLevel(0, ground, direction, turbulence * ground);
                    wind.addWindLevel(3048, cloud, direction, turbulence * cloud);
                    configuredWind = wind.withSeed(seed);
                }
                final WindModel seededWind = configuredWind;
                simulation.simulate(new AbstractSimulationListener() {
                    @Override public void startSimulation(SimulationStatus status) {
                        status.getSimulationConditions().setWindModel(seededWind);
                    }
                });
                var data = simulation.getSimulatedData();
                var b = data.getBranch(0);
                var groundHit = b.getLastEvent(FlightEvent.Type.GROUND_HIT);
                var deployment = b.getLastEvent(FlightEvent.Type.RECOVERY_DEVICE_DEPLOYMENT);
                double east = b.getLast(FlightDataType.TYPE_POSITION_X);
                double north = b.getLast(FlightDataType.TYPE_POSITION_Y);
                var abort = b.getLastEvent(FlightEvent.Type.SIM_ABORT);
                String warnings = (data.getWarningSet().toString() + (abort==null ? "" : " ABORT: " + abort.getData()))
                    .replace('"', '\'').replace('\n', ' ');
                out.printf("%s,%d,%.9f,%.9f,%.9f,%.9f,%d,%.6f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%s,\"%s\"%n",
                    c[0],simIndex,ground,cloud,Double.parseDouble(c[4]),turbulence,seed,elevation,
                    data.getMaxAltitude(),data.getFlightTime(),east,north,Math.hypot(east,north),
                    Math.abs(b.getLast(FlightDataType.TYPE_VELOCITY_Z)),data.getTimeToApogee(),
                    b.get(FlightDataType.TYPE_MASS).get(0),b.getLast(FlightDataType.TYPE_MASS),
                    data.getLaunchRodVelocity(),deployment==null ? Double.NaN : deployment.getTime(),
                    data.getDeploymentVelocity(),groundHit!=null,warnings);
                out.flush();
                if (row % 50 == 0) System.err.println("Completed " + row + "/" + (cases.size()-1));
            }
        }
        System.exit(0);
    }
}
