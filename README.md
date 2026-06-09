# WP1 FRESH-CARE — Eulerian Evaluation of Surface Current Products

This repository contains the code used to evaluate satellite-derived ocean surface
current products against in-situ drifter observations from the
[Global Drifter Program (GDP)](https://www.aoml.noaa.gov/phod/gdp/).  
The workflow is part of Work Package 1 (WP1) of the **FRESH-CARE** project.

> The pipeline is organised as a sequence of Jupyter notebooks and one standalone
> Python script.  Run them in the order described below.

---

## Table of Contents

1. [Repository structure](#repository-structure)
2. [Workflow overview](#workflow-overview)
3. [Setup](#setup)
4. [Step-by-step guide](#step-by-step-guide)
   - [Step 1 — Clean drifter data](#step-1--clean-drifter-data)
   - [Step 2 — Merge observational data](#step-2--merge-observational-data)
   - [Step 3 — Drifter data overview (optional)](#step-3--drifter-data-overview-optional)
   - [Step 4 — Interpolate model currents to drifter positions](#step-4--interpolate-model-currents-to-drifter-positions)
   - [Step 5 — General results analysis](#step-5--general-results-analysis)
   - [Step 6 — Regional results analysis](#step-6--regional-results-analysis)
   - [Step 7 — Seasonal / monthly analysis](#step-7--seasonal--monthly-analysis)
5. [Expected directory layout](#expected-directory-layout)
6. [Input data](#input-data)
7. [Adding a new current product](#adding-a-new-current-product)
8. [Dependencies](#dependencies)
9. [Authors](#authors)
10. [License](#license)

---

## Repository structure

```
codes/
├── cleaning_drifter_data.ipynb       # Step 1 – raw GDP NetCDF → cleaned per-buoy CSVs
├── merging_observational_data.ipynb  # Step 2 – per-buoy CSVs → single merged parquet
├── new_drifter_data_overview.ipynb   # Step 3 – visualise drifter trajectories (optional)
├── interpolate_models.py             # Step 4 – interpolate model grids to drifter positions
├── general_results_analysis.ipynb    # Step 5 – global metrics, Taylor diagrams, KDE plots
├── regional_results_analysis.ipynb   # Step 6 – metrics broken down by Arctic sector
├── seasonal_results_analysis.ipynb   # Step 7 – monthly & seasonal breakdown
├── requirements.txt
└── README.md
```

---

## Workflow overview

```
GDP NetCDF file
      │
      ▼
[Step 1] cleaning_drifter_data.ipynb
      │  Quality filtering, low-pass filter, 6-hour standardisation
      │  → data_per_buoy/*.csv  →  data_filtered/*.csv  →  data_ready/*.csv
      ▼
[Step 2] merging_observational_data.ipynb
      │  Concatenate all per-buoy CSVs, assign Arctic region labels (shapefile),
      │  convert longitude convention
      │  → drifters_merged.parquet
      ▼
[Step 3] new_drifter_data_overview.ipynb   (optional — visualisation only)
      │  Arctic map of all drifter trajectories colour-coded by region
      │  → overview figure
      ▼
[Step 4] interpolate_models.py
      │  For each current product and each day, opens the matching NetCDF,
      │  interpolates (bilinear or Delaunay for curvilinear grids) to
      │  each drifter position, appends u_model / v_model columns
      │  → model_outputs/{product}_interpolated.parquet
      ▼
[Step 5] general_results_analysis.ipynb
      │  RMSE, Bias, Correlation (global), KDE distributions,
      │  Taylor diagrams, polar-rose RMSE by direction
      │  → results/*.png
      ▼
[Step 6] regional_results_analysis.ipynb
      │  Same metrics broken down by Arctic sector
      │  Heatmaps, spatial maps of binned RMSE
      │  → results/*.png
      ▼
[Step 7] seasonal_results_analysis.ipynb
         Monthly & seasonal metrics, time-series plots
         → results/*.png
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/wp1-fresh-care-classic-evaluation.git
cd wp1-fresh-care-classic-evaluation
```

### 2. Create and activate a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows
```

Or with conda:

```bash
conda create -n fresh-care python=3.11
conda activate fresh-care
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> `cartopy` and `geopandas` sometimes require system-level GEOS/PROJ libraries.
> On Linux: `sudo apt install libgeos-dev libproj-dev`.  
> On macOS with Homebrew: `brew install geos proj`.

### 4. Configure paths

Every script and notebook has a small **Paths / Configuration** section near the
top (usually the second cell in notebooks, or the `# Configuration` block in the
Python script).  
Update those paths to match where you store your data before running anything.

---

## Step-by-step guide

### Step 1 — Clean drifter data

**Notebook:** `cleaning_drifter_data.ipynb`

**What it does:**

1. Reads the raw GDP 6-hourly NetCDF file (`drifter_6hour_360lon.nc`).
2. Splits records by buoy ID and saves one CSV per buoy to `data_per_buoy/`.
3. Applies quality filters:
   - Removes fill values (`-1e34`, `-999999`).
   - Drops observations with positioning error above threshold (`ERR_POS_MAX`).
   - Removes observations with current speed > `MAX_SPEED` (2.5 m/s by default).
4. Applies a low-pass Butterworth filter to remove inertial/tidal variability.
5. Standardises data to a 6-hour temporal grid and saves to `data_ready/`.

**Paths to configure:**

| Variable | Description |
|---|---|
| `input_data` | Folder containing the raw NetCDF and subdirectories |
| `data_per_bouy` | Output folder for raw per-buoy CSVs |
| `data_filtered` | Intermediate filtered CSVs |
| `data_ready` | Final cleaned per-buoy CSVs used by subsequent steps |

---

### Step 2 — Merge observational data

**Notebook:** `merging_observational_data.ipynb`

**What it does:**

1. Reads all cleaned per-buoy CSVs from `data_ready/`.
2. Concatenates them into a single `pandas` DataFrame.
3. Performs a spatial join with an Arctic regions shapefile to assign a sector
   label (`id_sector`) to each observation.
4. Saves the merged and labelled dataset as `drifters_merged.parquet`.

**Paths to configure:**

| Variable | Description |
|---|---|
| `input_folder` | Path to `data_ready/` (output of Step 1) |
| `output_drifters_file` | Destination for the merged parquet |
| `arctic_regions_file` | Path to the Arctic regions shapefile (`.shp`) |

---

### Step 3 — Drifter data overview *(optional)*

**Notebook:** `new_drifter_data_overview.ipynb`

**What it does:**

Generates an Arctic polar map showing all drifter trajectories coloured by
sector/region.  Useful to visually verify the spatial coverage before running
the evaluation.

**Paths to configure:**

| Variable | Description |
|---|---|
| `DATA_PATH` | Path to `data_ready/` |
| `OUTPUT_PATH` | Where to save the output figure |
| `regions_info` | Path to the regions shapefile / GeoJSON |

---

### Step 4 — Interpolate model currents to drifter positions

**Script:** `interpolate_models.py`

**What it does:**

For each configured current product and for each year in `YEARS` (2011–2021 by
default):

1. Loads the merged drifter parquet.
2. For every unique date, finds the corresponding daily NetCDF file of the
   product.
3. Interpolates the gridded `u` and `v` velocity fields at each drifter
   position using:
   - **bilinear** interpolation (`xarray.interp`) for regular lat/lon grids.
   - **Delaunay triangulation + linear** interpolation (with nearest-neighbour
     fallback) for curvilinear grids.
4. Appends `u_model` and `v_model` columns to the drifter data.
5. Saves one parquet per product to `OUTPUT_DIR`.

**How to run:**

```bash
python interpolate_models.py
```

**Paths / configuration to update inside the script:**

| Variable | Description |
|---|---|
| `DRIFTERS_PATH` | Path to `drifters_merged.parquet` (output of Step 2) |
| `OUTPUT_DIR` | Destination folder for interpolated parquets |
| `YEARS` | Year range to process |
| `MODEL_CONFIG` | Dictionary of current products — see below |

**`MODEL_CONFIG` keys:**

Each product entry in `MODEL_CONFIG` supports the following fields:

| Key | Type | Description |
|---|---|---|
| `path` | `str` | Root folder containing the product's NetCDF files |
| `pattern` | `str` | Glob pattern to match files (e.g. `"*.nc"`, `"**/*.nc"`) |
| `u_name` | `str` | Name of the eastward velocity variable in the NetCDF |
| `v_name` | `str` | Name of the northward velocity variable in the NetCDF |
| `time_name` | `str` | Name of the time coordinate |
| `lat_name` | `str` | Name of the latitude coordinate/variable |
| `lon_name` | `str` | Name of the longitude coordinate/variable |
| `lon_type` | `int` | Longitude convention: `180` → [−180, 180], `360` → [0, 360] |
| `curvilinear` | `bool` | `False` for regular grids, `True` for curvilinear grids |

> **Note:** NetCDF files must be named with an 8-digit date (`yyyymmdd`) somewhere
> in the filename (e.g. `currents_20150312.nc`) so that the script can match each
> file to the correct day.

**Output files** (one per product):

```
model_outputs/
├── ADT-SST_interpolated.parquet
├── ADT-SSS_interpolated.parquet
└── ...
```

Each output parquet keeps all original drifter columns plus `u_model` and
`v_model`.

---

### Step 5 — General results analysis

**Notebook:** `general_results_analysis.ipynb`

**What it does:**

Computes and plots **global** (pan-Arctic) evaluation metrics:

- RMSE, Bias, Pearson Correlation for speed, u-component, and v-component.
- KDE distributions comparing observed vs modelled variables.
- Taylor diagrams (normalised STD, centred RMSE, correlation).
- Polar-rose plots of vectorial RMSE binned by observed current direction.

**Paths to configure:**

| Variable | Description |
|---|---|
| `DATA_DIR` | Folder with interpolated parquets (output of Step 4) |
| `OUTPUT_DIR` | Destination for figures |

---

### Step 6 — Regional results analysis

**Notebook:** `regional_results_analysis.ipynb`

**What it does:**

Same metrics as Step 5 but broken down by **Arctic sector** (using the
`id_sector` labels assigned in Step 2):

- Heatmaps of RMSE / Bias / Correlation with rows = sectors, columns = products.
- Spatial maps of binned RMSE on an Arctic polar projection.

**Paths to configure:** same as Step 5 (`DATA_DIR`, `OUTPUT_DIR`).

---

### Step 7 — Seasonal / monthly analysis

**Notebook:** `seasonal_results_analysis.ipynb`

**What it does:**

Computes metrics aggregated by **month** and **season** to study temporal
variability in model performance.

**Paths to configure:** same as Step 5 (`DATA_DIR`, `OUTPUT_DIR`).

---

## Expected directory layout

The scripts expect (or create) the following directory structure.  
You can place the data anywhere — just update the path variables accordingly.

```
<data_root>/
├── in_situ_data/
│   ├── raw_data/
│   │   └── drifter_6hour_360lon.nc          ← GDP raw file (Step 1 input)
│   ├── data_per_bouy/                        ← created by Step 1
│   ├── data_filtered/                        ← created by Step 1
│   ├── data_ready/                           ← created by Step 1
│   └── drifters_merged.parquet              ← created by Step 2
│
├── model_outputs/                            ← created by Step 4
│   ├── ProductA_interpolated.parquet
│   └── ProductB_interpolated.parquet
│
└── results/                                  ← created by Steps 5-7
    ├── taylor_diagram_speed.png
    └── ...

<regions_data>/
└── arctic_regions.shp   (+ .dbf, .prj …)    ← Arctic sectors shapefile
```

---

## Input data

| Dataset | Source | Format | Used in |
|---|---|---|---|
| GDP 6-hourly drifter data | [Global Drifter Program](https://www.aoml.noaa.gov/phod/gdp/) — publicly available | NetCDF | Step 1 |
| Arctic regions shapefile | Project-specific | Shapefile | Step 2 |
| Surface current products (NetCDF) | Various — see `MODEL_CONFIG` in `interpolate_models.py` | NetCDF (daily files) | Step 4 |

---

## Adding a new current product

1. Open `interpolate_models.py`.
2. Add a new entry to the `MODEL_CONFIG` dictionary following the existing
   examples.  Set `curvilinear = True` if the product uses a curvilinear grid.
3. Re-run Step 4 to generate the new interpolated parquet.
4. The analysis notebooks (Steps 5–7) will pick up the new product automatically
   as long as you add its filename to the `files` dictionary at the top of each
   notebook.

---

## Dependencies

See `requirements.txt` for the full pinned list. Core packages:

| Package | Purpose |
|---|---|
| `xarray` | Reading and interpolating NetCDF files |
| `pandas` | Tabular data manipulation |
| `numpy` | Numerical operations |
| `netCDF4` | Low-level NetCDF reading (Step 1) |
| `scipy` | Signal filtering and spatial interpolation |
| `geopandas` / `shapely` | Spatial join for region assignment |
| `cartopy` | Arctic map projections |
| `matplotlib` | All plotting |
| `skill_metrics` | Taylor diagram computation |

---

## Authors

**r0squete** and **jcrespinesteve**
Contributions and issue reports are welcome via GitHub Issues.

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for
details.
