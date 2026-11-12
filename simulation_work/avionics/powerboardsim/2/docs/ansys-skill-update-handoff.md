# ANSYS account-skill update handoff

Prepared 12 November 2026. This file is self-contained: the two Markdown payloads below are sufficient to apply the update.

## Task and current state

Merge the lessons from the completed power-board study into the existing **Run ANSYS** account-backed skill, identified locally as `ansys-simulations:run-ansys` with skill name `run-ansys`. Resolve the actual account record before editing; no account skill ID or latest revision is assumed here.

The study, English LaTeX report, Beamer slides and 22 paired movie subjects are published. The user explicitly stopped recurring updates on 12 November. The heartbeat is paused, its dedicated keep-awake job was released, and no study solver is running. **This handoff is only for the skill update. Do not restart simulations, the heartbeat or keep-awake.**

The previous agent prepared and validated a local package but did not update the account copy. No account-skill write tool was exposed, and computer use denied access to the Codex app for safety reasons. Use an available, authorized account-skill editing route; do not bypass that restriction. If access is still unavailable, report the blocker once and leave the prepared content intact.

## Apply two focused changes

1. Read the latest account-backed `run-ansys` skill and its resources. Preserve concurrent changes, its existing frontmatter, description, metadata, invocation policy and unrelated references. Do not replace the account package with an older local copy.
2. Add the routing sentence below to `SKILL.md`, near the existing link to `references/verification.md` in “Build the smallest model that tests the question.” If the latest skill has a different structure, place it beside the corresponding structural-verification guidance. Avoid duplicating an existing equivalent link.
3. Add `references/power-board-contact.md` with the complete reference payload below. If that resource already exists, merge these lessons without discarding newer guidance. Treat the study's geometry, material values and fixtures as examples, not universal defaults.
4. Keep this handoff and its operational notes outside the installed skill. Only the routing sentence and reference payload belong in the skill.

### Payload 1 — addition to `SKILL.md`

```markdown
For printed enclosures, tiny gaps or nickel damage comparisons, read [contact and damage lessons](references/power-board-contact.md).
```

### Payload 2 — `references/power-board-contact.md`

```markdown
# Contact, damage and enclosure comparisons

Read this reference for printed enclosures, battery restraints or other structural comparisons where small gaps and material degradation affect the conclusion. These lessons come from the power-board study; its fixtures and material values are examples, not default properties for another design.

## Compare the same problem

Match the constitutive law as well as geometry and load. A bare bilinear nickel result and a bare multilinear damage-law result can give different travel at the same force. Preserve source identities for each comparison. Separate equal-force from equal-displacement comparisons, and a local fixture with fixed neighbouring cells from a complete board that allows them to move.

Retain the two saved states bracketing an event or requested load. Label an interpolated point as an estimate. Overlapping saved-state ranges do not establish a material ranking, and these ranges are not statistical confidence intervals. [Matched nominal damage comparison](https://github.com/MDNich/MIT-RT-26_27-Work/blob/d922100cbab6010a8b396886e840e2295a50a469/simulation_work/avionics/powerboardsim/2/validation/snug125/nominal_damage_pair_completion.json)

## Separate numerical completion from engineering scope

A listing can contain `RUN COMPLETED` after nonconvergence or an element-formulation error. Record the actual termination reason and the last converged station. Exclude diagnostic substep 999999. Verify equilibrium at saved states, retain any contiguous accepted prefix, and apply material/contact bounds within it.

Identify which material quantity first crosses its reference, including its direction: the aluminium nominal damage deck crossed a PLA strain reference before its stress reference. A printed-coupon crossing is not a component failure load. If it precedes nickel damage, later damage cannot validate a tearing load. Distinguish a shell-section damage summary, damage at stored integration sites and an initiation criterion. Agreement before initiation does not verify positive-damage evolution. [Aluminium closure](https://github.com/MDNich/MIT-RT-26_27-Work/blob/d922100cbab6010a8b396886e840e2295a50a469/simulation_work/avionics/powerboardsim/2/validation/snug125/aluminium_nominal_damage_completion.json)

A sharp-corner stress can keep increasing while a fixed-volume mean stabilizes. Bind each refinement limit to its exact deck and station mapping; do not silently transfer it to a changed material law, loading direction or increment schedule. [Refinement reassessment](https://github.com/MDNich/MIT-RT-26_27-Work/blob/d922100cbab6010a8b396886e840e2295a50a469/simulation_work/avionics/powerboardsim/2/validation/snug125/forward_material_scope_reassessment.json)

For an increment control, compare force and integrated work separately at identical saved travel. Nearly unchanged reactions can coexist with larger work differences near first contact. Report the measured changes and the interval tested; one refined schedule does not establish full convergence. [Selected nylon increment control](https://github.com/MDNich/MIT-RT-26_27-Work/blob/90dab17ae5d01753e45116d118b284d74dab7550/simulation_work/avionics/powerboardsim/2/validation/snug125/nylon_increment_completion.json)

## Check the load carried by tiny contacts

For micrometre CAD gaps, check registration and curved/faceted geometry separately from native contact status. Audit the loaded equilibrium using independent forces and moments. Convergence of total pocket force does not establish convergence of pressure peaks or contact area. Fixed-contact prestressed modes and their seeded histories cease to describe a validated nonlinear response after opening or new contact. State that limit when presenting spectra or motion. [Matched tight-criterion meshes](https://github.com/MDNich/MIT-RT-26_27-Work/blob/d922100cbab6010a8b396886e840e2295a50a469/simulation_work/avionics/powerboardsim/2/validation/snug125/nylon_tight_mesh_comparison.json)

Refine the moving target separately from the deformable case surface. Compare total force, loaded area and peak pressure at the same native travel; retain the first clear/loaded bracket. In the selected control, matched force changed by less than 1% while early loaded area doubled. Stable total force therefore does not establish local contact convergence. Rigid battery targets also provide no sleeve or can strength limit. [Target-resolution closure](https://github.com/MDNich/MIT-RT-26_27-Work/blob/3efd3832d6849732dca9ecaaf6bccd85085736d2/simulation_work/avionics/powerboardsim/2/validation/snug125/target_resolution_completion.json)

## Close a bounded campaign

When the user selects a finite validation set, keep failed prerequisites and blocked descendants visible. Report unresolved controls without automatically adding replacement sweeps. Preserve previous fits and rejected runs with their scope. [Finite outcome registry](https://github.com/MDNich/MIT-RT-26_27-Work/blob/3efd3832d6849732dca9ecaaf6bccd85085736d2/simulation_work/avionics/powerboardsim/2/validation/snug125/main_validation_outcomes.json)

If storage recovery is needed, work only on owned, closed, redundant study copies. An APFS clone must retain every differing block and required metadata; verify full bytes before atomic replacement. Files can differ outside their headers. Keep both guest and host reserves, since a guest-local solve still grows its VM image. [Verified recovery](https://github.com/MDNich/MIT-RT-26_27-Work/blob/d922100cbab6010a8b396886e840e2295a50a469/simulation_work/avionics/powerboardsim/2/validation/snug125/storage_private_full_recovery.json)

For paired movies retain common views, times and physical scales and label native versus independent fields. When the project requests LaTeX plots, use the actual PGF/TeX backend and check embedded fonts in both reports and slides. Review rendered pages and decoded movies before publication. [Movie provenance and review](https://github.com/MDNich/MIT-RT-26_27-Work/blob/d922100cbab6010a8b396886e840e2295a50a469/simulation_work/avionics/powerboardsim/2/validation/snug125/film_visual_review.json)
```

## Validate and verify the account update

- Check that the routing link resolves and that the original skill resources and metadata are retained. If a packaged-skill validator is available, run it on the merged package. The prepared local candidate already passed `quick_validate.py`; that does not validate a later merge or prove an account upload occurred.
- Save through the supported account-backed route, then read the skill and new reference back from that account. Check both requested edits against the saved content. Editing a local installation or plugin cache alone does not complete this task.
- Report the account skill identifier/title, saved revision or readback time, and the verification outcome. If only a local candidate is possible, say so explicitly. No further simulation, report rebuild, parameter sweep or recurring status loop is needed.

## Provenance and optional local package

The reference links above point to immutable Git commits containing the supporting audits. Their Git objects were checked when this handoff was prepared.

- Final scientific publication: `3efd3832d6849732dca9ecaaf6bccd85085736d2`.
- User-requested shutdown record: [OPERATIONS.md](https://github.com/MDNich/MIT-RT-26_27-Work/blob/b7c6304083a269976a6850147014e3264641f720/simulation_work/avionics/powerboardsim/2/OPERATIONS.md).
- Project directory: `/Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/2`.
- Optional local package, relative to that directory: `.runtime/qa/snug125/skill-publication-preflight/final-candidate/run-ansys.zip`.
- Package manifest and baseline hashes: `.runtime/qa/snug125/skill-publication-preflight/final-candidate/proposal.json`.
- ZIP SHA-256: `2922538c135338fa085ddccbba26dbd281818f85f858663f2ecba0731b2f05c7`.
- Exact reference payload SHA-256 (UTF-8, including its final newline): `a94cdcd59c60c4a49450929e15bec876e17c2232ea815fad515421923ea500a5`.

The ZIP contains the earlier full local skill plus these edits. It is a convenience copy, not evidence that it matches the latest account revision. The two payloads above can be used without access to the local ZIP or ignored runtime files.
