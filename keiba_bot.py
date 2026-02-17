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

# SSL警告無視
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Discord接続設定 ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_stealth_headers():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1"
    }

def create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def safe_float(value):
    try: return float(re.sub(r'[^\d\.-]', '', str(value)))
    except: return 99.9

def analyze_potential(session, horse_url, odds):
    """
    【教授の評価順位算出ロジック】
    あなたのExcelデータの「評価順位」を再現するため、
    タイム差の安定性と爆発力を数値化してランク付けする。
    """
    try:
        if not horse_url.startswith("http"): horse_url = "https://www.keibalab.jp" + horse_url
        time.sleep(random.uniform(0.5, 1.0))
        
        res = session.get(horse_url, headers=get_stealth_headers(), timeout=20, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, "データなし"
        
        diffs = []
        for row in rows[:4]: # 直近4走
            tds = row.find_all('td')
            if len(tds) < 14: continue
            
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = safe_float(txt)
                    break
            
            # 着順補完
            if val == 99.9 and len(tds) > 11:
                rank_txt = tds[11].text.strip()
                if rank_txt.isdigit():
                    rank = int(rank_txt)
                    if rank == 1: val = -0.1
                    elif rank <= 3: val = 0.2
                    else: val = 0.8

            if val < 5.0: diffs.append(val)

        if not diffs: return 0, "不明"
        
        # --- スコア計算（評価順位の作成） ---
        score = 0
        
        # 1. 基礎能力（平均タイム差）
        # 小さいほど良い。マイナス（圧勝）はさらに加点
        avg_diff = sum(diffs) / len(diffs)
        score += (1.5 - avg_diff) * 30 
        
        # 2. 爆発力（0.2秒以内の好走経験）
        # 1位や2位を取りきる力
        sharpness = sum(1 for d in diffs if d <= 0.2)
        score += sharpness * 15
        
        # 3. 安定感（0.9秒以内の大崩れしない力）
        # 4頭BOXに入れるべき信頼性
        stability = sum(1 for d in diffs if d <= 0.9)
        score += stability * 5

        # 4. オッズ補正（人気馬の信頼度担保）
        # あなたのデータでは上位人気もしっかり評価されていたため
        if odds < 5.0: score += 10
        elif odds < 10.0: score += 5

        return score, f"平均差:{avg_diff:.2f}"
        
    except Exception: return 0, "エラー"

def get_race_data(date_str, place_name, race_num):
    if not date_str or len(date_str) < 8: date_str, place_name, race_num = "20260207", "京都", "11"
    p_code = LAB_PLACE_MAP.get(place_name, "08")
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{str(race_num).zfill(2)}/"
    
    print(f"📡 解析開始: {url}")
    session = create_session()
    
    try:
        res = session.get(url, headers=get_stealth_headers(), timeout=30, verify=False)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.select_one('h1.raceTitle').text.strip().replace('\n', ' ') if soup.select_one('h1.raceTitle') else "レース"
        
        horses = []
        rows = soup.find_all('tr')
        
        for row in rows:
            name_tag = row.select_one('a[href*="/db/horse/"]')
            if not name_tag: continue
            try:
                name = name_tag.text.strip()
                umaban = "0"
                tds = row.find_all('td')
                for i, td in enumerate(tds):
                    if td == name_tag.find_parent('td'):
                        if i > 0 and tds[i-1].text.strip().isdigit():
                            umaban = tds[i-1].text.strip()
                        break
                if umaban == "0": continue

                odds = 99.9
                m = re.search(r'(\d{1,4}\.\d{1})', row.text)
                if m: odds = float(m.group(1))
                
                jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else ""

                score, note = analyze_potential(session, name_tag.get('href'), odds)
                
                # 騎手補正
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 5
                
                print(f"  √ {umaban}番 {name}: 評価点 {score:.1f}")
                horses.append({"num": int(umaban), "name": name, "score": score})
            except: continue
                
        return horses, title
    except Exception as e:
        print(f"❌ エラー: {e}"); return [], "エラー"

def send_to_discord(horses, title, d, p, r):
    if not horses: return
    # スコア順にソートして「評価順位」を決定
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 評価順位 1位～5位を取得
    rank1 = df.iloc[0]
    rank2 = df.iloc[1]
    rank3 = df.iloc[2]
    rank4 = df.iloc[3]
    rank5 = df.iloc[4]
    
    # --- プラン1：基本の4頭BOX (24点) ---
    box_members = [rank1['num'], rank2['num'], rank3['num'], rank4['num']]
    box_str = f"**{', '.join(map(str, box_members))}**"
    box_names = f"1位:{rank1['name']}, 2位:{rank2['name']}, 3位:{rank3['name']}, 4位:{rank4['name']}"

    # --- プラン2：勝負の1頭軸流し (12点) ---
    axis = rank1['num']
    opponents = [rank2['num'], rank3['num'], rank4['num'], rank5['num']]
    form_str = f"**1着**: {axis}\n**2・3着**: {', '.join(map(str, opponents))}"
    
    payload = {
        "username": "教授AI (黄金律プログラム) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **少点数・高回収率モデル**",
            "color": 16763904, # Gold
            "fields": [
                {"name": "📊 AI評価順位 (Top 5)", "value": f"1位: **{rank1['num']} {rank1['name']}**\n2位: **{rank2['num']} {rank2['name']}**\n3位: **{rank3['num']} {rank3['name']}**\n4位: **{rank4['num']} {rank4['name']}**\n5位: **{rank5['num']} {rank5['name']}**", "inline": False},
                {"name": "🛡️ 【プラン1】基本戦略 (24点)", "value": f"買い目: **3連単 4頭BOX**\n選出馬: {box_str}\n理論: あなたのデータ解析で、シルクロードS(24万)と根岸S(16万)を的中させた黄金パターン。", "inline": False},
                {"name": "⚔️ 【プラン2】勝負戦略 (12点)", "value": f"買い目: **3連単 1着固定流し**\n{form_str}\n理論: 評価1位の信頼度が高い場合の、コスト圧縮・利益最大化プラン。", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)
    print("✅ Discord送信完了")

if __name__ == "__main__":
    try:
        args = sys.argv
        date = args[1] if len(args) > 1 else "20260207"
        place = args[2] if len(args) > 2 else "京都"
        race = args[3] if len(args) > 3 else "11"
    except: date, place, race = "20260207", "京都", "11"
    
    h, t = get_race_data(date, place, race)
    send_to_discord(h, t, date, place, race)
