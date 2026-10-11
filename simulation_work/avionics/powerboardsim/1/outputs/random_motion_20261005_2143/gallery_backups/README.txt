POWER BOARD: 4K / 60 FPS VIDEO COMPANIONS

These clips accompany the modal comparison and random vibration reports.
The PDFs are unchanged. This is post-processing of the existing results;
no analysis was re-solved and no material, connection or load was changed.

HOW TO VIEW
Open index.html in a browser, or open an MP4 directly in a video player.
Each file is 3840 x 2160, 60 progressive frames/s, H.264 High profile in MP4.
The hardware encoder is Apple's VideoToolbox with software fallback disabled.
Use full-screen playback and 1x speed. There is no audio.

WHAT MOVES
Modal figures 1-3: Mechanical's native harmonic mode-shape animation.
Each cycle takes 3 seconds on screen; the same cycle repeats three times.
This is deliberately slowed playback, unrelated to the physical period.
Eigenvectors are normalized and deformation is magnified. Values on the
native modal legend are not predictions of physical vibration amplitude.

Random-vibration figures 2-18: the camera gently rocks through +/-18 degrees
around the report's nominal view, with cosine easing at each turnaround.
The RMS field and displayed deformation remain fixed. Automatic graphical
deformation scaling magnifies the displayed shape; use the legend and report
tables for numerical RMS amplitudes. A round trip takes
4 seconds and is repeated twice. This is NOT a random response time history.
RMS results do not specify simultaneous displacement signs or phases.
The displacement results are one-sigma component RMS values. The native
68.269% Gaussian annotation does not apply to equivalent-stress RMS.

STUDY IDENTIFICATION
H: Modal, retained refined default-contact baseline (20 accepted modes).
G: Modal, existing six-bolt setup with 750 N per bolt (20 accepted modes).
F: Random Vibration, X base excitation, existing 750 N bolt configuration.
E: Random Vibration, Y base excitation, same configuration.
D: Random Vibration, Z base excitation, same configuration.
Random cases use 2% damping and the existing expanded modal basis.
Random figures 2-14 show all-body fields; figures 15-18 retain their PCB
result scopes. Context geometry can remain visible outside the contour scope.
Report graphs (input PSD and effective modal mass) remain static.

NUMERICAL AND IMAGE PROVENANCE
All geometry, contours, camera frames and legends are rendered by ANSYS
Mechanical 2026 R1 (v261). No deformation is synthesized by an image model.
The native modal export fixes its on-screen legend at a small pixel size.
For readability, its unchanged, fixed-range legend is replaced in the video
by the same legend from a separate native Mechanical 4K still export.
A small explanatory footer is added during encoding. Random clips retain
the legend directly in every Mechanical frame. Native regional decimal
commas are preserved. Date/time annotations are hidden to avoid flicker. The random-video ruler
is hidden to leave clear space for the explanatory footer.
GPU acceleration was reported active by Mechanical's modal exporter.
The Windows VM exposes a Parallels WDDM GPU, not a directly passed-through
physical GPU. Video encoding runs on the Mac host's hardware video engine.

REPRODUCING THE EXPORTS
1. Open the saved power-board project in Mechanical 2026 R1. Use the existing
   solved/retained result branches identified by manifest.json. Object IDs
   are project-specific; verify each result's name, scope, maximum and mode
   frequency before using the included scripts with another project copy.
2. Preserve the retained default baseline. It is obsolete in the shared
   current model because the bolt contacts are now active. Do not update or
   solve that branch against the current contacts to recreate this baseline.
   The script checks its stored 20-mode frequency list before export.
3. Copy a reproduction/*/export.py script to an accessible Windows path.
   Change OUT to a fresh output directory if reproducing elsewhere. These
   are IronPython scripts executed inside Mechanical's scripting console.
   They only change display settings and export graphics; there is no Solve.
4. Run execfile(r'C:\path\to\export.py'). Result maxima are checked before
   and after every export. Each script writes audit.txt and COMPLETE.txt.
5. Modal export uses NumberOfFrames=91 and Duration=1.5 s. Mechanical's
   forward/backward exporter produces 180 frames at 60 fps. The PNG masters
   are in native_frames. The encoding sequence repeats these frames three
   times for a 9 s clip. legend_source.png provides the larger native legend.
6. Random export writes 121 native 4K PNGs. For frame i=0..120, the camera
   angle is -18*cos(pi*i/120) degrees around the nominal camera UpVector.
   Rodrigues rotation is applied to the ViewVector. Scene height is fixed
   after fitting, so there is no artificial zoom during the movement.
7. Build the random encoding order as 0..120,119..1, then repeat it once.
   At 60 fps this is 480 frames / 8 s. Reverse travel reuses the identical
   camera positions; no optical-flow or synthesized intermediate frames
   are used. A frame is rendered for every distinct forward camera angle.
8. Encode the PNG sequence with ffmpeg's h264_videotoolbox at 60 fps,
   yuv420p, High profile / Level 5.2, 80 Mb/s target and fast-start MP4.
   Hardware-only operation uses -allow_sw 0. Exact argument lists are
   included as reproduction/<clip>/encode_command.json, with absolute
   paths from this run. Adapt those paths when moving the package.
9. Confirm width=3840, height=2160, r_frame_rate=60/1 and frame count
   540 (modal) or 480 (random) using ffprobe. Decode each complete MP4
   with ffmpeg -v error -i video.mp4 -f null - and inspect representative
   frames. Check unclipped geometry, legends, footer, field scopes and
   visible motion. SHA256SUMS.txt identifies the delivered video files.

This export does not extend the convergence or physical qualification of
the original exploratory analyses. Refer to the reports for their modeling
assumptions, contact idealizations and convergence limitations.

REFERENCE FOR INTERPRETING RMS VISUALIZATIONS
ANSYS describes random-vibration results as statistical quantities rather
than time-history dynamic results. The RMS contours alone do not define
a physical motion sequence.
https://innovationspace.ansys.com/courses/courses/random-vibration-analysis/lessons/summary-23/
