import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_csv")
MONTHS     = {6: "June", 7: "July", 8: "August", 9: "September"}
GHI_COL    = "GHI"
HOUR_START = 8
HOUR_END   = 17

MONTH_CMAPS = {
    6: "Reds",
    7: "Oranges",
    8: "Greens",
    9: "Blues",
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


def build_daily_curves(df, year, month):
    sub = df[
        (df["Year"] == year) &
        (df["Month"] == month) &
        df["Hour"].between(HOUR_START, HOUR_END)
    ].copy()
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
    df      = load_data()
    years   = sorted(df["Year"].unique())
    n_years = len(years)

    fig, ax = plt.subplots(figsize=(15, 7))

    shades = np.linspace(0.35, 0.85, n_years)
    cache  = {}

    for month, month_name in MONTHS.items():
        print(f"\n{month_name}")
        for i, year in enumerate(years):
            curves, time_points, labels = build_daily_curves(df, year, month)
            n = len(curves)
            if n < 2:
                print(f"  {year}: skipped ({n} day(s))")
                cache[(month, year)] = None
                continue

            depths     = modified_band_depth(curves)
            median_idx = int(np.argmax(depths))
            print(f"  {year}: median day {labels[median_idx]}  (depth={depths[median_idx]:.4f})")
            cache[(month, year)] = (curves, time_points, labels, median_idx)

            for curve in curves:
                ax.plot(time_points, curve, color="#c8c8c8", linewidth=0.4, alpha=0.5, zorder=1)

    for month, month_name in MONTHS.items():
        cmap = plt.get_cmap(MONTH_CMAPS[month])
        for i, year in enumerate(years):
            entry = cache.get((month, year))
            if entry is None:
                continue
            curves, time_points, labels, median_idx = entry
            ax.plot(
                time_points,
                curves[median_idx],
                color=cmap(shades[i]),
                linewidth=1.8,
                zorder=2,
                label=f"{month_name} {year}",
            )

    xticks  = np.arange(HOUR_START, HOUR_END + 0.5, 0.5)
    xlabels = [f"{int(t)}:{int((t % 1) * 60):02d}" for t in xticks]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, rotation=45, ha="right")

    ax.set_xlabel("Time of Day", fontsize=13)
    ax.set_ylabel("Global Horizontal Irradiance  [W/m²]", fontsize=12)
    ax.set_title(
        f"Per-Year Monthly Median GHI Curves — {years[0]}–{years[-1]}\n"
        f"June · July · August · September  (Modified Band Depth)",
        fontsize=14,
    )
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.legend(fontsize=8, ncol=4, loc="upper left", framealpha=0.9,
              title="Month  /  Year", title_fontsize=9)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step2b_.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved to: {out_path}")
    plt.show()


if __name__ == "__main__":
    main()
