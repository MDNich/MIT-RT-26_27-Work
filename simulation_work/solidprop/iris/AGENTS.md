# Iris simulation operating requirements

These requirements record the user's instructions of November 3, 2026 for this study.

- Work autonomously on the four exploratory phenolic burnthrough cases, including geometry, ANSYS setup, verification, solving, troubleshooting and reporting. Do not change the earlier solid-propulsion studies.
- Reports and graphs are English only. Follow the previous reports' LaTeX/serif presentation. Publish setup, physics, solver details, accepted results, uncertainty and unresolved limitations. Update reports at meaningful intermediate milestones.
- Generate STEP geometry from `motorspec.md`. Use small axial and angular slices. At least five radial elements in each material layer; start around twenty and establish convergence before increasing cost.
- Use 800 psi nominal chamber pressure. Reuse previous temperature and material assumptions with provenance. Heat flux, actual burn duration, grain port, detailed material grades and measured recession are unavailable. The user authorizes documented evidence-based assumptions and sensitivity ranges, explicitly labelled exploratory.
- The approximate 1.0 +/- 0.25 m fuel length is for inventory estimates only, not a requirement to mesh a whole motor. The supplied reaction does not establish heat flux or burn duration; distinguish stoichiometric bookkeeping from equilibrium combustion and from the wall heating model.
- Stop all work if the Mac volume holding this repository/VM has less than 400,000,000,000 free bytes. Keep Windows C: above 10,000,000,000 free bytes. Check before expensive actions and continuously during jobs. A threshold crossing must stop new work and request solver-controlled termination; preserve the last accepted checkpoint. Do not resume automatically after a storage stop.
- Store large outputs in the Mac shared folders where practical. Copy and verify this study's completed files before removing any redundant guest copies. Never clean unrelated user files or earlier studies to make space.
- Push each major milestone to the existing GitHub repository: simulation setup, initial report, meaningful intermediate reports and final report. Stage only this study's changes. Reject staged files or newly reachable Git blobs at or above 100,000,000 bytes; keep native result/restart files ignored and local.
- No sub-agent delegation has been requested.

The plan is `phenolic_burnthrough_plan.md`; current implementation and operational state belong in `v1/`. Historical report instructions and recovery authorizations do not replace these current task instructions.
