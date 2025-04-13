import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pickle
from datetime import datetime
from fpdf import FPDF
import re
import io

# Load models
with open("aqi_model.pkl", "rb") as file:
    models = pickle.load(file)

pollutants = ['PM2.5', 'PM10', 'NO2', 'NH3', 'SO2', 'CO', 'O3']

# Sub-index calculator
def calculate_sub_index(pollutant, value):
    breakpoints = {
        'PM2.5': [(0,30,0,50), (31,60,51,100), (61,90,101,200), (91,120,201,300), (121,250,301,400), (251,500,401,500)],
        'PM10': [(0,50,0,50), (51,100,51,100), (101,250,101,200), (251,350,201,300), (351,430,301,400), (431,600,401,500)],
        'NO2':  [(0,40,0,50), (41,80,51,100), (81,180,101,200), (181,280,201,300), (281,400,301,400), (401,1000,401,500)],
        'NH3':  [(0,200,0,50), (201,400,51,100), (401,800,101,200), (801,1200,201,300), (1201,1800,301,400), (1801,2400,401,500)],
        'SO2':  [(0,40,0,50), (41,80,51,100), (81,380,101,200), (381,800,201,300), (801,1600,301,400), (1601,2000,401,500)],
        'CO':   [(0.0,1.0,0,50), (1.1,2.0,51,100), (2.1,10.0,101,200), (10.1,17.0,201,300), (17.1,34.0,301,400), (34.1,50.0,401,500)],
        'O3':   [(0,50,0,50), (51,100,51,100), (101,168,101,200), (169,208,201,300), (209,748,301,400), (749,1000,401,500)],
    }
    for bp in breakpoints[pollutant]:
        low, high, index_low, index_high = bp
        if low <= value <= high:
            return round(((index_high - index_low)/(high - low)) * (value - low) + index_low)
    return 0

def get_health_tip(aqi):
    if aqi <= 50:
        return "🌿 Good: Air quality is ideal. No precautions needed."
    elif aqi <= 100:
        return "😊 Satisfactory: Acceptable air quality. Sensitive individuals should avoid outdoor exertion."
    elif aqi <= 200:
        return "😐 Moderate: Consider limiting prolonged outdoor exertion."
    elif aqi <= 300:
        return "😷 Poor: People with heart/lung disease, children and older adults should reduce prolonged outdoor exertion."
    elif aqi <= 400:
        return "🚫 Very Poor: Everyone should avoid outdoor physical activity."
    else:
        return "🛑 Severe: Avoid all outdoor activity. Use air purifiers indoors."

def remove_emojis(text):
    return re.sub(r'[\U00010000-\U0010ffff]', '', text)

# Get features from date
def get_date_features(date_str):
    date = datetime.strptime(date_str, "%d-%m-%Y")
    return pd.DataFrame({
        'Year': [date.year],
        'Month': [date.month],
        'Day': [date.day],
        'DayOfWeek': [date.weekday()]
    })

# Predict AQI
def predict_aqi(input_date):
    features = get_date_features(input_date)
    predicted = {}
    for pollutant in pollutants:
        predicted[pollutant] = models[pollutant].predict(features)[0]
    sub_indices = {p: calculate_sub_index(p, v) for p, v in predicted.items()}
    aqi = max(sub_indices.values())
    if aqi <= 50:
        category = 'Good'
    elif aqi <= 100:
        category = 'Satisfactory'
    elif aqi <= 200:
        category = 'Moderate'
    elif aqi <= 300:
        category = 'Poor'
    elif aqi <= 400:
        category = 'Very Poor'
    else:
        category = 'Severe'
    return predicted, sub_indices, aqi, category

# PDF Report
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "Mumbai AQI Prediction Report", ln=True, align='C')

    def add_results(self, date, aqi, category, predicted, tip):
        self.set_font("Arial", '', 10)
        self.cell(0, 10, f"Date: {date}", ln=True)
        self.cell(0, 10, f"AQI: {aqi} ({category})", ln=True)
        clean_tip = remove_emojis(tip)
        self.multi_cell(0, 10, f"Health Tip: {clean_tip}")
        self.ln(5)
        for k, v in predicted.items():
            self.cell(0, 8, f"{k}: {v:.2f}", ln=True)

    def output_bytes(self):
        return self.output(dest='S').encode('latin1')

# Streamlit UI
st.set_page_config(page_title="Mumbai AQI Predictor", layout="centered")
st.title("🌆 Mumbai AQI Prediction")
st.markdown("Enter a date to get the predicted AQI and pollutant levels for Mumbai city.")

selected_date = st.date_input("📅 Select Date", format="DD-MM-YYYY")
predict_btn = st.button("Predict AQI")

if predict_btn:
    date_str = selected_date.strftime("%d-%m-%Y")
    predicted, sub_indices, aqi, category = predict_aqi(date_str)

    st.subheader(f"✅ AQI for {selected_date.strftime('%B %d, %Y')}")
    st.markdown(f"**AQI**: `{aqi}`")
    st.markdown(f"**Category**: `{category}`")

    # Health Tip
    tip = get_health_tip(aqi)
    st.subheader("🩺 Health Tip")
    st.info(get_health_tip(aqi))

    st.subheader("📊 Predicted Pollutants")
    pollutant_df = pd.DataFrame(predicted.items(), columns=["Pollutant", "Concentration (µg/m³ / mg/m³)"])
    st.table(pollutant_df.style.format({"Concentration (µg/m³ / mg/m³)": "{:.2f}"}))

    # Chart
    st.subheader("📉 Pollutant Levels Chart")
    st.bar_chart(pollutant_df.set_index("Pollutant"))

    st.subheader("📊 AQI Sub-Indices")
    df_subindices = pd.DataFrame(sub_indices.items(), columns=["Pollutant", "Sub-Index"])
    st.dataframe(df_subindices)

    st.subheader("📘 AQI Scale")
    scale_data = [
        ("0-50", "Good", "#00e400"),
        ("51-100", "Satisfactory", "#a3c853"),
        ("101-200", "Moderate", "#ffff00"),
        ("201-300", "Poor", "#ff7e00"),
        ("301-400", "Very Poor", "#ff0000"),
        ("401-500", "Severe", "#7e0023")
    ]
    scale_df = pd.DataFrame(scale_data, columns=["AQI Range", "Category", "Color"])
    def color_cell(row):
        return ["background-color: " + row.Color if col == "Color" else "" for col in scale_df.columns]
    st.table(scale_df.style.apply(color_cell, axis=1))

    pdf = PDF()
    pdf.add_page()
    pdf.add_results(date_str, aqi, category, predicted, tip)
    pdf_data = pdf.output_bytes()
    st.subheader("📄 Download Report")
    st.download_button("📄 Download AQI Report (PDF)", data=pdf_data, file_name="Mumbai_AQI_Report.pdf", mime="application/pdf")
