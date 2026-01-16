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

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Fbref Scraper AI", layout="wide")

st.title("⚽ Fbref Advanced Scraper")
st.markdown("Seleziona i campionati, le stagioni e le statistiche per scaricare il dataset completo.")

# --- SIDEBAR (INPUT UTENTE) ---
with st.sidebar:
    st.header("Configurazione")
    
    leagues_opt = ['Serie A', 'Premier League', 'Liga', 'Bundesliga', 'Ligue 1']
    seasons_opt = [f"{str(i).zfill(2)}-{str(i+1).zfill(2)}" for i in range(17, 26)]
    stats_opt = [
        'standard', 'gk', 'gk_advanced', 'shooting', 'passing', 
        'pass_types', 'sca & gca', 'defense', 'possession', 
        'playing time', 'miscellaneous'
    ]

    selected_leagues = st.multiselect("Seleziona Campionati", leagues_opt, default=['Serie A'])
    selected_seasons = st.multiselect("Seleziona Stagioni", seasons_opt, default=['24-25'])
    selected_stats = st.multiselect("Seleziona Statistiche", stats_opt, default=['standard'])
    
    start_btn = st.button("Avvia Scraping", type="primary")

# --- FUNZIONE DI SCRAPING ---
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

    # --- SELENIUM SETUP OTTIMIZZATO ---
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # IMPOSTAZIONI CRITICHE PER LINUX/STREAMLIT CLOUD
    # Diciamo a Selenium dove trovare esattamente Chromium e il Driver di sistema
    options.binary_location = "/usr/bin/chromium"
    
    try:
        # Invece di scaricare il driver, usiamo quello installato da packages.txt
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        
        # FIX ANTI-BOT
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        st.error(f"Errore avvio Driver: {e}")
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
                    # Evitiamo errore se total_steps è 0
                    if total_steps > 0:
                        progress_val = min(current_step / total_steps, 0.99)
                        progress_bar.progress(progress_val)
                    
                    if s_type not in type_map: continue
                    
                    status_text.text(f"Scraping in corso: {league} {season} - Tabella: {s_type}...")
                    
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
                        
                        # --- PULIZIA DATI ---
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
                            # Intersezione sicura delle colonne chiave
                            merge_on = [c for c in id_cols if c in existing_cols and c in current_cols]
                            
                            if merge_on:
                                merged_data_storage[group_key] = pd.merge(
                                    merged_data_storage[group_key], df, on=merge_on, how='outer'
                                )
                    except Exception as e:
                        print(f"Errore scraping {league} {season} {s_type}: {e}")
                        continue

    except Exception as main_e:
        st.error(f"Errore critico durante lo scraping: {main_e}")
    finally:
        # Chiudiamo tutto correttamente
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

# --- ESECUZIONE ---
if start_btn:
    if not selected_leagues or not selected_seasons or not selected_stats:
        st.warning("Seleziona almeno un campionato, una stagione e una statistica.")
    else:
        # FIX SINTASSI: Uso virgolette doppie esterne per gestire l'apostrofo interno
        with st.spinner("Sto scaricando i dati da Fbref... (L'operazione può richiedere tempo)"):
            df_result = scrape_fbref_merged(selected_leagues, selected_seasons, selected_stats)
        
        if not df_result.empty:
            st.success("Scraping completato!")
            st.write(f"Righe scaricate: {len(df_result)}")
            st.dataframe(df_result.head())
            
            csv = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Scarica CSV",
                data=csv,
                file_name="fbref_data_merged.csv",
                mime="text/csv"
            )
        else:
            st.error("Nessun dato trovato o errore durante lo scraping. Controlla i log.")