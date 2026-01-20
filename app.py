import streamlit as st
import pandas as pd
import time
import random
import logging
import sys
import os

# --- CRITICAL PATCH FOR PYTHON 3.12+ ---
# undetected_chromedriver uses 'distutils' which was removed in Python 3.12
if sys.version_info >= (3, 12):
    import types
    from packaging import version # This requires 'packaging' in requirements.txt
    
    # Create a fake distutils.version module
    if "distutils" not in sys.modules:
        sys.modules["distutils"] = types.ModuleType("distutils")
    if "distutils.version" not in sys.modules:
        sys.modules["distutils.version"] = types.ModuleType("distutils.version")
    
    # Mock LooseVersion using packaging.version
    class LooseVersion(version.Version):
        def __init__(self, vstring):
            super().__init__(vstring)

    # Inject LooseVersion into the fake module
    sys.modules["distutils.version"].LooseVersion = LooseVersion

# --- END PATCH ---

from fake_useragent import UserAgent
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Scrape That!", layout="wide")

# Initialize session state
if "run_scrape" not in st.session_state:
    st.session_state.run_scrape = False
if "request_count" not in st.session_state:
    st.session_state.request_count = 0
if "session_start" not in st.session_state:
    st.session_state.session_start = time.time()

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    
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

# --- ANTI-DETECTION UTILITIES ---
class AntiDetectionConfig:
    """Centralized configuration for anti-detection measures"""
    
    # Realistic user agents (recent Chrome versions)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    
    # Screen resolutions (width, height)
    SCREEN_SIZES = [
        (1920, 1080),
        (1366, 768),
        (1536, 864),
        (1440, 900)
    ]
    
    # Timing configurations (in seconds)
    MIN_PAGE_LOAD_WAIT = 4.5
    MAX_PAGE_LOAD_WAIT = 8.0
    MIN_BETWEEN_REQUESTS = 3.0
    MAX_BETWEEN_REQUESTS = 7.0
    
    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 12
    COOLDOWN_AFTER_N_REQUESTS = 25
    COOLDOWN_DURATION = (45, 90)  # seconds range
    
    @staticmethod
    def get_random_viewport():
        """Return random but realistic viewport dimensions"""
        width, height = random.choice(AntiDetectionConfig.SCREEN_SIZES)
        return width, height
    
    @staticmethod
    def get_human_delay(base_min=None, base_max=None):
        """Generate human-like delay with micro-variations"""
        min_delay = base_min or AntiDetectionConfig.MIN_PAGE_LOAD_WAIT
        max_delay = base_max or AntiDetectionConfig.MAX_PAGE_LOAD_WAIT
        
        # Primary delay
        delay = random.uniform(min_delay, max_delay)
        
        # Add micro-jitter (human reaction time variance)
        jitter = random.gauss(0, 0.3)
        
        return max(1.0, delay + jitter)


def create_stealth_driver():
    """
    Create an undetected Chrome driver with advanced anti-fingerprinting
    This replaces the standard Selenium WebDriver
    """
    
    options = uc.ChromeOptions()
    
    # Basic stealth options
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    
    # Randomize viewport
    width, height = AntiDetectionConfig.get_random_viewport()
    options.add_argument(f'--window-size={width},{height}')
    
    # Language and locale
    options.add_argument('--lang=en-US,en;q=0.9')
    options.add_argument('--accept-lang=en-US,en;q=0.9')
    
    # Disable automation indicators
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Randomize user agent
    user_agent = random.choice(AntiDetectionConfig.USER_AGENTS)
    options.add_argument(f'user-agent={user_agent}')
    
    # Additional fingerprint randomization
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.images": 1,  # Load images for realism
    }
    options.add_experimental_option("prefs", prefs)
    
    try:
        # Use undetected-chromedriver (primary anti-detection)
        driver = uc.Chrome(options=options, version_main=120)
        
        # Execute additional stealth scripts
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = {runtime: {}};
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        """
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': stealth_js})
        
        return driver
        
    except Exception as e:
        st.error(f"Failed to create stealth driver: {e}")
        st.info("Falling back to standard Chrome driver...")
        
        # Fallback to standard Selenium (less effective but functional)
        try:
            service = Service("/usr/bin/chromedriver")
            options_fallback = Options()
            options_fallback.add_argument("--headless")
            options_fallback.add_argument("--no-sandbox")
            options_fallback.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(service=service, options=options_fallback)
            return driver
        except Exception as e2:
            st.error(f"Fallback driver also failed: {e2}")
            return None


def simulate_human_behavior(driver, wait_time=None):
    """
    Simulate human-like interactions to avoid detection
    """
    try:
        # Random scroll behavior
        if random.random() > 0.7:  # 30% chance to scroll
            scroll_amount = random.randint(100, 500)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.3, 0.8))
        
        # Occasional mouse movement simulation
        if random.random() > 0.8:  # 20% chance
            try:
                action = ActionChains(driver)
                body = driver.find_element(By.TAG_NAME, "body")
                action.move_to_element_with_offset(body, random.randint(0, 100), random.randint(0, 100))
                action.perform()
            except:
                pass
        
        # Variable wait time
        delay = wait_time if wait_time else AntiDetectionConfig.get_human_delay()
        time.sleep(delay)
        
    except Exception as e:
        # Silent failure - these are enhancement behaviors
        pass


def smart_rate_limiter(request_count, session_start):
    """
    Intelligent rate limiting with exponential backoff
    Returns: (should_continue, updated_count, message)
    """
    elapsed_minutes = (time.time() - session_start) / 60
    
    # Calculate current rate
    if elapsed_minutes > 0:
        current_rate = request_count / elapsed_minutes
    else:
        current_rate = 0
    
    # Enforce rate limit
    if current_rate > AntiDetectionConfig.MAX_REQUESTS_PER_MINUTE:
        wait_time = 60 - (time.time() - session_start) % 60
        return False, request_count, f"⏱️ Rate limit: waiting {int(wait_time)}s"
    
    # Periodic cooldown (every N requests)
    if request_count > 0 and request_count % AntiDetectionConfig.COOLDOWN_AFTER_N_REQUESTS == 0:
        cooldown = random.uniform(*AntiDetectionConfig.COOLDOWN_DURATION)
        return False, request_count, f"☕ Cooldown break: {int(cooldown)}s (prevents pattern detection)"
    
    return True, request_count + 1, None


# --- BUY ME A COFFEE POPUP ---
@st.dialog("Support the Developer")
def show_coffee_popup():
    col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
    with col_img2:
        st.image("https://media.tenor.com/6heB-WgIU1kAAAAi/transparent-coffee.gif", use_container_width=True)
    
    st.markdown("""
    Manual data collection is a nightmare I've handled so you don't have to. While you enjoy your fresh dataset, remember that this code is powered by high-quality caffeine. 
    
    If 'Scrape That!' provided value to your project, feel free to fuel my next update. **I can't scrape coffee beans, so I have to buy them.**
    """)
    
    st.markdown("""
        <div style="display: flex; justify-content: center; margin-bottom: 25px; margin-top: 10px;">
            <a href="https://buymeacoffee.com/antoniolupo" target="_blank">
                <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 180px !important;" >
            </a>
        </div>
    """, unsafe_allow_html=True)
    
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

# --- ENHANCED SCRAPING FUNCTION WITH ANTI-DETECTION ---
def scrape_fbref_merged(leagues, seasons, stat_types):
    """
    CORE SCRAPING LOGIC - Enhanced with anti-detection layers
    The data extraction logic remains unchanged, only request handling is modified
    """
    status_text = st.empty()
    progress_bar = st.progress(0)
    debug_container = st.container()
    
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

    # === ANTI-DETECTION: Create stealth driver ===
    driver = create_stealth_driver()
    if driver is None:
        st.error("❌ Could not initialize browser driver")
        return pd.DataFrame()

    merged_data_storage = {}
    total_steps = len(leagues) * len(seasons) * len(stat_types)
    current_step = 0
    request_count = 0
    session_start = time.time()
    
    # Success/failure tracking
    successful_scrapes = 0
    failed_scrapes = 0
    blocked_attempts = 0

    try:
        for league in leagues:
            if league not in league_map: continue
            comp_id, comp_slug = league_map[league]['id'], league_map[league]['slug']
            
            for season in seasons:
                group_key = (league, season)
                
                for s_type in stat_types:
                    current_step += 1
                    progress = min(current_step / total_steps, 0.99)
                    progress_bar.progress(progress)
                    
                    # === ANTI-DETECTION: Rate limiting check ===
                    can_proceed, request_count, rate_msg = smart_rate_limiter(request_count, session_start)
                    if not can_proceed:
                        status_text.text(rate_msg)
                        # Extract wait time from message
                        if "waiting" in rate_msg:
                            wait_seconds = int(rate_msg.split("waiting ")[1].split("s")[0])
                            time.sleep(wait_seconds)
                        elif "Cooldown" in rate_msg:
                            cooldown = random.uniform(*AntiDetectionConfig.COOLDOWN_DURATION)
                            time.sleep(cooldown)
                        continue
                    
                    status_text.text(f"🔍 Scraping: {league} {season} - {s_type}... (Request {request_count}/{total_steps})")
                    
                    url_slug, table_id_key = type_map[s_type]['url'], type_map[s_type]['table_id']
                    
                    if season == '25-26': 
                        url = f"https://fbref.com/en/comps/{comp_id}/{url_slug}/{comp_slug}-Stats"
                    else:
                        years = season.split('-')
                        full_year_str = f"20{years[0]}-20{years[1]}"
                        url = f"https://fbref.com/en/comps/{comp_id}/{full_year_str}/{url_slug}/{full_year_str}-{comp_slug}-Stats"
                    
                    # === ANTI-DETECTION: Smart retry with exponential backoff ===
                    max_retries = 3
                    retry_count = 0
                    page_loaded = False
                    
                    while retry_count < max_retries and not page_loaded:
                        try:
                            # Navigate to URL
                            driver.get(url)
                            
                            # === ANTI-DETECTION: Human-like wait after page load ===
                            initial_wait = AntiDetectionConfig.get_human_delay(
                                AntiDetectionConfig.MIN_PAGE_LOAD_WAIT,
                                AntiDetectionConfig.MAX_PAGE_LOAD_WAIT
                            )
                            time.sleep(initial_wait)
                            
                            # === ANTI-DETECTION: Simulate human behavior ===
                            simulate_human_behavior(driver)
                            
                            # Check for Cloudflare challenge or blocking
                            page_source = driver.page_source.lower()
                            if "challenge-platform" in page_source or "captcha" in page_source:
                                blocked_attempts += 1
                                status_text.text(f"⚠️ Bot detection triggered. Retry {retry_count+1}/{max_retries}...")
                                
                                # Exponential backoff
                                backoff_time = (2 ** retry_count) * random.uniform(5, 10)
                                time.sleep(backoff_time)
                                retry_count += 1
                                continue
                            
                            # Wait for table to load
                            wait = WebDriverWait(driver, 20)
                            table_element = wait.until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, f"table[id*='{table_id_key}']"))
                            )
                            
                            page_loaded = True
                            
                            # === DATA EXTRACTION (UNCHANGED CORE LOGIC) ===
                            dfs = pd.read_html(table_element.get_attribute('outerHTML'))
                            if not dfs: 
                                failed_scrapes += 1
                                continue
                                
                            df = dfs[0]
                            
                            if isinstance(df.columns, pd.MultiIndex):
                                df.columns = [col[1] if "Unnamed" in col[0] else f"{col[0]}_{col[1]}" for col in df.columns]

                            if 'Rk' in df.columns: 
                                df = df[df['Rk'] != 'Rk'].drop(columns=['Rk'])
                            if 'Matches' in df.columns: 
                                df = df.drop(columns=['Matches'])
                            
                            df = df.drop_duplicates(subset=['Player', 'Squad'])
                            df = df.rename(columns={col: f"{s_type}_{col}" for col in df.columns if col not in id_cols})

                            if group_key not in merged_data_storage:
                                merged_data_storage[group_key] = df
                            else:
                                merge_on = [c for c in id_cols if c in merged_data_storage[group_key].columns and c in df.columns]
                                if merge_on:
                                    merged_data_storage[group_key] = pd.merge(
                                        merged_data_storage[group_key], 
                                        df, 
                                        on=merge_on, 
                                        how='outer'
                                    )
                            
                            successful_scrapes += 1
                            
                            # === ANTI-DETECTION: Variable delay between requests ===
                            between_delay = AntiDetectionConfig.get_human_delay(
                                AntiDetectionConfig.MIN_BETWEEN_REQUESTS,
                                AntiDetectionConfig.MAX_BETWEEN_REQUESTS
                            )
                            time.sleep(between_delay)
                            
                        except Exception as e:
                            retry_count += 1
                            failed_scrapes += 1
                            
                            if retry_count < max_retries:
                                status_text.text(f"⚠️ Error on {league} {season} {s_type}. Retry {retry_count}/{max_retries}...")
                                backoff = (2 ** retry_count) * random.uniform(3, 6)
                                time.sleep(backoff)
                            else:
                                status_text.text(f"❌ Failed: {league} {season} {s_type} after {max_retries} attempts")
                                with debug_container:
                                    st.warning(f"Skipped: {league} {season} {s_type} - {str(e)[:100]}")
                                continue
    
    finally:
        # Clean shutdown
        try:
            driver.quit()
        except:
            pass
        
        progress_bar.empty()
        status_text.empty()
        
        # Display session statistics
        st.success(f"""
        ✅ **Scraping Session Complete**
        - Successful: {successful_scrapes}
        - Failed: {failed_scrapes}
        - Blocked attempts: {blocked_attempts}
        - Success rate: {successful_scrapes/(successful_scrapes+failed_scrapes)*100:.1f}% (if total > 0 else "N/A")
        """)

    # Combine all data
    final_dfs = [
        df_data.assign(League=league, Season=season) 
        for (league, season), df_data in merged_data_storage.items()
    ]
    
    return pd.concat(final_dfs, ignore_index=True) if final_dfs else pd.DataFrame()


# --- TRIGGER LOGIC ---
if start_btn:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Please select at least one league, one season, and one statistic.")
    else:
        show_coffee_popup()

# Execute scraping
if st.session_state.run_scrape:
    st.session_state.run_scrape = False
    
    st.info("🛡️ **Anti-Detection Mode Active** - Using stealth browser with human-like behavior")
    
    with st.spinner("Downloading data from FBRef with anti-detection measures..."):
        df_result = scrape_fbref_merged(selected_leagues, selected_seasons, selected_stats)
    
    if not df_result.empty:
        st.success(f"✅ Scraping completed! Rows downloaded: {len(df_result)}")
        
        # Preview data
        st.subheader("Data Preview")
        st.dataframe(df_result.head(10))
        
        # Download button
        csv = df_result.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Complete Dataset (CSV)", 
            data=csv, 
            file_name="fbref_data_merged.csv", 
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.error("❌ No data retrieved. Check the error messages above for details.")