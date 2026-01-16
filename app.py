import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="Scrape That!", layout="centered")

# 2. Custom CSS for Black & White Theme and Centering
st.markdown("""
    <style>
    /* Force Black and White / Grayscale */
    :root {
        --primary-color: #000000;
        --background-color: #ffffff;
        --secondary-background-color: #f0f0f0;
        --text-color: #000000;
        --font: sans-serif;
    }
    
    /* Grayscale filter for toggles and buttons to remove default Streamlit colors */
    .stToggle, .stCheckbox, .stButton > button {
        filter: grayscale(100%);
    }

    /* Centering the Header */
    .header-container {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: center;
        margin-bottom: 10px;
    }
    
    .title-text {
        font-size: 3rem;
        font-weight: bold;
        margin-left: 15px;
        color: black;
        line-height: 1;
    }

    .subtitle-text {
        text-align: center;
        font-size: 1.2rem;
        font-weight: normal;
        color: #333;
        margin-top: -10px;
        margin-bottom: 30px;
    }

    /* Center the configuration area */
    div[data-testid="stVerticalBlock"] > div {
        align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Header Section (Logo + Title)
# Using columns to center align the image and text effectively
col_spacer_l, col_content, col_spacer_r = st.columns([1, 4, 1])

with col_content:
    # We use HTML to ensure the logo height matches the text visually
    st.markdown(f"""
        <div class="header-container">
            <img src="https://cdn.brandfetch.io/idmNg5Llwe/w/400/h/400/theme/dark/icon.jpeg?c=1dxbfHSJFAPEGdCLU4o5B" style="height: 60px; width: auto;">
            <span class="title-text">Scrape That!</span>
        </div>
        <p class="subtitle-text">Advanced football data extraction tool</p>
    """, unsafe_allow_html=True)

st.divider()

# 4. Configuration Section (Centered)
st.markdown("<h3 style='text-align: center;'>Configuration</h3>", unsafe_allow_html=True)

# Using a centered column for the form controls
c1, c2, c3 = st.columns([1, 2, 1])

with c2:
    # Select All Logic
    select_all = st.checkbox("Select All Leagues", value=False)
    
    st.write("Select Leagues:")
    # Define available leagues
    leagues_list = ["Premier League", "Serie A", "La Liga", "Bundesliga", "Ligue 1"]
    
    selected_leagues = []
    
    # Toggle Buttons
    for league in leagues_list:
        # If select_all is True, the individual toggles default to True. 
        # Otherwise they follow their own state (defaulting to False initially).
        is_on = st.toggle(league, value=select_all)
        if is_on:
            selected_leagues.append(league)

    st.write("") # Spacer
    
    # Seasons Selection (25/26 descending)
    seasons = ["25/26", "24/25", "23/24", "22/23", "21/22", "20/21"]
    selected_season = st.selectbox("Select Season", seasons, index=None, placeholder="Choose a season...")

# 5. Logic to show data (Placeholder)
if selected_leagues and selected_season:
    st.divider()
    st.markdown(f"<h4 style='text-align: center;'>Data for {selected_season}</h4>", unsafe_allow_html=True)
    
    # Mock Data Creation
    data = {
        'League': [selected_leagues[i % len(selected_leagues)] for i in range(15)],
        'Team': [f'Team {i+1}' for i in range(15)],
        'Matches': [38] * 15,
        'Points': [90 - (i*3) for i in range(15)]
    }
    df = pd.DataFrame(data)

    # Show head(10) as requested
    st.dataframe(df.head(10), use_container_width=True)

elif select_all or (selected_leagues and not selected_season):
     st.info("Please select a season to view data.")