import streamlit as st
import pandas as pd
import time
import random
import os
import shutil
import undetected_chromedriver as uc
from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Scrape That!", layout="wide")

# Initialize session state for scraping trigger
if "run_scrape" not in st.session_state:
    st.session_state.run_scrape = False

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    
    /* Button Styles */
    div.stButton > button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 2px solid #000000 !important;
        border-radius: 5px;
        transition: all 0.3s;
    }
    
    div.stButton > button p {
        color: #ffffff !important;
    }

    div.stButton > button:hover {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
    
    div.stButton > button:hover p {
        color: #000000 !important;
    }

    h1, h2, h3, h4, p {
        text-align: center;
        color: #000000 !important;
    }
    
    .header-container {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 20px;
        margin-bottom: 10px;
    }
    .header-logo {
        height: 60px;
        width: 60px;
        border-radius: 10px;
    }
    .header-title {
        font-size: 3.5rem;
        font-weight: 700;
        margin: 0;
        line-height: 1;
        color: #000000;
    }
    </style>
""", unsafe_allow_html=True)

# --- BUY ME A COFFEE POPUP ---
@st.dialog("Support the Developer")
def show_coffee_popup():
    # GIF above the text
    col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
    with col_img2:
        st.image("https://media.tenor.com/6heB-WgIU1kAAAAi/transparent-coffee.gif", use_container_width=True)
    
    # Text with Bold emphasis on the last sentence
    st.markdown("""
    Manual data collection is a nightmare I’ve handled so you don't have to. While you enjoy your fresh dataset, remember that this code is powered by high-quality caffeine. 
    
    If 'Scrape That!' provided value to your project, feel free to fuel my next update. **I can't scrape coffee beans, so I have to buy them.**
    """)
    
    # Official Buy Me A Coffee Button
    st.markdown("""
        <div style="display: flex; justify-content: center; margin-bottom: 25px; margin-top: 10px;">
            <a href="https://buymeacoffee.com/antoniolupo" target="_blank">
                <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 180px !important;" >
            </a>
        </div>
    """, unsafe_allow_html=True)
    
    # Action Button to start scraping
    if st.button("Continue without donating & Start Scraping", use_container_width=True):
        st.session_state.run_scrape = True
        st.rerun()

# --- HEADER SECTION ---
logo_url = "https://cdn.brandfetch.io/idmNg5Llwe/w/400/h/400/theme/dark/icon.jpeg?c=1dxbfHSJFAPEGdCLU4o5B"

st.markdown(f"""
    <div class="header-container">
        <img src="{logo_url}" class="header-logo">
        <h1 class="header-title">Scrape That!</h1>
    </div>
    <p style="text-align: center; font-size: 1.1rem; color: #333333; margin-bottom: 40px;">
        Select leagues, seasons, and stats to download the complete dataset.
    </p>
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

# --- SCRAPING FUNCTION (CLOUD FIXED) ---
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

    # --- 1. SETUP VIRTUAL DISPLAY ---
    # Necessary for undetected-chromedriver to run "headless" without being flagged
    display = Display(visible=0, size=(800, 600))
    display.start()

    # --- 2. SETUP DRIVER PATHS ---
    # Copy system chromedriver to a writable location (/tmp) to avoid Permission Denied errors
    system_driver_path = "/usr/bin/chromedriver"
    writable_driver_path = "/tmp/chromedriver"
    
    # Only copy if we haven't already (or if system driver exists)
    if os.path.exists(system_driver_path):
        try:
            shutil.copyfile(system_driver_path, writable_driver_path)
            os.chmod(writable_driver_path, 0o755) # Make executable
        except Exception as e:
            st.error(f"Could not copy driver: {e}")
            display.stop()
            return pd.DataFrame()
    
    # --- 3. INIT UNDETECTED DRIVER ---
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = uc.Chrome(
            options=options,
            driver_executable_path=writable_driver_path, 
            version_main=131 # Optional: Remove if version mismatch occurs
        )
    except Exception as e:
        st.error(f"Driver startup failed: {e}")
        try:
            display.stop()
        except:
            pass
        return pd.DataFrame()

    merged_data_storage = {}
    total_steps = len(leagues) * len(seasons) * len(stat_types)
    current_step = 0

    try:
        for league in leagues:
            if league not in league_map: continue
            comp_id, comp_slug = league_map[league]['id'], league_map[league]['slug']
            for season in seasons:
                group_key = (league, season)
                for s_type in stat_types:
                    current_step += 1
                    progress_bar.progress(min(current_step / total_steps, 0.99))
                    status_text.text(f"Scraping: {league} {season} - {s_type}...")
                    
                    url_slug, table_id_key = type_map[s_type]['url'], type_map[s_type]['table_id']
                    
                    if season == '25-26': 
                        url = f"https://fbref.com/en/comps/{comp_id}/{url_slug}/{comp_slug}-Stats"
                    else:
                        years = season.split('-')
                        full_year_str = f"20{years[0]}-20{years[1]}"
                        url = f"https://fbref.com/en/comps/{comp_id}/{full_year_str}/{url_slug}/{full_year_str}-{comp_slug}-Stats"
                    
                    try:
                        driver.get(url)
                        time.sleep(random.uniform(5, 8)) # Wait for Cloudflare
                        
                        wait = WebDriverWait(driver, 20)
                        table_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"table[id*='{table_id_key}']")))
                        
                        # Use outerHTML to parse with pandas
                        html_content = table_element.get_attribute('outerHTML')
                        dfs = pd.read_html(html_content)
                        if not dfs: continue
                        df = dfs[0]
                        
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = [col[1] if "Unnamed" in col[0] else f"{col[0]}_{col[1]}" for col in df.columns]

                        if 'Rk' in df.columns: df = df[df['Rk'] != 'Rk'].drop(columns=['Rk'])
                        if 'Matches' in df.columns: df = df.drop(columns=['Matches'])
                        df = df.drop_duplicates(subset=['Player', 'Squad'])
                        df = df.rename(columns={col: f"{s_type}_{col}" for col in df.columns if col not in id_cols})

                        if group_key not in merged_data_storage:
                            merged_data_storage[group_key] = df
                        else:
                            merge_on = [c for c in id_cols if c in merged_data_storage[group_key].columns and c in df.columns]
                            if merge_on:
                                merged_data_storage[group_key] = pd.merge(merged_data_storage[group_key], df, on=merge_on, how='outer')
                    except:
                        continue
    finally:
        try:
            driver.quit()
            display.stop()
        except:
            pass
        progress_bar.empty()
        status_text.empty()

    final_dfs = [df_data.assign(League=league, Season=season) for (league, season), df_data in merged_data_storage.items()]
    return pd.concat(final_dfs, ignore_index=True) if final_dfs else pd.DataFrame()

# --- TRIGGER LOGIC ---
if start_btn:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Please select at least one league, one season, and one statistic.")
    else:
        show_coffee_popup()

# Executes scraping only if state is set to True
if st.session_state.run_scrape:
    st.session_state.run_scrape = False # Reset for next click
    with st.spinner("Downloading data from Fbref... (This may take some time)"):
        df_result = scrape_fbref_merged(selected_leagues, selected_seasons, selected_stats)
    
    if not df_result.empty:
        st.success("Scraping completed!")
        st.write(f"Rows downloaded: {len(df_result)}")
        st.dataframe(df_result.head(10))
        csv = df_result.to_csv(index=False).encode('utf-8')
        st.download_button(label="Download CSV", data=csv, file_name="fbref_data_merged.csv", mime="text/csv")
    else:
        st.error("No data found or error during scraping.")