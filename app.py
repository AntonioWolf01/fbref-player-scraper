import streamlit as st
import pandas as pd
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Scrape That!", layout="wide")

# --- CUSTOM CSS & DESIGN FIXES ---
st.markdown("""
    <style>
    /* Import Fonts */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;400;500;700&family=Playfair+Display:ital,wght@1,600&display=swap');

    /* 1. GLOBAL RESET - Force Text Color to Gainsboro everywhere */
    html, body, [class*="css"], .stMarkdown, .stText, p {
        font-family: 'DM Sans', sans-serif !important;
        color: gainsboro !important;
    }

    /* 2. BACKGROUND - Darker overlay to ensure text readability */
    .stApp {
        background-image: linear-gradient(rgba(20, 20, 20, 0.85), rgba(20, 20, 20, 0.95)), url("https://i.postimg.cc/TP5LtjtN/Gemini-Generated-Image-k7c480k7c480k7c4.png");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }

    /* 3. TITLE STYLING - High Contrast White */
    .main-title {
        font-family: 'Playfair Display', serif !important;
        font-style: italic;
        font-weight: 600;
        font-size: 5rem !important;
        text-align: center;
        color: #ffffff !important; /* Force White */
        margin-bottom: 0px;
        text-shadow: 4px 4px 8px rgba(0,0,0,0.9); /* Drop shadow for pop */
    }

    .subtitle {
        text-align: center;
        font-size: 1.2rem;
        color: #dddddd !important;
        margin-bottom: 40px;
        font-weight: 400;
    }

    /* 4. EXPANDER HEADERS - Fix the "White Bar" issue */
    .streamlit-expanderHeader {
        background-color: #2b2b2b !important; /* Dark Grey Background */
        color: white !important;
        border: 1px solid #444;
        border-radius: 8px;
    }
    
    /* Fix the arrow icon color in expanders */
    .streamlit-expanderHeader svg {
        fill: white !important; 
        color: white !important;
    }

    /* 5. EXPANDER CONTENT & WIDGET LABELS - Fix "Invisible Text" */
    div[data-testid="stExpander"] {
        background-color: rgba(30, 30, 30, 0.5); /* Semi-transparent backing */
        border-radius: 0 0 8px 8px;
        border: 1px solid #444;
        border-top: none;
        padding: 10px;
    }

    /* Force Toggle and Checkbox Labels to be visible */
    label[data-testid="stWidgetLabel"] p, 
    div[data-testid="stMarkdownContainer"] p {
        color: #e0e0e0 !important; /* Bright light grey */
        font-size: 16px !important;
    }

    /* 6. BUTTON STYLING */
    div.stButton > button {
        width: 100%;
        background-color: gainsboro;
        color: #1e1e1e !important; /* Dark text on light button */
        font-weight: bold;
        border: none;
        padding: 15px;
        font-size: 18px;
        border-radius: 8px;
        transition: 0.3s;
        margin-top: 20px;
    }
    div.stButton > button:hover {
        background-color: #ffffff;
        box-shadow: 0px 0px 15px rgba(255,255,255,0.3);
    }
    
    /* Hide the Streamlit main menu and footer for a cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<h1 class="main-title">Scrape That!</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Select leagues, seasons, and statistics to download the complete dataset.</p>', unsafe_allow_html=True)

# --- CONSTANTS ---
LEAGUES_OPT = ['Serie A', 'Premier League', 'Liga', 'Bundesliga', 'Ligue 1']
SEASONS_OPT = [f"{str(i).zfill(2)}-{str(i+1).zfill(2)}" for i in range(17, 26)]
STATS_OPT = [
    'standard', 'gk', 'gk_advanced', 'shooting', 'passing', 
    'pass_types', 'sca & gca', 'defense', 'possession', 
    'playing time', 'miscellaneous'
]

# --- HELPER FOR SELECTION ---
def render_selection_section(title, options, key_prefix):
    """Renders an expander with Select All and Toggles."""
    selected_items = []
    # Using st.expander directly. The CSS above handles the styling.
    with st.expander(title, expanded=True):
        # Select All Checkbox
        select_all = st.checkbox(f"Select All {title}", key=f"all_{key_prefix}")
        
        st.markdown("---") # Visual separator
        
        # Determine specific selection state
        current_selection = options if select_all else []
        
        # Grid layout for toggles
        cols = st.columns(3)
        for i, option in enumerate(options):
            col = cols[i % 3]
            with col:
                # If select_all is True, the toggle defaults to True. 
                # Note: Real-time sync between "Select All" and individual toggles is tricky in Streamlit 
                # without Session State callbacks, but this is the cleanest visual implementation.
                is_checked = st.toggle(option, value=select_all, key=f"{key_prefix}_{option}")
                if is_checked:
                    selected_items.append(option)
                    
    return selected_items

# --- CONFIGURATION (CENTERED) ---
c1, c2, c3 = st.columns([1, 6, 1]) # Adjusted width for better centering
with c2:
    selected_leagues = render_selection_section("Leagues", LEAGUES_OPT, "lg")
    selected_seasons = render_selection_section("Seasons", SEASONS_OPT, "sn")
    selected_stats = render_selection_section("Statistics", STATS_OPT, "st")
    
    start_btn = st.button("START SCRAPING")

# --- SCRAPING ENGINE ---
def scrape_fbref_merged(leagues, seasons, stat_types):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    league_map = {
        'Serie A': {'id': '11', 'slug': 'Serie-A'},
        'Premier League': {'id': '9', 'slug': 'Premier-League'},
        'Liga': {'id': '12', 'slug': 'La-Liga'},
        'Bundesliga': {'id': '20', 'slug': 'Bundesliga'},
        'Ligue 1': {'id': '13', 'slug': 'Ligue-1'}
    }
    
    type_map = {
        'standard': {'url': 'stats', 'table_id': 'stats_standard'},
        'gk': {'url': 'keepers', 'table_id': 'stats_keeper'},
        'gk_advanced': {'url': 'keepersadv', 'table_id': 'stats_keeper_adv'},
        'shooting': {'url': 'shooting', 'table_id': 'stats_shooting'},
        'passing': {'url': 'passing', 'table_id': 'stats_passing'},
        'pass_types': {'url': 'passing_types', 'table_id': 'stats_passing_types'},
        'sca & gca': {'url': 'gca', 'table_id': 'stats_gca'},
        'defense': {'url': 'defense', 'table_id': 'stats_defense'},
        'possession': {'url': 'possession', 'table_id': 'stats_possession'},
        'playing time': {'url': 'playingtime', 'table_id': 'stats_playing_time'},
        'miscellaneous': {'url': 'misc', 'table_id': 'stats_misc'}
    }

    id_cols = ['Player', 'Nation', 'Pos', 'Squad', 'Age', 'Born']

    # --- SELENIUM SETUP ---
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Try to locate chromium/driver automatically or use system defaults
    options.binary_location = "/usr/bin/chromium"
    
    driver = None
    try:
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        # Fallback for local testing if linux paths fail
        try:
             driver = webdriver.Chrome(options=options)
        except:
             st.error(f"Driver Error: {e}")
             return pd.DataFrame()

    merged_data_storage = {}
    
    total_steps = len(leagues) * len(seasons) * len(stat_types)
    current_step = 0

    try:
        for league in leagues:
            if league not in league_map: continue
            comp_id = league_map[league]['id']
            comp_slug = league_map[league]['slug']
            
            for season in seasons:
                group_key = (league, season)
                
                for s_type in stat_types:
                    current_step += 1
                    if total_steps > 0:
                        progress_val = min(current_step / total_steps, 1.0)
                        progress_bar.progress(progress_val)
                    
                    if s_type not in type_map: continue
                    
                    status_text.markdown(f"<span style='color:gainsboro'>**Processing:** {league} | Season {season} | Table: *{s_type}*</span>", unsafe_allow_html=True)
                    
                    url_slug = type_map[s_type]['url']
                    table_id_key = type_map[s_type]['table_id']
                    
                    if season == '25-26': 
                        url = f"https://fbref.com/en/comps/{comp_id}/{url_slug}/{comp_slug}-Stats"
                    else:
                        years = season.split('-')
                        full_year_str = f"20{years[0]}-20{years[1]}"
                        url = f"https://fbref.com/en/comps/{comp_id}/{full_year_str}/{url_slug}/{full_year_str}-{comp_slug}-Stats"
                    
                    try:
                        driver.get(url)
                        time.sleep(random.uniform(2, 4))
                        
                        wait = WebDriverWait(driver, 10)
                        table_selector = f"table[id*='{table_id_key}']"
                        table_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, table_selector)))
                        
                        dfs = pd.read_html(table_element.get_attribute('outerHTML'))
                        if not dfs: continue
                        df = dfs[0]
                        
                        # --- DATA CLEANING ---
                        if isinstance(df.columns, pd.MultiIndex):
                            new_cols = []
                            for col in df.columns:
                                if "Unnamed" in col[0]: new_cols.append(col[1])
                                else: new_cols.append(f"{col[0]}_{col[1]}")
                            df.columns = new_cols

                        if 'Rk' in df.columns:
                            df = df[df['Rk'] != 'Rk']
                            df = df.drop(columns=['Rk'])
                        if 'Matches' in df.columns:
                            df = df.drop(columns=['Matches'])
                        
                        df = df.drop_duplicates(subset=['Player', 'Squad'])
                        
                        cols_to_rename = {col: f"{s_type}_{col}" for col in df.columns if col not in id_cols}
                        df = df.rename(columns=cols_to_rename)

                        if group_key not in merged_data_storage:
                            merged_data_storage[group_key] = df
                        else:
                            existing_cols = merged_data_storage[group_key].columns.tolist()
                            current_cols = df.columns.tolist()
                            merge_on = [c for c in id_cols if c in existing_cols and c in current_cols]
                            
                            if merge_on:
                                merged_data_storage[group_key] = pd.merge(
                                    merged_data_storage[group_key], df, on=merge_on, how='outer'
                                )
                    except Exception as e:
                        print(f"Skipping {league} {season} {s_type}: {e}")
                        continue

    except Exception as main_e:
        st.error(f"Critical Scraping Error: {main_e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        progress_bar.empty()
        status_text.empty()

    final_dfs = []
    for (league, season), df_data in merged_data_storage.items():
        df_data['League'] = league
        df_data['Season'] = season
        final_dfs.append(df_data)
    
    if final_dfs:
        return pd.concat(final_dfs, ignore_index=True)
    return pd.DataFrame()

# --- MAIN EXECUTION ---
if start_btn:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Please select at least one league, one season, and one statistic.")
    else:
        with st.spinner("Connecting to servers and retrieving data..."):
            df_result = scrape_fbref_merged(selected_leagues, selected_seasons, selected_stats)
        
        if not df_result.empty:
            st.success("Scraping Completed Successfully!")
            st.markdown(f"**Total Rows Retrieved:** {len(df_result)}")
            
            st.dataframe(df_result.head(10)) 
            
            csv = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="fbref_data_scraped.csv",
                mime="text/csv"
            )
        else:
            st.error("No data found or an error occurred. Please check your selection.")