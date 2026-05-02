import glob
import os

import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import numpy as np
import pandas as pd

DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_csv")
HOUR_START = 8
HOUR_END   = 17
N_OUTLIERS = 3


def load_csv():
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV found in {DATA_DIR}. Run nsrdb_collector.py first.")
    path = files[0]
    print(f"Loading: {os.path.basename(path)}")
    df = pd.read_csv(path, comment="#")
    df.columns = df.columns.str.strip()
    return df


def build_curves(df):
    hours = list(range(HOUR_START, HOUR_END + 1))
    sub = df[df["Hour"].between(HOUR_START, HOUR_END)].copy()
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
    return pivot.values.astype(float), hours, list(pivot.index)


def modified_band_depth(curves):
    n, T   = curves.shape
    depths = np.zeros(n)
    n_pairs = n * (n - 1) // 2

    for j in range(n):
        for k in range(j + 1, n):
            lower = np.minimum(curves[j], curves[k])
            upper = np.maximum(curves[j], curves[k])
            depths += ((curves >= lower) & (curves <= upper)).mean(axis=1)

    depths /= n_pairs
    return depths


def plot_functional_boxplot(curves, hours, labels, depths):
    n    = len(curves)
    rank = np.argsort(depths)[::-1]

    median_idx   = rank[0]
    deep2_idx    = rank[1]
    deep3_idx    = rank[2]
    outlier_idxs = rank[-N_OUTLIERS:]

    C_ALL     = "#c8c8c8"
    C_MEDIAN  = "#e63946"
    C_DEEP2   = "#f4a261"
    C_DEEP3   = "#2a9d8f"
    C_OUTLIER = "#6a0dad"

    fig, ax = plt.subplots(figsize=(12, 6))

    for i in range(n):
        if i not in {median_idx, deep2_idx, deep3_idx} and i not in outlier_idxs:
            ax.plot(hours, curves[i], color=C_ALL, linewidth=0.8, alpha=0.6, zorder=1)

    for i in outlier_idxs:
        ax.plot(hours, curves[i], color=C_OUTLIER, linewidth=1.4,
                linestyle="--", alpha=0.85, zorder=2,
                label=f"Outlier: {labels[i]} (depth={depths[i]:.3f})")

    ax.plot(hours, curves[deep3_idx], color=C_DEEP3, linewidth=2.2, zorder=3,
            label=f"3rd deepest: {labels[deep3_idx]} (depth={depths[deep3_idx]:.3f})")
    ax.plot(hours, curves[deep2_idx], color=C_DEEP2, linewidth=2.2, zorder=4,
            label=f"2nd deepest: {labels[deep2_idx]} (depth={depths[deep2_idx]:.3f})")
    ax.plot(hours, curves[median_idx], color=C_MEDIAN, linewidth=3, zorder=5,
            label=f"Median: {labels[median_idx]} (depth={depths[median_idx]:.3f})")

    ax.set_xlabel("Hour of Day", fontsize=13)
    ax.set_ylabel("GHI (W/m²)", fontsize=13)
    ax.set_title(
        f"Hourly GHI Curves — Functional Band Depth Analysis\n"
        f"{n} days  |  Hours {HOUR_START}:00 – {HOUR_END}:00",
        fontsize=14,
    )
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h}:00" for h in hours], rotation=45)
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    grey_patch = mlines.Line2D([], [], color=C_ALL, linewidth=1,
                               label=f"All other days ({n - 3 - N_OUTLIERS})")
    handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=[grey_patch] + handles, fontsize=9, loc="upper left", framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step1a.png")
    plt.savefig(out_path, dpi=150)
    print(f"Plot saved to: {out_path}")
    plt.show()


def print_summary(labels, depths):
    rank = np.argsort(depths)[::-1]
    print("\nBand Depth Ranking (most central → most outlying)")
    print(f"{'Rank':>4}  {'Date':<12}  {'Depth':>7}")
    print("-" * 30)
    for pos, idx in enumerate(rank, 1):
        marker = ""
        if pos == 1:
            marker = " <- median"
        elif pos == 2:
            marker = " <- 2nd deepest"
        elif pos == 3:
            marker = " <- 3rd deepest"
        elif pos > len(labels) - N_OUTLIERS:
            marker = " <- outlier"
        print(f"{pos:>4}  {labels[idx]:<12}  {depths[idx]:>7.4f}{marker}")


def main():
    df = load_csv()
    curves, hours, labels = build_curves(df)
    n = len(curves)
    print(f"Built {n} daily curves × {len(hours)} time points (hours {HOUR_START}–{HOUR_END})")

    if n < 4:
        raise ValueError(f"Need at least 4 days of data to compute band depth; got {n}.")

    print("Computing modified band depth...")
    depths = modified_band_depth(curves)

    print_summary(labels, depths)
    plot_functional_boxplot(curves, hours, labels, depths)


if __name__ == "__main__":
    main()
