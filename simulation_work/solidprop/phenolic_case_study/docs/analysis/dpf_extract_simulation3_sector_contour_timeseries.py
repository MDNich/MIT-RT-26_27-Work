"""Extract final Simulation 3 sector pyrolysis-contour time series.

This wrapper reuses the validated distributed-RTH extractor while applying
the corrected Simulation 3 hot radius and phe0 thickness.
"""

import sys
import traceback
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import dpf_extract_simulation2_contour_timeseries as core  # noqa: E402


core.base.PHE0_INNER_RADIUS_M = 0.066675
core.base.PHE0_THICKNESS_M = 0.001270


if __name__ == "__main__":
    try:
        core.main()
    except BaseException:
        traceback.print_exc()
        raise
