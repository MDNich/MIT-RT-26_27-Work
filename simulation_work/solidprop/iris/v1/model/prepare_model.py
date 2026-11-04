#!/usr/bin/env python3
"""Build a self-contained MAPDL run directory for the new-motor study.

No solve is performed.  The generated mesh is a conformal structured grid
with shared nodes at the phenolic/aluminium interface.  All large solver and
checkpoint files remain in the ignored runtime directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def material_input(cfg: dict) -> str:
    m = cfg["material"]
    table = [
        (22.0, .25, .30, 900, 800), (26.85, .25, .30, 900, 800),
        (326.85, .32, .35, 1100, 900), (626.85, .36, .40, 1300, 1000),
        (776.85, .36, .44, 1300, 1250), (926.85, .36, .49, 1300, 1550),
        (1226.85, .36, .68, 1300, 1950), (1426.85, .36, .81, 1300, 2060),
        (1926.85, .36, 1.24, 1300, 2085), (2476.85, .36, 1.73, 1300, 2090),
    ]
    out = ["! Phenolic UserMatTh: reference densities; fixed mesh; no thermal expansion.",
           "TB,USER,1,10,15,THERM"]
    for temp, kv, kc, cpv, cpc in table:
        kv*=m.get('phenolic_k_scale',1.);kc*=m.get('phenolic_k_scale',1.)
        cpv*=m.get('phenolic_cp_scale',1.);cpc*=m.get('phenolic_cp_scale',1.)
        out += [f"TBTEMP,{temp}",
                f"TBDATA,1,{kv},{kc},{cpv},{cpc},{m['virgin_reference_density_kg_m3']},{m['char_reference_density_kg_m3']}",
                f"TBDATA,7,333,64081,1,{m['pyrolysis_enthalpy_J_kg']},273.15,1600",
                "TBDATA,13,300,1,1"]
    out += ["TB,STATE,1,,5", "TBDATA,1,0,0,0,0,0"]
    return "\n".join(out) + "\n"


def create_mesh(cfg: dict) -> tuple[dict, list[tuple[int, float, float, float]], list[tuple[int, int, list[int]]]]:
    g = cfg["geometry"]
    nr_p = g["phenolic_radial_rows"]
    nr_a = g["aluminium_radial_rows"]
    nt = g["angular_divisions"]
    ny = g["axial_divisions"]
    theta0 = -math.radians(g["angle_deg"]) / 2.0
    dtheta = math.radians(g["angle_deg"]) / nt
    dy = g["length_m"] / ny
    rp = [g["inner_radius_m"] + i * g["phenolic_thickness_m"] / nr_p for i in range(nr_p + 1)]
    ra = [g["phenolic_outer_radius_m"] + i * g["aluminium_thickness_m"] / nr_a for i in range(1, nr_a + 1)]
    radii = rp + ra

    def nid(ir: int, it: int, iy: int) -> int:
        return 1 + (ir * (nt + 1) + it) * (ny + 1) + iy

    nodes: list[tuple[int, float, float, float]] = []
    for ir, radius in enumerate(radii):
        for it in range(nt + 1):
            theta = theta0 + it * dtheta
            for iy in range(ny + 1):
                nodes.append((nid(ir, it, iy), radius * math.sin(theta), iy * dy, radius * math.cos(theta)))

    elements: list[tuple[int, int, list[int]]] = []
    element_map: dict[str, dict] = {}
    rows: list[list[dict]] = [[] for _ in range(nr_p)]
    outer: list[dict] = []
    eid = 0
    for ir in range(len(radii) - 1):
        r0, r1 = radii[ir], radii[ir + 1]
        mat = 1 if ir < nr_p else 2
        for it in range(nt):
            for iy in range(ny):
                eid += 1
                n = [nid(ir, it, iy), nid(ir + 1, it, iy), nid(ir + 1, it + 1, iy), nid(ir, it + 1, iy),
                     nid(ir, it, iy + 1), nid(ir + 1, it, iy + 1), nid(ir + 1, it + 1, iy + 1), nid(ir, it + 1, iy + 1)]
                volume = 0.5 * (r1 * r1 - r0 * r0) * dtheta * dy
                elements.append((eid, mat, n))
                element_map[str(eid)] = {"mat": mat, "typ": mat, "nodes": n, "volume": volume}
                if ir < nr_p:
                    rows[ir].append({"element": eid, "face": 5, "nodes": [n[i] for i in (3, 0, 4, 7)],
                                     "area": r0 * dtheta * dy, "volume": volume})
                if ir == len(radii) - 2:
                    outer.append({"element": eid, "face": 3, "nodes": [n[i] for i in (1, 2, 6, 5)],
                                  "area": r1 * dtheta * dy})
    assert all(len(row) == nt * ny for row in rows)
    assert len(outer) == nt * ny
    mesh = {"elements": element_map, "rows": rows, "outer": outer}
    return mesh, nodes, elements


def export_macro(max_node: int, max_element: int) -> str:
    out = ["FINISH", "/POST1", "SET,LAST", "ALLSEL,ALL", "*GET,V0_TIME,ACTIVE,0,SET,TIME",
           "*CFOPEN,observed_time,txt", "*VWRITE,V0_TIME", "(E24.16)", "*CFCLOSE"]
    for name, length in (("V0_N", max_node), ("V0_T", max_node), ("V0_M", max_node), ("V0_E", max_element)):
        out += [f"*DEL,{name}", f"*DIM,{name},ARRAY,{length}"]
    out += ["*VFILL,V0_N(1),RAMP,1,1", "*VGET,V0_T(1),NODE,1,TEMP", "*VGET,V0_M(1),NODE,1,NSEL",
            "*CFOPEN,node_temperatures,txt", "*VMASK,V0_M(1)", "*VWRITE,V0_N(1),V0_T(1)",
            "(F10.0,1X,E24.16)", "*CFCLOSE", "*VFILL,V0_E(1),RAMP,1,1",
            "ESEL,S,TYPE,,1,2", "ESEL,R,LIVE", "ETABLE,ERAS"]
    fields = [("ALP", "SVAR,1"), ("GAS", "SVAR,3"), ("GSEN", "SVAR,5"), ("QZ", "TF,Z"),
              ("CAP", "NMISC,38"), ("GEN", "NMISC,39"), ("CONV", "NMISC,40"),
              ("HFX", "NMISC,41"), ("RAD", "NMISC,42"),
              ("HCONV", "NMISC,29"), ("OCONV", "NMISC,17")]
    for label, item in fields:
        out += [f"*DEL,V0_{label}", f"*DIM,V0_{label},ARRAY,{max_element}"]
        out += ["ESEL,S,MAT,,1"] if item.startswith("SVAR") else ["ESEL,S,TYPE,,1,2"]
        # This structured mesh has contiguous live IDs (removed rows are a
        # prefix). Retrieve only the selected live material range, not undefined
        # casing SVAR entries or already-dead rows.
        out += ["ESEL,R,LIVE", f"ETABLE,{label},{item}",
                "*GET,V0_FIRST,ELEM,0,NUM,MIN", "*GET,V0_COUNT,ELEM,0,COUNT",
                "*VLEN,V0_COUNT", f"*VGET,V0_{label}(V0_FIRST),ELEM,V0_FIRST,ETAB,{label}", "*VLEN"]
    out += ["*DEL,V0_EM", f"*DIM,V0_EM,ARRAY,{max_element}", "ESEL,S,TYPE,,1,2", "ESEL,R,LIVE",
            "*VGET,V0_EM(1),ELEM,1,ESEL", "*CFOPEN,element_fields,txt", "*VMASK,V0_EM(1)",
            "*VWRITE,V0_E(1),V0_ALP(1),V0_GAS(1),V0_GSEN(1),V0_QZ(1)", "(F10.0,4(1X,E24.16))", "*CFCLOSE",
            "*CFOPEN,energy_fields,txt", "*VMASK,V0_EM(1)",
            "*VWRITE,V0_E(1),V0_CAP(1),V0_GEN(1),V0_CONV(1),V0_HFX(1),V0_RAD(1),V0_HCONV(1),V0_OCONV(1)",
            "(F10.0,7(1X,E22.14))", "*CFCLOSE", "ALLSEL,ALL", "FINISH"]
    return "\n".join(out) + "\n"


def driver(cfg: dict, resume: bool = False) -> str:
    root = cfg["windows_root"]
    restart = "ANTYPE,,REST,V0_PREVIOUS,,CONTINUE" if resume else "ANTYPE,,REST,,,CONTINUE"
    prefix = "! Resume only from a verified accepted checkpoint.\n" if resume else """! New motor v0; launched only by launch_v0.ps1 -Run.
/INPUT,model_base,inp
/SOLU
ANTYPE,TRANS,NEW
NROPT,FULL
THOPT,FULL
TRNOPT,FULL
TINTP,,,,1
AUTOTS,ON
NEQIT,60
KBC,1
ESTIF,1E-6
DMPOPTION,RNNN,NO
RESCONTROL,DEFINE,ALL,LAST,-1,,%d
OUTRES,ALL,LAST
OUTRES,SVAR,LAST
FINISH
""" % cfg["output"]["save_restart_generations"]
    loop = f"""*DO,V0_LOOP,1,{cfg['numerics']['max_steps']}
  /DELETE,step_control,inp
  /SYS,{root}\\couple.cmd prepare
  V0_OK=0
  /INPUT,step_control,inp
  *IF,V0_OK,NE,1,THEN
    /COM,V0_PREPARE_FAILED_OR_MISSING
    /EXIT,NOSAVE
  *ENDIF
  *IF,V0_DONE,EQ,1,THEN
    *EXIT
  *ENDIF
  /SOLU
  *IF,V0_INDEX,GT,1,THEN
    {restart}
  *ENDIF
  /INPUT,step_control,inp
  /INPUT,apply_loads,inp
  TIME,V0_TARGET
  DELTIM,V0_DT,{cfg['minimum_dt_s']},V0_DT,OFF
  SOLVE
  /INPUT,export_fields,mac
  /DELETE,accepted,inp
  /SYS,{root}\\couple.cmd accept
  V0_OK=0
  /INPUT,accepted,inp
  *IF,V0_OK,NE,1,THEN
    /COM,V0_POSTPROCESS_OR_BALANCE_FAILED
    /EXIT,NOSAVE
  *ENDIF
*ENDDO
/COM,V0_CONTROLLER_STOPPED_CHECK_STATE_JSON
/EXIT,NOSAVE
"""
    if cfg["ranks"] == 1:
        prefix=prefix.replace("DMPOPTION,RNNN,NO", "! SMP pilot: no distributed restart option")
    return prefix + loop


def write_model(cfg: dict, nodes: list, elements: list, output: Path) -> None:
    m = cfg["material"]
    lines = ["/BATCH", "/CONFIG,NOELDB,1", "/TITLE,New motor phenolic consumption v0", "/UNITS,MKS", "/PREP7",
             "SHPP,ON", "ET,1,278", "ET,2,278", "KEYOPT,1,15,1", "KEYOPT,2,15,1", material_input(cfg).rstrip(),
             f"MP,KXX,2,{m['aluminium_conductivity_W_m_K']}", f"MP,C,2,{m['aluminium_heat_capacity_J_kg_K']}",
             f"MP,DENS,2,{m['aluminium_density_kg_m3']}", "! Nodes"]
    lines += [f"N,{nid},{x:.12e},{y:.12e},{z:.12e}" for nid, x, y, z in nodes]
    lines += ["! Phenolic elements", "TYPE,1", "MAT,1"]
    lines += ["E," + ",".join(map(str, n)) for _, mat, n in elements if mat == 1]
    lines += ["! Casing elements", "TYPE,2", "MAT,2"]
    if cfg.get("case_material") == "cf":
        lines += ["MPDELE,ALL,2", f"MP,DENS,2,{m['aluminium_density_kg_m3']}"]
        for i,t in enumerate([22,100,150,200,300,600,1000,1500,2230.85],1):
            cp = cfg.get('cf_cp_constant_J_kg_K',2.8773*min(200,max(20,t))+687.31)*cfg.get('cf_cp_scale',1.)
            lines += [f"MPTEMP,{i},{t}", f"MPDATA,KXX,2,{i},{cfg['cf_inplane_k']}",
                      f"MPDATA,KYY,2,{i},{cfg['cf_inplane_k']}",
                      f"MPDATA,KZZ,2,{i},{cfg['cf_radial_k']}", f"MPDATA,C,2,{i},{cp}"]
        nt=cfg['geometry']['angular_divisions']; ny=cfg['geometry']['axial_divisions']
        half=math.radians(cfg['geometry']['angle_deg'])/2
        for it in range(nt):
            theta=-half+(it+.5)*2*half/nt
            lines += ["K,100001,0,0,0",f"K,100002,{math.cos(theta)},0,{-math.sin(theta)}",
                      "K,100003,0,1,0",f"CSKP,{11+it},0,100001,100002,100003","KDELE,100001,100003"]
        lines += ["CSYS,0"]
        for eid,mat,n in elements:
            if mat==2:
                it=((eid-1)//ny)%nt
                lines += [f"ESYS,{11+it}", "E,"+",".join(map(str,n))]
        lines += ["ESYS,0"]
    else:
        lines += ["E," + ",".join(map(str, n)) for _, mat, n in elements if mat == 2]
    lines += ["ALLSEL,ALL", f"TUNIF,{cfg['initial_temperature_C']}", "FINISH"]
    (output / "model_base.inp").write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT.parent / "ansystmp" / "windows")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    args = parser.parse_args()
    from ops import disks
    disks()
    output = args.output.resolve()
    if (output / "state.json").exists():
        raise RuntimeError("Existing run state preserved; use a new sibling runtime directory.")
    output.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    mesh, nodes, elements = create_mesh(cfg)
    nr=cfg['geometry']['phenolic_radial_rows']; nt=cfg['geometry']['angular_divisions']; ny=cfg['geometry']['axial_divisions']
    mesh['temperature_nodes'] = {
        'case_inner': [1+(nr*(nt+1)+it)*(ny+1)+iy for it in range(nt+1) for iy in range(ny+1)],
        'case_outer': sorted({n for f in mesh['outer'] for n in f['nodes']})}
    cfg['expected_nodes']=len(nodes);cfg['expected_elements']=len(elements)
    for name in ("coupler.py", "usermatth.F", "usermatthLib.dll", "request_pause.ps1", "status_v0.ps1", "package_check.py"):
        shutil.copy2(ROOT / name, output / name)
    (output / "config.json").write_text(json.dumps(cfg,indent=2)+"\n")
    (output / "mesh_map.json").write_text(json.dumps(mesh, separators=(",", ":")), encoding="utf-8")
    write_model(cfg, nodes, elements, output)
    (output / "material_v0.apdl").write_text(material_input(cfg), encoding="ascii")
    (output / "export_fields.mac").write_text(export_macro(len(nodes), len(elements)), encoding="ascii")
    (output / "run_v0.inp").write_text(driver(cfg, False), encoding="ascii")
    (output / "resume_v0.inp").write_text(driver(cfg, True), encoding="ascii")
    python = r"C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe"
    (output / "couple.cmd").write_text(f'@echo off\r\n"{python}" "{cfg["windows_root"]}\\coupler.py" %1 --root "{cfg["windows_root"]}"\r\nexit /b %ERRORLEVEL%\r\n', encoding="ascii")
    shutil.copy2(ROOT / "launch_v0.ps1", output / "launch_v0.ps1")
    preflight = """! Read-only native MAPDL preflight: there is deliberately no SOLVE command.
/INPUT,model_base,inp
ALLSEL,ALL
*GET,V0_NN,NODE,0,COUNT
*GET,V0_NE,ELEM,0,COUNT
*VWRITE,V0_NN,V0_NE
('V0_PREFLIGHT_COUNTS NODES=',F12.0,' ELEMENTS=',F12.0)
/COM,V0_PREFLIGHT_COMPLETE_NO_SOLVE
FINISH
/EXIT,NOSAVE
"""
    (output / "preflight_v0.inp").write_text(preflight, encoding="ascii")
    summary = {
        "nodes": len(nodes), "solid_elements": len(elements),
        "phenolic_elements": sum(mat == 1 for _, mat, _ in elements),
        "aluminium_elements": sum(mat == 2 for _, mat, _ in elements),
        "phenolic_rows": len(mesh["rows"]), "faces_per_row": [len(row) for row in mesh["rows"]],
        "outer_faces": len(mesh["outer"]),
        "radial_pitch_phenolic_um": 1e6 * cfg["geometry"]["phenolic_thickness_m"] / cfg["geometry"]["phenolic_radial_rows"],
        "radial_pitch_aluminium_um": 1e6 * cfg["geometry"]["aluminium_thickness_m"] / cfg["geometry"]["aluminium_radial_rows"],
        "model_sha256": hashlib.sha256((output / "model_base.inp").read_bytes()).hexdigest(),
        "solve_started": False,
    }
    (output / "mesh_validation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "PREPARED_NOT_STARTED.txt").write_text("Model generated and validated structurally. No solver process has been started.\n", encoding="utf-8")
    subprocess.run([sys.executable, str(output / "package_check.py"), "--seal"], check=True)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
