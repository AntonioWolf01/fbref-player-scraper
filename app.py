import streamlit as st
import pandas as pd
import time
import random
import streamlit.components.v1 as components
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Scrape That!", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #000000; }
    div.stButton > button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 2px solid #000000 !important;
        border-radius: 5px;
        transition: all 0.3s;
    }
    div.stButton > button p { color: #ffffff !important; }
    div.stButton > button:hover {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
    div.stButton > button:hover p { color: #000000 !important; }
    h1, h2, h3, h4, p { text-align: center; color: #000000 !important; }
    .header-container { display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px; }
    .header-logo { height: 60px; width: 60px; border-radius: 10px; }
    .header-title { font-size: 3.5rem; font-weight: 700; margin: 0; line-height: 1; color: #000000; }
    .subtitle { text-align: center; font-size: 1.1rem; font-weight: 400; color: #333333; margin-top: -10px; margin-bottom: 40px; }
    div[data-testid="stVerticalBlock"] { align-items: center; }
    </style>
""", unsafe_allow_html=True)

# --- BUY ME A COFFEE MODAL ---
@st.dialog("Support the Dev ☕")
def show_bmac_modal():
    # Tenor GIF Implementation
    components.html("""
        <div class="tenor-gif-embed" data-postid="16868093837531698009" data-share-method="host" data-aspect-ratio="1" data-width="100%">
            <a href="https://tenor.com/view/transparent-coffee-work-drink-penguin-gif-16868093837531698009">Transparent Coffee Sticker</a> from <a href="https://tenor.com/search/transparent-stickers">Transparent Stickers</a>
        </div>
        <script type="text/javascript" async src="https://tenor.com/embed.js"></script>
    """, height=350)
    
    st.markdown("""
    **Let's be honest:** maintaining a scraper is a game of cat and mouse, and debugging Selenium requires a steady stream of caffeine. 
    
    If this tool saved you hours of manual copy-pasting or helped you win your Fantasy Football league, consider fueling my next coding session. I can't scrape coffee beans (yet), so I have to buy them.
    """)
    
    if st.button("Close & Continue", use_container_width=True):
        st.rerun()

# --- HEADER SECTION ---
logo_url = "https://cdn.brandfetch.io/idmNg5Llwe/w/400/h/400/theme/dark/icon.jpeg?c=1dxbfHSJFAPEGdCLU4o5B"
st.markdown(f"""
    <div class="header-container">
        <img src="{logo_url}" class="header-logo">
        <h1 class="header-title">Scrape That!</h1>
    </div>
    <p class="subtitle">Select leagues, seasons, and stats to download the complete dataset.</p>
""", unsafe_allow_html=True)

# --- CONFIGURATION ---
st.write("---")
st.header("Configuration")

leagues_opt = ['Serie A', 'Premier League', 'Liga', 'Bundesliga', 'Ligue 1']
seasons_opt = [f"{str(i).zfill(2)}-{str(i+1).zfill(2)}" for i in range(25, 16, -1)]
stats_opt = ['standard', 'gk', 'gk_advanced', 'shooting', 'passing', 'pass_types', 'sca & gca', 'defense', 'possession', 'playing time', 'miscellaneous']

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Leagues")
    toggle_leagues = st.toggle("Select All Leagues")
    selected_leagues = st.multiselect("Select Leagues", leagues_opt, default=leagues_opt if toggle_leagues else [], label_visibility="collapsed")
with col2:
    st.subheader("Seasons")
    toggle_seasons = st.toggle("Select All Seasons")
    selected_seasons = st.multiselect("Select Seasons", seasons_opt, default=seasons_opt if toggle_seasons else [], label_visibility="collapsed")
with col3:
    st.subheader("Stats")
    toggle_stats = st.toggle("Select All Stats")
    selected_stats = st.multiselect("Select Stats", stats_opt, default=stats_opt if toggle_stats else [], label_visibility="collapsed")

st.write("")
start_btn = st.button("Start Scraping", use_container_width=True)
st.write("---")

# --- SCRAPING FUNCTION ---
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

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = "/usr/bin/chromium"
    
    try:
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        st.error(f"Driver startup error: {e}")
        return pd.DataFrame()

    merged_data_storage = {}
    total_steps = len(leagues) * len(seasons) * len(stat_types)
    current_step = 0

    try:
        for league in leagues:
            comp_id = league_map[league]['id']
            comp_slug = league_map[league]['slug']
            for season in seasons:
                group_key = (league, season)
                for s_type in stat_types:
                    current_step += 1
                    progress_bar.progress(min(current_step / total_steps, 0.99))
                    status_text.text(f"Scraping: {league} {season} - {s_type}...")
                    
                    url_slug, table_id_key = type_map[s_type]['url'], type_map[s_type]['table_id']
                    if season == '25-26': url = f"https://fbref.com/en/comps/{comp_id}/{url_slug}/{comp_slug}-Stats"
                    else:
                        y = season.split('-')
                        url = f"https://fbref.com/en/comps/{comp_id}/20{y[0]}-20{y[1]}/{url_slug}/20{y[0]}-20{y[1]}-{comp_slug}-Stats"
                    
                    try:
                        driver.get(url)
                        time.sleep(random.uniform(3, 5))
                        wait = WebDriverWait(driver, 15)
                        table_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"table[id*='{table_id_key}']")))
                        df = pd.read_html(table_element.get_attribute('outerHTML'))[0]
                        
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = [col[1] if "Unnamed" in col[0] else f"{col[0]}_{col[1]}" for col in df.columns]
                        if 'Rk' in df.columns: df = df[df['Rk'] != 'Rk'].drop(columns=['Rk'])
                        if 'Matches' in df.columns: df = df.drop(columns=['Matches'])
                        
                        df = df.drop_duplicates(subset=['Player', 'Squad'])
                        df = df.rename(columns={col: f"{s_type}_{col}" for col in df.columns if col not in id_cols})

                        if group_key not in merged_data_storage: merged_data_storage[group_key] = df
                        else:
                            merge_on = [c for c in id_cols if c in merged_data_storage[group_key].columns and c in df.columns]
                            merged_data_storage[group_key] = pd.merge(merged_data_storage[group_key], df, on=merge_on, how='outer')
                    except: continue
    finally:
        driver.quit()
        progress_bar.empty()
        status_text.empty()

    final_dfs = [df.assign(League=l, Season=s) for (l, s), df in merged_data_storage.items()]
    return pd.concat(final_dfs, ignore_index=True) if final_dfs else pd.DataFrame()

# --- EXECUTION LOGIC ---

# 1. Logic for Start Scraping
if start_btn:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Please select at least one league, one season, and one statistic.")
    else:
        # Trigger the popup
        show_bmac_modal()
        # Set a flag to start scraping after the modal is closed
        st.session_state.ready_to_scrape = True

# Actual Scraping Execution
if st.session_state.get("ready_to_scrape"):
    with st.spinner("Downloading data from Fbref..."):
        df_result = scrape_fbref_merged(selected_leagues, selected_seasons, selected_stats)
        st.session_state.df_result = df_result
        st.session_state.ready_to_scrape = False # Reset flag

# Display Results
if "df_result" in st.session_state and not st.session_state.df_result.empty:
    df_res = st.session_state.df_result
    st.success("Scraping completed!")
    st.write(f"Rows downloaded: {len(df_res)}")
    st.dataframe(df_res.head(10))
    
    csv = df_res.to_csv(index=False).encode('utf-8')
    
    # Logic for Download CSV
    # When user clicks this, the dialog pops up, but the download is handled by the widget
    if st.download_button(
        label="Download CSV",
        data=csv,
        file_name="fbref_data_merged.csv",
        mime="text/csv",
        on_click=show_bmac_modal # This triggers the popup when clicked
    ):
        pass