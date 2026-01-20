import streamlit as st
import pandas as pd
import time
import random
import re
import requests as standard_requests
from io import StringIO
from curl_cffi import requests
from bs4 import BeautifulSoup

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Scrape That! (Proxy Edition)", layout="wide")

# Initialize session state
if "run_scrape" not in st.session_state:
    st.session_state.run_scrape = False

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
    div.stButton > button:hover {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    .header-container { display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px; }
    .header-logo { height: 60px; width: 60px; border-radius: 10px; }
    .header-title { font-size: 3.5rem; font-weight: 700; margin: 0; line-height: 1; color: #000000; }
    </style>
""", unsafe_allow_html=True)

# --- GLOBAL FUNCTIONS (DEFINED HERE TO PREVENT CRASHES) ---
@st.dialog("Support the Developer")
def show_coffee_popup():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://media.tenor.com/6heB-WgIU1kAAAAi/transparent-coffee.gif", use_container_width=True)
    st.markdown("""
    I've upgraded the scraper to use **Chrome Network Impersonation** to bypass blocks!
    
    If this tool saves you time, please consider fueling my next update.
    """)
    st.markdown("""
        <div style="display: flex; justify-content: center; margin-bottom: 25px;">
            <a href="https://buymeacoffee.com/antoniolupo" target="_blank">
                <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" style="height: 50px !important;width: 180px !important;" >
            </a>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Continue & Start Scraping", use_container_width=True):
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
        <b>Proxy Edition:</b> Uses IP rotation to bypass server blocks.
    </p>
""", unsafe_allow_html=True)

# --- CONFIGURATION & SIDEBAR ---
st.write("---")
st.header("Configuration")

# Sidebar: Proxy Logic
with st.sidebar:
    st.header("Connection Settings")
    use_auto_proxy = st.checkbox("🔄 Auto-Rotate Free Proxies", value=True, help="Automatically fetches public proxies to bypass IP bans.")
    st.caption("OR use your own:")
    manual_proxy = st.text_input("Custom Proxy URL", placeholder="http://user:pass@ip:port")

leagues_opt = ['Serie A', 'Premier League', 'Liga', 'Bundesliga', 'Ligue 1']
seasons_opt = [f"{str(i).zfill(2)}-{str(i+1).zfill(2)}" for i in range(25, 16, -1)]
stats_opt = ['standard', 'gk', 'gk_advanced', 'shooting', 'passing', 'pass_types', 'sca & gca', 'defense', 'possession', 'playing time', 'miscellaneous']

c1, c2, c3 = st.columns(3)
with c1:
    toggle_leagues = st.toggle("Select All Leagues")
    selected_leagues = st.multiselect("Leagues", leagues_opt, default=leagues_opt if toggle_leagues else [], label_visibility="collapsed")
with c2:
    toggle_seasons = st.toggle("Select All Seasons")
    selected_seasons = st.multiselect("Seasons", seasons_opt, default=seasons_opt if toggle_seasons else [], label_visibility="collapsed")
with c3:
    toggle_stats = st.toggle("Select All Stats")
    selected_stats = st.multiselect("Stats", stats_opt, default=stats_opt if toggle_stats else [], label_visibility="collapsed")

start_btn = st.button("Start Scraping", use_container_width=True)
st.write("---")

# --- PROXY UTILITIES ---
def get_free_proxies():
    """Fetches a list of free HTTPS proxies from public APIs."""
    proxies = []
    try:
        # Source 1: Proxyscrape
        url1 = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all"
        r1 = standard_requests.get(url1, timeout=5)
        if r1.status_code == 200:
            proxies += r1.text.strip().split('\r\n')
        
        # Source 2: Proxy List Download
        url2 = "https://www.proxy-list.download/api/v1/get?type=https"
        r2 = standard_requests.get(url2, timeout=5)
        if r2.status_code == 200:
            proxies += r2.text.strip().split('\r\n')
            
    except Exception as e:
        print(f"Proxy fetch error: {e}")
    
    # Remove empty strings and duplicates
    return list(set([p for p in proxies if p]))

def test_and_get_working_proxy(proxy_list):
    """
    Tries proxies from the list until one connects to FBref.
    Returns the working proxy dict or None.
    """
    random.shuffle(proxy_list)
    status_msg = st.empty()
    
    # Try max 15 proxies to save time
    for i, proxy_ip in enumerate(proxy_list[:15]):
        proxy_url = f"http://{proxy_ip}"
        proxies = {"http": proxy_url, "https": proxy_url}
        status_msg.text(f"Testing proxy {i+1}/15: {proxy_ip}...")
        
        try:
            # Quick check against the target
            r = requests.get("https://fbref.com", proxies=proxies, impersonate="chrome124", timeout=5)
            if r.status_code == 200:
                status_msg.success(f"Connected via {proxy_ip}!")
                time.sleep(1)
                status_msg.empty()
                return proxies
        except:
            continue
            
    status_msg.error("Could not find a working free proxy. Try running again or use a Custom Proxy.")
    return None

# --- SCRAPING UTILS ---
def clean_html_content(html_content):
    """Unhides commented-out data tables."""
    return re.sub(r'', '', html_content)

def fetch_data(url, proxies=None):
    """Fetches URL using curl_cffi with TLS impersonation."""
    try:
        response = requests.get(
            url, 
            impersonate="chrome124", 
            proxies=proxies,
            timeout=15
        )
        return response
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def scrape_fbref_merged(leagues, seasons, stat_types, use_auto, manual_proxy_str):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # --- SETUP PROXY ---
    active_proxies = None
    if manual_proxy_str:
        active_proxies = {"http": manual_proxy_str, "https": manual_proxy_str}
        st.info(f"Using Custom Proxy: {manual_proxy_str}")
    elif use_auto:
        with st.spinner("Fetching and testing free proxies... (This takes a moment)"):
            candidates = get_free_proxies()
            st.write(f"Found {len(candidates)} candidates.")
            active_proxies = test_and_get_working_proxy(candidates)
            if not active_proxies:
                return pd.DataFrame() # Stop if no proxy found
    else:
        st.warning("Attempting Direct Connection (High risk of block)")
    
    # --- MAPPINGS ---
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
    merged_data_storage = {}
    
    total_steps = len(leagues) * len(seasons) * len(stat_types)
    current_step = 0

    for league in leagues:
        if league not in league_map: continue
        comp_id, comp_slug = league_map[league]['id'], league_map[league]['slug']
        
        for season in seasons:
            group_key = (league, season)
            
            for s_type in stat_types:
                current_step += 1
                progress_bar.progress(min(current_step / total_steps, 0.99))
                status_text.text(f"Fetching: {league} {season} - {s_type}...")
                
                url_slug, table_id_key = type_map[s_type]['url'], type_map[s_type]['table_id']
                
                if season == '25-26': 
                    url = f"https://fbref.com/en/comps/{comp_id}/{url_slug}/{comp_slug}-Stats"
                else:
                    years = season.split('-')
                    full_year_str = f"20{years[0]}-20{years[1]}"
                    url = f"https://fbref.com/en/comps/{comp_id}/{full_year_str}/{url_slug}/{full_year_str}-{comp_slug}-Stats"
                
                # RETRY LOGIC (Rotate proxy if 403)
                max_retries = 3
                for attempt in range(max_retries):
                    response = fetch_data(url, proxies=active_proxies)
                    
                    if not response:
                        continue # Network error
                    
                    if response.status_code == 429:
                        time.sleep(10) # Cool down
                        continue
                        
                    if response.status_code == 403:
                        print("403 Blocked. Retrying...")
                        time.sleep(random.uniform(2, 5))
                        continue
                        
                    if response.status_code == 200:
                        # SUCCESS
                        html = clean_html_content(response.text)
                        try:
                            # Loose matching for table ID
                            dfs = pd.read_html(StringIO(html), match=table_id_key)
                            if not dfs: 
                                # Fallback: any table
                                dfs = pd.read_html(StringIO(html))
                            
                            if dfs:
                                df = dfs[0]
                                
                                # CLEANING
                                if isinstance(df.columns, pd.MultiIndex):
                                    df.columns = [col[1] if "Unnamed" in col[0] else f"{col[0]}_{col[1]}" for col in df.columns]

                                if 'Rk' in df.columns: df = df[df['Rk'] != 'Rk'].drop(columns=['Rk'])
                                if 'Matches' in df.columns: df = df.drop(columns=['Matches'])
                                df = df.drop_duplicates(subset=['Player', 'Squad'])
                                df = df.rename(columns={col: f"{s_type}_{col}" for col in df.columns if col not in id_cols})

                                # MERGING
                                if group_key not in merged_data_storage:
                                    merged_data_storage[group_key] = df
                                else:
                                    merge_on = [c for c in id_cols if c in merged_data_storage[group_key].columns and c in df.columns]
                                    if merge_on:
                                        merged_data_storage[group_key] = pd.merge(merged_data_storage[group_key], df, on=merge_on, how='outer')
                                break # Exit retry loop
                        except Exception as e:
                            print(f"Parsing failed: {e}")
                            
                    time.sleep(random.uniform(2, 4)) # Polite delay

    progress_bar.empty()
    status_text.empty()
    
    final_dfs = [df_data.assign(League=league, Season=season) for (league, season), df_data in merged_data_storage.items()]
    return pd.concat(final_dfs, ignore_index=True) if final_dfs else pd.DataFrame()

# --- TRIGGER LOGIC ---
if start_btn:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Please select at least one league, one season, and one statistic.")
    else:
        # Call the global function
        show_coffee_popup()

# Executes scraping only if state is set to True
if st.session_state.run_scrape:
    st.session_state.run_scrape = False
    
    # Run the scraper
    df_result = scrape_fbref_merged(
        selected_leagues, 
        selected_seasons, 
        selected_stats,
        use_auto_proxy,
        manual_proxy
    )
    
    if not df_result.empty:
        st.success("Scraping completed!")
        st.write(f"Rows downloaded: {len(df_result)}")
        st.dataframe(df_result.head(10))
        csv = df_result.to_csv(index=False).encode('utf-8')
        st.download_button(label="Download CSV", data=csv, file_name="fbref_data_merged.csv", mime="text/csv")
    else:
        st.error("No data found.")
        st.markdown("""
        **Troubleshooting:**
        1. **Free Proxies are Unreliable:** The auto-rotator might have picked a proxy that is slow or also blocked. **Try clicking 'Start' again** to fetch a fresh list.
        2. **Manual Proxy:** If you have a working residential proxy, paste it in the sidebar.
        """)