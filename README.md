# Fare Sense: Smart Route Fare Estimation

This project predicts taxi fares based on pickup/drop coordinates, datetime, and passenger details.
It includes:
- Data cleaning & preprocessing
- Feature engineering (distance, time features)
- Machine learning model (Random Forest)
- Streamlit app for fare prediction
- PostgreSQL database integration

## Project Structure
- `data/` → raw & processed data
- `notebooks/` → Jupyter notebooks
- `src/` → utility and helper scripts
- `app/` → Streamlit app
- `models/` → trained ML models
- `tests/` → unit tests

## Setup
1. Clone repo  
2. Create virtual environment  
3. Install dependencies (`pip install -r requirements.txt`)  
4. Run notebooks or `streamlit run app/streamlit_app.py`
