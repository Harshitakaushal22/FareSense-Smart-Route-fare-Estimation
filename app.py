from xml.parsers.expat import model
import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
import requests
import folium
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import math
from datetime import datetime
import joblib

# Load your trained Random Forest model
rf_model = joblib.load("rf_model.pkl")  # Make sure this file exists in your repo

def get_connection():
    return psycopg2.connect(
        host="ep-spring-rice-adodtb8d-pooler.c-2.us-east-1.aws.neon.tech",
        port=5432,
        database="neondb",
        user="neondb_owner",
        password="npg_LgHaiw70kCNc"
    )

def save_to_db(user_name, fare, duration, distance, pickup_location, dropoff_location):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO trip_records
            (user_name, pickup_location, dropoff_location,
             predicted_fare, predicted_duration_minutes, distance_km)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_name, pickup_location, dropoff_location, fare, duration, distance)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as error:
        st.error(f"Database error: {error}")

def fetch_trip_history():
    try:
        conn = get_connection()
        query = """
        SELECT user_name, pickup_location, dropoff_location,
               predicted_fare, predicted_duration_minutes, distance_km, created_at
        FROM trip_records
        ORDER BY created_at DESC;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as error:
        st.error(f"Error fetching history: {error}")
        return pd.DataFrame()

OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"
geolocator = Nominatim(user_agent="taxi_fare_app")

def get_coords_from_address(address):
    try:
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        return None
    except:
        return None

st.title("🚖 FareSense: Smart Route & Fare Estimation")
st.markdown("### Get estimated fare, shortest route, and travel time for your trip.")

menu = st.sidebar.radio("Menu", ["Predict Fare", "Trip History"])

if menu == "Predict Fare":
    user_name = st.text_input("Enter Your Name:")
    if not user_name:
        st.warning("Please enter your name to continue.")
        st.stop()

    pickup_location = st.text_input("Pickup Location:")
    dropoff_location = st.text_input("Drop-off Location:")
    st.markdown("---")
    st.markdown("#### Or, select locations on the map")
    st.write("Click on the map to set your pickup and drop-off points.")

    if 'pickup_coords' not in st.session_state:
        st.session_state['pickup_coords'] = None
    if 'dropoff_coords' not in st.session_state:
        st.session_state['dropoff_coords'] = None

    m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)

    if st.session_state['pickup_coords']:
        folium.Marker(st.session_state['pickup_coords'], tooltip="Pickup").add_to(m)
    if st.session_state['dropoff_coords']:
        folium.Marker(st.session_state['dropoff_coords'], tooltip="Drop-off").add_to(m)

    map_data = st_folium(m, width=700, height=500)

    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        if st.session_state['pickup_coords'] is None:
            st.session_state['pickup_coords'] = [lat, lon]
            st.info(f"Pickup location set: {lat:.4f}, {lon:.4f}")
        elif st.session_state['dropoff_coords'] is None:
            st.session_state['dropoff_coords'] = [lat, lon]
            st.info(f"Drop-off location set: {lat:.4f}, {lon:.4f}")

    if st.button("Predict"):
        if pickup_location and dropoff_location:
            pickup_coords = get_coords_from_address(pickup_location)
            dropoff_coords = get_coords_from_address(dropoff_location)
            if not pickup_coords or not dropoff_coords:
                st.warning("Could not find coordinates for one or both locations.")
                st.stop()
        elif st.session_state['pickup_coords'] and st.session_state['dropoff_coords']:
            pickup_coords = st.session_state['pickup_coords']
            dropoff_coords = st.session_state['dropoff_coords']
            
            pickup_location = f"Lat: {pickup_coords[0]:.4f}, Lon: {pickup_coords[1]:.4f}"
            dropoff_location = f"Lat: {dropoff_coords[0]:.4f}, Lon: {dropoff_coords[1]:.4f}"
        else:
            st.warning("Please enter or select both pickup and drop-off locations.")
            st.stop()

        try:
            response = requests.get(
                f"{OSRM_URL}{pickup_coords[1]},{pickup_coords[0]};{dropoff_coords[1]},{dropoff_coords[0]}?overview=false"
            )
            data = response.json()
            if data['code'] != 'Ok':
                st.warning("Could not find a driving route.")
                st.stop()

            trip_distance_km = data['routes'][0]['distance'] / 1000
            predicted_trip_duration = data['routes'][0]['duration'] / 60

            avg_speed = (trip_distance_km / predicted_trip_duration) * 60 if predicted_trip_duration > 0 else 0
            if avg_speed < 15:
                traffic = '🚨 Very High'
            elif avg_speed < 30:
                traffic = '⚠️ High'
            elif avg_speed < 50:
                traffic = 'Moderate'
            else:
                traffic = 'Low'
        except Exception as e:
            st.error(f"Error fetching route: {e}")
            st.stop()

        # Predict fare using Random Forest
        features = [[trip_distance_km, predicted_trip_duration]]
        predicted_fare = rf_model.predict(features)[0]

        # Time and Day adjustments
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()  # 0=Mon, 6=Sun
        adjusted_fare = predicted_fare

        # Weekend discount
        if current_day >= 5:
            adjusted_fare -= 4.0
        # Morning (6-10) & Evening (17-20) -> higher fare
        if 6 <= current_hour <= 10 or 17 <= current_hour <= 20:
            adjusted_fare += 5.0
        else:  # Afternoon & Night -> lower fare
            adjusted_fare -= 2.0

        BASE_FARE = 10.0
        adjusted_fare = max(BASE_FARE, adjusted_fare)

        # Save to DB
        save_to_db(user_name, adjusted_fare, predicted_trip_duration, trip_distance_km,
                   pickup_location, dropoff_location)

        st.success("### ✅ Prediction Completed!")
        st.metric("Estimated Fare", f"₹{adjusted_fare:.2f}")
        st.metric("Estimated Trip Duration", f"{math.ceil(predicted_trip_duration)} minutes")
        st.metric("Distance", f"{trip_distance_km:.2f} km")
        st.info(f"Traffic conditions: {traffic}")

elif menu == "Trip History":
    st.markdown("### 📜 Your Trip History")
    history_df = fetch_trip_history()
    if not history_df.empty:
        st.dataframe(history_df)
    else:
        st.info("No trip history found yet.")
