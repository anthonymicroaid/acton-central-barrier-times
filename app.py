from flask import Flask, render_template
import requests
from datetime import datetime, timedelta, UTC
import os

app = Flask(__name__)

STATION_CODE = "910GACTNCTL"  # NaPTAN ID for Acton Central
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

def get_barrier_state(departures, current_time):
    if not departures:
        return None, None, None

    # Sort departures by closing time
    closings = []
    for dep in departures[:20]:
        departure_time_str = dep.get("expectedArrival", dep.get("timeToLive", None))
        if departure_time_str:
            closing_time = calculate_barrier_closing(departure_time_str)
            if closing_time:
                closings.append(closing_time)

    if not closings:
        return None, None, None

    closings.sort()
    next_closing = closings[0]
    last_opening = None

    # Check for overlapping trains (within 2 minutes) and calculate closed duration
    overlap_window = timedelta(minutes=2)  # Window for considering trains as overlapping
    base_closed_duration = timedelta(seconds=90)  # Base duration for a single train (90 seconds)
    max_closed_duration = timedelta(minutes=3)  # Maximum closed duration (3 minutes)
    overlap_count = 0

    for i in range(len(closings) - 1):
        if closings[i + 1] - closings[i] < overlap_window:
            overlap_count += 1
        else:
            break

    # Calculate closed duration: base + 30 seconds per overlapping train
    closed_duration = base_closed_duration + timedelta(seconds=30 * overlap_count)
    # Cap the closed duration at the maximum
    closed_duration = min(closed_duration, max_closed_duration)
    last_opening = next_closing + closed_duration

    # Determine current state
    if current_time >= next_closing and current_time < last_opening:
        return "closed", next_closing, last_opening
    return "open", next_closing, last_opening

@app.route('/')
def index():
    departures = get_departure_times()
    current_time = datetime.now(UTC)
    if departures is None:
        return render_template('index.html', upcoming=["Error fetching data from TfL API"], next_closing=None, next_opening=None, state=None)

    stratford_trains = []
    richmond_trains = []
    
    for departure in departures[:20]:
        destination = departure.get("destinationName", "Unknown").replace("(London) Rail Station", "").strip()
        departure_time_str = departure.get("expectedArrival", departure.get("timeToLive", None))
        if not departure_time_str:
            continue
        
        closing_time = calculate_barrier_closing(departure_time_str)
        if closing_time is None:
            continue

        if closing_time > current_time:
            local_time = closing_time
            closing_str = local_time.strftime("%H:%M")
            entry = (closing_time, f"Barrier closing for {destination} train: {closing_str}")
            if "Stratford" in destination:
                stratford_trains.append(entry)
            elif "Richmond" in destination:
                richmond_trains.append(entry)

    combined = []
    for i in range(2):
        if i < len(stratford_trains):
            combined.append(stratford_trains[i])
        if i < len(richmond_trains):
            combined.append(richmond_trains[i])

    combined.sort(key=lambda x: x[0])
    upcoming = [item[1] for item in combined[:3]]

    # Determine barrier state and times
    state, next_closing, next_opening = get_barrier_state(departures, current_time)
    next_closing = next_closing.isoformat() if next_closing else None
    next_opening = next_opening.isoformat() if next_opening else None

    if not upcoming:
        upcoming = ["No upcoming departures found."]
    return render_template('index.html', upcoming=upcoming, next_closing=next_closing, next_opening=next_opening, state=state)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))