
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from math import radians, sin, cos, sqrt, atan2

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # one level up from scripts/
DB_PATH = PROJECT_ROOT / "cta_trains.db"
PLOT_DIR = PROJECT_ROOT / "assets" / "eda_plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

ROUTE_TABLES = ["red", "blue", "brn", "g", "org", "p", "pink", "y"]

# --- Haversine function (meters) ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

# --- Connect to DB ---
if not DB_PATH.exists():
    raise FileNotFoundError(f"Database not found at {DB_PATH}")

conn = sqlite3.connect(str(DB_PATH))

summary_stats = {}
speed_data = {}

for table in ROUTE_TABLES:
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    if df.empty:
        continue

    # Convert timestamp
    df['ts_utc'] = pd.to_datetime(df['ts_utc'])

    # --- Basic Info ---
    summary_stats[table] = {
        "rows": len(df),
        "missing_lat": df['lat'].isnull().sum(),
        "missing_lon": df['lon'].isnull().sum()
    }

    # --- Plot timestamp distribution ---
    plt.figure(figsize=(10, 4))
    df['ts_utc'].hist(bins=50)
    plt.title(f"Timestamp Distribution - {table.capitalize()} Line")
    plt.xlabel("Time")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(PLOT_DIR / f"{table}_timestamp_distribution.png")
    plt.close()

    # --- Plot lat/lon scatter ---
    plt.figure(figsize=(6, 6))
    sns.scatterplot(x=df['lon'], y=df['lat'], alpha=0.5)
    plt.title(f"Train Positions - {table.capitalize()} Line")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.tight_layout()
    plt.savefig(PLOT_DIR / f"{table}_positions.png")
    plt.close()

    # --- Compute speeds ---
    df = df.sort_values(['rn', 'ts_utc'])
    speeds = []
    for rn, group in df.groupby('rn'):
        lat_prev, lon_prev, t_prev = None, None, None
        for _, row in group.iterrows():
            if lat_prev is not None and lon_prev is not None:
                dist_m = haversine(lat_prev, lon_prev, row['lat'], row['lon'])
                dt = (row['ts_utc'] - t_prev).total_seconds()
                if dt > 0 and dist_m > 1:
                    speed_mps = dist_m / dt
                    speeds.append(speed_mps * 3.6)  # km/h
            lat_prev, lon_prev, t_prev = row['lat'], row['lon'], row['ts_utc']

    if speeds:
        speed_data[table] = speeds

conn.close()

# --- Multi-route speed distribution plot ---
num_routes = len(speed_data)
cols = 2
rows = (num_routes + 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(12, rows * 4))
axes = axes.flatten()

for i, (route, speeds) in enumerate(speed_data.items()):
    sns.histplot(speeds, bins=40, kde=True, ax=axes[i])
    axes[i].set_title(f"{route.capitalize()} Line Speed Distribution")
    axes[i].set_xlabel("Speed (km/h)")
    axes[i].set_ylabel("Frequency")

for j in range(i+1, len(axes)):
    axes[j].axis('off')

plt.tight_layout()
plt.savefig(PLOT_DIR / "all_routes_speed_distribution.png")
plt.close()

# --- Print summary stats ---
print("Summary Stats:")
for route, stats in summary_stats.items():
    print(f"{route.capitalize()} Line: Rows={stats['rows']}, Missing lat={stats['missing_lat']}, Missing lon={stats['missing_lon']}")

print("\nSpeed Stats:")
for route, speeds in speed_data.items():
    print(f"{route.capitalize()} Line: Avg={np.mean(speeds):.2f} km/h, Max={np.max(speeds):.2f} km/h")

print(f"\nEDA plots saved to: {PLOT_DIR}")

