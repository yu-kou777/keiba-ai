# -*- coding: utf-8 -*-
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time
import random
import os # 環境検知用に追加

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定：Discord Webhook ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"
LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_stealth_headers():
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Referer": "https://www.google.com/"}

def analyze_horse(session, url, name):
    try:
        if not url.startswith("http"): url = "https://www.keibalab.jp" + url
        time.sleep(random.uniform(0.5, 1.0))
        res = session.get(url, headers=get_stealth_headers(), timeout=15, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, 9.9
        
        diffs = []
        for row in rows[:5]:
            tds = row.find_all('td')
            if len(tds) < 14: continue
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = float(re.sub(r'[^\d\.-]', '', txt))
                    break
            if val < 5.0: diffs.append(val)
        
        if not diffs: return 0, 9.9
        best = min(diffs)
        score = (60 if best <= 0.0 else 45 if best <= 0.3 else 0) + (sum(1 for d in diffs if 0.0 <= d <= 0.5) * 15)
        return score, best
    except: return 0, 9.9

def run_prediction(d, p, r):
    if not d: d = time.strftime("%Y%m%d")
    p_code = LAB_PLACE_MAP.get(p, "05")
    # 未来の出馬表ページを優先
    url = f"https://www.keibalab.jp/db/race/{d}{p_code}{str(r).zfill(2)}/shutsubahyou.html"
    print(f"📡 解析開始: {url}")
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=3))
    
    try:
        res = session.get(url, headers=get_stealth_headers(), timeout=30, verify=False)
        # もし出馬表がなければ結果ページを試す
        if res.status_code != 200:
            url = url.replace("/shutsubahyou.html", "/")
            res = session.get(url, headers=get_stealth_headers(), timeout=30, verify=False)
            
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.select_one('h1.raceTitle').text.strip().replace('\n', ' ') if soup.select_one('h1.raceTitle') else "Race"
        
        horses = []
        rows = soup.find_all('tr')
        for row in rows:
            link = row.select_one('a[href*="/db/horse/"]')
            if not link: continue
            name = link.text.strip()
            # 馬番とオッズ
            tds = row.find_all('td')
            umaban = next((td.text.strip() for td in tds if td.text.strip().isdigit()), "0")
            odds_m = re.search(r'(\d{1,4}\.\d{1})', row.text)
            odds = float(odds_m.group(1)) if odds_m else 99.9
            
            score, best = analyze_horse(session, link.get('href'), name)
            print(f"  √ {umaban}番 {name}: {score}点")
            horses.append({"num": int(umaban), "score": score, "is_ana": (best <= 0.6 and odds > 15.0)})
            
        return horses, title
    except Exception as e:
        print(f"❌ Error: {e}"); return [], "Err"

def send_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    row1 = df.head(3)['num'].tolist()
    row2 = df.head(5)['num'].tolist()
    ana = df[df['is_ana']]['num'].tolist()
    # フィルタによる点数調整
    top = df.iloc[0]['score']
    limit = 5 if top >= 75 else 9
    row3 = list(dict.fromkeys(row2 + ana + df.iloc[5:8]['num'].tolist()))[:limit]

    payload = {"username":"教授AI","embeds":[{"title":f"🎯 {p}{r}R {title}","description":f"📅 {d} | **3-5-{limit}構成**","fields":[{"name":"🔥 軸・相手","value":f"{row1} → {row2}"},{"name":"💰 買い目","value":f"1:{row1}\n2:{row2}\n3:{row3}"}]}]}
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 else ""
    place = args[2] if len(args) > 2 else "東京"
    race = args[3] if len(args) > 3 else "11"
    
    h, t = run_prediction(date, place, race)
    send_discord(h, t, date, place, race)
    
    # --- 修正箇所：GitHub Actionsではinputをスキップする ---
    if not os.environ.get('GITHUB_ACTIONS'):
        input("\n解析完了。Enterで閉じます...")
    else:
        print("\n✅ [GitHub Actions] 処理を正常終了しました。")
