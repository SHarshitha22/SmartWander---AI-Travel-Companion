import streamlit as st
from pymongo import MongoClient
import cohere
import requests
from datetime import datetime
from urllib.parse import quote_plus
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from collections import defaultdict
from translate import Translator
from gtts import gTTS
import io
import bcrypt
import re
import html
from streamlit_folium import st_folium
import folium

# API KEYS
MONGO_URI = "API_KEY"
COHERE_API_KEY = "API_Key"
WEATHER_API_KEY = "API_kEY"
GOOGLE_PLACES_API_KEY = "API_kEY"

# INIT CLIENTS 
client = MongoClient(MONGO_URI)
db = client["smartwander_db"]
itinerary_collection = db["itineraries"]
travel_collection = db["Travel_data"]
users_collection = db["users"]
co = cohere.Client(COHERE_API_KEY)

st.set_page_config(page_title="Smart Wander", layout="wide",initial_sidebar_state="collapsed"
)


st.markdown(
    """
    <style>
    .main > div {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        display: none;
    }
     
    /* Set overall app background to white */
    .stApp {
        background-color: white !important;
    }

    /* Main container */
    .block-container {
        background-color: white !important;
    }

    /* Sidebar (if you use it) */
    section[data-testid="stSidebar"] {
        background-color: white !important;
    }

    /* Widgets like selectbox, sliders, etc. */
    div[data-baseweb="select"] > div {
        background-color: white !important;
        color: black !important;
    }

    /* Input boxes and buttons */
    input, textarea, .stButton>button, .stDownloadButton>button {
        background-color: white !important;
        color: black !important;
        border: 1px solid #ccc !important;
    }

    /* Expanders */
    details {
        background-color: white !important;
        color: black !important;
        border: 1px solid #ccc !important;
    }
    .activity-title {
    font-weight: bold;
    color: #205781; /* your dark blue */
    margin-bottom: 8px;
    font-size: 18px;
/* subtle light blue highlight */
    padding: 6px 10px;
    border-radius: 5px;
}

element-container iframe {
    background-color: transparent !important;
}

/* Or target the parent container */
[data-testid="stMarkdownContainer"] {
    background-color: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
}

    /* Containers and markdown */
    .stContainer {
        background-color: white !important;
    }

    /* Activity cards (yours) */
    .activity-card {
        background-color: #fdfdfd !important;
        color: #222 !important;
    }

    /* Subheaders, text, labels */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
        color: #111 !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)

#  USER AUTH 
def create_user(email, password):
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    user_data = {"email": email, "password": hashed_pw}
    users_collection.insert_one(user_data)

def authenticate_user(email, password):
    user = users_collection.find_one({"email": email})
    if user and bcrypt.checkpw(password.encode(), user["password"]):
        return True
    return False

# ========== LOAD TOURIST DATA ==========
def load_tourist_data_from_mongodb():
    try:
        cursor = travel_collection.find({})
        data = defaultdict(list)
        for doc in cursor:
            for district, places in doc.items():
                if district == "_id":
                    continue  # Skip MongoDB internal ID
                if isinstance(places, list):
                    data[district].extend(places)
        return data
    except Exception as e:
        st.error(f"Failed to load data from MongoDB: {e}")
        return {}

attractions = load_tourist_data_from_mongodb()

# ========== WEATHER API ==========
def get_weather_forecast(city, days=3):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if "list" not in data:
            raise ValueError("Invalid weather response")

        daily_forecast = {}
        for entry in data["list"]:
            dt = datetime.fromtimestamp(entry["dt"])
            if dt.hour == 12:
                date = dt.date().isoformat()
                if len(daily_forecast) < days:
                    daily_forecast[date] = {
                        "temp": entry["main"]["temp"],
                        "description": entry["weather"][0]["description"]
                    }
        return daily_forecast
    except Exception as e:
        print("Weather API error:", e)
        return {f"Day {i+1}": {"temp": "N/A", "description": "Weather unavailable"} for i in range(days)}

# ========== GOOGLE PLACES API ==========
def get_nearby_restaurant(lat, lng, rank=0, radius=500):
    url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type=restaurant&key={GOOGLE_PLACES_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            restaurant = data["results"][rank % len(data["results"])]
            name = restaurant["name"]
            place_id = restaurant["place_id"]
            return name
        else:
            return "No restaurant found", "N/A"
    except Exception as e:
        print(f"Error fetching restaurant data: {e}")
        return "Error", "N/A"

# ========== GOOGLE PLACES STAY RECOMMENDATION ==========
def get_top_stays(city, rank=3):
    url = (
        f"https://maps.googleapis.com/maps/api/place/textsearch/json"
        f"?query=hotels+in+{quote_plus(city)}"
        f"&key={GOOGLE_PLACES_API_KEY}"
    )
    try:
        response = requests.get(url)
        results = response.json().get("results", [])[:rank]
        stays = []
        for hotel in results:
            name = hotel.get("name", "N/A")
            place_id = hotel.get("place_id", "")
            map_link = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            rating = hotel.get("rating", "N/A")
            stays.append(
                f"**{name}** (Rating: {rating})  \n"
                f"- [Google Maps Link]({map_link})\n"
            )
        if stays:
            city_url = city.lower().replace(" ", "-")
            goibibo_link = f"https://www.goibibo.com/hotels/hotels-in-{city_url}-ct/"
            stays.append(f"\n🔗 [Browse more stays on Goibibo]({goibibo_link})")
        return stays if stays else ["No stays found."]
    except Exception as e:
        print(f"Error fetching stay data: {e}")
        return ["Error fetching stay data."]

# ========== QUERY GENERATION ==========
def create_itinerary_query(data, destination, mood=None, days=2, selected_places=None, start_time=None):
    if destination not in data:
        return f"No info available for {destination}."

    days = min(days, 5)
    filtered = [
        attr for attr in data[destination]
        if (mood is None or attr['mood'].lower() == mood.lower()) and
           (attr['name'] in selected_places if selected_places else True)
    ]
    if not filtered:
        return f"No attractions in {destination} match the mood '{mood}' or selected places."

    weather = get_weather_forecast(destination, days)
    query = f"Generate a {days}-day travel itinerary for a tourist visiting {destination}.\n"
    query += f"The tourist prefers a {mood} mood.\n" if mood else "The tourist has no specific mood preference.\n"

    query += "\nWeather forecast:\n"
    for i, (date, info) in enumerate(weather.items(), start=1):
        query += f"Day {i} ({date}): {info['description'].capitalize()}, {info['temp']}°C\n"

    query += "\nTourist attractions:\n"
    for attr in filtered:
        query += f"- {attr['name']}: {attr['description']} (Mood: {attr['mood']})\n"

    query += f"\nNow, generate a detailed {days}-day itinerary in this format:\n"
    query += "Day 1 : Weather: <weather condition and temperature>.\n"
    query += "Breakfast [8 AM - 9 AM]: <Breakfast place suggestion with name>\n"
    query += "Morning [9 AM - 12 PM]: <Activity details>\n"
    query += "Lunch [12:30 PM - 2 PM]: <Meal suggestion with restaurant name>\n"
    query += "Afternoon [2 PM - 5 PM]: <Activity details>\n"
    query += "Evening [5 PM - 7 PM]: <Relaxing or optional activity>\n"
    query += "Dinner [7:30 PM - 9 PM]: <Dinner place suggestion with name.Do not give ny links>\n\n"
    query += "Use a friendly and informative tone. Do not include hashtags or special characters. Plain text only.\n"
    query += "At the end of each day, include a clearly labeled paragraph titled '🚨 Travel Safety Tips' with practical safety advice for that day's locations (e.g., avoid heat exposure, beware of crowded areas, local emergency numbers, etc.)."

    return query

# ========== TRANSLATION & TTS ==========
def translate_to_kannada(text):
    try:
        cleaned_text = text.strip()
        translator = Translator(to_lang="kn")
        translated = translator.translate(cleaned_text)
        return translated
    except Exception as e:
        return f"[Translation error: {e}]"

def text_to_speech_kannada(text):
    try:
        tts = gTTS(text=text, lang='kn')
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        return audio_bytes
    except Exception as e:
        st.error(f"Text-to-Speech error: {e}")
        return None

# ========== UI COMPONENTS ==========
# Initialize session state variables
if "page" not in st.session_state:
    st.session_state.page = "home"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "show_auth" not in st.session_state:
    st.session_state.show_auth = False
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"




# Instead, let's create navbar using Streamlit widgets for reliable interaction:
def render_navbar_streamlit(): 
    col1, col2, col3 = st.columns([6, 1, 2])
    with col1:
        st.markdown('<h1 style="color:#205781; font-size: 75px; margin: 0;">Smart Wander</h1>', unsafe_allow_html=True)
        st.markdown(
                """
                <style>
                .navbar {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    background-color: #f0f2f6;
                    padding: 10px 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }
                .navbar-logout-btn{
                background-color: transparent !important;
                color: white !important;
                border: 1px solid rgba(255,255,255,0.3) !important;
                padding: 4px 10px !important;
                border-radius: 4px !important;
                font-size: 12px !important;
                margin-left: 10px !important;
                transition: all 0.3s ease !important;
            }
            .navbar-logout-btn:hover {
                background-color: rgba(255,255,255,0.1) !important;
                border-color: rgba(255,255,255,0.5) !important;
                transform: none !important;
            }
                </style>
                """,
                unsafe_allow_html=True
            )

    st.markdown('<div class="navbar">', unsafe_allow_html=True)
    with col3:
        
        current_page = st.session_state.get("page", "home")

        if current_page == "home":
            if st.button("Get Started!", key="navbar_account_btn"):
                st.markdown("""
                <style>
                    div.stButton > button.navbar_account_btn {
                        font-size: 18px !important;
                        padding: 12px 28px !important;
                        border-radius: 8px !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                st.session_state.show_auth = not st.session_state.get("show_auth", False)

        # Show Logout on all pages except landing and auth
        if current_page not in ["home", "account_auth_page"]:
            if st.button("Logout", key="navbar_logout_btn"):
                st.session_state.logged_in = False
                st.session_state.user_email = None
                st.session_state.page = "home"
                st.rerun()

        if current_page not in ["home", "account_auth_page","dashboard_page"]:
            if st.button("Dashboard", key="navbar_dashboard_btn"):
                st.session_state.page = "dashboard_page"
                st.rerun()



def landing_page():
    
    st.markdown(
        """
        <style>
        .landing-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 80px 24px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #205781;
            background: linear-gradient(rgba(246,248,213,0.85), rgba(246,248,213,0.85)), url('https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1350&q=80') no-repeat center center fixed;
            background-size: cover;
            min-height: 75vh;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 40px;
        }
        .landing-container h1 {
            font-size: 48px;
            font-weight: 800;
            margin-bottom: 16px;
        }
        .landing-container h2 {
            font-size: 22px;
            font-weight: 400;
            margin-bottom: 24px;
            max-width: 800px;
        }
        .features {
            display: flex;
            justify-content: center;
            gap: 32px;
            margin-top: 24px;
            flex-wrap: wrap;
            max-width: 900px;
        }
        .feature-card {
            background: white;
            border-radius: 8px;
            padding: 24px;
            box-shadow: 0 4px 6px rgb(0 0 0 / 0.1);
            max-width: 280px;
            text-align: left;
            color: #205781;
        }
        .feature-card h3 {
            font-size: 20px;
            margin-bottom: 12px;
            font-weight: 700;
        }
        .feature-card p {
            font-size: 16px;
            font-weight: 400;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="landing-container">
            <h1>Discover Karnataka with Smart Wander</h1>
            <h2>Your intelligent travel companion for personalized itineraries, seamless translations, and unforgettable experiences.</h2>
            <div class="features">
                <div class="feature-card">
                    <h3>Itinerary Generator</h3>
                    <p>Create personalized daily travel plans with recommended attractions, restaurants, and safety tips.</p>
                </div>
                <div class="feature-card">
                    <h3>Language Translator</h3>
                    <p>Translate English to Kannada instantly with audio playback to help you communicate.</p>
                </div>
                <div class="feature-card">
                    <h3>Travel Tips</h3>
                    <p>Get real-time weather forecasts and essential safety advice for each destination.</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # Show login/signup only when toggled
    if st.session_state.get("show_auth", False):
        st.markdown("---")  # horizontal separator
        account_auth_page()

def account_auth_page():
    st.markdown("<h3 style='text-align:center;'>Welcome to Smart Wander</h3>", unsafe_allow_html=True)

    # Initialize state variables
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"
    if "show_auth" not in st.session_state:
        st.session_state.show_auth = False

    # Navbar toggle button
    if st.session_state.show_auth:
        # Centered login/signup buttons in three columns
        col_a, col_b, col_c = st.columns([2,1, 2])
        with col_a:
            st.write("")  # spacer
        with col_b:
            login_col, or_col, signup_col = st.columns([1, 1, 1])
            with login_col:
                if st.button("Login"):
                    st.session_state.auth_mode = "login"
            with or_col:
                st.markdown("<p style='text-align:center;'>or</p>", unsafe_allow_html=True)
            with signup_col:
                if st.button("Signup"):
                    st.session_state.auth_mode = "signup"
        with col_c:
            st.write("")  # spacer

        # Centered form inputs
        form_col_left, form_col_center, form_col_right = st.columns([2, 3, 2])
        with form_col_center:
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")

            if st.session_state.auth_mode == "signup":
                confirm_password = st.text_input("Confirm Password", type="password")
                if st.button("Create Account"):
                    if not email or not password or not confirm_password:
                        st.warning("Please fill in all fields.")
                    elif password != confirm_password:
                        st.warning("Passwords do not match.")
                    else:
                        try:
                            if users_collection.find_one({"email": email}):
                                st.error("Email already registered.")
                            else:
                                create_user(email, password)
                                st.success(f"Account created and logged in as {email}")
                                st.session_state["logged_in"] = True
                                st.session_state["user_email"] = email
                                st.session_state.page = "dashboard_page"
                                st.rerun()
                        except Exception as e:
                            st.error(f"Signup error: {e}")

            else:  # LOGIN MODE
                if st.button("Login Now"):
                    if not email or not password:
                        st.warning("Please enter both email and password.")
                    elif authenticate_user(email, password):
                        st.session_state["logged_in"] = True
                        st.session_state["user_email"] = email
                        st.success(f"Logged in as {email}")
                        st.session_state.page = "dashboard_page"
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")


        

def dashboard_page():
    st.markdown(
        """
        <style>
        /* Container that holds buttons */
        .dashboard-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: 50px;
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1f3a5f;
        }

        /* Override Streamlit's button wrapper */
        div.stButton > button {
            font-size: 100px !important;
            color:white;
            padding: 40px 60px !important;
            width: 100% !important;
            border-radius: 20px !important;
            background-color: #e6f2ff !important;
            color: #1f3a5f !important;
            font-weight: 1000 !important;
            text-transform: uppercase; 
            text-shadow: 5px 5px 5px rgba(0,0,0,0.15);
            box-shadow: 0 6px 10px rgba(0,0,0,0.15) !important;
            transition: background-color 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease !important;
        }

        div.stButton > button:hover {
            background-color: #d9eefe !important;
            box-shadow: 0 12px 24px rgba(0,0,0,0.2) !important;
            transform: translateY(-3px) !important;
            cursor: pointer !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
    "<h2 style='text-align: center; font-weight: bold;font-style:italic'>Welcome!</h2>",
    unsafe_allow_html=True
        )

    if st.button(" Itinerary Generator", key="go_itinerary"):
        st.session_state["page"] = "itinerary"
        st.rerun()

    st.write("")  # small gap

    if st.button(" Language Translator", key="go_translator"):
        st.session_state["page"] = "translator"
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

def itinerary_page():
    # Create two columns with appropriate spacing
    left_col, right_col = st.columns([5, 5], gap="large")
    
    with st.container(border=True):
        with left_col:
            
                st.subheader("Plan Your Trip!")
                st.markdown("<br>", unsafe_allow_html=True)
                # Destination selection with emoji
                destination = st.selectbox(
                    " Select your destination",
                    options=list(attractions.keys()),
                    index=0,
                    key="destination_select"
                )

                mood_options_with_emojis = [
                    "Spiritual & Cultural",
                    "Nature & Relaxation",
                    "History & Heritage",
                    "Fun & Entertainment",
                    "Adventurous & Outdoors",
                    " None"]
               
                mood = st.selectbox(
                    "Select your preferred travel style:",
                    options=mood_options_with_emojis,
                    index=0,
                    key="mood_select"
                )
                
                
                # Date selection
                start_date = st.date_input(
                    "Select the start date of your trip:",
                    key="start_date_select"
                )

                days_input = st.slider(
                    "Number of days",
                    min_value=1,
                    max_value=5,  # Increased max days to 7
                    value=2,
                    key="days_slider"
                )

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Generate Itinerary", use_container_width=True, type="primary"):
                    with st.spinner("Generating your itinerary..."):
                        query = create_itinerary_query(
                            attractions,
                            destination,
                            None if mood == "None" else mood,
                            days_input
                        )
                        response = co.chat(model="command-r", message=query, temperature=0.7)
                        st.session_state["generated"] = True
                        st.session_state["itinerary_text"] = response.text
                        st.session_state["destination"] = destination
                        st.rerun()

    with st.container(border=True):
        with right_col:
            if st.session_state.get("generated"):
                st.subheader("Your Personalized Itinerary!")

                # Parse the itinerary into day-wise blocks
                itinerary_days = []
                current_day = []
                for line in st.session_state.itinerary_text.split('\n'):
                    if line.startswith("Day "):
                        if current_day:
                            itinerary_days.append('\n'.join(current_day))
                        current_day = [line]
                    elif line.strip():
                        current_day.append(line)
                if current_day:
                    itinerary_days.append('\n'.join(current_day))

                # CSS styles
                st.markdown("""
                    <style>
                    .activity-card {
                        background-color: #f8f9fa;
                        padding: 15px;
                        margin-bottom: 10px;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                        border: 1px solid #e9ecef;
                    }
                    .activity-title {
                        font-weight: bold;
                        color: #2c3e50;
                        margin-bottom: 8px;
                    }
                    </style>
                """, unsafe_allow_html=True)

                for i, day_content in enumerate(itinerary_days, 1):
                    day_title = f"Day {i}" if not day_content.startswith("Day ") else day_content.split('\n')[0]

                    with st.expander(f" {day_title}", expanded=i == 1):
                        lines = day_content.split('\n')[1:]
                        current_card = []
                        safety_tips_body = ""

                        for line in lines:
                            if not line.strip():
                                continue

                            if line.startswith("🚨 Travel Safety Tips:"):
                                if current_card:
                                    title, details = current_card[0], current_card[1:]
                                    title_html = f"<div class='activity-title'>{html.escape(title.strip())}</div>"
                                    details_html = "<br>".join([html.escape(d.strip()) for d in details])
                                    st.markdown(
                                        f"<div class='activity-card'>{title_html}<div>{details_html}</div></div>",
                                        unsafe_allow_html=True
                                    )
                                    current_card = []

                                safety_tips_body = html.escape(line.replace("🚨 Travel Safety Tips:", "").strip())

                            elif re.match(r"^[A-Za-z].*?:", line):
                                if current_card:
                                    title, details = current_card[0], current_card[1:]
                                    title_html = f"<div class='activity-title'>{html.escape(title.strip())}</div>"
                                    details_html = "<br>".join([html.escape(d.strip()) for d in details])
                                    st.markdown(
                                        f"<div class='activity-card'>{title_html}<div>{details_html}</div></div>",
                                        unsafe_allow_html=True
                                    )
                                current_card = [line]
                            else:
                                current_card.append(line)

                        if current_card:
                            title, details = current_card[0], current_card[1:]
                            title_html = f"<div class='activity-title'>{html.escape(title.strip())}</div>"
                            details_html = "<br>".join([html.escape(d.strip()) for d in details])
                            st.markdown(
                                f"<div class='activity-card'>"
                                f"<div class='activity-title' style='color:#205781; font-size:18px; padding:6px 10px; border-radius:5px;'>"
                                f"{html.escape(title.strip())}</div>"
                                f"<div>{details_html}</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )

                        if safety_tips_body:
                            st.markdown(
                                f"""
                                <div class='activity-card'>
                                    <div class='activity-title'>🚨 Travel Safety Tips</div>
                                    <div style="color: #343a40; font-size: 14px; line-height: 1.6; padding-top: 6px;">
                                        {safety_tips_body}
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                # 🏨 Recommended stays section
                with st.expander(" View Recommended Stays", expanded=False):
                    top_stays = get_top_stays(st.session_state["destination"])
                    for stay in top_stays:
                        st.markdown(stay, unsafe_allow_html=True)
                # ✅ Personalization section
                personalize = st.button(" Want to personalize the itinerary?")
                if personalize:
                    st.session_state.personalize_mode = True

                    if st.session_state.get("personalize_mode", False):
                        available_places = [attr["name"] for attr in attractions.get(st.session_state["destination"], [])]
                        selected_places = st.multiselect("Select places to include in your itinerary", options=available_places)

                    if selected_places:
                        if st.button("Update Itinerary"):
                            update_query = create_itinerary_query(
                                attractions,
                                st.session_state["destination"],
                                mood if mood else None,
                                days_input,
                                selected_places
                            )
                            update_response = co.chat(model="command-r", message=update_query, temperature=0.7)
                            st.session_state.itinerary_text = update_response.text
                            st.success("✅ Itinerary updated successfully!")
                            st.rerun()

                

                # 💾 Save itinerary section (only ONCE)
                with st.container(border=True):
                    if st.button(" Download as PDF", use_container_width=True):
                        # Your PDF logic here...
                        st.toast("PDF generated successfully!", icon="✅")

            

           
            else:
                with st.container(border=True):
                    st.subheader("Your Itinerary Is on a Coffee Break....")
                    st.markdown("""
                    Hit **Generate Itinerary** to wake it up!

                    **Here's what you'll get once it's caffeinated:**
                    -  A daily plan tailored to your vibe  
                    -  Safety tips to keep it fun, not frantic
                    """)


                    # Create a Folium map centered at Bangalore (example coordinates)
                    m = folium.Map(location=[12.9716, 77.5946], zoom_start=10)

                    # Display the interactive map smaller, similar to image size
                    st_folium(m, width=800, height=320)


def translator_page():
    st.markdown(
        """
        <style>
        .input-box, .output-box {
            background: #f0faff;
            padding: 24px;
            border-radius: 16px;
            font-size: 22px;
            font-weight: 600;
            color: #1f3a5f;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .translate-button {
            font-size: 20px !important;
            font-weight: bold !important;
            padding: 14px 24px !important;
            border-radius: 12px !important;
            background-color: #205781 !important;
            color: #fff !important;
            width: 100% !important;
        }
        .translate-button:hover {
            background-color: #163d54 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<h2 style='text-align:center;'> ENGLISH TO KANNADA TRANSLATOR </h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 3], gap="large")

    with col1:
        st.markdown("####  Input Text")
        #st.markdown("<br><br>", unsafe_allow_html=True)
        user_input = st.text_area("", height=250, key="translator_input")

        st.markdown("<br>", unsafe_allow_html=True)
        translate_clicked = st.button("TRANSLATE TO KANNADA", key="translate_btn", use_container_width=True)

    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        translated_box = st.empty()
        st.markdown("<br><br>", unsafe_allow_html=True)
        audio_box = st.empty()

    if translate_clicked:
        if user_input.strip():
            kannada_output = translate_to_kannada(user_input)

            translated_box.markdown(
                f"""
                <div class="output-box">
                    <b>TRANSLATED TEXT:</b><br><br>{kannada_output}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<br><br>", unsafe_allow_html=True)

            audio_file = text_to_speech_kannada(kannada_output)
            if audio_file:
                audio_box.markdown("🔊 <b>LISTEN IN KANNADA:</b>", unsafe_allow_html=True)
                audio_box.audio(audio_file, format="audio/mp3")
        else:
            st.warning("⚠️ Please enter some text to translate.")


def main():
    render_navbar_streamlit()

    if st.session_state.page == "home":
        landing_page()
    elif st.session_state.page == "login_signup":
        account_auth_page()
    elif st.session_state.page == "dashboard_page":
        dashboard_page()
    elif st.session_state.page == "itinerary":
        itinerary_page()
    elif st.session_state["page"] == "translator":
            translator_page()

# 🔽 Run main
if __name__ == "__main__":
    main()