from flask import Flask, render_template
import requests
from datetime import datetime, timedelta, UTC
import os

app = Flask(__name__)

STATION_CODE = "910GACTNCTL"
API_URL = f"https://api.tfl.gov.uk/StopPoint/{STATION_CODE}/Arrivals"

def get_departure_times():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException:
        return None

def calculate_barrier_closing(departure_time_str):
    if departure_time_str:
        departure_time = datetime.fromisoformat(departure_time_str.replace("Z", "+00:00"))
        closing_time = departure_time - timedelta(minutes=2)
        return closing_time
    return None

@app.route('/')
def index():
    departures = get_departure_times()
    current_time = datetime.now(UTC)
    if departures is None:
        return render_template('index.html', upcoming=["Error fetching data from TfL API"])

    stratford_trains = []
    richmond_trains = []
    
    for departure in departures[:20]:
        destination = departure.get("destinationName", "Unknown")
        departure_time_str = departure.get("expectedArrival", departure.get("timeToLive", None))
        if not departure_time_str:
            continue
        
        closing_time = calculate_barrier_closing(departure_time_str)
        if closing_time is None:
            continue
        time_until_closing = (closing_time - current_time).total_seconds() / 60

        if time_until_closing > 0:
            local_time = closing_time  # GMT/UTC+0 for March 12, 2025
            closing_str = local_time.strftime("%H:%M")
            entry = (closing_time, f"To {destination}: {closing_str} ({int(time_until_closing)} mins)")
            if "Stratford" in destination:
                stratford_trains.append(entry)
            elif "Richmond" in destination:
                richmond_trains.append(entry)

    combined = []
    for i in range(5):
        if i < len(stratford_trains):
            combined.append(stratford_trains[i])
        if i < len(richmond_trains):
            combined.append(richmond_trains[i])

    combined.sort(key=lambda x: x[0])
    upcoming = [item[1] for item in combined]

    if not upcoming:
        upcoming = ["No upcoming departures found."]
    return render_template('index.html', upcoming=upcoming)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))