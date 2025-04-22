import requests
import os
import pandas as pd
from bs4 import BeautifulSoup

# Konfiguration
API_KEY = os.environ.get("PLAUSIBLE_API_KEY")
SITE_ID = os.environ.get("PLAUSIBLE_SITE_ID")
API_URL = "https://plausible.io/api/v1/stats/breakdown"

# Excel einlesen
events_df = pd.read_excel("events.xlsx")

# Nur zukünftige Events
events_df = events_df[events_df["Datum"] >= pd.Timestamp.today().normalize()]
events_df["Event_clean"] = events_df["Event"].str.strip().str.lower()

# API-Abfrage
from datetime import datetime, timedelta
start_date = (datetime.today() - timedelta(days=28)).strftime("%Y-%m-%d")
end_date = datetime.today().strftime("%Y-%m-%d")

payload = {
    "site_id": SITE_ID,
    "metrics": "visitors",
    "property": "event:props:name",
    "period": "custom",  # <--- wichtig
    "date": f"{start_date},{end_date}",
    "filters": "event:props:name!=null"
}

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

print("Sende Anfrage an:", API_URL)
response = requests.get(API_URL, headers=headers, params=payload)
print("Status Code:", response.status_code)
print("Antwort:", response.text)
response.raise_for_status()
data = response.json()

# Eventinfos ergänzen
def get_event_info(name):
    name_clean = name.strip().lower()
    match = events_df[events_df["Event_clean"] == name_clean]
    if not match.empty:
        return {
            "date": match.iloc[0]["Datum"].strftime("%Y-%m-%d"),
            "location": match.iloc[0]["Location"]
        }
    return {"date": "-", "location": "-"}

# Eventinfos vorbereiten
def is_upcoming(event):
    info = get_event_info(event["name"])
    if info["date"] == "-":
        return False
    event_date = datetime.strptime(info["date"], "%Y-%m-%d")
    return event_date >= datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

# Nur zukünftige Events berücksichtigen und sortieren
filtered_events = [
    e for e in data["results"]
    if e["name"] != "(none)" and is_upcoming(e)
]

# Sortieren nach Besucherzahl, dann Top 10 nehmen
top_events = sorted(filtered_events, key=lambda x: x["visitors"], reverse=True)[:10]

event_details = {e["name"]: get_event_info(e["name"]) for e in top_events}

# HTML-Tabelle
table_rows = ""
for i, e in enumerate(top_events, start=1):
    name = e["name"]
    props = event_details.get(name, {})

    date_obj = datetime.strptime(props["date"], "%Y-%m-%d") if props["date"] != "-" else None
    if date_obj:
        formatted_date = date_obj.strftime("%d.%m")
        weekday_short = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]
        weekday = weekday_short[date_obj.weekday()]
        date_html = f'{formatted_date}<br><span>{weekday}</span>'
    else:
        date_html = "-"

    location = props["location"]
    table_rows += f"<tr><td>{i}.</td><td class='date-cell'>{date_html}</td><td>{name}</td><td>{location}</td></tr>\n"

table_html = f"""
<h2 style="text-align:center; font-weight:bold;">
  Top 10 Raves
  <span class="info-container" onclick="toggleInfoPopup(event)" style="cursor:pointer; margin-left:8px;">
    <span class="info-icon" style="display:inline-block; width:16px; height:16px; border:1px solid #666; border-radius:50%; text-align:center; font-size:12px; line-height:16px; color:#666;">i</span>
  </span>
</h2>
<div id="info-popup" class="info-popup" style="display:none; margin-bottom:15px; font-size:13px; color:#333; background:#f9f9f9; padding:10px; border:1px solid #ccc; border-radius:6px;">
  Die Top 10 Raves werden durch unsere Besucher und ihre Klicks auf ravebro.de bestimmt. Die Liste wird zweimal täglich aktualisiert (7 & 19 Uhr).
</div>
<table>
<thead><tr><th>Platz</th><th>Datum</th><th>Event</th><th>Location</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
"""

# statistik.html aktualisieren
with open("statistik.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

# Alte Tabelle entfernen (falls vorhanden)
for header in soup.find_all(["h2", "h3"]):
    if "Top 10 Raves" in header.text:
        table = header.find_next("table")
        if table:
            table.decompose()
        header.decompose()
        break

for header in soup.find_all(["h2", "h3"]):
    if "Top 10 Städte" in header.text:
        header.insert_before(BeautifulSoup(table_html, "html.parser"))
        break

new_content = str(soup)

# Bestehenden Dateiinhalt lesen
with open("statistik.html", "r", encoding="utf-8") as f:
    old_content = f.read()

# Nur überschreiben, wenn sich etwas geändert hat
if new_content != old_content:
    with open("statistik.html", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Datei aktualisiert.")
else:
    print("Keine Änderung in statistik.html.")