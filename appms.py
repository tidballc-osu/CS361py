# Author: Christopher Tidball
# Date: 8/17/23
# Description: Fetches flight data by calling flightAware API and weather data by calling Hana's
# weather microservice

import os
import requests
import geopy
import geopy.distance
import json
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

load_dotenv()

app = Flask(__name__)
URL = "https://weather-microservice.onrender.com/weather"
API_URL = "https://aeroapi.flightaware.com/aeroapi/"
auth_header = {'x-apikey': os.getenv('APIKEY')}

def get_bounding_box(lat, lon, rad) -> (str, str, str, str):
    """Takes a single location and radius and returns a box (needed for flight search API)"""
    start = geopy.Point(lat, lon)
    d = geopy.distance.distance(miles=rad)

    # Calculate the two corners then use those to get all for corners
    bounding_point_ne = d.destination(point=start, bearing=45)
    bounding_point_sw = d.destination(point=start, bearing=225)
    lat_max = str(round(bounding_point_ne.latitude, 6))
    lat_min = str(round(bounding_point_sw.latitude, 6))
    lon_max = str(round(bounding_point_ne.longitude, 6))
    lon_min = str(round(bounding_point_sw.longitude, 6))
    return lat_min, lat_max, lon_min, lon_max

def get_flights_in_area(bounding_box) -> object:
    """Takes a box (coordinates) and fetches an array of flights in the box"""
    query = "{range lat " + bounding_box[0] + " " + bounding_box[1] + "} {range lon " + bounding_box[2] + " " + \
            bounding_box[3] + "} {true inAir}"
    payload = {'query': query, 'howMany': 10, 'offset': 0}
    response = requests.get(API_URL + f"flights/search/advanced", params=payload, headers=auth_header)
    response.raise_for_status()
    flight_data = response.json()
    if response.status_code != 200:
        print('Error with flight API')
        return []
    return flight_data

def truncate_flight_data(flight):
    """Takes flight object and returns truncated format and appends weather api data"""
    return {
        "ident": flight['ident'],
        "aircraft_type": flight['aircraft_type'],
        "origin_city": flight['origin']['city'],
        "origin_code": flight['origin']['code_iata'],
        "origin_name": flight['origin']['name'],
        "destination_city": flight['destination']['city'],
        "destination_code": flight['destination']['code_iata'],
        "destination_name": flight['destination']['name'],
        "weather": get_weather('33.6541267', '-84.4171372') # Fetch weather from API
    }

def get_weather(lat, lon):
    # Fetch weather object from microservice
    try:
        # Make API call to Weather API to fetch weather data
        params = {
            'latitude': lat,
            'longitude': lon
        }
        response = requests.get(URL, params=params)
        response.raise_for_status()
        weather_data = response.json()
        return weather_data['weather_description']

    except requests.exceptions.RequestException as e:
        print(e)
        return jsonify({"error": "Error fetching flight data.", "status_code": 500}), 500
    except KeyError:
        return jsonify({"error": "Invalid response from flight API.", "status_code": 500}), 500

@app.route('/flights', methods=['GET'])
@cross_origin()
def get_data():
    # Get latitude and longitude from query parameters
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    # Create area to search
    bounding_box = get_bounding_box(float(lat), float(lon), int(5))

    # Fetch flights overhead
    flight_data = get_flights_in_area(bounding_box)

    # Only return the data we need
    flights = flight_data['flights']
    truncated_flight_data = map(truncate_flight_data, flight_data['flights'])
    truncated_flight_list = list(truncated_flight_data)
    truncated_flight_json = json.dumps(truncated_flight_list)

    # Handle errors
    if not lat or not lon:
        return jsonify({"error": "Latitude and longitude are required parameters.", "status_code": 400}), 400

    return truncated_flight_json, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

# Testing:
# Using web browser: http://localhost:5000/weather?latitude=37.7749&longitude=-122.4194
# Example of San Francisco ^
