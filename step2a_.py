import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_csv")
MONTHS     = {6: "June", 7: "July", 8: "August", 9: "September"}
GHI_COL    = "GHI"
HOUR_START = 8
HOUR_END   = 17

MONTH_COLORS = {
    6: "#e63946",
    7: "#f4a261",
    8: "#2a9d8f",
    9: "#457b9d",
}


def load_data():
    csvs = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    if not csvs:
        raise FileNotFoundError(f"No CSV file found in: {DATA_DIR}")
    path = os.path.join(DATA_DIR, csvs[0])
    print(f"Loading: {csvs[0]}")
    df = pd.read_csv(path, skiprows=1)
    df.columns = df.columns.str.strip()
    return df


def build_daily_curves(df, month):
    sub = df[(df["Month"] == month) & df["Hour"].between(HOUR_START, HOUR_END)].copy()
    sub["time"] = sub["Hour"] + sub["Minute"] / 60.0
    sub["date"] = (
        sub["Year"].astype(str) + "-"
        + sub["Month"].astype(str).str.zfill(2) + "-"
        + sub["Day"].astype(str).str.zfill(2)
    )
    time_points = sorted(sub["time"].unique())
    pivot = (
        sub.pivot_table(index="date", columns="time", values=GHI_COL, aggfunc="mean")
        .reindex(columns=time_points)
        .dropna()
    )
    return pivot.values.astype(float), np.array(time_points), list(pivot.index)


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


def main():
    df         = load_data()
    year_range = f"{df['Year'].min()}–{df['Year'].max()}"

    fig, ax = plt.subplots(figsize=(13, 6))

    for month, month_name in MONTHS.items():
        curves, time_points, labels = build_daily_curves(df, month)
        n = len(curves)
        print(f"\n{month_name} ({year_range}): {n} days with complete data")

        if n < 2:
            print(f"  Skipping {month_name} — not enough days.")
            continue

        depths     = modified_band_depth(curves)
        median_idx = int(np.argmax(depths))
        print(f"  Median day: {labels[median_idx]}  (depth={depths[median_idx]:.4f})")

        ax.plot(
            time_points,
            curves[median_idx],
            color=MONTH_COLORS[month],
            linewidth=2.5,
            label=f"{month_name}  —  median day: {labels[median_idx]}",
        )

    xticks  = np.arange(HOUR_START, HOUR_END + 0.5, 0.5)
    xlabels = [f"{int(t)}:{int((t % 1) * 60):02d}" for t in xticks]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, rotation=45, ha="right")

    ax.set_xlabel("Time of Day", fontsize=13)
    ax.set_ylabel("Global Horizontal Irradiance  [W/m²]", fontsize=12)
    ax.set_title(
        f"Monthly Median GHI Curves — {year_range}\n"
        f"June · July · August · September  (Modified Band Depth)",
        fontsize=14,
    )
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.legend(fontsize=11, loc="upper left", framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step2a_.png")
    plt.savefig(out_path, dpi=150)
    print(f"\nPlot saved to: {out_path}")
    plt.show()


if __name__ == "__main__":
    main()
