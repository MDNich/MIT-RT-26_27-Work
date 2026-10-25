# Ground station network requirements and protocol

Design revision **0.1**, proposed wire protocol **1.0**, 25 October 2026.

[Read the PDF](Ground_Station_Network_Requirements_Protocol.pdf).

This forward design covers the ten-computer Launch/Away network, Bonjour
discovery, HTTP metadata/snapshots, WebSocket telemetry and status, and H.264 in
MPEG-TS over SRT. It includes station and Iris/Balius channel assignments,
identity and mission handling, JSON message contracts, reconnect and gap
semantics, media session allocation, UI requirements, limits and acceptance tests.

**This is a requirements document, not an implementation or field-validation
report.** H.264 and the general architecture follow the user discussion; the
specific SRT profile, endpoint names and numeric defaults are proposed engineering
choices. Board-switch/uplink commands and remote pointer actuation remain
unsupported pending their hardware and authorization contracts.

The companion [v0a manual](../v0a/README.md) documents released behavior. This
document does not change application code or redefine that released baseline.

## Sources and build

- `main.tex`, `parts/`: editable LaTeX report in the established report style.
- `figures/`: all diagrams drawn with TikZ; no raster diagrams.
- `examples/`: complete synthetic JSON exchanges. They are not real flight data.
- `validate_document.py`: documentation-only checks of references and examples.
- `validation.json`: compilation and document QA evidence, when generated.

Requires a TeX installation providing `latexmk`, pdfLaTeX, KOMA-Script, Latin
Modern and TikZ, plus Python 3 for documentation checks.

```sh
make          # Check examples, compile, copy final PDF here
make check    # Validate documentation inputs only
make clean    # Remove intermediates; retain the PDF
```

No runtime application implementation, firmware or performance test is included.
