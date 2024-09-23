import requests
import streamlit as st
from datetime import datetime
import polyline

# Your access token
access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5ZWQ1YjMyNTZiNzExMDdjNGFiMjkxNGU3N2U0Y2Y3NyIsImlzcyI6Imh0dHA6Ly9pbnRlcm5hbC1hbGItb20tcHJkZXppdC1pdC0xMjIzNjk4OTkyLmFwLXNvdXRoZWFzdC0xLmVsYi5hbWF6b25hd3MuY29tL2FwaS92Mi91c2VyL3Bhc3N3b3JkIiwiaWF0IjoxNzI3MDUzODk5LCJleHAiOjE3MjczMTMwOTksIm5iZiI6MTcyNzA1Mzg5OSwianRpIjoiMFFoNXJaNTdFUHN0UndVayIsInVzZXJfaWQiOjQ2OTksImZvcmV2ZXIiOmZhbHNlfQ.z32Q5Ys1Q5Rn5VPbu1bVBkFMsqQ1IeD63FJzEyleKbY"  # Replace this with your actual OneMap token

def refresh_access_token():
    # Replace this with your logic to obtain a new access token
    return "your_new_access_token"

def token_needs_refreshing():
    # Implement your logic to check if the token is nearing expiry
    return False  # Placeholder; implement actual check based on token expiry

def check_and_refresh_token():
    global access_token
    if token_needs_refreshing():
        access_token = refresh_access_token()

def get_latlon_from_postal(postal_code):
    url = "https://www.onemap.gov.sg/api/common/elastic/search"
    params = {
        "searchVal": postal_code,
        "returnGeom": "Y",
        "getAddrDetails": "Y",
        "pageNum": 1
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if 'results' in data and len(data['results']) > 0:
            lat = float(data['results'][0]['LATITUDE'])
            lon = float(data['results'][0]['LONGITUDE'])
            return lat, lon
    st.error("No results found for the postal code.")
    return None

def get_dengue_clusters_with_extents(extents):
    check_and_refresh_token()
    url = f"https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=dengue_cluster&extents={extents}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("SrchResults", [])
    else:
        st.error(f"Error {response.status_code}: {response.text}")
        return None

def get_theme_data(query_name, extents):
    check_and_refresh_token()
    url = f"https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName={query_name}&extents={extents}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("SrchResults", [])
    else:
        st.error(f"Failed to retrieve data for {query_name}. Status Code: {response.status_code}")
        return []

def get_general_route(start, end, route_type):
    check_and_refresh_token()
    url = f"https://www.onemap.gov.sg/api/public/routingsvc/route?start={start}&end={end}&routeType={route_type}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to retrieve {route_type} route. Status Code: {response.status_code}")
        return None

def get_public_transport_route(start, end, date, time, mode, max_walk_distance=1000, num_itineraries=1):
    check_and_refresh_token()
    url = f"https://www.onemap.gov.sg/api/public/routingsvc/route?start={start}&end={end}&routeType=pt&date={date}&time={time}&mode={mode}&maxWalkDistance={max_walk_distance}&numItineraries={num_itineraries}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        st.error(f"Failed to retrieve public transport route. Status Code: {response.status_code}")
        return None

    data = response.json()

    if "plan" not in data or "itineraries" not in data["plan"]:
        st.error("No valid public transport routes found.")
        return None

    itinerary = data["plan"]["itineraries"][0]  # Get the first itinerary
    fare = itinerary.get("fare", "N/A")  # Get fare if available

    # Process legs of the trip to extract bus and train details and route geometry
    transit_details = []
    full_route_geometry = []  # List to hold combined decoded coordinates for each leg
    for leg in itinerary["legs"]:
        mode = leg["mode"]
        if leg["transitLeg"]:  # If it's a transit leg (bus/train)
            route = leg.get("route", "")
            agency = leg.get("agencyName", "")
            transit_details.append({
                "mode": mode,
                "route": route,
                "agency": agency,
                "start": leg["from"]["name"],
                "end": leg["to"]["name"]
            })

        # Decode each leg's geometry and append to the overall route
        if "legGeometry" in leg and "points" in leg["legGeometry"]:
            leg_points = leg["legGeometry"]["points"]
            decoded_leg = polyline.decode(leg_points)  # Decode the polyline points
            full_route_geometry.extend(decoded_leg)  # Add decoded points to the full route

    return {
        "fare": fare,
        "transit_details": transit_details,
        "route_geometry": full_route_geometry,  # List of decoded coordinates
        "total_duration": itinerary["duration"] // 60  # Convert seconds to minutes
    }

# Streamlit interface and app logic
st.title("OneMap API Integration")

# Add your Streamlit UI components here
# Example usage of functions:
postal_code = st.text_input("Enter Postal Code:")
if st.button("Get Coordinates"):
    coordinates = get_latlon_from_postal(postal_code)
    if coordinates:
        st.success(f"Coordinates: {coordinates}")

# More UI elements can be added as needed

