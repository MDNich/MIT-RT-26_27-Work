POWER BOARD — REPRESENTATIVE RANDOM-VIBRATION MOTION
Working calculation package, 5 October 2026

Purpose
Produce physical displacement histories for separate X, Y, and Z base acceleration cases. These are seeded synthetic realizations of the specified random environment, not measured vibration and not camera rotations over RMS contours. Final videos must be native Mechanical renders at 3840 x 2160 and encoded at 60 fps. No video is accepted without resolution, frame-count, decode, and motion checks.

Inherited model
Use the complete previously solved assembly (PCB, components, three batteries, nickel strips, supports and fasteners). Reuse analysis C / object 4254, the 38-mode prestressed basis spanning 485.964268212 to 3986.07476348 Hz, with six bolts tightened to 750 N each and then locked. Use the same 781 mounting nodes and the same material and contact definitions as the accepted random-vibration report. The battery connection authorization is nickel-only; no new battery-to-PCB bond is introduced. Preserve the existing baseline and PSD studies.

This is a linearized response about the saved pretension state. Contact opening, impacts, gross sliding, material nonlinearity during vibration, and joint loosening are not recalculated. The mesh, material assumptions, contact idealizations and modal truncation qualifications of the earlier report still apply. This calculation is exploratory.

Excitation and damping
Frequency / one-sided acceleration PSD:
20 Hz     0.026 g^2/Hz
50 Hz     0.160 g^2/Hz
800 Hz    0.160 g^2/Hz
2000 Hz   0.026 g^2/Hz
Interpolate in log frequency and log PSD. Zero outside the prescribed band. The existing Mechanical acceleration conversion uses 9.806 m/s^2 per g; use the same conversion for comparison. Use 2% critical damping on every retained mode. The original eigensolution remains undamped.

The input generator uses an eight-second periodic record at 65536 samples/s. At positive Fourier frequencies, the complex coefficient magnitude is N sqrt(S(f) df / 2), with independent uniform phases. Use seeds 20261005, 20261006 and 20261007 for X, Y and Z respectively. This produces an approximately Gaussian random-phase realization with a reproducible periodogram. A half-cosine ramp is applied over the first 0.1 second. Planned native histories are nine seconds long; discard the first second for steady-response statistics. The accepted run manifests and audits, when present, define the actual duration and step size.

Native calculation procedure
1. Copy the saved modal .db, .mode, .full, .emat and .esav files, including all twelve distributed rank files, to a new Windows-local directory. Never run against the Workbench source directory.
2. In a no-SOLVE MAPDL preflight, resume the database, check the model inventory, confirm all 781 support nodes have blocked UX, UY and UZ degrees of freedom, and confirm the first and last retained frequencies. Seal the input with SHA-256.
3. Restart the modal solution with ANTYPE,MODAL,RESTART and MODCONT,,ON. At the already blocked support nodes, identify enforced bases UX=1, UY=2, UZ=3. Clear nodal forces and global acceleration. Generate the three enforced motion vectors. Keep the original eigensolution; do not re-extract modes or reapply pretension loads.
4. Validate the native completion and errors, then stage each transient in a fresh directory. Copy the enforced-motion .enf files as well as the .mode, .full, .mlv (when present), and .db files. Preserve all twelve ranks.
5. Define ANTYPE,TRANS and TRNOPT,MSUP,38,,1,YES,NMK,YES. Apply DMPRAT,0.02. Use TINTP,GAMMA=0 (average-acceleration Newmark without added algorithmic damping), with AVSMOOTH=1. Set a constant DELTIM. Request unwrapped, mass-normalized modal coordinates with MCFOPT,1,0,0.
6. First solve the zero-input initial state. Read the acceleration table with *TREAD and apply DVAL,base,ACC,%PBACC%,,OFF to the active direction, leaving the other two bases at zero. OFF requests motion relative to the mounting base. Solve to the required end time.
7. First perform a 0.25-second X pilot at 32768 integration steps/s. Verify it against an independently implemented average-acceleration Newmark integration using the original signed participation factors. Inspect failures before modifying or relaunching any calculation.
8. For accepted runs, retain the .mcf/.rdsp histories, exact native input, seed, acceleration record, solver log, native file inventory, hashes and numerical audit. Do not accept a run solely because a result file exists.

Independent checks
A frequency-domain modal calculation uses q_j(f) = -Gamma_j a(f) / [omega_j^2 - omega^2 + 2 i zeta omega_j omega]. Expand the result using the original Mechanical modal displacement vectors at the nine directional RMS hotspot combinations, plus a mounting node. The eight-second periodic reference agrees with the earlier PSD displacement peaks within 0.02% for all nine comparisons. See reference_response_audit.json for the individual values. This verifies modal normalization, gravity conversion, signed participation factors and PSD interpolation; it does not replace native transient verification.

The native transient audit must also verify finite modal coordinates, monotonically increasing time, the requested end time, zero relative support displacement, agreement with independent time integration, and agreement of steady RMS response with the prior study. Time-resolution sensitivity must be checked before final video acceptance.

Rendering and playback
Use actual transient result sets and a fixed camera. Do not animate a single RMS scalar field as though it were a signed displacement vector. Do not reverse the physical history to manufacture a cyclic loop. Use a stationary short time window, with a constant, explicitly stated deformation magnification. Label playback as slowed representative motion; display the actual simulated time. Contour labels must describe instantaneous results rather than RMS. The native project uses SI units.

License and environment
ANSYS MAPDL 2026 R1.02, Build 26.1, UP20260202, x64 on Windows 11 ARM64 in Parallels. Standalone solver uses twelve distributed ranks and job name file. License endpoint: 1055@MARCDNICHITBF25. Mechanical remains in read-only configuration while standalone MAPDL occupies the available ansys license; reactivate the Mechanical Enterprise license after the native calculations complete. A concurrent checkout failed and was dismissed; it did not stop the native solver.

Source of truth
execution_contract.json records the execution contract. Each runtime manifest ties the exact input to native preflight. ACCEPTED.json files are written only after the relevant checks pass. Absence of an acceptance file means the calculation or export is not yet accepted. All sources and generated inputs are in this package's control, basis and inputs directories.

Resume checkpoint, 6 October 2026
All three native SMP histories completed for nine seconds at 65536 steps/s. Their nine steady RMS checks agree with the earlier PSD results within 0.158%; independently integrated modal coordinates agree within 0.0013%. See transient_X, transient_Y and transient_Z/ACCEPTED.json. The SMP and DMP 0.25 s pilots have identical modal coordinates. Native displacement-only expansion agrees with original modal shapes within 9.9e-8 relative L2 at the validation nodes.

Mechanical import detail: create a Transient Structural analysis, link InitialConditions[0].ModalEnvironmentTransientMSUPIC to the original 38-mode modal analysis, set StepEndTime and especially AnalysisSettings.TimeStep to match the source history BEFORE reading the native result file. The default time step exceeds the short proof duration and causes result evaluation to fail despite a valid RST. Select By=ResultSet and SetNumber=1 (or the required actual set). Imported results must stay in a separate archive outside the Workbench-generated directory.

Native animation resolution: set the native IAnimationController.SetExportStreamWidthHeight(3840,2160) as well as AnimationExportSettings(3840,2160). The explicit stream setting fixed a previous viewport-size export. PrepPost successfully rendered the original modal proof. Set ForwardBackwardMode=0 for a physical, forward-only history; verify the resulting frame count and times before accepting production clips.

6 October rendering correction and production window
The production integration is SMP, one rank, for 9 s at 65536 steps/s. The original enforced-basis generation and the corrected database-save experiment are DMP, twelve ranks. Mechanical uses the separate PrepPost seat during native structural calculations.

The video window is 1.00006103515625 to 1.029296875 s, 480 samples at 1/16384 s spacing. At 60 fps this is 8 s of playback, slowed by 273.0667. Every frame is forward in physical time; there is no ping-pong loop. Deformation magnification is 50, constant across frames. Signed displacement contours use fixed symmetric bounds over the window. The fields are instantaneous, not RMS. The first second is excluded to avoid the ramp/startup transient.

Mechanical must have CalculateTimeHistory=True before ExportAnimation. False animates a single selected state and is not an acceptable physical time history. The four-state proof was compared against four separately evaluated SetNumber images. The accepted X expansion was checked at six saved times and seven nodes against the original modal shapes multiplied by the native modal coordinates; relative L2 error was 6.59e-8. See expand_X/ACCEPTED.json. The renderer uses ResultSets, ForwardBackwardMode=0, 480 frames and explicit native 3840x2160 stream dimensions. Verify exactly 480 distinct complete PNG images before encoding. Native default video encoding is not the delivery encoder; the final MP4 uses macOS VideoToolbox at 60 fps, 80 Mbit/s target, 120 Mbit/s maximum, with explicit physical-time and magnification labels.

Shared-folder performance: long renders and concurrent large transfers through Parallels sharing stalled intermittently. Completed native fields remain in the Windows runtime and in the host archive. Subsequent renders should read and write locally in Windows, then copy their PNG frames to the host after rendering, before macOS hardware encoding.

Stress recovery diagnosis (not yet an accepted stress animation): a modal restart can perform element expansion when FINISH is issued. Saving the database before FINISH records an earlier state. The initial enforced-basis run saved before FINISH. The fresh basis_saved experiment issues SOLVE, FINISH, SAVE in that order, with the same eigenbasis and MXPAND settings. Its 51 input replicas were checked byte-for-byte against the original Workbench modal source before moving the copies from an earlier failed PSD runtime. The original source is unchanged. Accept stress results only after a successful native stress expansion and numerical checks; the corrected save order alone is not proof of valid stresses.
