#!/usr/bin/env python3
"""
Calculate and compare X, Y, and Z acceleration PSDs from an
Altus Metrum AltosUI CSV export, with an optional single-axis
acceleration dataset from a second CSV.

Example:
  python3 flight_psd.py altos_export.csv \
      --columns accel_x accel_y accel_z \
      --units m/s2 --fs 100 \
      --compare-csv acceleration_only.csv \
      --compare-column acceleration \
      --compare-units g --compare-fs 100

Using timestamps for the primary CSV:
  python3 flight_psd.py altos_export.csv \
      --columns accel_x accel_y accel_z \
      --units m/s2 --time-column time

Using timestamps for both CSV files:
  python3 flight_psd.py altos_export.csv \
      --columns accel_x accel_y accel_z \
      --units m/s2 --time-column time \
      --compare-csv acceleration_only.csv \
      --compare-column acceleration \
      --compare-units g \
      --compare-time-column time

Outputs:
  <prefix>_x.csv
  <prefix>_y.csv
  <prefix>_z.csv
  <prefix>_comparison.csv  (when comparison CSV is supplied)
  <prefix>.png

PSD units are g^2/Hz.

At 100 Hz sampling, the Nyquist frequency is 50 Hz.
Frequencies above the Nyquist frequency cannot be characterized.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import welch


G0 = 9.80665

# Reference PSD profile
REF_FREQS = [20.0, 50.0]
REF_PSDS = [0.026, 0.16]


def calculate_psd(df, column, args):
    """Calculate the one-sided PSD for one acceleration axis."""

    if column not in df.columns:
        raise ValueError(
            f"Column {column!r} not found. Available columns: "
            + ", ".join(df.columns)
        )

    values = pd.to_numeric(
        df[column], errors="coerce"
    ).to_numpy(dtype=float)

    good = np.isfinite(values)
    x = values[good]

    if len(x) < 16:
        raise ValueError(
            f"Too few valid samples in column {column!r}; "
            "at least 16 are required."
        )

    # Determine sampling frequency.
    if args.time_column:
        if args.time_column not in df.columns:
            raise ValueError(
                f"Time column {args.time_column!r} not found."
            )

        t_all = pd.to_numeric(
            df[args.time_column], errors="coerce"
        ).to_numpy(dtype=float)

        t = t_all[good]
        dt = np.diff(t)

        if (
            len(dt) == 0
            or np.any(~np.isfinite(dt))
            or np.any(dt <= 0)
        ):
            raise ValueError(
                f"Timestamps for {column!r} must be finite "
                "and strictly increasing."
            )

        dt_med = float(np.median(dt))
        fs_time = 1.0 / dt_med
        rel_dev = np.max(np.abs(dt - dt_med)) / dt_med

        if args.fs is not None:
            if abs(args.fs - fs_time) / fs_time > 0.02:
                raise ValueError(
                    f"--fs conflicts with timestamp-derived "
                    f"sampling rate for {column!r}: "
                    f"{fs_time:.6g} Hz."
                )

        if rel_dev > 0.02 and not args.allow_irregular:
            raise ValueError(
                f"Nonuniform sampling detected for {column!r} "
                f"(maximum interval deviation "
                f"{100 * rel_dev:.2f}%). Analyze a uniform-rate "
                "segment. --allow-irregular permits small timing "
                "jitter but does not resample the data."
            )

        fs = args.fs if args.fs is not None else fs_time

    elif args.fs is not None:
        fs = args.fs

    else:
        raise ValueError(
            "Provide --fs or --time-column."
        )

    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("Sampling rate must be positive.")

    # Convert acceleration to g.
    if args.units == "m/s2":
        x = x / G0

    # Remove the mean before calculating the PSD.
    x = x - np.mean(x)

    nperseg = min(args.nperseg, len(x))

    f, pxx = welch(
        x,
        fs=fs,
        window="hann",
        nperseg=nperseg,
        noverlap=nperseg // 2,
        detrend="constant",
        scaling="density",
        return_onesided=True,
    )

    return f, pxx, len(x), fs


def band_rms(f, pxx, low, high):
    """Integrate PSD between band edges, including interpolated edges."""

    if low < f[0] or high > f[-1]:
        return float("nan")

    inside = (f > low) & (f < high)

    fb = np.concatenate(([low], f[inside], [high]))
    pb = np.interp(fb, f, pxx)

    # Integrate PSD to obtain variance, then take the square root.
    variance = float(np.trapezoid(pb, fb))
    return np.sqrt(max(variance, 0.0))


def save_psd_csv(output_path, f, pxx):
    """Save PSD values and their decibel representation."""

    result = pd.DataFrame({
        "frequency_Hz": f,
        "psd_g2_per_Hz": pxx,
        "psd_dB_g2_per_Hz": 10 * np.log10(
            np.maximum(pxx, np.finfo(float).tiny)
        ),
    })

    result.to_csv(output_path, index=False)


def add_psd_to_plot(ax, f, pxx, label):
    """Add a PSD curve to the shared comparison plot."""

    positive = f > 0

    ax.plot(
        f[positive],
        pxx[positive],
        label=label,
        linewidth=1.4,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)

    # Primary CSV: three acceleration axes.
    ap.add_argument(
        "csv",
        type=Path,
        help="Primary CSV exported from AltosUI",
    )

    ap.add_argument(
        "--columns",
        nargs=3,
        required=True,
        metavar=("X_COLUMN", "Y_COLUMN", "Z_COLUMN"),
        help="Acceleration column names for X, Y, and Z",
    )

    ap.add_argument(
        "--units",
        choices=("g", "m/s2"),
        required=True,
        help="Units of the primary acceleration columns",
    )

    ap.add_argument(
        "--fs",
        type=float,
        default=None,
        help="Primary sampling rate in Hz",
    )

    ap.add_argument(
        "--time-column",
        default=None,
        help="Primary timestamp column, in seconds",
    )

    # Optional comparison CSV: one acceleration column.
    ap.add_argument(
        "--compare-csv",
        type=Path,
        default=None,
        help="Optional second CSV containing acceleration data",
    )

    ap.add_argument(
        "--compare-column",
        default=None,
        help="Acceleration column name in the second CSV",
    )

    ap.add_argument(
        "--compare-units",
        choices=("g", "m/s2"),
        default=None,
        help="Units of the comparison data; defaults to --units",
    )

    ap.add_argument(
        "--compare-fs",
        type=float,
        default=None,
        help=(
            "Sampling rate of the comparison CSV in Hz. "
            "Defaults to the primary sampling rate when "
            "no comparison timestamp column is provided."
        ),
    )

    ap.add_argument(
        "--compare-time-column",
        default=None,
        help="Timestamp column in the comparison CSV, in seconds",
    )

    # PSD settings.
    ap.add_argument(
        "--nperseg",
        type=int,
        default=1024,
        help="Welch segment length (default: 1024)",
    )

    ap.add_argument(
        "--out-prefix",
        default="flight_psd",
        help="Output filename prefix",
    )

    ap.add_argument(
        "--allow-irregular",
        action="store_true",
        help=(
            "Allow timestamp jitter; does not correct gaps "
            "or changes in sampling rate"
        ),
    )

    args = ap.parse_args()

    if args.nperseg < 16:
        ap.error("--nperseg must be at least 16")

    # The comparison CSV and its column must be specified together.
    if args.compare_csv is not None and not args.compare_column:
        ap.error("--compare-column is required with --compare-csv")

    if args.compare_column and args.compare_csv is None:
        ap.error("--compare-csv is required with --compare-column")

    if args.compare_time_column and args.compare_csv is None:
        ap.error(
            "--compare-time-column requires --compare-csv"
        )

    if args.compare_fs is not None and (
        not np.isfinite(args.compare_fs) or args.compare_fs <= 0
    ):
        ap.error("--compare-fs must be a positive number")

    try:

        df = pd.read_csv(
            args.csv,
            comment="#",
            skipinitialspace=True,
        )

        df.columns = [str(c).strip() for c in df.columns]

        # Use a linear PSD axis and logarithmic frequency axis.
        fig, ax = plt.subplots(figsize=(10, 6))

        axis_names = ["X", "Y", "Z"]
        results = []

        # ---------------------------------------------------------
        # 2. Calculate and plot X, Y, and Z PSDs.
        # ---------------------------------------------------------
        for axis_name, column in zip(
            axis_names, args.columns
        ):
            f, pxx, n, fs = calculate_psd(
                df, column, args
            )

            out_csv = Path(
                f"{args.out_prefix}_{axis_name.lower()}.csv"
            )

            save_psd_csv(out_csv, f, pxx)

            add_psd_to_plot(
                ax,
                f,
                pxx,
                f"{axis_name}-axis ({column})",
            )

            total_rms = np.sqrt(
                max(float(np.trapezoid(pxx, f)), 0.0)
            )

            rms_20_50 = band_rms(
                f, pxx, 20.0, 50.0
            )

            results.append({
                "axis": axis_name,
                "samples": n,
                "fs": fs,
                "nyquist": fs / 2,
                "resolution": f[1] - f[0],
                "total_rms": total_rms,
                "rms_20_50": rms_20_50,
            })

            print(f"\n{axis_name}-axis: {column}")
            print(f"Samples used: {n}")
            print(f"Sampling rate: {fs:.6g} Hz")
            print(f"Nyquist frequency: {fs / 2:.6g} Hz")
            print(
                f"Frequency resolution: "
                f"{f[1] - f[0]:.6g} Hz"
            )
            print(
                f"Total integrated PSD RMS: "
                f"{total_rms:.6g} g"
            )

            if np.isfinite(rms_20_50):
                print(
                    f"20-50 Hz RMS: {rms_20_50:.6g} g"
                )
            else:
                print(
                    "20-50 Hz RMS unavailable: "
                    "band not fully covered."
                )

            print(f"Saved: {out_csv}")

        # ---------------------------------------------------------
        # 3. Optional second CSV containing a single acceleration
        #    signal. Calculate its PSD and overlay it on the plot.
        # ---------------------------------------------------------
        if args.compare_csv is not None:
            compare_df = pd.read_csv(
                args.compare_csv,
                comment="#",
                skipinitialspace=True,
            )

            compare_df.columns = [
                str(c).strip() for c in compare_df.columns
            ]

            # Use the specified comparison units, or fall back
            # to the primary CSV units.
            compare_units = (
                args.compare_units
                if args.compare_units is not None
                else args.units
            )

            # If comparison timestamps are supplied, calculate
            # the rate from them unless --compare-fs is specified.
            #
            # Without timestamps, use --compare-fs if provided;
            # otherwise reuse the primary dataset's sampling rate.
            if args.compare_time_column:
                compare_fs = args.compare_fs
            else:
                compare_fs = (
                    args.compare_fs
                    if args.compare_fs is not None
                    else results[0]["fs"]
                )

            # Build settings for the existing PSD calculation
            # function, without changing the primary settings.
            compare_args = argparse.Namespace(
                units=compare_units,
                fs=compare_fs,
                time_column=args.compare_time_column,
                nperseg=args.nperseg,
                allow_irregular=args.allow_irregular,
            )

            f_cmp, pxx_cmp, n_cmp, fs_cmp = calculate_psd(
                compare_df,
                args.compare_column,
                compare_args,
            )

            # Save the comparison PSD separately.
            compare_out_csv = Path(
                f"{args.out_prefix}_comparison.csv"
            )

            save_psd_csv(
                compare_out_csv,
                f_cmp,
                pxx_cmp,
            )

            # Overlay the additional acceleration PSD on the
            # SAME graph as the original X, Y, and Z curves.
            add_psd_to_plot(
                ax,
                f_cmp,
                pxx_cmp,
                f"Comparison ({args.compare_column})",
            )

            total_rms_cmp = np.sqrt(
                max(
                    float(np.trapezoid(pxx_cmp, f_cmp)),
                    0.0,
                )
            )

            rms_20_50_cmp = band_rms(
                f_cmp, pxx_cmp, 20.0, 50.0
            )

            results.append({
                "axis": "Comparison",
                "samples": n_cmp,
                "fs": fs_cmp,
                "nyquist": fs_cmp / 2,
                "resolution": f_cmp[1] - f_cmp[0],
                "total_rms": total_rms_cmp,
                "rms_20_50": rms_20_50_cmp,
            })

            print(
                f"\nComparison dataset: {args.compare_column}"
            )
            print(f"File: {args.compare_csv}")
            print(f"Samples used: {n_cmp}")
            print(f"Units supplied: {compare_units}")
            print(f"Sampling rate: {fs_cmp:.6g} Hz")
            print(
                f"Nyquist frequency: {fs_cmp / 2:.6g} Hz"
            )
            print(
                f"Frequency resolution: "
                f"{f_cmp[1] - f_cmp[0]:.6g} Hz"
            )
            print(
                f"Total integrated PSD RMS: "
                f"{total_rms_cmp:.6g} g"
            )

            if np.isfinite(rms_20_50_cmp):
                print(
                    f"20-50 Hz RMS: "
                    f"{rms_20_50_cmp:.6g} g"
                )
            else:
                print(
                    "20-50 Hz RMS unavailable: "
                    "band not fully covered."
                )

            print(f"Saved: {compare_out_csv}")

        # ---------------------------------------------------------
        # 4. Reference PSD profile.
        # ---------------------------------------------------------
        ax.plot(
            REF_FREQS,
            REF_PSDS,
            color="red",
            linestyle="-",
            linewidth=2,
            marker="o",
            markersize=6,
            label="Reference PSD profile",
        )

        # ---------------------------------------------------------
        # 5. Format the combined plot.
        # ---------------------------------------------------------
        common_nyquist = min(
            result["nyquist"] for result in results
        )

        if common_nyquist <= 20.0:
            raise ValueError(
                "The lowest Nyquist frequency must exceed "
                "20 Hz to display the requested 20 Hz "
                "lower plot limit."
            )

        ax.set_xscale("log")
        ax.set_xlim(20.0, common_nyquist)

        # Keep the PSD axis linear to support the selected
        # reference values and a zero lower bound.
        ax.set_ylim(0.0, 0.2)

        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Acceleration PSD (g²/Hz)")
        ax.set_title(
            "Acceleration PSD Comparison: X, Y, Z, and Reference"
        )

        ax.set_xticks([20, 50])
        ax.set_xticklabels(["20", "50"])

        ax.set_yticks([
            0.001,
            0.01,
            0.026,
            0.1,
            0.16,
            0.2,
        ])

        ax.set_yticklabels([
            "0.001",
            "0.01",
            "0.026",
            "0.1",
            "0.16",
            "0.2",
        ])

        ax.grid(
            True,
            which="major",
            alpha=0.5,
        )

        ax.legend()
        fig.tight_layout()

        # ---------------------------------------------------------
        # 6. Save the combined graph.
        # ---------------------------------------------------------
        out_png = Path(f"{args.out_prefix}.png")

        fig.savefig(out_png, dpi=180)
        plt.close(fig)

        print(f"\nSaved combined plot: {out_png}")

        print(
            "\nCaution: compare like-for-like sampling rates, "
            "bandwidths, sensor locations, units, and flight phases."
        )

        print(
            "At 100 Hz sampling, frequencies above 50 Hz "
            "cannot be characterized."
        )

    except (
        ValueError,
        OSError,
        pd.errors.ParserError,
    ) as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()