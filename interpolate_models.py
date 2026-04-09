# Script to interpolate ocean current models to drifter trajectories
# r0squete - 2026-04-01
#
# HOW TO RUN:
#   python interpolate_models.py
#
# OUTPUT:
#   One parquet per model in OUTPUT_DIR, e.g. "ADT-SST_interpolated.parquet"
#   Each file keeps all original drifter columns + u_model, v_model

import gc
import glob
import os
import re
import warnings

import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import Delaunay

warnings.filterwarnings("ignore")

# Configuration

DRIFTERS_PATH = (
    "/home/FRESH-CARE/Codes/Fusion_stuff/fresh_care_wp1_classic_validation/"
    "in_situ_data/drifters_merged.parquet"
)

OUTPUT_DIR = (
    "/home/FRESH-CARE/Codes/Fusion_stuff/fresh_care_wp1_classic_validation/"
    "model_outputs"
)

YEARS = range(2011, 2022)  # 2011-2021 inclusive
# YEARS = range(2011, 2012)  # quick test

# Model configuration:
#   path        : folder with NetCDF files
#   pattern     : glob pattern (supports ** for subdirectories)
#   u_name      : eastward velocity variable name in the NetCDF
#   v_name      : northward velocity variable name in the NetCDF
#   time_name   : name of the time coordinate
#   lat_name    : name of the latitude coordinate/variable
#   lon_name    : name of the longitude coordinate/variable
#   lon_type    : 180 -> model uses [-180, 180]
#                 360 -> model uses [0, 360]  (converted automatically)
#   curvilinear : False -> regular lat/lon grid (bilinear interp with xarray)
#                 True  -> 2-D curvilinear grid  (Delaunay triangulation + linear)

MODEL_CONFIG = {
    "ADT-SST": {
        "path": "/data/FRESH-CARE/fusion_results/currents/ADT-SST",
        "pattern": "*.nc",
        "u_name": "ug",
        "v_name": "vg",
        "time_name": "time",
        "lat_name": "lat",
        "lon_name": "lon",
        "lon_type": 180,
        "curvilinear": False,
    },
    "ADT-SSS": {
        "path": "/data/FRESH-CARE/fusion_results/currents/ADT-SSS",
        "pattern": "*.nc",
        "u_name": "ug",
        "v_name": "vg",
        "time_name": "time",
        "lat_name": "lat",
        "lon_name": "lon",
        "lon_type": 180,
        "curvilinear": False,
    },
    "ADT-0.25": {
        "path": "/data/FRESH-CARE/Data_satellite/AVISO/regridded/0.25",
        "pattern": "*.nc",
        "u_name": "ugos",
        "v_name": "vgos",
        "time_name": "time",
        "lat_name": "lat",
        "lon_name": "lon",
        "lon_type": 180,
        "curvilinear": False,
    },
    "OSCAR-geos": {
        "path": "/data/FRESH-CARE/ext_currents_datasets/OSCAR/data",
        "pattern": "*.nc",
        "u_name": "ug",
        "v_name": "vg",
        "time_name": "time",
        "lat_name": "latitude",
        "lon_name": "longitude",
        "lon_type": 360,
        "curvilinear": False,
    },
}


# Functions


def get_files_for_year(path: str, pattern: str, year: int) -> list:
    """Return all files whose filename date matches the given year."""
    recursive = "**" in pattern
    all_files = sorted(glob.glob(os.path.join(path, pattern), recursive=recursive))
    return [f for f in all_files if _year_from_file(f) == year]


def _year_from_file(filepath: str) -> int | None:
    ts = _date_from_filename(filepath)
    return ts.year if ts is not None else None


def _date_from_filename(filepath: str) -> pd.Timestamp | None:
    """
    Look for an 8-digit substring (yyyymmdd) in the filename.
    Returns a Timestamp or None if nothing parseable is found.
    """
    match = re.search(r"(\d{8})", os.path.basename(filepath))
    if match:
        try:
            return pd.to_datetime(match.group(1), format="%Y%m%d")
        except ValueError:
            return None
    return None


def build_date_index(files: list) -> dict:
    """
    Build a dict mapping date (Timestamp at midnight) -> filepath for fast
    day-by-day lookup. Files with no parseable date in the name are skipped.
    """
    index = {}
    for f in files:
        date = _date_from_filename(f)
        if date is None:
            print(
                f"     WARNING: could not parse date from {os.path.basename(f)}, skipping.",
                flush=True,
            )
            continue
        index[date.normalize()] = f
    return index


def convert_lon(lon_series: pd.Series, target: int) -> pd.Series:
    """Convert drifter longitudes to match the model convention (180 or 360)."""
    if target == 360:
        return lon_series % 360
    return ((lon_series + 180) % 360) - 180


def open_file(filepath: str, cfg: dict) -> xr.Dataset:
    """
    Open a NetCDF file, keep only the velocity variables (+ lat/lon for
    curvilinear grids), rename coordinates to canonical names (lat, lon, time),
    and load everything into memory.
    """
    ds = xr.open_dataset(filepath, engine="netcdf4")
    lat_n, lon_n = cfg["lat_name"], cfg["lon_name"]

    # Keep only what we need
    vars_to_keep = [cfg["u_name"], cfg["v_name"]]
    if cfg["curvilinear"]:
        # 2-D lat/lon may be data_vars; if they are coords they survive the subset automatically
        for name in [lat_n, lon_n]:
            if name in ds.data_vars:
                vars_to_keep.append(name)
    ds = ds[vars_to_keep]

    # For curvilinear grids: if lat/lon were coords in the original dataset,
    # xarray drops them after subsetting — re-attach them
    if cfg["curvilinear"]:
        orig = xr.open_dataset(filepath, engine="netcdf4")
        for name in [lat_n, lon_n]:
            if name not in ds.coords and name not in ds.data_vars:
                if name in orig.coords or name in orig.data_vars:
                    ds = ds.assign_coords({name: orig[name]})
        orig.close()

    # Rename to canonical names: lat, lon, time
    rename_map = {}
    rename_dims = {}

    if cfg["time_name"] != "time" and cfg["time_name"] in ds.coords:
        rename_map[cfg["time_name"]] = "time"

    for orig_name, canon in [(lat_n, "lat"), (lon_n, "lon")]:
        if orig_name == canon:
            continue
        if orig_name in ds.coords and canon not in ds.coords:
            rename_map[orig_name] = canon
        if orig_name in ds.dims and canon not in ds.dims:
            rename_dims[orig_name] = canon

    if rename_map:
        ds = ds.rename(rename_map)

    for old_dim, new_dim in rename_dims.items():
        if old_dim in ds.dims:
            if new_dim in ds.coords:
                ds = ds.swap_dims({old_dim: new_dim})
            else:
                ds = ds.rename({old_dim: new_dim})

    ds.load()
    return ds


def interp_regular(ds: xr.Dataset, df_day: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Bilinear interpolation on a regular lat/lon grid.
    xarray.interp applies linear interpolation along each axis, which is
    equivalent to bilinear interpolation in 2-D.
    """
    lons = xr.DataArray(
        convert_lon(df_day["longitude"], cfg["lon_type"]).values, dims="points"
    )
    lats = xr.DataArray(df_day["latitude"].values, dims="points")

    u_out = (
        ds[cfg["u_name"]]
        .squeeze(drop=True)
        .interp(lat=lats, lon=lons, method="linear")
        .values
    )
    v_out = (
        ds[cfg["v_name"]]
        .squeeze(drop=True)
        .interp(lat=lats, lon=lons, method="linear")
        .values
    )

    return pd.DataFrame({"u_model": u_out, "v_model": v_out}, index=df_day.index)


def interp_curvilinear(
    ds: xr.Dataset, df_day: pd.DataFrame, cfg: dict, tri_cache: dict
) -> pd.DataFrame:
    """
    Linear interpolation on a curvilinear grid using Delaunay triangulation.
    The triangulation is expensive but cached across days for the same model/year.
    Points outside the model domain fall back to nearest-neighbour.
    """
    lat_key = "lat" if "lat" in ds.coords or "lat" in ds.data_vars else cfg["lat_name"]
    lon_key = "lon" if "lon" in ds.coords or "lon" in ds.data_vars else cfg["lon_name"]

    lat_flat = ds[lat_key].values.ravel()
    lon_flat = ds[lon_key].values.ravel()
    u_flat = ds[cfg["u_name"]].squeeze(drop=True).values.ravel()
    v_flat = ds[cfg["v_name"]].squeeze(drop=True).values.ravel()

    # Drop invalid grid points before triangulating
    valid = np.isfinite(lat_flat) & np.isfinite(lon_flat) & np.isfinite(u_flat)
    grid_pts = np.column_stack((lat_flat[valid], lon_flat[valid]))
    u_valid = u_flat[valid]
    v_valid = v_flat[valid]

    # Build Delaunay triangulation once; reuse for all days of the same year
    if "tri" not in tri_cache:
        tri_cache["tri"] = Delaunay(grid_pts)
    tri = tri_cache["tri"]

    drifter_pts = np.column_stack(
        (
            df_day["latitude"].values,
            convert_lon(df_day["longitude"], cfg["lon_type"]).values,
        )
    )

    u_out = LinearNDInterpolator(tri, u_valid)(drifter_pts)
    v_out = LinearNDInterpolator(tri, v_valid)(drifter_pts)

    # Nearest-neighbour fallback for points outside the model convex hull
    nan_mask = np.isnan(u_out) | np.isnan(v_out)
    if np.any(nan_mask):
        nn = NearestNDInterpolator(grid_pts, np.column_stack((u_valid, v_valid)))
        uv_nn = nn(drifter_pts[nan_mask])
        u_out[nan_mask] = uv_nn[:, 0]
        v_out[nan_mask] = uv_nn[:, 1]

    return pd.DataFrame({"u_model": u_out, "v_model": v_out}, index=df_day.index)


# Main


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60, flush=True)
    print("Loading drifter data...", flush=True)
    drifters = pd.read_parquet(DRIFTERS_PATH)
    drifters["time"] = pd.to_datetime(drifters["time"])
    drifters["_year"] = drifters["time"].dt.year
    t = drifters["time"]
    if t.dt.tz is not None:
        t = t.dt.tz_localize(None)
    drifters["_date"] = t.dt.normalize()
    print(f"  Total drifter points : {len(drifters):,}", flush=True)
    print(f"  Columns              : {list(drifters.columns)}", flush=True)
    print("=" * 60, flush=True)

    for model_name, cfg in MODEL_CONFIG.items():
        print(f"\n{'=' * 60}", flush=True)
        print(f"MODEL: {model_name}", flush=True)
        print(f"{'=' * 60}", flush=True)

        yearly_results = []

        for year in YEARS:
            print(f"\n  -- {year} --", flush=True)

            df_year = drifters[drifters["_year"] == year].copy()
            if df_year.empty:
                print("     No drifter points, skipping.", flush=True)
                continue
            print(f"     Drifter points : {len(df_year):,}", flush=True)

            files = get_files_for_year(cfg["path"], cfg["pattern"], year)
            if not files:
                print(
                    f"     WARNING: no NetCDF files found in {cfg['path']}", flush=True
                )
                continue
            print(f"     NetCDF files   : {len(files)}", flush=True)

            date_index = build_date_index(files)
            unique_dates = sorted(df_year["_date"].unique())
            print(f"     Unique drifter dates : {len(unique_dates)}", flush=True)

            day_results = []
            matched = 0
            missing = 0
            tri_cache: dict = {}  # Delaunay cache — only used for curvilinear grids

            for date in unique_dates:
                df_day = df_year[df_year["_date"] == date]
                filepath = date_index.get(date)

                if filepath is None:
                    missing += 1
                    continue

                ds = None
                try:
                    ds = open_file(filepath, cfg)
                    if cfg["curvilinear"]:
                        day_res = interp_curvilinear(ds, df_day, cfg, tri_cache)
                    else:
                        day_res = interp_regular(ds, df_day, cfg)
                    day_results.append(day_res)
                    matched += 1

                except Exception as exc:
                    print(f"     ERROR on {date.date()}: {exc}", flush=True)
                    # On the first error, print the file structure to help diagnose
                    if matched == 0 and missing == 0:
                        try:
                            _ds = xr.open_dataset(filepath, engine="netcdf4")
                            print(
                                f"     [diag] vars  : {list(_ds.data_vars)}", flush=True
                            )
                            print(f"     [diag] coords: {list(_ds.coords)}", flush=True)
                            _ds.close()
                        except Exception:
                            pass

                finally:
                    if ds is not None:
                        ds.close()
                    del ds

            print(
                f"     Days matched : {matched}  |  Days missing : {missing}",
                flush=True,
            )

            if day_results:
                year_result = pd.concat(day_results)
                yearly_results.append(year_result)
                valid_pts = year_result["u_model"].notna().sum()
                print(
                    f"     Interpolated : {len(year_result):,} points  ({valid_pts:,} non-NaN)",
                    flush=True,
                )
            else:
                print("     No results for this year.", flush=True)

            del df_year, tri_cache
            gc.collect()

        # Save model results: join interpolated values back onto the original drifter dataframe
        if yearly_results:
            all_results = pd.concat(yearly_results)
            output = drifters.drop(columns=["_year", "_date"]).join(
                all_results, how="left"
            )
            out_path = os.path.join(OUTPUT_DIR, f"{model_name}_interpolated.parquet")
            output.reset_index(drop=True).to_parquet(out_path, index=False)
            print(f"\n  Saved -> {out_path}", flush=True)
            del all_results, output
        else:
            print(f"\n  No results for {model_name}. Nothing saved.", flush=True)

        gc.collect()

    del drifters
    gc.collect()

    print("\n" + "=" * 60, flush=True)
    print("All models processed.", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
