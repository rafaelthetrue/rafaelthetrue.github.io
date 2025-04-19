import requests
import datetime
import os
from bs4 import BeautifulSoup

API_KEY = os.environ.get("PLAUSIBLE_API_KEY")
SITE_ID = os.environ.get("PLAUSIBLE_SITE_ID")
API_URL = "https://plausible.io/api/v1/stats/breakdown"

params = {
    "site_id": SITE_ID,
    "period": "30d",
    "property": "event:name",
    "filters": "event:name==event-klick"
}

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

print("Sende Anfrage an:", API_URL)
print("Mit Parametern:", params)

response = requests.get(API_URL, params=params, headers=headers)
print("Status Code:", response.status_code)
print("Antwort:", response.text)

response.raise_for_status()  # wird explizit Fehler werfen, wenn API-Fehler vorliegt
data = response.json()

# Top 10 Eventnamen holen
top_events = sorted(data["results"], key=lambda x: x["visitors"], reverse=True)[:10]

# Rohdaten für Datum + Location (aus event props)
event_details = {}
details_response = requests.get(
    "https://plausible.io/api/v1/stats/event-data",
    params={"site_id": SITE_ID, "event_name": "event-klick", "limit": 1000},
    headers=headers
)
if details_response.ok:
    for item in details_response.json().get("results", []):
        props = item["event"]["props"]
        event_name = props.get("name")
        if event_name in [e["name"] for e in top_events]:
            event_details[event_name] = {
                "date": props.get("date", "-"),
                "location": props.get("location", "-")
            }

# Neue Tabelle bauen
table_rows = ""
for i, e in enumerate(top_events, start=1):
    name = e["name"]
    props = event_details.get(name, {})
    date = props.get("date", "-")
    location = props.get("location", "-")
    table_rows += f"<tr><td>{i}</td><td>{date}</td><td>{name}</td><td>{location}</td></tr>\n"

table_html = f"""
<h3 style="text-align:center; font-weight:bold;">Top 10 meistgeklickte bevorstehende Events</h3>
<table style="margin: 10px auto 20px auto; border-collapse: collapse; text-align: left; max-width: 600px; width: 100%;">
<thead><tr><th>Platz</th><th>Datum</th><th>Event</th><th>Location</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
"""

# statistik.html öffnen und bearbeiten
with open("statistik.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

# Bestehende Top-Raves-Tabelle entfernen, falls vorhanden
for existing in soup.find_all("h3"):
    if "Top 10 meistgeklickte" in existing.text:
        next_table = existing.find_next("table")
        if next_table:
            next_table.decompose()
        existing.decompose()

# Neue Tabelle vor "Top 10 Städte" einfügen
for header in soup.find_all("h3"):
    if "Top 10 Städte" in header.text:
        header.insert_before(BeautifulSoup(table_html, "html.parser"))
        break

# Datei speichern
with open("statistik.html", "w", encoding="utf-8") as f:
    f.write(str(soup))