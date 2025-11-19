import json
from pathlib import Path
import geopandas as gpd

REPO_ROOT = Path(__file__).resolve().parents[1]
SHAPE_PATH = REPO_ROOT / "shape_files" / "CTA_RailLines.shp"
OUT_PATH = REPO_ROOT / "cta_routes.json"

# Exact mapping from LEGEND code -> route key
LEGEND_TO_ROUTE = {
    "RD": "red",
    "BL": "blue",
    "BR": "brn",
    "GR": "g",
    "OR": "org",
    "PR": "p",      # Purple
    "PK": "pink",
    "YL": "y",      # Yellow
}

def main():
    print(f"Reading shapefile: {SHAPE_PATH}")
    gdf = gpd.read_file(SHAPE_PATH)

    print("Columns:", list(gdf.columns))
    print("Unique LEGEND values:", gdf["LEGEND"].dropna().unique())

    # Reproject to WGS84 for Leaflet
    gdf = gdf.to_crs(epsg=4326)

    routes = {v: [] for v in LEGEND_TO_ROUTE.values()}

    for _, row in gdf.iterrows():
        legend = (row.get("LEGEND") or "").strip().upper()
        route = LEGEND_TO_ROUTE.get(legend)
        if not route:
            continue

        geom = row.geometry
        if geom is None:
            continue

        if geom.geom_type == "LineString":
            coords = [(pt[1], pt[0]) for pt in geom.coords]  # (lat, lon)
            routes[route].append(coords)
        elif geom.geom_type == "MultiLineString":
            for line in geom.geoms:
                coords = [(pt[1], pt[0]) for pt in line.coords]
                routes[route].append(coords)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(routes, f)

    for r, segs in routes.items():
        print(f"{r}: {len(segs)} segments")

    print(f"Wrote routes JSON to: {OUT_PATH.resolve()}")

if __name__ == "__main__":
    main()
