# mediLocator.py
import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import geocoder
from datetime import datetime
import os
from dotenv import load_dotenv
from geopy.distance import geodesic
import pandas as pd

# Load environment variables
load_dotenv()

API_KEY = "AIzaSyBx827KsGam_YfYb7ucls9iYpAWwXJk9PM"

def get_location():
    """Get location either from user input or IP-based geolocation"""
    location_method = st.radio(
        "Choose location method:",
        ("Use my current location", "Enter coordinates manually")
    )
    
    if location_method == "Enter coordinates manually":
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Latitude", value=40.7128)
            st.caption("Example: 40.7128 (New York)")
        with col2:
            lon = st.number_input("Longitude", value=-74.0060)
            st.caption("Example: -74.0060 (New York)")
        return [lat, lon] if lat != 0 and lon != 0 else None
    else:
        try:
            g = geocoder.ip("me")
            if g.ok:
                return g.latlng
            else:
                st.error("Unable to fetch location from IP. Please enter coordinates manually.")
                return None
        except Exception as e:
            st.error(f"Error getting location: {str(e)}")
            return None

def fetch_hospitals(lat, lon, radius=5000, keyword=None):
    """Fetch nearby hospitals using Google Places API"""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    
    try:
        params = {
            "location": f"{lat},{lon}",
            "radius": radius,
            "type": "hospital",
            "key": API_KEY
        }
        if keyword:
            params["keyword"] = keyword
            
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching hospitals: {str(e)}")
        return None

def get_place_details(place_id):
    """Fetch detailed information about a place"""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    
    try:
        params = {
            "place_id": place_id,
            "fields": "formatted_phone_number,website,opening_hours,reviews",
            "key": API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get('result', {})
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching place details: {str(e)}")
        return {}

def get_distance(coord1, coord2):
    """Calculate distance between two coordinates in kilometers"""
    return round(geodesic(coord1, coord2).kilometers, 2)

def create_hospital_map(user_lat, user_lon, hospitals):
    """Create Folium map with hospital markers and routes"""
    map = folium.Map(location=[user_lat, user_lon], zoom_start=14)
    
    # Add user location
    folium.Marker(
        location=[user_lat, user_lon],
        popup="Your Location",
        icon=folium.Icon(color="red", icon="home"),
    ).add_to(map)
    
    # Create a feature group for hospitals
    hospital_group = folium.FeatureGroup(name="Hospitals")
    
    for hospital in hospitals[:10]:
        try:
            name = hospital.get("name", "N/A")
            lat = hospital["geometry"]["location"]["lat"]
            lon = hospital["geometry"]["location"]["lng"]
            distance = get_distance((user_lat, user_lon), (lat, lon))
            
            popup_html = f"""
                <b>{name}</b><br>
                Distance: {distance}km<br>
                Rating: {hospital.get('rating', 'No rating')}/5<br>
                Address: {hospital.get('vicinity', 'No address available')}
            """
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color="blue", icon="info-sign"),
            ).add_to(hospital_group)
            
        except Exception as e:
            continue
    
    hospital_group.add_to(map)
    folium.LayerControl().add_to(map)
    return map

def export_to_csv(hospitals, user_location):
    """Export hospital data to CSV"""
    data = []
    for hospital in hospitals:
        hospital_lat = hospital["geometry"]["location"]["lat"]
        hospital_lon = hospital["geometry"]["location"]["lng"]
        distance = get_distance(user_location, (hospital_lat, hospital_lon))
        
        data.append({
            "Name": hospital.get("name", "N/A"),
            "Address": hospital.get("vicinity", "N/A"),
            "Rating": hospital.get("rating", "No rating"),
            "Distance (km)": distance,
            "Latitude": hospital_lat,
            "Longitude": hospital_lon
        })
    
    return pd.DataFrame(data)

def main():
    st.title("MediLocator")
    st.subheader("Find and Analyze Nearby Hospitals")
    
    # Sidebar filters
    st.sidebar.header("Search Filters")
    radius = st.sidebar.slider("Search Radius (km)", 1, 20, 5) * 1000
    keyword = st.sidebar.text_input("Search by keyword (e.g., emergency, pediatric)")
    min_rating = st.sidebar.slider("Minimum Rating", 1.0, 5.0, 3.0)
    
    location = get_location()
    
    if location:
        user_lat, user_lon = location
        st.success(f"Location set to: {user_lat:.4f}, {user_lon:.4f}")
        
        with st.spinner("Fetching nearby hospitals..."):
            hospitals_data = fetch_hospitals(user_lat, user_lon, radius, keyword)
        
        if hospitals_data and "results" in hospitals_data:
            hospitals = hospitals_data["results"]
            hospitals = [h for h in hospitals if h.get('rating', 0) >= min_rating]
            
            if not hospitals:
                st.warning("No hospitals found matching your criteria.")
                return
            
            tab1, tab2, tab3 = st.tabs(["List View", "Map View", "Analytics"])
            
            with tab1:
                st.write("### Nearby Hospitals:")
                for i, hospital in enumerate(hospitals[:10], 1):
                    with st.expander(f"{i}. {hospital.get('name', 'N/A')}"):
                        details = get_place_details(hospital['place_id'])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"📍 Address: {hospital.get('vicinity', 'N/A')}")
                            st.write(f"⭐ Rating: {hospital.get('rating', 'No rating')}/5")
                            if 'formatted_phone_number' in details:
                                st.write(f"📞 Phone: {details['formatted_phone_number']}")
                        with col2:
                            if 'website' in details:
                                st.write(f"🌐 [Visit Website]({details['website']})")
                            if 'opening_hours' in details:
                                st.write("⏰ Hours:", "Open now" if details['opening_hours'].get('open_now') else "Closed")
            
            with tab2:
                st.write("### Map View")
                map = create_hospital_map(user_lat, user_lon, hospitals)
                st_folium(map, width=700, height=500)
            
            with tab3:
                st.write("### Analytics")
                df = export_to_csv(hospitals, (user_lat, user_lon))
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Average Rating:", round(df['Rating'].mean(), 2))
                    st.write("Total Hospitals Found:", len(df))
                with col2:
                    st.write("Average Distance:", round(df['Distance (km)'].mean(), 2), "km")
                    st.write("Closest Hospital:", round(df['Distance (km)'].min(), 2), "km away")
                
                st.download_button(
                    label="Download Hospital Data",
                    data=df.to_csv(index=False),
                    file_name="nearby_hospitals.csv",
                    mime="text/csv"
                )
                
                st.write("### Rating Distribution")
                st.bar_chart(df['Rating'].value_counts())
            
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.error("Failed to fetch hospital data. Please try again later.")

if __name__ == "__main__":
    main()