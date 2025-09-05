import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta

import requests
import pandas as pd

API_KEY = os.environ.get("PLAUSIBLE_API_KEY")
SITE_ID = os.environ.get("PLAUSIBLE_SITE_ID")
API_URL = "https://plausible.io/api/v1/stats/breakdown"

STAT_PATH = Path("statistik.html")
START_MARK = "<!-- AUTO:TOP10-RAVES:START -->"
END_MARK   = "<!-- AUTO:TOP10-RAVES:END -->"

# ---------- Helpers ----------

def pick(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None

def read_events(path="events.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)

    col_date  = pick(df.columns, ["Datum","Date","date"])
    col_event = pick(df.columns, ["Event","Name","event"])
    col_loc   = pick(df.columns, ["Location","Locations","Venue","Ort/Location","Club","Location(s)"])

    if not col_date or not col_event:
        raise SystemExit("Spalten 'Datum'/'Event' nicht gefunden (auch nicht in Alternativen).")

    # Datum robust parsen
    df[col_date] = pd.to_datetime(df[col_date], errors="coerce", dayfirst=True)
    df = df.dropna(subset=[col_date, col_event]).copy()

    # Nur heute/ Zukunft
    today0 = pd.Timestamp.today().normalize()
    df = df[df[col_date] >= today0].copy()

    # Normalisierte Eventnamen
    df["Event_clean"] = df[col_event].astype(str).str.strip().str.lower()

    # Vereinheitlichte Spaltennamen
    df = df.rename(columns={col_date: "Datum", col_event: "Event"})
    if col_loc:
        df = df.rename(columns={col_loc: "Location"})
    else:
        df["Location"] = "-"

    return df[["Datum","Event","Event_clean","Location"]]

def weekday_short(dt: datetime) -> str:
    return ["Mo.","Di.","Mi.","Do.","Fr.","Sa.","So."][dt.weekday()]

def fetch_plausible(site_id: str, api_key: str, days:int=7):
    start_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    end_date   = datetime.utcnow().date().isoformat()
    params = {
        "site_id": site_id,
        "metrics": "visitors",
        "property": "event:props:name",
        "period": "custom",
        "date": f"{start_date},{end_date}",
        "filters": "event:props:name!=null"
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(API_URL, headers=headers, params=params, timeout=30)
    print("GET", r.url)
    print("Status:", r.status_code)
    print("Preview:", r.text[:300])
    r.raise_for_status()
    return r.json().get("results", [])

def build_table_html(top_rows):
    rows_html = []
    for i, row in enumerate(top_rows, start=1):
        date_html = row["date_html"]
        name = row["name"]
        loc = row.get("location","-")
        rows_html.append(
            f"<tr><td>{i}.</td><td class='date-cell'>{date_html}</td><td>{name}</td><td>{loc}</td></tr>"
        )

    table = f"""
<h2 style="text-align:center; font-weight:bold;">
  Top 10 Raves
  <span class="info-container" onclick="toggleInfoPopup(event)" style="cursor:pointer; margin-left:8px;">
    <span class="info-icon">i</span>
  </span>
</h2>
<div id="info-popup" class="info-popup" style="display:none; margin-bottom:15px; font-size:13px; color:#333; background:#f9f9f9; padding:10px; border:1px solid #ccc; border-radius:6px;">
  Die Top 10 Raves werden durch unsere Besucher und ihre Klicks auf ravebro.de bestimmt. Die Liste wird zweimal täglich aktualisiert (7 &amp; 19 Uhr).
</div>
<table>
  <thead><tr><th>Platz</th><th>Datum</th><th>Event</th><th>Location</th></tr></thead>
  <tbody>
    {chr(10).join(rows_html)}
  </tbody>
</table>
""".strip()
    return table

def inject_between_markers(src: str, start_mark: str, end_mark: str, payload_html: str) -> str:
    start_idx = src.find(start_mark)
    end_idx   = src.find(end_mark)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        raise SystemExit("Marker nicht gefunden oder Reihenfolge fehlerhaft in statistik.html")
    before = src[: start_idx + len(start_mark)]
    after  = src[end_idx:]
    return before + "\n" + payload_html + "\n" + after

# ---------- Main ----------

def main():
    if not API_KEY or not SITE_ID:
        raise SystemExit("PLAUSIBLE_API_KEY / PLAUSIBLE_SITE_ID nicht gesetzt.")

    events = read_events("events.xlsx")

    # Map: name_clean -> Liste kommender Termine (falls mehrere)
    event_map = {}
    for _, r in events.iterrows():
        key = r["Event_clean"]
        event_map.setdefault(key, []).append({"date": r["Datum"].to_pydatetime(), "location": r["Location"]})

    # Plausible lesen
    results = fetch_plausible(SITE_ID, API_KEY, days=7)

    today0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    seen = set()
    upcoming = []

    for e in results:
        name = e.get("name")
        visitors = e.get("visitors", 0)
        if not name or name == "(none)":
            continue

        key = name.strip().lower()
        infos = event_map.get(key, [])
        if not infos:
            continue

        # Nächster zukünftiger Termin nehmen
        future_infos = [i for i in infos if i["date"] >= today0]
        if not future_infos:
            continue
        info = sorted(future_infos, key=lambda x: x["date"])[0]
        dt = info["date"]

        # Duplicate gleicher Eventname vermeiden
        if key in seen:
            continue
        seen.add(key)

        upcoming.append({
            "name": name,
            "visitors": visitors,
            "date": dt,
            "date_html": f"{dt:%d.%m}<br><span>{weekday_short(dt)}</span>",
            "location": info["location"] or "-",
        })

    # Top 10 nach visitors
    upcoming.sort(key=lambda x: x["visitors"], reverse=True)
    top10 = upcoming[:10]

    block_html = build_table_html(top10)

    src = STAT_PATH.read_text(encoding="utf-8")
    new_src = inject_between_markers(src, START_MARK, END_MARK, block_html)

    if new_src != src:
        STAT_PATH.write_text(new_src, encoding="utf-8")
        print("statistik.html aktualisiert.")
    else:
        print("Keine Änderung in statistik.html.")

if __name__ == "__main__":
    main()