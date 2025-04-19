import requests
import datetime
import os
from bs4 import BeautifulSoup

# Konfiguration
API_KEY = os.environ.get("PLAUSIBLE_API_KEY")
SITE_ID = os.environ.get("PLAUSIBLE_SITE_ID")
API_URL = "https://plausible.io/api/v1/stats/breakdown"

params = {
    "site_id": SITE_ID,
    "period": "30d",
    "property": "event:name",
    "filters": "event:name==event-klick",
    "limit": 1000
}

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

# Anfrage an Plausible API
print("Sende Anfrage an:", API_URL)
print("Mit Parametern:", params)

response = requests.get(API_URL, params=params, headers=headers)
print("Status Code:", response.status_code)
print("Antwort:", response.text)

response.raise_for_status()
data = response.json()

top_events = sorted(data["results"], key=lambda x: x["visitors"], reverse=True)[:10]

# Zusätzliche Details abfragen
event_details = {}
details_url = "https://plausible.io/api/v1/stats/event-data"
details_params = {"site_id": SITE_ID, "event_name": "event-klick", "limit": 1000}
print("Frage Detaildaten ab:", details_url)
print("Mit Parametern:", details_params)

details_response = requests.get(details_url, params=details_params, headers=headers)
print("Detailantwort-Status:", details_response.status_code)
print("Detailantwort-Text:", details_response.text)
for item in details_response.json().get("results", []):
    props = item["event"].get("props", {})
    print("Event-Props gefunden:", props)  # <-- Logging!

    event_name = props.get("name")
    if event_name in [e["name"] for e in top_events]:
        event_details[event_name] = {
            "date": props.get("date", "-"),
            "location": props.get("location", "-")
        }
# Tabelle generieren
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

# statistik.html aktualisieren
with open("statistik.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

# Alte Tabelle entfernen
for existing in soup.find_all("h3"):
    if "Top 10 meistgeklickte" in existing.text:
        next_table = existing.find_next("table")
        if next_table:
            next_table.decompose()
        existing.decompose()

# Neue Tabelle vor „Top 10 Städte“ einfügen
for header in soup.find_all("h3"):
    if "Top 10 Städte" in header.text:
        header.insert_before(BeautifulSoup(table_html, "html.parser"))
        break

# Speichern
with open("statistik.html", "w", encoding="utf-8") as f:
    f.write(str(soup))