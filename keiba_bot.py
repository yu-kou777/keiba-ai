import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def analyze_singularity(horse_url, odds):
    """過去3走のタイム差を解析し、エネルギー充填率(Score)を算出"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(0.4)
        res = requests.get("https://www.keibalab.jp" + horse_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        
        diffs = []
        for row in rows[:3]:
            txt = row.find_all('td')[13].text.strip() if len(row.find_all('td')) > 13 else ""
            m = re.search(r'(-?\d+\.\d+)', txt)
            if m: diffs.append(float(m.group(1)))
        
        if not diffs: return 0, False
        
        # 1. タイム差の収束性 (0.3秒以内を『特異点』と定義)
        convergence = sum(40 for d in diffs if d <= 0.3)
        # 2. 平均ポテンシャル
        avg_poten = max(0, 1.2 - (sum(diffs)/len(diffs))) * 20
        # 3. 市場の歪み (穴馬フラグ)
        is_chaos = (min(diffs) <= 0.5 and odds > 20.0)
        
        return (convergence + avg_poten), is_chaos
    except: return 0, False

def get_lab_data(date_str, place_name, race_num):
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"📡 物理解析エンジン起動中...")
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.select_one('h1.raceTitle').text.strip().replace('\n', ' ')
        
        horses = []
        for row in soup.find_all('tr'):
            name_tag = row.select_one('a[href*="/db/horse/"]')
            if not name_tag or len(row.find_all('td')) < 5: continue
            
            name = name_tag.text.strip()
            # 馬番抽出
            tds = row.find_all('td')
            umaban = re.sub(r'\D', '', tds[list(row.find_all('td')).index(name_tag.find_parent('td')) - 1].text)
            jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else ""
            odds = float(re.search(r'(\d+\.\d+)', row.text).group(1)) if re.search(r'(\d+\.\d+)', row.text) else 99.0
            
            score, is_ana = analyze_singularity(name_tag.get('href'), odds)
            # 騎手補正
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15

            horses.append({"num": int(umaban), "name": name, "score": score, "is_ana": is_ana})
            print(f"  🔍 馬番{umaban}: 解析完了")
            
        return horses, title
    except Exception as e: return [], "解析エラー"

def send_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 👑 軸2頭 (Singularity)
    axis = df.head(2)['num'].tolist()
    # 🐎 2列目 (軸 + Bridge)
    bridge = df.iloc[2:4]['num'].tolist()
    row2 = axis + bridge
    # 💰 3列目 (2列目 + Chaos)
    chaos = df[df['is_ana']].head(2)['num'].tolist()
    row3 = list(set(row2 + chaos + df.iloc[4:5]['num'].tolist()))[:6]

    payload = {
        "username": "教授AI (数理的3連単) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **24点・高回収率フォーメーション**",
            "color": 3447003,
            "fields": [
                {"name": "👑 1着軸 (2頭)", "value": f"**{axis[0]}番, {axis[1]}番**", "inline": True},
                {"name": "🐎 2着候補 (4頭)", "value": f"{', '.join(map(str, row2))}", "inline": True},
                {"name": "🌀 3着候補 (6頭)", "value": f"{', '.join(map(str, row3))}", "inline": True},
                {"name": "💰 推奨買い目: 3連単(24点)", "value": f"**1着**: {axis[0]}, {axis[1]}\n**2着**: {', '.join(map(str, row2))}\n**3着**: {', '.join(map(str, row3))}", "inline": False},
                {"name": "📈 理論的根拠", "value": "過去3走のタイム差が0.3秒以内の『収束』を検知。軸馬が2着に落ちる事象をカバーし、かつ低人気高ポテンシャル馬を3列目に配置しました。", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 and args[1] != "" else "20260222"
    place = args[2] if len(args) > 2 and args[2] != "" else "東京"
    race = args[3] if len(args) > 3 else "11"
    h, t = get_lab_data(date, place, race)
    send_discord(h, t, date, place, race)

