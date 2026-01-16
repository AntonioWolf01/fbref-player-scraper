import streamlit as st
import pandas as pd
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Scrape That!", layout="wide")

# --- CUSTOM CSS: BLACK & WHITE THEME ---
st.markdown("""
<style>
    /* Main Background and Text */
    .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    
    /* Headings */
    h1, h2, h3, h4, h5, h6, .markdown-text-container {
        color: #000000 !important;
        font-family: 'Helvetica', 'Arial', sans-serif;
    }
    
    /* Buttons (Primary) - Black Background, White Text */
    div.stButton > button {
        background-color: #000000;
        color: #ffffff;
        border: 2px solid #000000;
        border-radius: 0px; /* Sharp edges for modern B&W look */
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #ffffff;
        color: #000000;
        border: 2px solid #000000;
    }
    
    /* Progress Bar Color */
    .stProgress > div > div > div > div {
        background-color: #000000;
    }
    
    /* Inputs/Selectboxes */
    div[data-baseweb="select"] > div {
        border-color: #000000;
    }
    
    /* Toggle Colors */
    div[data-testid="stCheckbox"] label span {
        color: #000000;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("Scrape That!")
st.markdown("### Select leagues, seasons, and stats to download the complete dataset.")
st.markdown("---")

# --- CONFIGURATION (CENTERED) ---
# Options definitions
leagues_opt = ['Serie A', 'Premier League', 'La Liga', 'Bundesliga', 'Ligue 1']
seasons_opt = [f"{str(i).zfill(2)}-{str(i+1).zfill(2)}" for i in range(17, 26)]
stats_opt = [
    'standard', 'gk', 'gk_advanced', 'shooting', 'passing', 
    'pass_types', 'sca & gca', 'defense', 'possession', 
    'playing time', 'miscellaneous'
]

# Layout using columns for the settings
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. Leagues")
    all_leagues = st.toggle("Select All Leagues", value=False)
    if all_leagues:
        selected_leagues = leagues_opt
        st.caption(f"Selected: {len(selected_leagues)} Leagues")
    else:
        selected_leagues = st.multiselect("Choose Leagues", leagues_opt, default=['Serie A'])

with col2:
    st.subheader("2. Seasons")
    all_seasons = st.toggle("Select All Seasons", value=False)
    if all_seasons:
        selected_seasons = seasons_opt
        st.caption(f"Selected: {len(selected_seasons)} Seasons")
    else:
        selected_seasons = st.multiselect("Choose Seasons", seasons_opt, default=['24-25'])

with col3:
    st.subheader("3. Statistics")
    all_stats = st.toggle("Select All Stats", value=False)
    if all_stats:
        selected_stats = stats_opt
        st.caption(f"Selected: {len(selected_stats)} Stat Tables")
    else:
        selected_stats = st.multiselect("Choose Stats", stats_opt, default=['standard'])

st.markdown("---")
start_btn = st.button("START SCRAPING", type="primary", use_container_width=True)

# --- SCRAPING FUNCTION ---
def scrape_fbref_merged(leagues, seasons, stat_types):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # Updated keys to match English UI
    league_map = {
        'Serie A': {'id': '11', 'slug': 'Serie-A'},
        'Premier League': {'id': '9', 'slug': 'Premier-League'},
        'La Liga': {'id': '12', 'slug': 'La-Liga'}, # Changed key from 'Liga' to 'La Liga'
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

    # --- SELENIUM SETUP OPTIMIZED ---
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # CRITICAL SETTINGS FOR LINUX/STREAMLIT CLOUD
    options.binary_location = "/usr/bin/chromium"
    
    try:
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        
        # FIX ANTI-BOT
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        st.error(f"Driver startup error: {e}")
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
                        progress_val = min(current_step / total_steps, 0.99)
                        progress_bar.progress(progress_val)
                    
                    if s_type not in type_map: continue
                    
                    status_text.text(f"Scraping: {league} {season} - Table: {s_type}...")
                    
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
                        time.sleep(random.uniform(3, 6))
                        
                        wait = WebDriverWait(driver, 15)
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
                            # Safe intersection of key columns
                            merge_on = [c for c in id_cols if c in existing_cols and c in current_cols]
                            
                            if merge_on:
                                merged_data_storage[group_key] = pd.merge(
                                    merged_data_storage[group_key], df, on=merge_on, how='outer'
                                )
                    except Exception as e:
                        print(f"Error scraping {league} {season} {s_type}: {e}")
                        continue

    except Exception as main_e:
        st.error(f"Critical error during scraping: {main_e}")
    finally:
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

# --- EXECUTION ---
if start_btn:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Please select at least one league, one season, and one statistic.")
    else:
        with st.spinner("Scraping data from Fbref... (This operation may take some time)"):
            df_result = scrape_fbref_merged(selected_leagues, selected_seasons, selected_stats)
        
        if not df_result.empty:
            st.success("Scraping completed!")
            st.write(f"Rows downloaded: {len(df_result)}")
            
            # Show head(10) as requested
            st.dataframe(df_result.head(10))
            
            csv = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="fbref_data_merged.csv",
                mime="text/csv"
            )
        else:
            st.error("No data found or an error occurred during scraping. Check logs.")