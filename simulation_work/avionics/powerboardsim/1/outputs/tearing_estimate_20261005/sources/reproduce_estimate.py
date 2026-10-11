#!/usr/bin/env python3
"""Reproduce an assumed nickel tearing law. Does not launch or modify ANSYS."""
import csv, hashlib, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SRC = ROOT / "outputs/granta_audit_20261005/records/nickel200_annealed_sheet_20C.csv"
rows = list(csv.DictReader(SRC.open()))
p_end = float(rows[-1]["true_plastic_strain"])
s_end = float(rows[-1]["true_stress_MPa"])
tail = [(math.log(float(r["true_plastic_strain"])), math.log(float(r["true_stress_MPa"])))
        for r in rows if float(r["true_plastic_strain"]) >= 0.15]
xm = sum(x for x,y in tail)/len(tail)
ym = sum(y for x,y in tail)/len(tail)
n = sum((x-xm)*(y-ym) for x,y in tail)/sum((x-xm)**2 for x,y in tail)
def onset(eta, e0):
    if eta < 0:
        return None # No compression branch supplied: stop and assess shear/pressure failure.
    return e0*math.exp(-1.5*max(eta-1/3,0.0))
def stress_extension(p, branch):
    assert p >= p_end
    return s_end if branch == "plateau" else s_end*(p/p_end)**n

params = {
 "status":"Exploratory engineering assumption, not calibrated; no FE solve performed",
 "date":"2026-10-05",
 "material_assumption":"Soft/annealed commercially pure nickel, 20 C, quasi-static",
 "units":{"length":"mm","stress":"MPa","force":"N","strain":"dimensionless"},
 "thickness_mm":0.15,
 "damage_initiation":{
   "reference_eta":1/3,"reference_strain_cases":[0.1,0.3,0.6],
   "nominal_reference_strain":0.3,"beta":1.5,
   "formula":"eps_i(eta)=eps0*exp(-beta*max(eta-1/3,0)) for eta>=0",
   "compression_domain":"Unspecified for eta<0; do not extrapolate or interpret as infinite fracture resistance",
   "low_triaxiality":"Plateau below eta=1/3 is an analyst assumption; Lode/shear dependence omitted",
   "accumulator":"omega=integral(d_equivalent_plastic_strain/eps_i(eta)); initiation at omega=1"
 },
 "damage_evolution":{
   "type":"Linear scalar damage versus relative equivalent plastic displacement",
   "u_full_mm_cases":[0.03,0.12,0.24],"nominal_u_full_mm":0.12,
   "formula":"u_p=integral(L_ch*d_equivalent_plastic_strain) after initiation; d=min(u_p/u_full,1)",
   "length_note":"Use verified solver characteristic length; 0.15 mm is only an assumed physical band used to estimate u_full."
 },
 "derivation":{
   "bar_reduction_of_area_21C":[0.66,0.78],
   "axial_log_fracture_strain_proxy":[-math.log(1-r) for r in [0.66,0.78]],
   "nominal_band_mm":0.15,
   "unrounded_u_full_mm":0.15*(-math.log(1-0.66)-0.3),
   "basis":"Special Metals Table 13 bar data plus assumed onset and band; not a thin-strip test",
   "engineering_elongation_log_scale":math.log(1.4),
   "log_scale_note":"Context for choosing 0.3 only, not conversion of gauge elongation into local damage strain"
 },
 "hardening":{
   "measured_proxy_end_plastic_strain":p_end,"end_stress_MPa":s_end,
   "tail_log_fit_exponent":n,
   "extrapolation_A":"Hold true stress at last exported value",
   "extrapolation_B":"sigma=sigma_end*(p/p_end)^n, n from log-log regression for p>=0.15 in exported data",
   "note":"Both extensions beyond 0.199999 are assumed and must be varied independently of damage",
   "extension_stop_strain":1.6
 },
 "source_csv_sha256":hashlib.sha256(SRC.read_bytes()).hexdigest(),
 "existing_FE":{"ux_mm":0.5,"reaction_N":8.1244061726,"peak_summary_EPPL":0.022279217374,
   "note":"Different plasticity law, no damage, no triaxiality path; not used to estimate rupture force"},
 "implementation":"Conceptual material proposal; no native APDL compatibility proof or material assignment"
}
(OUT/"estimated_tearing_law.json").write_text(json.dumps(params,indent=2)+"\n")
etas = [0,1/3,0.5,2/3,1.0]
with (OUT/"estimated_initiation.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["triaxiality","low_ductility","nominal","high_ductility"])
    for eta in etas: w.writerow([eta]+[onset(eta,e) for e in [.1,.3,.6]])
with (OUT/"assumed_hardening_extensions.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["plastic_strain","plateau_MPa","power_law_MPa"])
    for p in [p_end,.3,.4,.6,.8,1,1.2,1.6]:
        w.writerow([p,stress_extension(p,"plateau"),stress_extension(p,"power")])
assert abs(onset(1/3,.3)-.3)<1e-12
assert abs(onset(2/3,.3)-.18195919791379)<1e-12
assert all(onset(b,.3)<=onset(a,.3) for a,b in zip(etas,etas[1:]))
assert .1 < params["derivation"]["unrounded_u_full_mm"] < .13
assert 0 < n < 1
(OUT/"validation.json").write_text(json.dumps({
 "arithmetic_checks":"passed",
 "FE_solve_performed":False,
 "native_solver_material_compatibility_tested":False,
 "source_points":len(rows),
 "nominal_eta_2_3":onset(2/3,.3),
 "nominal_softening_mm_unrounded":params["derivation"]["unrounded_u_full_mm"],
 "hardening_tail_exponent":n
},indent=2)+"\n")
print(json.dumps({"nominal_eta_2_3":onset(2/3,.3),"u_full_mm_unrounded":params["derivation"]["unrounded_u_full_mm"],
                  "hardening_exponent":n,"sigma_at_p0_3_MPa":stress_extension(.3,"power")},indent=2))

