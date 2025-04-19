import requests
import datetime
import os
import pandas as pd
from bs4 import BeautifulSoup

# Konfiguration
API_KEY = os.environ.get("PLAUSIBLE_API_KEY")
SITE_ID = os.environ.get("PLAUSIBLE_SITE_ID")
API_URL = "https://plausible.io/api/v2/query"

# POST-Body:
payload = {
    "site_id": SITE_ID,
    "metrics": ["visitors"],
    "date_range": "30d",
    "property": "event:name",
    "limit": 1000
}

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

# Anfrage an Plausible API
print("Sende Anfrage an:", API_URL)
print("Mit Payload:", payload)

# POST
response = requests.post(API_URL, json=payload, headers=headers)
print("Status Code:", response.status_code)
print("Antwort:", response.text)

response.raise_for_status()
data = response.json()

print("Top Events aus Plausible:")
for r in data.get("results", []):
    print("-", r)

# Excel-Daten einlesen
events_df = pd.read_excel("events.xlsx")

# Nur zukünftige Events (Datum >= heute)
events_df = events_df[events_df["Datum"] >= pd.Timestamp.today().normalize()]

# Event-Namen in Excel-Datei bereinigen für robusten Vergleich
events_df["Event_clean"] = events_df["Event"].str.strip().str.lower()

# Hilfsfunktion zum Nachschlagen von Datum und Location anhand des Eventnamens
def get_event_info(name):
    name_clean = name.strip().lower()
    match = events_df[events_df["Event_clean"] == name_clean]
    if not match.empty:
        return {
            "date": match.iloc[0]["Datum"].strftime("%Y-%m-%d"),
            "location": match.iloc[0]["Location"]
        }
    return {"date": "-", "location": "-"}

top_events = sorted(data["results"], key=lambda x: x["visitors"], reverse=True)[:10]

event_details = {
    e["name"]: get_event_info(e["name"]) for e in top_events
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