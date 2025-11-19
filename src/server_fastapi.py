from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import sqlite3
import pandas as pd

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # repo root (one up from src/)
INDEX_HTML = PROJECT_ROOT / "index.html"
DB_PATH = Path(os.getenv("CTA_DB_PATH", PROJECT_ROOT / "cta_trains.db"))

# Only the tables we actually wrote in the logger
ROUTE_TABLES = {"red", "blue", "brn", "g", "org", "p", "pink", "y"}

app = FastAPI()

# Serve static files (index.html, etc.) from the project root
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT)), name="static")


@app.get("/")
def root():
    # Serve the map page
    if not INDEX_HTML.exists():
        # Helpful message if index.html is missing
        return JSONResponse(
            {"error": f"index.html not found at {INDEX_HTML}. Put your map HTML there."}, status_code=500
        )
    return FileResponse(str(INDEX_HTML))

@app.get("/cta_routes.json")
async def get_cta_routes():
    # cta_routes.json is in the same directory as index.html inside the image (/app)
    return FileResponse("cta_routes.json", media_type="application/json")


@app.get("/latest")
def latest():
    # Return latest snapshot rows across all existing route tables
    if not DB_PATH.exists():
        return JSONResponse([], status_code=200)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # Only keep tables we expect (avoid 'sqlite_sequence' and others)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        have = {r[0] for r in rows}
        tables = sorted(ROUTE_TABLES & have)
        if not tables:
            return JSONResponse([], status_code=200)

        frames = []
        for t in tables:
            # Skip empty tables (MAX(ts_utc) is NULL)
            max_ts = conn.execute(f"SELECT MAX(ts_utc) FROM {t}").fetchone()[0]
            if not max_ts:
                continue
            df = pd.read_sql_query(
                f"SELECT * FROM {t} WHERE ts_utc = ?", conn, params=(max_ts,)
            )
            if not df.empty:
                df["route"] = t
                frames.append(df)

        if not frames:
            return JSONResponse([], status_code=200)

        out = pd.concat(frames, ignore_index=True)
        # SQLite types might be ints 0/1; JSONify cleanly
        records = out.to_dict(orient="records")
        return JSONResponse(records)
    finally:
        conn.close()
