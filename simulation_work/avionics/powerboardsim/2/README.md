# Power-board battery case comparison

Revision 2 of the October populated power-board study. Both supplied CAD formats are retained in `geometry/`. The STEP is the source for geometry registration. The case is 3D-printed PLA with air between the cells and the case. The two mounting scenarios use aluminium screws or a catalog nylon screw. The six existing battery-attachment screws retain their original specification.

The study covers original and refined default modal analyses, static bolt preload and locking, prestressed modes, X/Y/Z random vibration, seeded motion and stress histories, nonlinear edge-cell pull and the subsequent nickel-damage investigation. The paired delivery matrix in [video_pairs.csv](validation/video_pairs.csv) contains the 22 verified October movie references. Its planned deliverables comprise 22 bare-board movies and 22 matched cased movies showing both fastener variants. Nominal geometry and contact assumptions will be stated with the corresponding results.

The [October baseline notes](case-study-preparation.md) identify the full local Workbench archive. The isolated runtime under `.runtime/` holds generated decks, solver files and temporary fields. Native receipts are checked before accepting results for publication.

## Material references

The printed-PLA baseline uses the directional coupon properties and print conditions in the [PolyLite PLA technical data sheet](https://polymaker.com/wp-content/uploads/lana-downloads/PolyLite-PLA_TDS_EN_V5.4.pdf). The mounting bore diameters in the STEP are 5.000 and 5.090 mm. McMaster-Carr's [nylon socket-head screw listing](https://www.mcmaster.com/products/nylon-allen-screws/) includes the M5 × 0.8 × 12 mm screw, catalog number 93640A149. The actual thread, screw length, installation preload, print orientation and infill are still unmeasured. Case-to-board hole registration will determine the modeled screw geometry.
