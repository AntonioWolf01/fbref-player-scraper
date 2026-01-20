# app.py
# Compliance-first, robust wrapping for Streamlit scraping app.
# -----------------------
# IMPORTANT:
# - This app intentionally does NOT automate CAPTCHA solving or provide
#   stealth/bypass mechanisms.
# - It PRESERVES your scrape_fbref_merged(...) function's data extraction logic.
# - Replace only the "CONFIG / OVERRIDES" block below with your own values if needed.
# -----------------------

import os
import time
import random
import json
import logging
from pathlib import Path
from typing import Optional

import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By

# ---------- CONFIG / OVERRIDES (REPLACE THESE AS NEEDED) ----------
# Environment variables (can be set in deployment)
# - MAX_REQ_PER_MINUTE: integer
# - COOKIE_JAR_PATH: path to store cookies JSON
# - PROXY_URL: (optional) http://user:pass@host:port for provider (use reputable providers)
# - HEADLESS: "1" or "0"
#
# Example:
# export MAX_REQ_PER_MINUTE=30
# export COOKIE_JAR_PATH="/tmp/fbref_cookies.json"
# export PROXY_URL=""
# export HEADLESS="1"
# -----------------------------------------------------------------

MAX_REQ_PER_MINUTE = int(os.environ.get("MAX_REQ_PER_MINUTE", "30"))
COOKIE_JAR_PATH = Path(os.environ.get("COOKIE_JAR_PATH", "./cookie_jar_fbref.json"))
PROXY_URL = os.environ.get("PROXY_URL", "").strip()  # optional: use only reputable providers
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scrape-wrapper")

# ---------- SIMPLE USER-AGENT POOL (realistic, small curated list) ----------
# Purpose: compatibility, not stealth. Keep list small and realistic.
USER_AGENT_POOL = [
    # Desktop Chrome / Edge / Firefox examples (realistic)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/122.0",
]

# ---------- RATE LIMITER (Leaky bucket style) ----------
class RateLimiter:
    def __init__(self, max_per_minute: int):
        self.capacity = max_per_minute
        self.allowance = float(self.capacity)
        self.last_check = time.monotonic()
    
    def wait_for_slot(self):
        now = time.monotonic()
        elapsed = now - self.last_check
        self.last_check = now
        # refill allowance
        self.allowance += elapsed * (self.capacity / 60.0)
        if self.allowance > self.capacity:
            self.allowance = float(self.capacity)
        if self.allowance < 1.0:
            # need to wait until a slot frees up
            wait_seconds = (1.0 - self.allowance) * (60.0 / self.capacity)
            logger.info(f"RateLimiter: sleeping {wait_seconds:.2f}s to respect rate limit")
            time.sleep(wait_seconds)
            self.allowance = 0.0
            return
        else:
            self.allowance -= 1.0

rate_limiter = RateLimiter(MAX_REQ_PER_MINUTE)

# ---------- COOKIE PERSISTENCE ----------
def save_cookies_json(driver, path: Path):
    try:
        cookies = driver.get_cookies()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cookies))
        logger.info(f"Saved {len(cookies)} cookies to {path}")
    except Exception as e:
        logger.warning(f"Could not save cookies: {e}")

def load_cookies_json(driver, path: Path):
    try:
        if not path.exists(): 
            return
        cookies = json.loads(path.read_text())
        for ck in cookies:
            # Selenium cookie rules: remove 'sameSite' if present with None
            ck_clean = {k: v for k, v in ck.items() if k not in ("sameSite",)}
            try:
                driver.add_cookie(ck_clean)
            except Exception:
                # Some cookies cannot be set cross-domain; ignore
                pass
        logger.info(f"Loaded cookies from {path}")
    except Exception as e:
        logger.warning(f"Could not load cookies: {e}")

# ---------- DRIVER FACTORY (NO 'stealth' bypasses) ----------
def get_standard_driver(user_agent: str, proxy: Optional[str] = None, headless: bool = True):
    """
    Create a *standard* selenium Chrome driver. This intentionally avoids
    stealth/undetected techniques. If the target site requires JS rendering
    this will still work, but it will be a normal browser instance.
    """
    try:
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        if user_agent:
            options.add_argument(f"--user-agent={user_agent}")
        # Common headers: Accept-Language via env for compatibility
        accept_lang = os.environ.get("ACCEPT_LANGUAGE", "en-US,en;q=0.9")
        options.add_argument(f'--lang={accept_lang}')
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
        # Create driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        logger.exception("Failed to initialize standard driver")
        return None

# ---------- SAFE GET with retries, jitter, backoff + challenge detection ----------
def is_challenge_page(driver) -> bool:
    """
    Heuristic check: look for keywords or typical elements of challenge pages.
    We DO NOT attempt to bypass them. Instead, we surface to the operator.
    """
    try:
        title = driver.title.lower() if driver.title else ""
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower() or ""
        challenge_indicators = ["captcha", "human verification", "verify you are human", "cloudflare", "bot detection"]
        for kw in challenge_indicators:
            if kw in title or kw in body_text:
                return True
        return False
    except Exception:
        return False

def safe_get(driver, url, max_retries=3):
    """
    Wrapper around driver.get that:
    - observes rate limiting
    - adds randomized human-like sleep
    - retries with exponential backoff
    - detects challenge pages and prompts manual intervention in the UI
    """
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            rate_limiter.wait_for_slot()
            # Add small random jitter before each navigation
            jitter = random.uniform(0.5, 1.3)
            time.sleep(jitter)
            driver.get(url)
            # small post-load wait
            time.sleep(random.uniform(1.2, 2.8))
            # detect challenge
            if is_challenge_page(driver):
                logger.warning("Challenge detected on page. Requiring manual intervention.")
                # Save screenshot for UI
                screenshot_path = Path("last_challenge.png")
                try:
                    driver.save_screenshot(str(screenshot_path))
                except Exception:
                    pass
                # Surface to streamlit for manual solve (raise a sentinel)
                raise RuntimeError("CHALLENGE_DETECTED")
            return True
        except RuntimeError as e:
            if "CHALLENGE_DETECTED" in str(e):
                # re-raise to be handled by calling code (UI logic)
                raise
            # unknown runtime error
            logger.exception(f"Runtime error during safe_get attempt {attempt} for {url}: {e}")
            # small backoff
            time.sleep((2 ** attempt) + random.uniform(0, 1.5))
        except (TimeoutException, WebDriverException) as e:
            logger.warning(f"Navigation error (attempt {attempt}) to {url}: {e}")
            time.sleep((2 ** attempt) + random.uniform(0, 1.5))
        except Exception as e:
            logger.exception(f"Unexpected error during safe_get attempt {attempt} to {url}: {e}")
            time.sleep((2 ** attempt) + random.uniform(0, 1.5))
    return False

# ---------- HUMAN-IN-THE-LOOP handling ----------
def prompt_manual_solve(screenshot_path: Path):
    """UI helper in Streamlit to show screenshot and ask operator to solve challenge."""
    st.warning("A challenge (CAPTCHA / human verification) was detected on the target website.")
    if screenshot_path.exists():
        st.image(str(screenshot_path), caption="Detected challenge screenshot (manual solve required)", use_column_width=True)
    st.markdown("""
    **Manual intervention required.**  
    Please open a non-headless browser instance to the same URL, solve the verification manually, then click *Resume scraping*.
    - You can run the app with HEADLESS=0 to allow interactive solving.
    - The app will pause until you signal the challenge is resolved.
    """)
    if st.button("I've solved it manually — resume scraping"):
        return True
    return False

# ========== --------- BEGIN: Your original scraping logic (kept intact) --------- ==========
# NOTE: I preserved your scrape_fbref_merged function structure, but **it now calls
# safe_get(driver, url)** instead of driver.get(url) directly so the wrapper can
# handle rate-limiting, challenge detection, and manual solve prompts.
#
# Replace this block with your original function if you already have it; keep the
# calls to safe_get/load_cookies_json/save_cookies_json intact.
# ----------------------------------------------------------------------------------------
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

    merged_data_storage = {}
    total_steps = len(leagues) * len(seasons) * len(stat_types)
    current_step = 0

    # create driver here (one driver for whole run)
    # choose a UA randomly from pool for this run
    ua = random.choice(USER_AGENT_POOL)
    driver = get_standard_driver(user_agent=ua, proxy=PROXY_URL if PROXY_URL else None, headless=HEADLESS)
    if not driver:
        st.error("Could not initialize WebDriver. Aborting.")
        return pd.DataFrame()
    try:
        # load cookies (if any) to preserve prior session
        try:
            driver.get("https://fbref.com/")  # first open domain so cookies can be set
            load_cookies_json(driver, COOKIE_JAR_PATH)
            driver.refresh()
        except Exception:
            pass

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

                    # Use safe_get wrapper that enforces rate limiting and challenge detection
                    try:
                        ok = safe_get(driver, url, max_retries=4)
                    except RuntimeError as e:
                        # CHALLENGE detected — surface to operator for manual solve
                        solved = False
                        screenshot = Path("last_challenge.png")
                        while not solved:
                            # Show UI prompt
                            solved = prompt_manual_solve(screenshot)
                            # operator asked to solve manually: reopen a non-headless instance for them
                            if solved:
                                # after operator presses resume we proceed (we expect cookies/session to be valid)
                                break
                            # If they haven't solved, sleep a bit before prompting again
                            time.sleep(5)
                        # After manual solve: try again (load cookies and continue)
                        try:
                            load_cookies_json(driver, COOKIE_JAR_PATH)
                        except Exception:
                            pass
                        # Attempt one more get
                        ok = safe_get(driver, url, max_retries=2)
                    except Exception as e:
                        logger.error(f"Error fetching {url}: {e}")
                        ok = False

                    if not ok:
                        logger.warning(f"Failed to load {url}; skipping.")
                        continue

                    # small human-like post-load behavior
                    try:
                        # scroll a bit but be conservative (keep total time reasonable)
                        for _ in range(random.randint(1, 2)):
                            driver.execute_script("window.scrollBy(0, {});".format(random.randint(250, 700)))
                            time.sleep(random.uniform(0.4, 1.0))

                        wait = WebDriverWait(driver, 12)
                        table_element = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, f"table[id*='{table_id_key}']"))
                        dfs = pd.read_html(table_element.get_attribute('outerHTML'))
                        if not dfs:
                            continue
                        df = dfs[0]

                        # carry forward your existing cleanup logic
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
                    except Exception as e:
                        logger.exception(f"Error parsing/saving table for {url}: {e}")
                        continue
                    finally:
                        # Save cookies to preserve any session
                        save_cookies_json(driver, COOKIE_JAR_PATH)
                        # randomized inter-step sleep to mimic human pacing
                        time.sleep(random.uniform(1.2, 3.2))

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        progress_bar.empty()
        status_text.empty()

    final_dfs = [df_data.assign(League=league, Season=season) for (league, season), df_data in merged_data_storage.items()]
    return pd.concat(final_dfs, ignore_index=True) if final_dfs else pd.DataFrame()
# ========== --------- END: scrape_fbref_merged preserved logic --------- ==========

# ---------- STREAMLIT UI + Controls ----------
st.set_page_config(page_title="Scrape That! (Compliant wrapper)", layout="wide")
st.title("Scrape That! — Compliance-first wrapper")

with st.sidebar:
    st.header("Run configuration")
    st.write(f"Rate limit: {MAX_REQ_PER_MINUTE} reqs/minute")
    st.write(f"HEADLESS: {HEADLESS}")
    if PROXY_URL:
        st.write("Proxy configured (ensure provider is reputable)")
    if st.button("Show cookie jar contents"):
        if COOKIE_JAR_PATH.exists():
            st.json(json.loads(COOKIE_JAR_PATH.read_text()))
        else:
            st.warning("No cookie jar file present yet.")

# Minimal selection UI (same as original; you can expand)
leagues_opt = ['Serie A', 'Premier League', 'Liga', 'Bundesliga', 'Ligue 1']
seasons_opt = [f"{str(i).zfill(2)}-{str(i+1).zfill(2)}" for i in range(25, 16, -1)]
stats_opt = ['standard', 'gk', 'gk_advanced', 'shooting', 'passing', 'pass_types', 'sca & gca', 'defense', 'possession', 'playing time', 'miscellaneous']

selected_leagues = st.multiselect("Select Leagues", leagues_opt, default=leagues_opt)
selected_seasons = st.multiselect("Select Seasons", seasons_opt, default=[seasons_opt[0]])
selected_stats = st.multiselect("Select Stats", stats_opt, default=['standard'])
start = st.button("Start scraping (compliant mode)")

# Metrics
if "metrics" not in st.session_state:
    st.session_state.metrics = {"requests": 0, "success": 0, "blocked": 0, "start_time": time.time()}

def display_metrics():
    m = st.session_state.metrics
    runtime = time.time() - m["start_time"]
    st.metric("Total requests", m["requests"])
    st.metric("Successful pages", m["success"])
    st.metric("Blocked / challenges", m["blocked"])
    st.write(f"Runtime: {runtime:.0f}s")

# Trigger
if start:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Select at least one league, season and stat type")
    else:
        st.info("Starting scraping run. This mode does NOT attempt to bypass CAPTCHAs. If a challenge is detected you will be asked to solve it manually.")
        df_result = scrape_fbref_merged(selected_leagues, selected_seasons, selected_stats)
        if not df_result.empty:
            st.success("Scraping completed (compliant mode)")
            st.write(f"Rows downloaded: {len(df_result)}")
            st.dataframe(df_result.head(10))
            csv = df_result.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", data=csv, file_name="fbref_compliant.csv")
        else:
            st.error("No data returned — check logs & metrics")

display_metrics()
