"""Regenerate the documentation's frozen schema tables, examples and source inventory."""
from pathlib import Path
from dataclasses import fields, MISSING, asdict
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
APP = ROOT.parent.parent / "rocket_UI_v0"
sys.path.insert(0, str(APP / "src"))
from rocket_gnc_monitor.domain import Mission, Sample
from rocket_gnc_monitor.location import decode_mgrs
from rocket_gnc_monitor.zephyrus import CSV_FIELDS

def esc(text):
    mapping = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
               "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
               "^": r"\textasciicircum{}"}
    return "".join(mapping.get(c, c) for c in str(text))

mission_notes = {
"name":"Human-readable mission name.",
"latitude":"WGS84 launch latitude in degrees; -90 to 90.",
"longitude":"WGS84 launch longitude in degrees; -180 to 180.",
"altitude":"Launch ellipsoid altitude in metres; used by geographic transforms.",
"altitude_msl":"Launch mean-sea-level elevation in metres; weather and engine atmosphere.",
"site_configured":"Explicit origin-established flag; required for LIVE trajectory and simulation.",
"launch_location_format":"Entry provenance: latlon, mgrs or pluscode.",
"launch_location_code":"Entered/resolved code; up to 80 characters. Canonical lat/lon remains authoritative.",
"launch_site_name":"Preset name, currently URRG or empty for Custom; up to 80 characters.",
"legacy_altitude":"unknown, ellipsoid, gps_agl or barometric_agl; selects trajectory height interpretation.",
"canard_count":"Number of UI canard slots, integer 0 to 16; four tabs are always added.",
"pointer_latitude":"Virtual antenna WGS84 latitude, degrees; physical tracking retains frozen receiver GPS.",
"pointer_longitude":"Virtual antenna WGS84 longitude, degrees.",
"pointer_altitude":"Virtual antenna WGS84 ellipsoid altitude, metres; physical legacy tracking retains height zero.",
"pointer_site_configured":"Boolean assertion that the antenna location is established; required for virtual trajectory tracking.",
"pointer_location_format":"Antenna entry: latlon, mgrs or relative; relative coordinates are recalculated during validation.",
"pointer_location_code":"MGRS entry provenance, up to 80 characters; canonical coordinates are authoritative for absolute entry.",
"pointer_launch_heading":"True heading from antenna to rocket on its launch pad, 0 to 360 degrees.",
"pointer_launch_distance":"Horizontal antenna-to-pad range in the antenna ENU frame, 0 to 100000 metres.",
"pointer_height_difference":"Antenna minus launch ellipsoid altitude, metres; positive means antenna above launch site.",
"pointer_calibrated":"Retained assertion, always cleared by disk load and mode changes; not a manual-send prerequisite.",
"pointer_az_offset":"Retained offset field; not applied by current legacy manual/tracking dispatch.",
"pointer_el_offset":"Retained offset field; not applied by current legacy manual/tracking dispatch.",
"pointer_el_min":"Stored route-helper envelope minimum; not an enforced operator control limit.",
"pointer_el_max":"Stored route-helper envelope maximum; ordered within -90 to 90 degrees.",
"pointer_az_min":"Stored route-helper azimuth minimum; not enforced by the legacy dispatch path.",
"pointer_az_max":"Stored route-helper azimuth maximum; ordered within 0 to 360 degrees.",
"pointer_full_rotation":"Stored route-helper choice; not a firmware cable-wrap guarantee.",
"freshness":"Maximum acceptable sample age, 0.1 to 60 seconds.",
"video_offset":"Seconds; positive value delays recorded video relative to telemetry.",
"wind":"1 to 200 increasing nonnegative AGL heights with east/north velocity components; max speed 150 m/s.",
"wind_source":"Human-readable profile provenance.",
"weather_raw":"Cached normalized request/result/provider payload, when retrieved.",
"model":"Selected ORK path. Archives embed it and rebind the extracted path.",
"motor_files":"Up to 100 custom curve paths; selected files are embedded in flight archives.",
"simulation_index":"Saved ORK simulation, zero-based integer 0 to 1000.",
"rail_length":"Launch rod length in metres; greater than 0 and at most 100.",
"rail_tilt":"Tilt from vertical in degrees; at least 0 and less than 90.",
"rail_heading":"True-north bearing in degrees; UI range 0 to 359.99.",
"seed":"Integer random seed, 0 to 2147483647.",
"low_battery":"Total-battery alert threshold in volts; 1-second dwell and 0.3 V clearing hysteresis.",
}
sample_notes = {
"t":"Device uptime seconds after wrap extension, or imported equivalent; align separately to flight zero.",
"sequence":"Packet counter; LIVE wire counter is uint16.",
"source":"Provenance such as LIVE, DEMO or LEGACY_CSV. REPLAY is a controller mode, not a rewrite of sample source.",
"received":"Host monotonic receive time in seconds; replay refreshes this for current display freshness.",
"utc":"Unix reception timestamp in seconds; original UTC retained for imported/demo data.",
"altitude":"Reported filtered barometric altitude, metres, or unavailable.",
"velocity":"Reported integrated velocity, metres/second, or unavailable.",
"latitude":"Rocket WGS84 latitude in degrees, or unavailable.",
"longitude":"Rocket WGS84 longitude in degrees, or unavailable.",
"gps_altitude":"Reported GPS height in metres, with explicit mission interpretation.",
"gps_fix":"GPS fix code; geographic display requires at least 3.",
"attitude":"Optional three-element roll/pitch/yaw integrated rotations, degrees; not a qualified attitude solution.",
"rates":"Optional XYZ angular rates, degrees/second; legacy Y sign is retained.",
"acceleration":"Optional XYZ acceleration, metres/second squared.",
"enu":"Optional local east/north/up metres; frame/provenance must be known.",
"battery":"Optional total battery volts, sum of the three cells for LIVE.",
"rssi":"Optional receiver RSSI in dBm.",
"phase":"Received or imported state label; unknown codes remain visible.",
"actuators":"Dictionary by channel name; demand/measured angles or legacy drive when actually available.",
"details":"Extensible decoded legacy values, boot/time metadata, receiver data, raw CSV provenance and quality notes.",
}
csv_notes = [
"Receive UTC, Unix seconds.","Six pyro continuity codes.","Four legacy drive values.",
"Four converted servo angles; first two use 60-degree scale, last two 50-degree scale; good CSV rounded to two decimals.",
"XYZ acceleration, m/s squared.","Filtered barometric altitude, m.","Legacy calibrated temperature, degrees C.",
"XYZ gyro rates, degrees/s.","Rocket fix code.","Rocket latitude, degrees.","Rocket longitude, degrees.",
"GPS height, m; datum depends on firmware/configuration.","Horizontal GPS accuracy, m.","Vertical GPS accuracy, m.",
"Satellite count.","Original raw device clock, milliseconds.","Integrated yaw, degrees.","Integrated pitch, degrees.",
"Integrated roll, degrees.","Legacy state enum string.","Packet counter.","Ground receiver RSSI, dBm.",
"Armed bits as list; good-packet CSV retains two unused zero entries.","Fired bits as list; same good-packet padding.",
"Rejected-packet counter.","Onboard RSSI, dBm.","Reported integrated velocity, m/s.",
"Maximum barometric altitude, m.","Maximum GPS altitude, m.",
"Pyro resistance list; good-packet output pads two unused zero entries.","Three cell voltages, V.","Total current, A.",
"Six rail voltages, V.","Six rail currents, A.","BMS enabled protection bits.","BMS triggered protection bits.",
"BMS temperature, degrees C.","Derived rail-enabled states from voltage proximity to nominal.",
"Legacy angle-from-vertical derived from pitch/yaw, degrees.","Frozen/display receiver latitude convention, rounded to five decimals.",
"Receiver longitude convention, rounded to five decimals.","Legacy ground fix Boolean: trailer fix equals 3.",
"Legacy receiver height: signed wire integer divided by 1000, rounded for display/CSV.",
]
assert set(mission_notes) == {f.name for f in fields(Mission)}
assert set(sample_notes) == {f.name for f in fields(Sample)}
assert len(CSV_FIELDS) == len(csv_notes) == 43

def table(headers, widths, rows):
    columns = "".join("L{"+width+r"\linewidth}" for width in widths)
    return (r"\begin{longtable}{@{}"+columns+r"@{}}"+"\n"+r"\toprule "+
            " & ".join(headers)+r" \\\midrule\endhead"+"\n"+
            "\n".join(" & ".join(row)+r" \\" for row in rows)+"\n"+
            r"\bottomrule\end{longtable}"+"\n")

default_mission = asdict(Mission())
default_names={"wind":"One calm layer at height 0","weather_raw":"{}","motor_files":"[]"}
mrows=[]
for f in fields(Mission):
    value=default_mission[f.name]
    default=default_names.get(f.name, str(value) if value != "" else "(empty)")
    mrows.append([r"\code{"+f.name+"}",esc(default),esc(mission_notes[f.name])])
srows=[]
for f in fields(Sample):
    default="required" if f.default is MISSING and f.default_factory is MISSING else "runtime factory" if f.default_factory is not MISSING else str(f.default)
    srows.append([r"\code{"+f.name+"}",esc(default),esc(sample_notes[f.name])])
(ROOT/"parts/mission-fields.tex").write_text(table(["Field","Default","Meaning"],[".28",".18",".47"],mrows))
(ROOT/"parts/sample-fields.tex").write_text(table(["Field","Default","Meaning"],[".22",".20",".51"],srows))
(ROOT/"parts/csv-fields.tex").write_text(table(["Column","Field","Meaning"],[".08",".34",".51"],[
    [str(i),r"\code{"+name+"}",esc(note)] for i,(name,note) in enumerate(zip(CSV_FIELDS,csv_notes),1)]))

point=decode_mgrs("18TUN2061530290")
mission=Mission(name="URRG template - verify launch elevations",launch_site_name="URRG",
                launch_location_format="mgrs",launch_location_code=point.code,
                latitude=point.latitude,longitude=point.longitude,site_configured=False)
mission.save(ROOT/"examples/urrg-mission.json")
wind={"schema_version":1,"source":"Documentation example only",
      "layers":[{"height":0,"east":0,"north":0},{"height":1000,"east":3,"north":-1}]}
(ROOT/"examples/wind.json").write_text(json.dumps(wind,indent=2)+"\n")
(ROOT/"examples/reference.csv").write_text("time_s,east_m,north_m,up_m\n0,0,0,0\n1,1,2,10\n2,2,4,20\n")
ref={"schema_version":1,"frame":"ENU","units":"m,s","name":"Documentation geometry example",
     "altitude_datum":"launch_relative","origin":[point.latitude,point.longitude,0],
     "synthetic":True,"controlled_model_validated":False}
(ROOT/"examples/reference.json").write_text(json.dumps(ref,indent=2)+"\n")

paths=list((APP/"src").rglob("*.py"))+list((APP/"simulation_bridge/src").rglob("*.java"))
paths+=list((APP/"scripts").glob("*.py"))+list((APP/"tests").glob("*.py"))+list((APP/"packaging").glob("*"))
paths+=list((APP/"resources").rglob("*"))+list((APP/"docs").glob("*.md"))
paths+=[APP/n for n in ["pyproject.toml","uv.lock","requirements-build.txt","Makefile","Makefile.macos","Makefile.windows"]]
entries={}
for path in sorted(set(paths)):
    if path.is_file():
        entries[path.relative_to(APP).as_posix()]={"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size}
style=Path("/Users/mdn/_CERN/protozero/_GenMAPS_block_inventory/docs/GenMAPS_CLASSIFICATION_PIPELINE_ARCHITECTURE.tex")
previous_path=ROOT/"evidence/source-manifest.json"
previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
# The supplied style reference lives outside this repository. Retain its audited
# hash when refreshing documentation on a teammate's machine.
style_hash=(hashlib.sha256(style.read_bytes()).hexdigest() if style.is_file()
            else previous.get("style_reference_sha256"))
manifest={"documentation_date":"2026-09-21","app_version":"0.1.0",
          "repository_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=APP,text=True).strip(),
          "scope":"Exact app files reviewed; repository HEAD can include unrelated project work.",
          "style_reference":str(style),"style_reference_sha256":style_hash,
          "files":entries}
(ROOT/"evidence/source-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
evidence=APP/"build/flight-files/validation-report.json"
if evidence.exists():
    (ROOT/"evidence/application-validation-2026-09-20.json").write_bytes(evidence.read_bytes())
print("Generated complete Mission/Sample/CSV tables, examples and source inventory.")
