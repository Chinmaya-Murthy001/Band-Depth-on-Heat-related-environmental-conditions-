import requests
import pandas as pd
import io
import os
import glob
import time
from datetime import datetime

BASE_URL = "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-aggregated-v4-0-0-download.csv"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_csv")

AVAILABLE_ATTRIBUTES = [
    "ghi", "dhi", "dni", "wind_speed", "wind_direction",
    "air_temperature", "surface_pressure", "relative_humidity",
    "dew_point", "surface_albedo", "precipitable_water",
    "solar_zenith_angle", "cloud_type", "fill_flag",
]

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


def prompt_int(prompt, min_val, max_val):
    while True:
        try:
            val = int(input(prompt).strip())
            if min_val <= val <= max_val:
                return val
            print(f"  Enter a value between {min_val} and {max_val}.")
        except ValueError:
            print("  Please enter a whole number.")


def prompt_float(prompt):
    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print("  Please enter a number.")


def collect_inputs():
    print("\n" + "=" * 60)
    print("  NSRDB Solar Data Collector")
    print("  Source: NREL National Solar Radiation Database")
    print("=" * 60)

    print("\n[Credentials]")
    print("  Get a free API key at: https://developer.nrel.gov/signup/")
    api_key     = input("  NREL API key: ").strip()
    full_name   = input("  Full name: ").strip()
    email       = input("  Email: ").strip()
    affiliation = input("  Affiliation (e.g. Student, University): ").strip() or "Student"

    print("\n[1/4] Location")
    print("  Example — Boston, MA: lat=42.36, lon=-71.05")
    lat = prompt_float("  Latitude  (-90  to  90):  ")
    while not (-90 <= lat <= 90):
        print("  Latitude must be between -90 and 90.")
        lat = prompt_float("  Latitude  (-90  to  90):  ")

    lon = prompt_float("  Longitude (-180 to 180): ")
    while not (-180 <= lon <= 180):
        print("  Longitude must be between -180 and 180.")
        lon = prompt_float("  Longitude (-180 to 180): ")
    if lon > 0 and lat > 20:
        print(f"  Note: lon={lon} is east of Greenwich. For US locations use a negative value.")
        if input("  Continue with this longitude? (y/n): ").strip().lower() != "y":
            lon = prompt_float("  Longitude (-180 to 180): ")

    current_year = datetime.now().year
    max_year = current_year - 2
    print(f"\n[2/4] Year Range  (available: 1998 – {max_year})")
    start_year = prompt_int("  Start year: ", 1998, max_year)
    end_year   = prompt_int("  End year:   ", start_year, max_year)

    print("\n[3/4] Month Range  (1 = January … 12 = December)")
    start_month = prompt_int("  Start month (1–12): ", 1, 12)
    end_month   = prompt_int("  End month   (1–12): ", start_month, 12)

    print("\n[4/4] Time Interval")
    print("  30 → 30-minute intervals  |  60 → 60-minute intervals")
    interval = prompt_int("  Interval (30 or 60): ", 1, 60)
    while interval not in (30, 60):
        print("  Please enter 30 or 60.")
        interval = prompt_int("  Interval (30 or 60): ", 1, 60)

    print("\n[Optional] Attributes")
    print("  Default: ghi, dhi, dni, wind_speed, air_temperature")
    print("  Available: " + ", ".join(AVAILABLE_ATTRIBUTES))
    custom = input("  Press Enter for defaults, or enter comma-separated attributes: ").strip()
    if custom:
        attrs = [a.strip() for a in custom.split(",") if a.strip() in AVAILABLE_ATTRIBUTES]
        if not attrs:
            print("  No valid attributes — using defaults.")
            attrs = ["ghi", "dhi", "dni", "wind_speed", "air_temperature"]
    else:
        attrs = ["ghi", "dhi", "dni", "wind_speed", "air_temperature"]

    return {
        "api_key":     api_key,
        "full_name":   full_name,
        "email":       email,
        "affiliation": affiliation,
        "reason":      "education",
        "lat":         lat,
        "lon":         lon,
        "start_year":  start_year,
        "end_year":    end_year,
        "start_month": start_month,
        "end_month":   end_month,
        "interval":    interval,
        "attributes":  attrs,
    }


def fetch_year(cfg, year):
    params = {
        "api_key":      cfg["api_key"],
        "wkt":          f"POINT({cfg['lon']} {cfg['lat']})",
        "names":        year,
        "interval":     cfg["interval"],
        "attributes":   ",".join(cfg["attributes"]),
        "leap_day":     "true",
        "utc":          "false",
        "full_name":    cfg["full_name"],
        "email":        cfg["email"],
        "affiliation":  cfg["affiliation"],
        "reason":       cfg["reason"],
        "mailing_list": "false",
    }

    print(f"  Fetching {year}...", end="", flush=True)
    try:
        resp = requests.get(BASE_URL, params=params, timeout=120)
    except requests.exceptions.RequestException as e:
        print(f" CONNECTION ERROR: {e}")
        return None

    if resp.status_code != 200:
        print(f" FAILED (HTTP {resp.status_code})")
        print(f"  Server response:\n    {resp.text[:500].strip()}")
        return None

    content_type = resp.headers.get("Content-Type", "")
    if "json" in content_type or resp.text.lstrip().startswith("{"):
        print(" FAILED (API returned JSON error)")
        print(f"  {resp.text[:400]}")
        return None

    lines = resp.text.splitlines()
    if len(lines) < 3:
        print(" FAILED (response too short)")
        print(f"  {resp.text[:300]}")
        return None

    metadata_str = lines[0]
    df = pd.read_csv(io.StringIO(resp.text), skiprows=2, low_memory=False)
    print(f" OK ({len(df):,} rows, columns: {list(df.columns[:5])}…)")
    return df, metadata_str


def filter_months(df, start_month, end_month):
    month_col = next((c for c in df.columns if c.lower() == "month"), None)
    if month_col is None:
        print("  Warning: 'Month' column not found — returning all rows.")
        return df
    return df[df[month_col].between(start_month, end_month)].copy()


def main():
    cfg = collect_inputs()

    print("\n" + "-" * 60)
    print("Summary")
    print(f"  Location   : {cfg['lat']}°N, {cfg['lon']}°E")
    print(f"  Years      : {cfg['start_year']} – {cfg['end_year']}")
    print(f"  Months     : {MONTH_NAMES[cfg['start_month']]} – {MONTH_NAMES[cfg['end_month']]}")
    print(f"  Interval   : {cfg['interval']} min")
    print(f"  Attributes : {', '.join(cfg['attributes'])}")
    print("-" * 60)
    if input("Proceed? (y/n): ").strip().lower() != "y":
        print("Aborted.")
        return

    all_frames   = []
    first_meta   = None
    failed_years = []
    total_years  = cfg["end_year"] - cfg["start_year"] + 1

    print(f"\nDownloading {total_years} year(s) of data:")

    for i, year in enumerate(range(cfg["start_year"], cfg["end_year"] + 1)):
        result = fetch_year(cfg, year)
        if result is None:
            failed_years.append(year)
            continue

        df, meta = result
        if first_meta is None:
            first_meta = meta

        all_frames.append(filter_months(df, cfg["start_month"], cfg["end_month"]))

        if i < total_years - 1:
            time.sleep(1.1)  # NREL rate limit: 1 request/second

    if not all_frames:
        print("\nNo data was retrieved. Check your API key and parameters.")
        if failed_years:
            print(f"  Failed years: {failed_years}")
        return

    combined = pd.concat(all_frames, ignore_index=True)

    if failed_years:
        print(f"\nWarning: could not fetch data for years: {failed_years}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    old_files = glob.glob(os.path.join(OUTPUT_DIR, "*.csv"))
    for f in old_files:
        os.remove(f)
    if old_files:
        print(f"\nCleared {len(old_files)} previous file(s) from data_csv/")

    out_name = (
        f"nsrdb_lat{cfg['lat']}_lon{cfg['lon']}_"
        f"{cfg['start_year']}-{cfg['end_year']}_"
        f"m{cfg['start_month']:02d}-m{cfg['end_month']:02d}.csv"
    )
    out_path = os.path.join(OUTPUT_DIR, out_name)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        if first_meta:
            f.write("# NSRDB Site Metadata: " + first_meta + "\n")
        combined.to_csv(f, index=False)

    print(f"\nDone. {len(combined):,} rows saved to:\n  {out_path}")


if __name__ == "__main__":
    main()
