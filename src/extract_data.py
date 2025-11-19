import os
import time
import json            # IMPORT LIBRARIES
import sqlite3
import requests
import math
from datetime import datetime, timezone
from pathlib import Path
from shapely.geometry import Point, shape
from shapely.ops import nearest_points

ENABLE_DEBUG = os.getenv("ENABLE_DEBUG", "0") == "1"

API_KEY = os.getenv("CTA_TRAIN_API_KEY") # FETCH API KEY 
if not API_KEY:
    raise SystemExit("CTA_TRAIN_API_KEY is not set. Example (PowerShell): $env:CTA_TRAIN_API_KEY='YOUR_KEY'")

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "30")) # HOW OFTEN TO REQUEST FROM API
DB_PATH = "cta_trains.db"

BASE_URL = "https://lapi.transitchicago.com/api/1.0/ttpositions.aspx"

ROUTES = { # MAPPING OF ALL ROUTES
    "Red":  "red",
    "Blue": "blue",
    "Brn":  "brn",
    "G":    "g",
    "Org":  "org",
    "P":    "p",
    "Pink": "pink",
    "Y":    "y",
}

# Fixing the problem of train veering off the route
# --- Load GeoJSON ---
GEOJSON_PATH = Path("cta_routes.geojson")
if not GEOJSON_PATH.exists():
    raise SystemExit(f"GeoJSON file not found at {GEOJSON_PATH}. Download from City of Chicago Data Portal.")

with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# make geojson route names correpond with our route names
NAME_MAP = {
    "Red": "red",
    "Blue": "blue",
    "Brown": "brn",
    "Green": "g",
    "Orange": "org",
    "Purple": "p",
    "Pink": "pink",
    "Yellow": "y"
}


route_geometries = {short: None for short in NAME_MAP.values()}

for feature in geojson_data.get("features", []):
    props = feature.get("properties", {})
    lines = props.get("lines", "")
    geom = shape(feature.get("geometry"))
    if lines and geom:
        for route_name in lines.split(","):
            route_name = route_name.strip()
            short_name = NAME_MAP.get(route_name)
            if short_name:
                if route_geometries[short_name] is None:
                    route_geometries[short_name] = geom
                else:
                    route_geometries[short_name] = route_geometries[short_name].union(geom)


for k,v in route_geometries.items():
    print(f"[DEBUG] Route {k}: geometry type={v.geom_type if v else 'None'}")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc         TEXT    NOT NULL,   -- ISO timestamp when we polled
    rn             TEXT,               -- run number (train ID)
    next_station   TEXT,               -- Next station name
    lat            REAL,
    lon            REAL,
    heading        INTEGER,            -- degrees (0-359)
    arriving_now   INTEGER,            -- 1/0
    delayed        INTEGER             -- 1/0
);
-- (Optional) Make (ts_utc, rn) unique to avoid duplicates if you re-run inserts
CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_ts_rn ON {table}(ts_utc, rn);
"""

def ensure_db(conn: sqlite3.Connection): # CONNECT TO THE DB AND CREATE THE TABLES
    with conn:
        for t in ROUTES.values():
            conn.executescript(SCHEMA_SQL.format(table=t))


# --- Filtering & Snapping ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def filter_and_snap(route_code: str, lat: float, lon: float):
    geoms = route_geometries.get(route_code.lower())
    if not geoms:
        #original coordinate 
        return lat, lon

    point = Point(lon, lat)
    buffer_distance = 0.0003  # ~3m
    closest_geom = None
    min_distance = float("inf")

    if geoms.geom_type == "MultiLineString":
        for line in geoms.geoms:
            dist = point.distance(line)
            if dist < min_distance:
                min_distance = dist
                closest_geom = line
    else:
        closest_geom = geoms
        min_distance = point.distance(geoms)

    if min_distance <= buffer_distance:
        return lat, lon

    nearest_point = closest_geom.interpolate(closest_geom.project(point))
    return nearest_point.y, nearest_point.x


def fetch_route_positions(route_code: str) -> list[dict]: # FETCH THE DATA
    """Fetch live positions for a single CTA route; returns normalized dicts."""
    params = {"key": API_KEY, "rt": route_code, "outputType": "JSON"}
    r = requests.get(BASE_URL, params=params, timeout=12)
    r.raise_for_status()
    ct = r.headers.get("Content-Type", "").lower()
    if "json" not in ct:
        # Not JSON? print head to help debug and return empty
        print(f"[{route_code}] Unexpected content-type={ct}")
        print(r.text[:300])
        return []

    data = r.json()
    ctatt = data.get("ctatt", {})
    if ctatt.get("errCd") not in (None, "0"):
        print(f"[{route_code}] CTA error {ctatt.get('errCd')}: {ctatt.get('errNm')}")
        return []

    out = []
    
    for block in ctatt.get("route", []):
        for t in block.get("train", []) or []:
            try:
                lat = float(t["lat"]) if t.get("lat") else None
                lon = float(t["lon"]) if t.get("lon") else None
                print(f"[DEBUG] Raw: route={route_code}, rn={t.get('rn')}, lat={lat}, lon={lon}, heading={t.get('heading')}")

                # snap for lat and lon
                if lat and lon:
                    lat, lon = filter_and_snap(route_code, lat, lon)
                
                if ENABLE_DEBUG:
                    print(f"[DEBUG] After snap: lat={lat}, lon={lon}")

                out.append({
                    "rn": t.get("rn"),
                    "next_station": t.get("nextStaNm"),
                    "lat": lat,
                    "lon": lon,
                    "heading": int(t["heading"]) if t.get("heading") else None,
                    "arriving_now": 1 if t.get("isApp") == "1" else 0,
                    "delayed": 1 if t.get("isDly") == "1" else 0,
                })
            except (ValueError, TypeError):
                continue
    return out

 
def insert_snapshot(conn: sqlite3.Connection, table: str, ts_iso: str, rows: list[dict]):
    if not rows:                     # STICK DATA IN DATABASE
        return
    sql = f"""
        INSERT OR IGNORE INTO {table}
        (ts_utc, rn, next_station, lat, lon, heading, arriving_now, delayed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    vals = [
        (
            ts_iso,
            r.get("rn"),
            r.get("next_station"),
            r.get("lat"),
            r.get("lon"),
            r.get("heading"),
            r.get("arriving_now"),
            r.get("delayed"),
        )
        for r in rows
    ]
    with conn:
        conn.executemany(sql, vals)

def main(): # MAIN FUNCTION TO PULL DATA EVERY LOOP AND POPULATE DATABASE UNTIL INTERUPTED
    print(f"Writing to SQLite DB: {DB_PATH}")
    print(f"Polling every {POLL_SECONDS}s. Press Ctrl+C to stop.")
    conn = sqlite3.connect(DB_PATH)
    ensure_db(conn)

    try:
        while True:
            ts_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
            total = 0
            for rt_code, table in ROUTES.items():
                try:
                    rows = fetch_route_positions(rt_code)
                    insert_snapshot(conn, table, ts_iso, rows)
                    print(f"[{ts_iso}] {rt_code:<4} -> {len(rows):2d} rows")
                    total += len(rows)
                    time.sleep(0.2)  # tiny pause between routes (be polite)
                except requests.RequestException as e:
                    print(f"[{rt_code}] request failed: {e}")
            print(f"[{ts_iso}] snapshot complete: {total} trains total\n")
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
