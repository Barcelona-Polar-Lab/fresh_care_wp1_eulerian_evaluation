# WP1 FRESH-CARE — Eulerian Evaluation of Surface Current Products 🌊📊

This directory contains the core computational framework used to evaluate satellite-derived ocean surface current products against *in-situ* drifter observations from the [Global Drifter Program (GDP)](https://www.aoml.noaa.gov/phod/gdp/).  

The workflow is a cornerstone of **Work Package 1 (WP1)** within the **FRESH-CARE** project.

> 💡 **Execution Note:** The pipeline is organized as a sequential suite of Jupyter notebooks and a standalone high-performance Python script. To ensure data integrity, execute them strictly in the order described below.

---

## Table of Contents
1. [📂 Repository Structure](#-repository-structure)
2. [🔄 Workflow Overview](#-workflow-overview)
3. [⚙️ Environment Setup](#%EF%B8%8F-environment-setup)
4. [📋 Step-by-Step Guide](#-step-by-step-guide)
5. [🏗️ Expected Directory Layout](#%EF%B8%8F-expected-directory-layout)
6. [💾 Input Data Assets](#-input-data-assets)
7. [🔌 Adding a New Current Product](#-adding-a-new-current-product)
8. [📦 Dependencies](#-dependencies)
9. [👥 Authors & Credits](#-authors--credits)
10. [📄 License](#-license)

---

## 📂 Repository Structure

```text
codes/
├── cleaning_drifter_data.ipynb       # Step 1 – Raw GDP NetCDF → Cleaned per-buoy CSVs
├── merging_observational_data.ipynb  # Step 2 – Per-buoy CSVs → Single merged Parquet
├── new_drifter_data_overview.ipynb   # Step 3 – Visualise drifter trajectories (Optional)
├── interpolate_models.py             # Step 4 – Interpolate model grids to drifter positions
├── general_results_analysis.ipynb    # Step 5 – Global metrics, Taylor diagrams, KDE plots
├── regional_results_analysis.ipynb   # Step 6 – Metrics broken down by Arctic sector
├── seasonal_results_analysis.ipynb   # Step 7 – Monthly & seasonal breakdown
├── requirements.txt                  # Python dependencies pinned list
└── README.md                         # This documentation file
```

---

## 🔄 Workflow Overview

```text
      GDP NetCDF Master File
                │
                ▼
  [Step 1] cleaning_drifter_data.ipynb
                │  Quality filtering, Butterworth low-pass, 6h standardisation
                │  → data_per_buoy/*.csv ➔ data_filtered/*.csv ➔ data_ready/*.csv
                ▼
  [Step 2] merging_observational_data.ipynb
                │  Concatenate buoys, spatial join with Arctic shapefile (sector labels),
                │  convert longitude conventions [0, 360] to [-180, 180]
                │  → drifters_merged.parquet
                ▼
  [Step 3] new_drifter_data_overview.ipynb (Optional Diagnostic Visualisation)
                │  Generate polar maps of active drifter trajectories colour-coded by region
                │  → overview spatial figures
                ▼
  [Step 4] interpolate_models.py
                │  Spatiotemporal interpolation (Bilinear / Delaunay curvilinear) 
                │  of gridded u/v model datasets onto discrete drifter tracks
                │  → model_outputs/{product}_interpolated.parquet
                ▼
  [Step 5] general_results_analysis.ipynb
                │  Compute Pan-Arctic metrics: RMSE, Bias, Correlation, Taylor Diagrams, KDEs
                │  → results/general_*.png
                ▼
  [Step 6] regional_results_analysis.ipynb
                │  Compute metrics broken down by Arctic sectors & spatial RMSE bin maps
                │  → results/regional_*.png
                ▼
  [Step 7] seasonal_results_analysis.ipynb
                │  Monthly and seasonal aggregation & time-series analysis
                │  → results/seasonal_*.png
```

---

## ⚙️ Environment Setup

### 1. Clone the Module Repository
```bash
git clone [https://github.com/Barcelona-Polar-Lab/wp1-fresh-care-classic-evaluation.git](https://github.com/Barcelona-Polar-Lab/wp1-fresh-care-classic-evaluation.git)
cd wp1-fresh-care-classic-evaluation
```

### 2. Activate Python Virtual Environment
Using standard `venv`:
```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows
```
Or using `conda`:
```bash
conda create -n fresh-care python=3.11 -y
conda activate fresh-care
```

### 3. Install Required Packages
```bash
pip install -r requirements.txt
```
> ⚠️ **System Library Requirement:** Core geospatial libraries like `cartopy` and `geopandas` require underlying low-level C bindings. 
> * **Linux (Ubuntu/Debian):** `sudo apt install libgeos-dev libproj-dev`
> * **macOS (Homebrew):** `brew install geos proj`

### 4. Configuration Check
Every script and notebook features a dedicated **Paths / Configuration** block in its topmost cells. You **must** update these local directory routes to point to your data root before firing up the scripts.

---

## 📋 Step-by-Step Guide

### 🛠️ Step 1 — Clean Drifter Data
* **Target Script:** `cleaning_drifter_data.ipynb`
* **Core Action:** Processes the raw GDP 6-hourly master file (`drifter_6hour_360lon.nc`), segments records by individual platform ID (`buoy ID`), and filters out noise.
* **QC Thresholds Applied:**
  * Drops fill values (`-1e34`, `-999999`).
  * Removes data points exceeding position error limits (`ERR_POS_MAX`).
  * Truncates unphysical speeds exceeding `MAX_SPEED` (2.5 m/s by default).
  * Applies a digital **Butterworth low-pass filter** to peel off tidal and inertial mooring high-frequency oscillations.

| Configuration Variable | Target Description |
| :--- | :--- |
| `input_data` | Root directory hosting the raw NetCDF source files |
| `data_per_bouy` | Output location for the initial per-buoy raw splits |
| `data_filtered` | Intermediate tracking directory for quality-controlled profiles |
| `data_ready` | Final destination for low-pass filtered, uniform 6h CSV logs |

---

### 🛠️ Step 2 — Merge Observational Data
* **Target Script:** `merging_observational_data.ipynb`
* **Core Action:** Concatenates isolated processed data frames into a highly efficient single storage format, applying a spatial indexing join.
* **Spatial Join Logic:** Uses a customized Arctic polygons shapefile to append a physical sector metadata tag (`id_sector`) to each data row.

| Configuration Variable | Target Description |
| :--- | :--- |
| `input_folder` | Route pointing to `data_ready/` (Outputs from Step 1) |
| `output_drifters_file`| Filename path for the integrated output master `.parquet` file |
| `arctic_regions_file` | Location of the regional Arctic sector shapefile components (`.shp`) |

---

### 🛠️ Step 3 — Drifter Data Overview *(Optional)*
* **Target Script:** `new_drifter_data_overview.ipynb`
* **Core Action:** Synthesizes an Arctic polar projection plot highlighting historical tracking density. It serves as a visual diagnostic tool to check spatial sampling completeness before running heavy statistics.

---

### 🛠️ Step 4 — Spatiotemporal Grid Interpolation
* **Target Script:** `interpolate_models.py`
* **Core Action:** Loops over selected current products and temporal spans (default 2011–2021) to project model grids exactly onto the drifter tracks.
* **Interpolation Engines:**
  * **Regular Lat/Lon Meshes:** Efficient bilinear lookup utilizing `xarray.interp`.
  * **Curvilinear Complex Meshes:** Built-in `SciPy` Delaunay triangulation + linear interpolation with an automatic nearest-neighbor fallback routine for boundary pixels.

Run via command line:
```bash
python interpolate_models.py
```

#### 📦 MODEL_CONFIG Variable Requirements:
Each custom current database added to the execution loop dictionary requires these tags:
* `path` / `pattern`: Data lookup strings (e.g., `"**/*.nc"`).
* `u_name` / `v_name`: Variable identifiers within the NetCDF headers.
* `lon_type`: Longitude convention flag (`180` for $[-180, 180]$ ranges or `360` for $[0, 360]$ grids).
* `curvilinear`: Boolean toggle (`True` / `False`) to assign the required interpolation engine.

---

### 🛠️ Steps 5, 6 & 7 — Statistical Diagnostics & Metrics
Statistical evaluation is divided into three analytical scales:

* **Step 5 — `general_results_analysis.ipynb`:** Computes pan-Arctic baseline parameters. Generates multi-panel Taylor Diagrams, Kernel Density Estimations (KDE), and directional polar-rose vectorial RMSE configurations.
* **Step 6 — `regional_results_analysis.ipynb`:** Breaks down accuracy scores per sector (Barents, Fram, Beaufort, etc.), outputting automated performance comparative heatmaps and binned spatial maps.
* **Step 7 — `seasonal_results_analysis.ipynb`:** Groups accuracy indices by month and season to highlight cyclical model performance loss due to ice coverage or summer melt dynamics.

---

## 🏗️ Expected Directory Layout

```text
<data_root>/
├── in_situ_data/
│   ├── raw_data/
│   │   └── drifter_6hour_360lon.nc          ← Input: Raw GDP track file
│   ├── data_per_bouy/                       ← Created in Step 1
│   ├── data_filtered/                       ← Created in Step 1
│   ├── data_ready/                          ← Created in Step 1
│   └── drifters_merged.parquet              ← Created in Step 2
│
├── model_outputs/                           ← Created in Step 4
│   ├── ProductA_interpolated.parquet
│   └── ProductB_interpolated.parquet
│
└── results/                                 ← Created in Steps 5-7
    ├── taylor_diagram_speed.png
    └── regional_metrics_heatmap.png

<regions_data>/
└── arctic_regions.shp  (+ .dbf, .prj ...)   ← Input: Sector bounding files
```

---

## 💾 Input Data Assets

| Dataset Asset Name | Source Provider | Data Format | Target Pipeline Node |
| :--- | :--- | :--- | :--- |
| GDP 6-hourly drifter track logs | [Global Drifter Program](https://www.aoml.noaa.gov/phod/gdp/) | NetCDF | Step 1 Ingestion |
| Arctic Geopolitical Sector Boundaries | FRESH-CARE Project Internal Domain | Shapefile (`.shp`) | Step 2 Regionalization |
| Fused Surface Current Maps | Miscellaneous Providers (CMEMS / TOPAZ5 / Custom) | NetCDF (Daily) | Step 4 Grid Mapping |

---

## 🔌 Adding a New Current Product

To ingest a new candidate model dataset into the evaluation suite:
1. Open `interpolate_models.py`.
2. Append a new structured entry matching your dataset variables into the `MODEL_CONFIG` dictionary.
3. Execute Step 4 to generate the corresponding `{product}_interpolated.parquet` output structure.
4. The notebook analyzers (Steps 5–7) will dynamically discover and process the new asset once its filename is appended to the `files` list dictionary cell at the top of each notebook.

---

## 📦 Dependencies

| Package | Specific Purpose inside Workflow |
| :--- | :--- |
| `xarray` / `netCDF4` | High-level and low-level multi-dimensional array slicing and interpolation |
| `pandas` | Tabular parsing and high-speed data manipulation |
| `numpy` / `scipy` | Core vector calculations and digital Butterworth signal filtering |
| `geopandas` / `shapely` | Geometric processing and polygon intersection metrics |
| `cartopy` / `matplotlib` | Orthographic polar projections and scientific figure plotting |
| `skill_metrics` | Tailored computation of Taylor Diagram coordinate spaces |

---

## 👥 Authors & Credits
* **Code Architecture & Base Development:** Aleida Rosquete-Estévez.
* **Feature Expansion, Testing & Notebook Expansion:** Júlia Crespin.
