import streamlit as st
import pandas as pd
import time
import random
import streamlit.components.v1 as components
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Scrape That!", layout="wide")

# Initialize Session States
if "df_result" not in st.session_state:
    st.session_state.df_result = None
if "run_scraping" not in st.session_state:
    st.session_state.run_scraping = False

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
    </style>
""", unsafe_allow_html=True)

# --- DIALOGS ---
@st.dialog("Support the Dev ☕")
def bmac_start_dialog():
    components.html("""
        <div class="tenor-gif-embed" data-postid="16868093837531698009" data-share-method="host" data-aspect-ratio="1" data-width="100%">
            <a href="https://tenor.com/view/transparent-coffee-work-drink-penguin-gif-16868093837531698009">Transparent Coffee Sticker</a> from <a href="https://tenor.com/search/transparent-stickers">Transparent Stickers</a>
        </div>
        <script type="text/javascript" async src="https://tenor.com/embed.js"></script>
    """, height=350)
    st.markdown("Let's be honest: maintaining a scraper is a game of cat and mouse, and debugging Selenium requires a steady stream of caffeine. If this tool saved you hours of manual copy-pasting or helped you win your Fantasy Football league, consider fueling my next coding session. I can't scrape coffee beans (yet), so I have to buy them.")
    if st.button("Close & Start Scraping", use_container_width=True):
        st.session_state.run_scraping = True
        st.rerun()

@st.dialog("Enjoy your data! ☕")
def bmac_download_dialog():
    components.html("""
        <div class="tenor-gif-embed" data-postid="16868093837531698009" data-share-method="host" data-aspect-ratio="1" data-width="100%">
            <a href="https://tenor.com/view/transparent-coffee-work-drink-penguin-gif-16868093837531698009">Transparent Coffee Sticker</a> from <a href="https://tenor.com/search/transparent-stickers">Transparent Stickers</a>
        </div>
        <script type="text/javascript" async src="https://tenor.com/embed.js"></script>
    """, height=350)
    st.markdown("Let's be honest: maintaining a scraper is a game of cat and mouse, and debugging Selenium requires a steady stream of caffeine. If this tool saved you hours of manual copy-pasting or helped you win your Fantasy Football league, consider fueling my next coding session.")
    if st.button("Close", use_container_width=True):
        st.rerun()

# --- HEADER ---
logo_url = "https://cdn.brandfetch.io/idmNg5Llwe/w/400/h/400/theme/dark/icon.jpeg?c=1dxbfHSJFAPEGdCLU4o5B"
st.markdown(f'<div class="header-container"><img src="{logo_url}" class="header-logo"><h1 class="header-title">Scrape That!</h1></div>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Select leagues, seasons, and stats to download the complete dataset.</p>', unsafe_allow_html=True)

# --- CONFIGURATION ---
st.write("---")
st.header("Configuration")

leagues_opt = ['Serie A', 'Premier League', 'Liga', 'Bundesliga', 'Ligue 1']
seasons_opt = [f"{str(i).zfill(2)}-{str(i+1).zfill(2)}" for i in range(25, 16, -1)]
stats_opt = ['standard', 'gk', 'gk_advanced', 'shooting', 'passing', 'pass_types', 'sca & gca', 'defense', 'possession', 'playing time', 'miscellaneous']

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Leagues")
    t_l = st.toggle("Select All Leagues")
    sel_leagues = st.multiselect("L", leagues_opt, default=leagues_opt if t_l else [], label_visibility="collapsed")
with col2:
    st.subheader("Seasons")
    t_s = st.toggle("Select All Seasons")
    sel_seasons = st.multiselect("S", seasons_opt, default=seasons_opt if t_s else [], label_visibility="collapsed")
with col3:
    st.subheader("Stats")
    t_st = st.toggle("Select All Stats")
    sel_stats = st.multiselect("St", stats_opt, default=stats_opt if t_st else [], label_visibility="collapsed")

if st.button("Start Scraping", use_container_width=True):
    if not sel_leagues or not sel_seasons or not sel_stats:
        st.warning("Please select at least one league, season, and statistic.")
    else:
        bmac_start_dialog()

st.write("---")

# --- SCRAPING LOGIC ---
def scrape_fbref_merged(leagues, seasons, stat_types):
    # (Keeping your original Selenium logic inside here...)
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    league_map = {'Serie A': {'id': '11', 'slug': 'Serie-A'}, 'Premier League': {'id': '9', 'slug': 'Premier-League'}, 'Liga': {'id': '12', 'slug': 'La-Liga'}, 'Bundesliga': {'id': '20', 'slug': 'Bundesliga'}, 'Ligue 1': {'id': '13', 'slug': 'Ligue-1'}}
    type_map = {'standard': {'url': 'stats', 'table_id': 'stats_standard'}, 'gk': {'url': 'keepers', 'table_id': 'stats_keeper'}, 'gk_advanced': {'url': 'keepersadv', 'table_id': 'stats_keeper_adv'}, 'shooting': {'url': 'shooting', 'table_id': 'stats_shooting'}, 'passing': {'url': 'passing', 'table_id': 'stats_passing'}, 'pass_types': {'url': 'passing_types', 'table_id': 'stats_passing_types'}, 'sca & gca': {'url': 'gca', 'table_id': 'stats_gca'}, 'defense': {'url': 'defense', 'table_id': 'stats_defense'}, 'possession': {'url': 'possession', 'table_id': 'stats_possession'}, 'playing time': {'url': 'playingtime', 'table_id': 'stats_playing_time'}, 'miscellaneous': {'url': 'misc', 'table_id': 'stats_misc'}}
    id_cols = ['Player', 'Nation', 'Pos', 'Squad', 'Age', 'Born']

    options = Options()
    options.add_argument("--headless")
    options.binary_location = "/usr/bin/chromium"
    
    try:
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        merged_data_storage = {}
        total = len(leagues) * len(seasons) * len(stat_types)
        count = 0

        for l in leagues:
            for s in seasons:
                for st_t in stat_types:
                    count += 1
                    progress_bar.progress(count/total)
                    status_text.text(f"Scraping {l} {s}...")
                    
                    # URL construction...
                    y = s.split('-')
                    if s == '25-26': url = f"https://fbref.com/en/comps/{league_map[l]['id']}/{type_map[st_t]['url']}/{league_map[l]['slug']}-Stats"
                    else: url = f"https://fbref.com/en/comps/{league_map[l]['id']}/20{y[0]}-20{y[1]}/{type_map[st_t]['url']}/20{y[0]}-20{y[1]}-{league_map[l]['slug']}-Stats"
                    
                    try:
                        driver.get(url)
                        time.sleep(3)
                        df = pd.read_html(driver.page_source, attrs={'id': type_map[st_t]['table_id']})[0]
                        # Data Cleaning...
                        if isinstance(df.columns, pd.MultiIndex): df.columns = [c[1] if "Unnamed" in c[0] else f"{c[0]}_{c[1]}" for c in df.columns]
                        df = df[df['Player'] != 'Player'].drop_duplicates(subset=['Player', 'Squad'])
                        df = df.rename(columns={c: f"{st_t}_{c}" for c in df.columns if c not in id_cols})
                        
                        if (l,s) not in merged_data_storage: merged_data_storage[(l,s)] = df
                        else: merged_data_storage[(l,s)] = pd.merge(merged_data_storage[(l,s)], df, on=[c for c in id_cols if c in df.columns], how='outer')
                    except: continue
        
        driver.quit()
        final_dfs = [df.assign(League=lk, Season=sk) for (lk, sk), df in merged_data_storage.items()]
        return pd.concat(final_dfs, ignore_index=True) if final_dfs else pd.DataFrame()
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# --- TRIGGER SCRAPING ---
if st.session_state.run_scraping:
    with st.spinner("Downloading data..."):
        res = scrape_fbref_merged(sel_leagues, sel_seasons, sel_stats)
        st.session_state.df_result = res
        st.session_state.run_scraping = False # Reset flag
    st.rerun()

# --- DISPLAY RESULTS ---
if st.session_state.df_result is not None:
    df = st.session_state.df_result
    if not df.empty:
        st.success("Scraping completed!")
        st.write(f"Rows: {len(df)}")
        st.dataframe(df.head(10))
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name="fbref_data.csv",
            mime="text/csv",
            on_click=bmac_download_dialog # Trigger popup on click
        )
    else:
        st.error("No data found. Please try different filters.")