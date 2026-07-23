"""Extract Simulation 2 SVAR profiles from the distributed RTH partitions.

This read-only DPF wrapper reuses the validated Simulation 1 spatial extractor
but adds the latest synchronized Simulation 2 history time to the six integer
times.  The resulting CSV files therefore contain profiles at 1--6 s for the
stacked comparisons and one additional latest-state profile for the standalone
radial SVAR1 figure.

Run with the ANSYS 2026 R1 CPython interpreter on Windows.
"""

import argparse
import sys
import traceback
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dpf_extract_svar_spatiotemporal_profiles as base  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("radial_output_csv", type=Path)
    parser.add_argument("axial_output_csv", type=Path)
    parser.add_argument("history_csv", type=Path)
    parser.add_argument("result_files", nargs="+", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    history = np.genfromtxt(
        args.history_csv,
        names=True,
        dtype=float,
        encoding="utf-8",
    )
    history = np.atleast_1d(history)
    if "time_s" not in (history.dtype.names or ()):
        raise RuntimeError("Unexpected Simulation 2 history columns.")
    latest_time = float(history["time_s"][-1])
    if latest_time < 6.0:
        raise RuntimeError(
            "The synchronized history stops before 6 s ({:.12g} s).".format(
                latest_time
            )
        )

    base.TARGET_TIMES_S = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, latest_time)
    sys.argv = [
        str(Path(base.__file__).resolve()),
        str(args.radial_output_csv),
        str(args.axial_output_csv),
    ] + [str(path) for path in args.result_files]
    base.main()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
