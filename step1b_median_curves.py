import glob
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_csv")
HOUR_START = 8
HOUR_END   = 17


def load_csv():
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV found in {DATA_DIR}. Run nsrdb_collector.py first.")
    path = files[0]
    print(f"Loading: {os.path.basename(path)}")
    df = pd.read_csv(path, comment="#")
    df.columns = df.columns.str.strip()
    return df


def build_daily_curves(df, year):
    hours = list(range(HOUR_START, HOUR_END + 1))
    sub = df[(df["Year"] == year) & df["Hour"].between(HOUR_START, HOUR_END)].copy()
    sub["date"] = (
        sub["Year"].astype(str) + "-"
        + sub["Month"].astype(str).str.zfill(2) + "-"
        + sub["Day"].astype(str).str.zfill(2)
    )
    pivot = (
        sub.pivot_table(index="date", columns="Hour", values="GHI", aggfunc="mean")
        .reindex(columns=hours)
        .dropna()
    )
    return pivot.values.astype(float), hours


def modified_band_depth(curves):
    n, _    = curves.shape
    depths  = np.zeros(n)
    n_pairs = n * (n - 1) // 2

    for j in range(n):
        for k in range(j + 1, n):
            lower   = np.minimum(curves[j], curves[k])
            upper   = np.maximum(curves[j], curves[k])
            depths += ((curves >= lower) & (curves <= upper)).mean(axis=1)

    depths /= n_pairs
    return depths


def median_curve_for_year(df, year):
    curves, hours = build_daily_curves(df, year)
    n = len(curves)
    if n == 0:
        return None, hours
    if n == 1:
        return curves[0], hours
    depths = modified_band_depth(curves)
    return curves[int(np.argmax(depths))], hours


def main():
    df    = load_csv()
    years = sorted(df["Year"].unique())
    hours = list(range(HOUR_START, HOUR_END + 1))

    print(f"Years found in data: {years}")

    year_medians = {}
    for yr in years:
        curve, _ = median_curve_for_year(df, yr)
        if curve is not None:
            year_medians[yr] = curve
            n_days = len(build_daily_curves(df, yr)[0])
            print(f"  {yr}: median curve from {n_days} days")
        else:
            print(f"  {yr}: no data — skipped")

    if len(year_medians) < 2:
        raise ValueError("Need at least 2 years of data to find a median of medians.")

    yr_list    = list(year_medians.keys())
    med_matrix = np.array([year_medians[yr] for yr in yr_list])

    print("\nComputing band depth across year-median curves...")
    meta_depths        = modified_band_depth(med_matrix)
    meta_rank          = np.argsort(meta_depths)[::-1]
    overall_median_idx = meta_rank[0]
    overall_median_yr  = yr_list[overall_median_idx]

    print(f"\nMedian of medians -> Year {overall_median_yr} "
          f"(depth={meta_depths[overall_median_idx]:.4f})")
    print("\nPer-year depth ranking:")
    for pos, idx in enumerate(meta_rank, 1):
        suffix = " <- overall median" if pos == 1 else ""
        print(f"  {pos}. {yr_list[idx]}  depth={meta_depths[idx]:.4f}{suffix}")

    cmap        = plt.get_cmap("tab10")
    year_colors = {yr: cmap(i % 10) for i, yr in enumerate(yr_list)}

    fig, ax = plt.subplots(figsize=(13, 6))

    for i, yr in enumerate(yr_list):
        is_median = (yr == overall_median_yr)
        ax.plot(
            hours,
            med_matrix[i],
            color=year_colors[yr],
            linewidth=3.5 if is_median else 1.8,
            zorder=5 if is_median else 2,
            alpha=1.0 if is_median else 0.75,
            label=f"{yr}" + (" * overall median" if is_median else ""),
        )
        if is_median:
            peak_h = hours[int(np.argmax(med_matrix[i]))]
            peak_v = med_matrix[i][int(np.argmax(med_matrix[i]))]
            ax.plot(peak_h, peak_v, "*", color=year_colors[yr], markersize=16, zorder=6)

    ax.set_xlabel("Hour of Day", fontsize=13)
    ax.set_ylabel("GHI (W/m²)", fontsize=13)
    ax.set_title(
        f"Per-Year Median GHI Curves (Hours {HOUR_START}:00–{HOUR_END}:00)\n"
        f"Median of medians -> {overall_median_yr} (*)",
        fontsize=14,
    )
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h}:00" for h in hours], rotation=45)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.legend(fontsize=10, loc="upper left", framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step1b.png")
    plt.savefig(out_path, dpi=150)
    print(f"\nPlot saved to: {out_path}")
    plt.show()


if __name__ == "__main__":
    main()
