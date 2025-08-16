# SmartWander: AI-Travel-Companion

Smart Wander is an intelligent travel companion app , designed to make exploring Karnataka smarter, easier, and more personalized. It generates AI-powered travel itineraries, provides real-time weather insights, integrates Google Maps data for stays & restaurants, and even offers English ↔ Kannada translation with text-to-speech support.

# FEATURES
1] Personalized Itinerary Generator
Create 1–5 day itineraries with suggested attractions, restaurants, and safety tips.
Customize based on mood (Nature, Heritage, Adventure, Relaxation, etc.).
Get weather-aware recommendations for each day.

2] Real-Time Weather Forecasts
Fetch live weather using OpenWeather API.
Integrated into daily itineraries for better planning.

3] Food & Stay Suggestions
Get nearby restaurants using Google Places API.
Discover top hotels & direct links to Goibibo.

4] Language Translation
Translate English to Kannada instantly.
Built-in text-to-speech (TTS) for Kannada output.

5] User Authentication
Secure signup/login using bcrypt password hashing.
User data stored safely in MongoDB.

6] MongoDB-Backed Travel Data
Preloaded tourist data for districts in Karnataka.
Easy to extend with new destinations.

7] Beautiful UI/UX
Clean, minimal Streamlit interface.
Custom CSS for modern cards, expanders, and navigation.
Landing page with feature highlights.

# TECH STACK
Frontend/UI: Streamlit + Custom CSS
Backend Logic: Python
Database: MongoDB (PyMongo)
AI & NLP: Cohere API
APIs Integrated: OpenWeather (Weather Forecasts) and Google Places API (Restaurants & Stays)

# Other Tools:
bcrypt (User Authentication)
gTTS (Text to Speech)
Folium + Streamlit-Folium (Interactive Maps)
