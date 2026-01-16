# ⚽ Scrape That! - FBRef Player Data Scraper

This project is a powerful, user-friendly **Streamlit** application designed to scrape, merge, and export comprehensive football player statistics from [FBRef](https://fbref.com).

It automates the tedious process of navigating multiple pages and tables, allowing analysts and data enthusiasts to build unified datasets containing all Fbref stats in one row per player.

---

## 🚀 Key Features

* **Multi-League Support:** Extract data from the "Big 5" European leagues (Premier League, Serie A, La Liga, Bundesliga, Ligue 1).
* **Historical Data:** Capable of scraping seasons from 2017-2018 up to the current 2025-2026 campaign.
* **Unified Datasets:** Automatically merges different statistical tables based on Player, Squad, and Season.
* **Anti-Blocking Measures:** Implements Selenium with custom headers and delays to mimic human behavior and avoid basic scraping blocks.

---

## 📊 Data Structure

The output is a merged CSV file where every row represents a unique player-season entry.

* **Identifiers:** Player, Nation, Pos, Squad, Age, Born, League, Season.
* **Metric Prefixes:** To avoid column name collisions, columns are prefixed with their source category:
    * `shooting_Gls`, `shooting_Sh`, `shooting_SoT`...
    * `passing_Cmp`, `passing_Att`, `passing_PrgP`...
    * `defense_Tkl`, `defense_Int`, `defense_Blocks`...

---

## ☕ Support the Dev

Let's be honest: maintaining a scraper is a game of cat and mouse, and debugging Selenium requires a steady stream of caffeine. 

If this tool saved you hours of manual copy-pasting or helped you win your Fantasy Football league, consider fueling my next coding session. I can't scrape coffee beans (yet), so I have to buy them.

<a href="https://buymeacoffee.com/antoniolupo" target="_blank">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >
</a>
