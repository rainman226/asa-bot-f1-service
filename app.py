from flask import Flask, request, jsonify
import requests
import sqlite3
from datetime import datetime
import pytz
from dateutil import parser
import os

app = Flask(__name__)

# Jolpicabase URL
JOLPICA_API = "http://api.jolpi.ca/ergast/f1/"

# Initialize database
def init_db():
    conn = sqlite3.connect('timezones.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS server_timezones 
                 (server_id TEXT PRIMARY KEY, timezone TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Function to get timezone for a server
def get_server_timezone(server_id):
    conn = sqlite3.connect('timezones.db')
    c = conn.cursor()
    c.execute("SELECT timezone FROM server_timezones WHERE server_id = ?", (server_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "UTC"  # Default to UTC if not set

# GET /next-race?server_id=...
@app.route('/next-race', methods=['GET'])
def get_next_race():
    server_id = request.args.get('server_id')
    if not server_id:
        return jsonify({"error": "server_id is required"}), 400

    # Fetch current season's schedule
    try:
        response = requests.get(f"{JOLPICA_API}current.json")
        response.raise_for_status()
        data = response.json()
        races = data['MRData']['RaceTable']['Races']
    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch race schedule from Jolpica API"}), 500

    # Find the next race
    now = datetime.now(pytz.UTC)
    next_race = None
    for race in races:
        race_date = parser.parse(f"{race['date']} {race['time']}")
        if race_date > now:
            next_race = race
            break

    if not next_race:
        return jsonify({"error": "No upcoming races found"}), 404

    # Get server's timezone
    server_tz = pytz.timezone(get_server_timezone(server_id))

    # Helper function to convert date and time to server's timezone
    def format_datetime(date_str, time_str):
        if not date_str or not time_str:
            return None
        dt = parser.parse(f"{date_str} {time_str}")
        dt_local = dt.astimezone(server_tz)
        return {
            "date": dt_local.strftime("%Y-%m-%d"),
            "time": dt_local.strftime("%H:%M:%S %Z")
        }

    # Extract and format race weekend schedule
    race_info = {
        "race_name": next_race['raceName'],
        "race": format_datetime(next_race['date'], next_race['time']),
        "fp1": format_datetime(
            next_race.get('FirstPractice', {}).get('date'),
            next_race.get('FirstPractice', {}).get('time')
        ),
        "fp2": format_datetime(
            next_race.get('SecondPractice', {}).get('date'),
            next_race.get('SecondPractice', {}).get('time')
        ),
        "fp3": format_datetime(
            next_race.get('ThirdPractice', {}).get('date'),
            next_race.get('ThirdPractice', {}).get('time')
        ),
        "qualifying": format_datetime(
            next_race.get('Qualifying', {}).get('date'),
            next_race.get('Qualifying', {}).get('time')
        )
    }

    # Remove None values (e.g., if a session like FP3 is missing for sprint weekends)
    race_info = {k: v for k, v in race_info.items() if v is not None}

    return jsonify(race_info)

# GET /latest-result
@app.route('/latest-result', methods=['GET'])
def get_latest_result():
    # Fetch the latest race result
    try:
        response = requests.get(f"{JOLPICA_API}current/last/results.json")
        response.raise_for_status()
        data = response.json()
        results = data['MRData']['RaceTable']['Races'][0]['Results']
    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch race results from Jolpica API"}), 500
    except IndexError:
        return jsonify({"error": "No race results found"}), 404

    # Prepare simplified ranking (position and driver name)
    ranking = [
        {
            "position": result['position'],
            "driver": f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
        }
        for result in results
    ]
    return jsonify({"ranking": ranking})

# POST /set-timezone
@app.route('/set-timezone', methods=['POST'])
def set_timezone():
    data = request.get_json()
    server_id = data.get('server_id')
    timezone = data.get('timezone')

    if not server_id or not timezone:
        return jsonify({"error": "server_id and timezone are required"}), 400

    # Validate timezone
    try:
        pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        return jsonify({"error": "Invalid timezone"}), 400

    # Store or update timezone in database
    conn = sqlite3.connect('timezones.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO server_timezones (server_id, timezone) VALUES (?, ?)",
              (server_id, timezone))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Timezone set to {timezone} for server {server_id}"})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))  # Use PORT env variable, default to 5000
    app.run(debug=True, host='0.0.0.0', port=port)