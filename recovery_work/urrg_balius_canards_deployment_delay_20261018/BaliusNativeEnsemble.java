import com.google.inject.*;
import com.google.inject.util.Modules;
import info.openrocket.core.database.MotorDatabaseLoader;
import info.openrocket.core.database.motor.*;
import info.openrocket.core.document.*;
import info.openrocket.core.file.*;
import info.openrocket.core.plugin.PluginModule;
import info.openrocket.core.rocketcomponent.*;
import info.openrocket.core.simulation.*;
import info.openrocket.core.simulation.ensemble.*;
import info.openrocket.core.startup.Application;
import info.openrocket.core.util.MathUtil;
import info.openrocket.swing.startup.GuiModule;
import jakarta.json.*;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.GZIPOutputStream;

/** Calls the installed OpenRocket app's native ensemble mode, without a custom variation listener. */
public class BaliusNativeEnsemble {
    static String sha(Path p) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));
    }
    static double mean(double[] a) { return Arrays.stream(a).average().orElseThrow(); }
    static double sd(double[] a) {
        double m=mean(a);return Math.sqrt(Arrays.stream(a).map(x->(x-m)*(x-m)).sum()/(a.length-1));
    }
    static PrintWriter writer(Path p) throws Exception {
        return new PrintWriter(Files.newBufferedWriter(p));
    }
    static double at(FlightDataBranch b, FlightDataType type, double t) {
        return Double.isFinite(t) ? MathUtil.interpolate(b.get(FlightDataType.TYPE_TIME),b.get(type),t) : Double.NaN;
    }
    public static void main(String[] args) throws Exception {
        Locale.setDefault(Locale.US);
        Path source=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectories(out);
        int runs=Integer.parseInt(args[2]),seed=Integer.parseInt(args[5]),threads=Integer.parseInt(args[6]);
        double massSigma=Double.parseDouble(args[3]),cdSigma=Double.parseDouble(args[4]);
        String inputHash=sha(source);
        System.setProperty("openrocket.bypass.presets","true");
        System.setProperty("openrocket.bypass.motors","true");
        var motorLoader=new MotorDatabaseLoader();var module=new GuiModule();
        Application.setInjector(Guice.createInjector(Modules.override(module).with(new AbstractModule() {
            @Override protected void configure() {
                bind(ThrustCurveMotorSetDatabase.class).toProvider(motorLoader::getDatabase).in(Scopes.SINGLETON);
                bind(MotorDatabase.class).toProvider(motorLoader::getDatabase).in(Scopes.SINGLETON);
            }
        }),new PluginModule()));
        module.startLoader();motorLoader.startLoading();motorLoader.blockUntilLoaded();
        var loader=new GeneralRocketLoader(source.toFile());var original=loader.load();
        System.out.println("Loader warnings: "+loader.getWarnings());
        if (!loader.getWarnings().isEmpty()) throw new IllegalStateException("Review loader warnings");
        var baseline=original.getSimulation(3);
        var rocket=(Rocket)baseline.getRocket().copyWithOriginalID();
        var document=OpenRocketDocumentFactory.createDocumentFromRocket(rocket);
        var simulation=baseline.duplicateSimulation(document,rocket);document.addSimulation(simulation);
        simulation.setName("J800T ensemble — mass σ 5%, Cd σ 2%");
        if (!simulation.getSimulationExtensions().isEmpty()) throw new IllegalStateException("Unexpected extension");
        var motors=simulation.getActiveConfiguration().getActiveMotors();
        if (motors.size()!=1 || !motors.iterator().next().getMotor().getDesignation().equals("J800T"))
            throw new IllegalStateException("Expected source J800T configuration");
        var opts=simulation.getOptions();
        opts.setLaunchLatitude(42.70416776971639);opts.setLaunchLongitude(-77.19029501648315);
        opts.setLaunchAltitude(268.603118896);
        if (opts.getWindSpeedAverage()!=2 || opts.getLaunchRodLength()!=1 || opts.getLaunchRodAngle()!=0)
            throw new IllegalStateException("Unexpected baseline wind/rail");
        if (args.length>7) {
            double windMean=Double.parseDouble(args[7]);
            if (!Double.isFinite(windMean) || windMean<0) throw new IllegalArgumentException("Invalid wind mean");
            double intensity=opts.getWindTurbulenceIntensity();
            opts.setWindSpeedAverage(windMean);
            opts.setWindTurbulenceIntensity(intensity);
            if (Math.abs(opts.getWindSpeedAverage()-windMean)>1e-12
                    || Math.abs(opts.getWindSpeedDeviation()-windMean*intensity)>1e-12)
                throw new IllegalStateException("Wind override not applied");
        }
        System.out.printf("Wind: mean=%.8f m/s, direction=%.3f deg, turbulence=%.5f, deviation=%.8f m/s%n",
            opts.getWindSpeedAverage(),Math.toDegrees(opts.getWindDirection()),
            opts.getWindTurbulenceIntensity(),opts.getWindSpeedDeviation());
        var settings=new EnsembleSettings(true,runs,0,.05,0,0,0,seed,massSigma,cdSigma,0,0,0,threads);
        opts.setEnsembleSettings(settings);opts.setRandomSeed(seed);
        JsonObjectBuilder recovery=Json.createObjectBuilder();
        for(var component:rocket) if(component instanceof Parachute chute) {
            var deployment=chute.getDeploymentConfigurations().get(simulation.getFlightConfigurationId());
            if(Math.abs(chute.getDiameter()-2.109216)>1e-10 || chute.getCD()!=.68
                    || !deployment.getDeployEvent().name().equals("APOGEE") || deployment.getDeployDelay()!=1)
                throw new IllegalStateException("Unexpected corrected recovery configuration");
            if(args.length>8) {
                double delay=Double.parseDouble(args[8]);
                if(!Double.isFinite(delay)||delay<0)throw new IllegalArgumentException("Invalid deployment delay");
                deployment.setDeployDelay(delay);
                simulation.setName(String.format("J800T ensemble — main at apogee + %.3f s",delay));
            }
            recovery.add("diameter_m",chute.getDiameter()).add("nominal_cd",chute.getCD())
                .add("deployment",deployment.getDeployEvent().name()).add("delay_s",deployment.getDeployDelay());
        }
        simulation.simulate(); // Native EnsembleRunner selected by the enabled EnsembleSettings.
        var data=simulation.getSimulatedData();var ensemble=data.getEnsembleResult();
        if(ensemble==null || ensemble.individualRuns()==null || ensemble.individualRuns().size()!=runs)
            throw new IllegalStateException("Native ensemble result missing or incomplete");
        var altitude=ensemble.samples(0,EnsembleMetric.MAX_ALTITUDE);
        var apogeeTime=ensemble.samples(0,EnsembleMetric.TIME_TO_APOGEE);
        if(altitude.length!=runs || apogeeTime.length!=runs) throw new IllegalStateException("Missing metrics");
        var average=data.getBranch(0);var deviation=ensemble.deviation(0);
        var bandTimes=average.get(FlightDataType.TYPE_TIME);
        var bandAltitudes=average.get(FlightDataType.TYPE_ALTITUDE);
        var bandDeviations=deviation.get(FlightDataType.TYPE_ALTITUDE);
        try(var w=writer(out.resolve("native_altitude_band.csv"))) {
            w.println("time_s,mean_altitude_m,stdev_altitude_m");
            for(int j=0;j<average.getLength();j++) {
                double t=bandTimes.get(j);
                double a=bandAltitudes.get(j);
                double d=bandDeviations.get(j);
                if(!Double.isFinite(a)||!Double.isFinite(d)) throw new IllegalStateException("Missing altitude band");
                w.printf("%.17g,%.17g,%.17g%n",t,a,d);
            }
        }
        Files.createDirectories(out.resolve("traces"));
        try(var w=writer(out.resolve("individual_metrics.csv"))) {
            w.println("run,mass_multiplier,cd_multiplier,apogee_m,time_to_apogee_s,apogee_event_s,ground_hit_s,launch_mass_kg,rail_speed_mps,impact_total_mps,impact_descent_mps,deployment_s,deployment_altitude_m,deployment_descent_mps,deployment_total_mps,tumble_s,impact_acceleration_z_mps2");
            for(int i=0;i<runs;i++) {
                var inputs=ensemble.individualRuns().parameters(i);
                var flight=ensemble.individualRuns().read(i,document);var branch=flight.getBranch(0);
                if(branch.getFirstEvent(FlightEvent.Type.APOGEE)==null
                        ||branch.getFirstEvent(FlightEvent.Type.GROUND_HIT)==null
                        ||branch.getFirstEvent(FlightEvent.Type.SIM_ABORT)!=null)
                    throw new IllegalStateException("Incomplete ensemble member "+(i+1));
                if(Math.abs(altitude[i]-flight.getMaxAltitude())>1e-7
                        ||Math.abs(apogeeTime[i]-flight.getTimeToApogee())>1e-7)
                    throw new IllegalStateException("Archive metric disagreement");
                var deployEvent=branch.getFirstEvent(FlightEvent.Type.RECOVERY_DEVICE_DEPLOYMENT);
                var tumbleEvent=branch.getFirstEvent(FlightEvent.Type.TUMBLE);
                double deployTime=deployEvent==null?Double.NaN:deployEvent.getTime();
                double groundTime=branch.getFirstEvent(FlightEvent.Type.GROUND_HIT).getTime();
                w.printf("%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g%n",i+1,
                    inputs.massMultiplier(),inputs.dragMultiplier(),altitude[i],apogeeTime[i],
                    branch.getFirstEvent(FlightEvent.Type.APOGEE).getTime(),
                    branch.getFirstEvent(FlightEvent.Type.GROUND_HIT).getTime(),
                    branch.get(FlightDataType.TYPE_MASS).get(0),flight.getLaunchRodVelocity(),
                    flight.getGroundHitVelocity(),-at(branch,FlightDataType.TYPE_VELOCITY_Z,groundTime),
                    deployTime,at(branch,FlightDataType.TYPE_ALTITUDE,deployTime),
                    -at(branch,FlightDataType.TYPE_VELOCITY_Z,deployTime),flight.getDeploymentVelocity(),
                    tumbleEvent==null?Double.NaN:tumbleEvent.getTime(),at(branch,FlightDataType.TYPE_ACCELERATION_Z,groundTime));
                try(var tr=new PrintWriter(new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(
                        out.resolve("traces").resolve(String.format("run_%04d.csv.gz",i+1))))))) {
                    var times=branch.get(FlightDataType.TYPE_TIME);
                    var heights=branch.get(FlightDataType.TYPE_ALTITUDE);
                    var verticalVelocities=branch.get(FlightDataType.TYPE_VELOCITY_Z);
                    var totalVelocities=branch.get(FlightDataType.TYPE_VELOCITY_TOTAL);
                    tr.println("time_s,altitude_m,velocity_z_mps,velocity_total_mps");
                    for(int j=0;j<branch.getLength();j++) tr.printf("%.17g,%.17g,%.17g,%.17g%n",
                        times.get(j),heights.get(j),verticalVelocities.get(j),totalVelocities.get(j));
                }
            }
        }
        var settingsJson=Json.createObjectBuilder();settings.attributes().forEach(settingsJson::add);
        var summary=Json.createObjectBuilder().add("source_path",source.toString()).add("source_sha256",inputHash)
            .add("engine","Native EnsembleRunner from /Applications/OpenRocket_MIT.app")
            .add("motor","J800T").add("settings",settingsJson).add("recovery",recovery)
            .add("completed",runs).add("attempted",runs).add("excluded",0)
            .add("wind_mean_mps",opts.getWindSpeedAverage()).add("wind_direction_deg",Math.toDegrees(opts.getWindDirection()))
            .add("wind_speed_deviation_mps",opts.getWindSpeedDeviation())
            .add("wind_turbulence_intensity",opts.getWindTurbulenceIntensity()).add("wind_realization_fixed",true)
            .add("launch_latitude_deg",opts.getLaunchLatitude()).add("launch_longitude_deg",opts.getLaunchLongitude())
            .add("launch_elevation_m",opts.getLaunchAltitude()).add("rail_length_m",opts.getLaunchRodLength())
            .add("apogee_mean_m",mean(altitude)).add("apogee_stdev_m",sd(altitude))
            .add("apogee_time_mean_s",mean(apogeeTime)).add("apogee_time_stdev_s",sd(apogeeTime))
            .add("minimum_member_apogee_m",Arrays.stream(altitude).min().orElseThrow())
            .add("maximum_member_apogee_m",Arrays.stream(altitude).max().orElseThrow())
            .add("standard_deviation","sample N-1; flight-to-flight spread, not confidence interval of mean")
            .add("plot_data","Unmodified native ensemble mean and pointwise sample standard deviation")
            .add("mass_definition","Whole vehicle mass and inertias scaled, including remaining propellant; CG fixed")
            .add("cd_definition","Native drag multiplier scales aerodynamic Cd and recovery-phase drag; nominal parachute unchanged")
            .add("warnings",data.getWarningSet().toString()).build();
        Files.writeString(out.resolve("summary.json"),summary.toString());
        if(runs>=10 && (args.length<=9 || Boolean.parseBoolean(args[9]))) {
            var storage=new StorageOptions();storage.setFileType(StorageOptions.FileType.OPENROCKET);
            storage.setSaveSimulationData(true);storage.setExplicitlySet(true);
            var saver=new GeneralRocketSaver();
            saver.save(out.resolve("J800T_native_ensemble.ork").toFile(),document,storage);
            if(!saver.getErrors().isEmpty()) throw new IllegalStateException("ORK save failed: "+saver.getErrors());
            System.out.println("Saved native ensemble ORK; warnings="+saver.getWarnings());
        }
        if(!inputHash.equals(sha(source)))throw new IllegalStateException("Source changed during run");
        System.out.println("RESULT "+summary);System.exit(0);
    }
}
