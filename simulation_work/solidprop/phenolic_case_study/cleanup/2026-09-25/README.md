# Phenolic case study: results-preserving cleanup

The user requested removal of intermediate simulation data while keeping the results of every previous attempt and the starting data needed to reproduce them. This cleanup is confined to `phenolic_case_study`; the separate, running `newmotor_phenolic_study` calculation is outside its scope.

The audited plan removes **89,586,198,384 bytes (83.43 GiB)** from **285,599,143,345 bytes (265.99 GiB)** of files, retaining approximately **182.55 GiB**, plus this small audit. These are file sizes, not a guarantee of immediately reclaimed APFS free space. `completion.json` records the actual outcome and filesystem measurements. The cleanup completed and every retained original file kept its size, modification time and inode. Sixteen local Time Machine snapshots remain; the filesystem did not immediately report an equivalent free-space increase. No backup snapshots were deleted.

| Removed category | Files | Bytes |
| --- | ---: | ---: |
| Byte-identical copies of results/restart databases/load histories | 51 | 46,944,152,800 |
| Terminal solver saved state, restart generations and matrix workspace | 556 | 39,718,617,088 |
| Redundant ZIP, checked against its extracted contents | 1 | 2,923,428,496 |

## Preserved attempts

Paths below are relative to `phenolic_case_study`. Times describe the existing evidence; they do not certify successful completion or physical validity.

| Attempt | Retained results and starting information |
| --- | --- |
| `tmp3/_archive_results/testrun_1/MECH` | Original serial `file.rth`, its own `ds.dat`, material descriptions and logs. Last recorded convergence approximately 0.6020626 s. |
| `tmp3/saved_scratch/Scr640F` | Complete eight-rank thermal results from the earlier distributed attempt, through approximately 2.22 s, with its own inputs and logs. Identical `_ProjectScratch/Scr640F` result copies are mapped here. |
| `tmp3/testbed2_files/dp0/SYS-3/MECH` | All eight unique rank thermal files from the later attempt, through approximately 6.38561694 s; its distinct `ds.dat`, initial model database and load history remain. |
| `tmp3_sim2/scratchDir_saved/ScrAEC7` | Earlier unique thermal files, controller/history evidence through approximately 0.70 s, and its inputs. |
| `tmp3_sim2/restart_checkpoints/ScrAEC7_stopped_20260717_1733_t0p75` | **Entire original 132-file starting checkpoint is preserved**, including all ten ranks, four restart generations, `.rdb`, `.ldhi`, original controller parameters, thermal files, inputs and DLL. Solver state is at 0.80 s while controller parameters are at 0.75 s. |
| `tmp3_sim2/_ProjectScratch/ScrAEC7` | Unique small evidence and input copies remain. Identical thermal/database/load-history files map to the preserved starting checkpoint. |
| `tmp3_sim2/resume_runs/RestartProbe_step16_20260719` | The recombined 0.80 s global `file.rth`, probe inputs and logs. Rank results identical to the original checkpoint map to that checkpoint. |
| `tmp3_sim2/resume_runs/ScrResume_step16_20260719` | Failed recovery's original APDL, parameters, logs and history remain. Its identical combined thermal file maps to the probe; identical rank results map to the starting checkpoint. |
| `tmp3_sim2/resume_runs/ScrResume_step16_v2_20260719` | Both the unique approximately 45.25 GiB combined thermal file and **all ten unique rank thermal files** remain. The solver reached 6.50 s, but controller history ends at 6.45 s and the run returned exit code 1. Combined-file completeness is not assumed. |

All other attempts/preparations, Workbench projects, Mechanical/CAD databases, geometry, material data, APDL/Fortran/Python source, tested DLLs, compiler/build evidence, histories, plots and report sources are retained. Equal file size alone was never used as evidence of duplication. In particular, the two same-size recovery APDL variants remain distinct (`*INQUIRE` versus `/INQUIRE`).

## Reproduction and postprocessing

Preserved sources describe MAPDL **2026 R1.02 on Windows x64** with the corresponding UserMatTh DLL. The archived serial attempt used one core, the later Simulation 1 attempts eight distributed ranks, and Simulation 2 ten. Use the documented model-specific environment and unit conventions, not a different release or rank count inferred from a filename.

Run reproductions in a **new working directory**. Copy the relevant original project/input deck, material/model dependencies, APDL/Fortran/Python sources and DLL into that working environment. Initial `ds.dat` decks and project files were not deduplicated or changed. Adjust machine-specific paths deliberately. This cleanup has not rerun the simulations and does not claim a fresh numerical reproduction.

To reproduce either step-16 recovery, stage the **original preserved checkpoint**, including its original 0.75 s `simulation2_state.parm`, matching ten-rank restart state, `.rdb` and `.ldhi`. Use the recombined 0.80 s `file.rth` retained in the probe directory where the recovery workflow requires it. Then use the specific attempt's original recovery APDL and launch settings. Do **not** initialize with that attempt's terminal controller parameters. The probe evidence identifies `.r001` as the required generation for load step 16/substep 1; all four original generations remain available.

Obsolete terminal `.esav`, `.osav`, `.rNNN` and sparse-solver work files outside the protected starting checkpoint were removed. **Those historical endpoints are no longer directly resumable from their old working directories.** Reproduction proceeds from original inputs or the retained starting checkpoint. Unique `.rdb` and `.ldhi` files are retained; duplicate copies have an explicit replacement mapping.

For result browsing, use the retained result paths above. `plan.json` maps each removed duplicate pathname to its byte-identical `retained_copy`. No hard links or symlinks were introduced: a future solve must not overwrite an archive through a shared writable alias. Software that hard-codes a removed duplicate path must use its mapped retained copy, or copy that retained file into a separate postprocessing workspace.

## Verification and audit files

- `plan.json`: exact removals, reasons, original size/mtime/inode, hashes for proven duplicates, and retained-copy mappings.
- `retained-files.json`: inventory of every original file kept, with SHA-256 for source/model/provenance and previously hashed result files. Unique large thermal files are protected by unchanged size, modification time and inode; they were not needlessly reread in full.
- `duplicate-verification.json`: full-file SHA-256 comparisons. Sampling only narrowed candidates; no sampled-only match authorized deletion.
- `zip-verification.json`: all 15 scientific/source/log payloads matched their extracted files byte-for-byte. The only extra member was 163 bytes of AppleDouble provenance metadata. Extracted source/results remain; separately listed terminal saved-state files were removed under the solver-work policy.
- `completion.json`: post-cleanup verification, exact byte counts and available-space measurements.

Before deletion, the target's metadata and tracked-file status were checked again. No simulation was started, stopped or resumed. Retained files and the complete starting checkpoint are checked after deletion; every removed `.rth` must resolve to a retained copy with a matching full SHA-256.

The file-role decisions follow ANSYS's [restart requirements](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/ans_bas/Hlp_G_BAS3_12.html) and [text/binary file descriptions](https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/ans_bas/Hlp_G_BAS18_4.html), together with the actual input decks and solve logs. These documentation editions support the file roles; they do not replace the preserved 2026 R1.02 environment for reproducing these attempts.
