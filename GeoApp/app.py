import streamlit as st
import geopandas as gpd
from shapely.geometry import box, Point
import streamlit_js_eval as sje
from datetime import datetime
from api.onemap import get_latlon_from_postal, get_dengue_clusters_with_extents, get_theme_data, get_route
from api.openweathermap import get_weather_data
from utils.data_processing import load_polygons_from_geojson_within_extents
from utils.map_creation import create_map_with_features, display_theme_locations
from prompts.language_prompts import prompts, themes

# Title for the Streamlit app
st.title("Geolocation with iframe in Streamlit")

def main():
    st.title("Interactive Geospatial App")

    # Fetch geolocation data (current location)
    geolocationData = sje.get_geolocation()

    # Check if geolocation data is available
    if geolocationData and "coords" in geolocationData:
        user_location = {
            "latitude": geolocationData["coords"]["latitude"],
            "longitude": geolocationData["coords"]["longitude"]
        }
    else:
        st.error("Unable to retrieve geolocation data. Please enable location services in your browser.")
        return  # Stop execution if geolocation is not available

    lat, lon = user_location["latitude"], user_location["longitude"]
    st.success(f"Current location retrieved: Latitude {lat}, Longitude {lon}")

    # Load the polygon data (GeoJSON)
    file_path = 'GeoApp/data/NParksParksandNatureReserves.geojson'
    try:
        gdf = gpd.read_file(file_path)
    except Exception as e:
        st.error(f"Error loading GeoJSON file: {e}")
        return

    # Get dengue clusters and polygon data
    dengue_clusters = get_dengue_clusters_with_extents(f"{lat-0.035},{lon-0.035},{lat+0.035},{lon+0.035}")
    extent_polygon = box(lon - 0.025, lat - 0.025, lon + 0.025, lat + 0.025)

    # Load nearby polygons and find nearest points to user location
    polygon_data = load_polygons_from_geojson_within_extents(gdf, extent_polygon, user_location)

    # Extract polygon names for selection
    polygon_names = [polygon['description'] for polygon in polygon_data if polygon['description'] != 'No description available']
    
    # Display map with current location
    create_map_with_features(lat, lon, "Current Location", dengue_clusters, [], polygon_data, user_location)

    # Language selection logic
    if 'language' not in st.session_state:
        st.write("Please select your language:")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("English", key="english_btn"):
                st.session_state['language'] = 'English'
        with col2:
            if st.button("Bahasa Melayu", key="malay_btn"):
                st.session_state['language'] = 'Malay'
        with col3:
            if st.button("தமிழ்", key="tamil_btn"):
                st.session_state['language'] = 'Tamil'
        with col4:
            if st.button("中文", key="chinese_btn"):
                st.session_state['language'] = 'Chinese'

    # Main flow after language selection
    if 'language' in st.session_state:
        # Use the selected language for prompts
        lang_prompts = prompts[st.session_state['language']]
        st.success(f"Selected Language: {st.session_state['language']}")

        # Input postal code to set as the return/home point, display only once
        user_input = st.text_input(lang_prompts['prompt'], value=st.session_state.get("user_input", ""))  # Ensure prompt comes from language file

        if st.button(lang_prompts['enter_button'], key="enter_btn"):
            if user_input:
                latlon = get_latlon_from_postal(user_input)
                if latlon:
                    home_lat, home_lon = latlon
                    st.session_state["user_input"] = user_input  # Save the postal code
                    st.session_state["home_lat"] = home_lat     # Save the postal code lat
                    st.session_state["home_lon"] = home_lon     # Save the postal code lon
                    st.success(f"Home location set: Latitude {home_lat}, Longitude {home_lon}")

                    # Fetch weather data for the current location
                    weather_data = get_weather_data(lat, lon)
                    st.subheader(lang_prompts["weather_prompt"])  # Use the language-specific weather prompt
                    if weather_data:
                        st.write(f"**{lang_prompts['weather_station']}**: {weather_data['name']}")
                        st.write(f"**{lang_prompts['weather']}**: {weather_data['weather'][0]['description'].capitalize()}")
                        st.write(f"**{lang_prompts['temperature']}**: {weather_data['main']['temp']}°C")
                        st.write(f"**{lang_prompts['feels_like']}**: {weather_data['main']['feels_like']}°C")
                        st.write(f"**{lang_prompts['humidity']}**: {weather_data['main']['humidity']}%")
                        st.write(f"**{lang_prompts['wind_speed']}**: {weather_data['wind']['speed']} m/s, {lang_prompts['wind_direction']}: {weather_data['wind']['deg']}°")

                    extents = f"{lat-0.035},{lon-0.035},{lat+0.035},{lon+0.035}"
                    dengue_clusters = get_dengue_clusters_with_extents(extents)

                    extent_polygon = box(lon - 0.025, lat - 0.025, lon + 0.025, lat + 0.025)
                    polygon_data = load_polygons_from_geojson_within_extents(gdf, extent_polygon, user_location)

                    theme_data = []
                    for theme in themes:
                        theme_data.extend(get_theme_data(theme, extents))

                    # Save theme data in session state
                    st.session_state['theme_data'] = theme_data

    # Handle theme selection and routing
    if polygon_names:
        # Allow user to select a polygon (park)
        selected_polygon = st.selectbox("Select a nearby park/location:", polygon_names)

        # Find the selected polygon's nearest point to user's location
        selected_polygon_coords = None
        for polygon in polygon_data:
            if polygon['description'] == selected_polygon:
                if isinstance(polygon['coordinates'][0], list):  # For MultiPolygon
                    selected_polygon_coords = polygon['coordinates'][0][0]  # First point of the first sub-polygon
                else:
                    selected_polygon_coords = polygon['coordinates'][0]  # First point of the polygon

        if selected_polygon_coords:
            start = f"{lat},{lon}"  # Use current geolocation as the start point
            end = f"{selected_polygon_coords[1]},{selected_polygon_coords[0]}"  # The nearest point of the selected polygon

            # Select route type
            route_type = st.selectbox("Select a Route Type", ["walk", "drive", "cycle", "pt"], key="route_type")
            if route_type == "pt":
                mode = st.selectbox("Select Public Transport Mode", ["TRANSIT", "BUS", "RAIL"], key="mode")
                max_walk_distance = st.number_input
            current_datetime = datetime.now()
            date_str = current_datetime.strftime("%m-%d-%Y")
            time_str = current_datetime.strftime("%H:%M:%S")

            # Fetch route data for public transport
            route_data = get_route(start, end, route_type, mode, date_str, time_str, max_walk_distance)
        else:
            # Fetch route data for walking, driving, or cycling
            route_data = get_route(start, end, route_type)

        # If route data is available, display the route and route summary
        if route_data and "route_geometry" in route_data:
            route_geometry = route_data["route_geometry"]
            create_map_with_features(lat, lon, st.session_state['user_input'], dengue_clusters, theme_data, polygon_data, user_location, route_geometry)

            # Assuming `route_data` is retrieved successfully
            if route_data and "route_summary" in route_data:
                total_time_seconds = route_data["route_summary"]["total_time"]  # Total time in seconds
                total_distance_meters = route_data["route_summary"]["total_distance"]  # Total distance in meters

                # Convert time to minutes and hours
                total_minutes = total_time_seconds // 60
                hours = total_minutes // 60
                minutes = total_minutes % 60

                if hours > 0:
                    time_str = f"{hours} hours {minutes} minutes"
                else:
                    time_str = f"{minutes} minutes"

                # Convert distance to kilometers
                total_distance_km = total_distance_meters / 1000

                # Display the total time and distance
                st.write(f"**Total Time**: {time_str}")
                st.write(f"**Total Distance**: {total_distance_km:.2f} km")
        else:
            st.error("Failed to generate route or route geometry missing.")

# Return Home and Restart buttons
col1, col2 = st.columns([1, 1])

with col1:
    if "home_lat" in st.session_state and "home_lon" in st.session_state:
        if st.button("Return Home", key="return_home_btn"):
            # Set the current location as the start and home location as the end
            start = f"{lat},{lon}"  # Current location
            end = f"{st.session_state['home_lat']},{st.session_state['home_lon']}"  # Home location (postal code)

            route_type = "drive"  # Default route type to drive for return home
            route_data = get_route(start, end, route_type)

            if route_data and "route_geometry" in route_data:
                route_geometry = route_data["route_geometry"]
                create_map_with_features(lat, lon, st.session_state['user_input'], dengue_clusters, theme_data, polygon_data, user_location, route_geometry)

                # Assuming `route_data` is retrieved
                max_walk_distance = st.number_input("Max Walk Distance (meters)", min_value=500, max_value=5000, step=500, value=1000, key="max_walk_distance")

                current_datetime = datetime.now()
                date_str = current_datetime.strftime("%m-%d-%Y")
                time_str = current_datetime.strftime("%H:%M:%S")

                # Get route for public transport
                route_data = get_route(start, end, route_type, mode, date_str, time_str, max_walk_distance)
            else:
                # Get route for walk, drive, or cycle
                route_data = get_route(start, end, route_type)

            # Check if route is successfully generated and display on the map
            if route_data and "route_geometry" in route_data:
                route_geometry = route_data["route_geometry"]
                create_map_with_features(lat, lon, st.session_state['user_input'], dengue_clusters, theme_data, polygon_data, user_location, route_geometry)

                # Assuming `route_data` is retrieved successfully
                if route_data and "route_summary" in route_data:
                    total_time_seconds = route_data["route_summary"]["total_time"]  # Total time in seconds
                    total_distance_meters = route_data["route_summary"]["total_distance"]  # Total distance in meters

                    # Convert time to minutes and hours
                    total_minutes = total_time_seconds // 60
                    hours = total_minutes // 60
                    minutes = total_minutes % 60

                    if hours > 0:
                        time_str = f"{hours} hours {minutes} minutes"
                    else:
                        time_str = f"{minutes} minutes"

                    # Convert distance to kilometers
                    total_distance_km = total_distance_meters / 1000

                    # Display the total time and distance
                    st.write(f"**Total Time**: {time_str}")
                    st.write(f"**Total Distance**: {total_distance_km:.2f} km")
            else:
                st.error("Failed to generate route or route geometry missing.")

    # Return Home and Restart buttons
    col1, col2 = st.columns([1, 1])

    with col1:
        if "home_lat" in st.session_state and "home_lon" in st.session_state:
            if st.button("Return Home", key="return_home_btn"):
                # Set the current location as the start and home location as the end
                start = f"{lat},{lon}"  # Current location
                end = f"{st.session_state['home_lat']},{st.session_state['home_lon']}"  # Home location (postal code)

                route_type = "drive"  # Default route type to drive for return home
                route_data = get_route(start, end, route_type)

                if route_data and "route_geometry" in route_data:
                    route_geometry = route_data["route_geometry"]
                    create_map_with_features(lat, lon, st.session_state['user_input'], dengue_clusters, theme_data, polygon_data, user_location, route_geometry)

                    # Assuming `route_data` is retrieved successfully
                    if route_data and "route_summary" in route_data:
                        total_time_seconds = route_data["route_summary"]["total_time"]  # Total time in seconds
                        total_distance_meters = route_data["route_summary"]["total_distance"]  # Total distance in meters

                        # Convert time to minutes and hours
                        total_minutes = total_time_seconds // 60
                        hours = total_minutes // 60
                        minutes = total_minutes % 60

                        if hours > 0:
                            time_str = f"{hours} hours {minutes} minutes"
                        else:
                            time_str = f"{minutes} minutes"

                        # Convert distance to kilometers
                        total_distance_km = total_distance_meters / 1000

                        # Display the total time and distance
                        st.write(f"**Total Time**: {time_str}")
                        st.write(f"**Total Distance**: {total_distance_km:.2f} km")

                else:
                    st.error("Failed to generate return home route.")

    with col2:
        if st.button("Restart", key="restart_btn"):
            st.session_state.clear()
            st.rerun()

# Run the Streamlit app
if __name__ == "__main__":
    main()
