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

    # Load the polygon data (GeoJSON) for parks
    file_path = 'GeoApp/data/NParksParksandNatureReserves.geojson'
    try:
        gdf = gpd.read_file(file_path)
    except Exception as e:
        st.error(f"Error loading GeoJSON file: {e}")
        return

    # Get dengue clusters and polygon data (for parks)
    dengue_clusters = get_dengue_clusters_with_extents(f"{lat-0.035},{lon-0.035},{lat+0.035},{lon+0.035}")
    extent_polygon = box(lon - 0.025, lat - 0.025, lon + 0.025, lat + 0.025)

    # Load nearby polygons (parks) and find nearest points to user location
    park_polygon_data = load_polygons_from_geojson_within_extents(gdf, extent_polygon, user_location)

    # Extract the names of the parks and their nearest points
    park_options = [park['description'] for park in park_polygon_data]
    park_nearest_points = [Point(park['coordinates'][0][0]) for park in park_polygon_data]

    # Fetch amenities using theme_data
    theme_data = []
    extents = f"{lat-0.035},{lon-0.035},{lat+0.035},{lon+0.035}"
    for theme in themes:
        theme_data.extend(get_theme_data(theme, extents))

    # Filter out amenities with valid names
    amenity_options = [f"{amenity.get('NAME', 'Unknown')} - {amenity.get('LatLng', 'N/A')}" for amenity in theme_data if amenity.get('NAME', '').strip()]
    amenity_nearest_points = [eval(amenity.get('LatLng')) for amenity in theme_data if amenity.get('LatLng', '')]

    # Display map with current location
    create_map_with_features(lat, lon, "Current Location", dengue_clusters, [], park_polygon_data, user_location)

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

    # Display park options and amenity options separately for route selection
    if park_options:
        selected_park = st.selectbox("Select a Nearby Park", park_options)
        if selected_park:
            # Find the index of the selected park to get the nearest point
            selected_park_index = park_options.index(selected_park)
            nearest_park_point = park_nearest_points[selected_park_index]

            start = f"{lat},{lon}"  # Use current geolocation as the start point
            end = f"{nearest_park_point.y},{nearest_park_point.x}"  # Use nearest park point coordinates as the end point

            # Select route type for parks
            route_type = st.selectbox("Select a Route Type (for Park)", ["walk", "drive", "cycle", "pt"], key="park_route_type")
            route_data = get_route(start, end, route_type)
            if route_data and "route_geometry" in route_data:
                route_geometry = route_data["route_geometry"]
                create_map_with_features(lat, lon, st.session_state['user_input'], dengue_clusters, theme_data, park_polygon_data, user_location, route_geometry)

    if amenity_options:
        selected_amenity = st.selectbox("Select a Nearby Amenity", amenity_options)
        if selected_amenity:
            # Find the index of the selected amenity to get the nearest point
            selected_amenity_index = amenity_options.index(selected_amenity)
            nearest_amenity_point = amenity_nearest_points[selected_amenity_index]

            start = f"{lat},{lon}"  # Use current geolocation as the start point
            end = f"{nearest_amenity_point[1]},{nearest_amenity_point[0]}"  # Use nearest amenity point coordinates as the end point

            # Select route type for amenities
            route_type = st.selectbox("Select a Route Type (for Amenity)", ["walk", "drive", "cycle", "pt"], key="amenity_route_type")
            route_data = get_route(start, end, route_type)
            if route_data and "route_geometry" in route_data:
                route_geometry = route_data["route_geometry"]
                create_map_with_features(lat, lon, st.session_state['user_input'], dengue_clusters, theme_data, park_polygon_data, user_location, route_geometry)

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
                    create_map_with_features(lat, lon, st.session_state['user_input'], dengue_clusters, theme_data, park_polygon_data, user_location, route_geometry)

    with col2:
        if st.button("Restart", key="restart_btn"):
            st.session_state.clear()
            st.rerun()

# Run the Streamlit app
if __name__ == "__main__":
    main()
