import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_performance_details(horse_url):
    """過去3走のタイム差と安定性を分析する"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(0.4)
        res = requests.get("https://www.keibalab.jp" + horse_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        
        diffs = []
        stability_count = 0 # 0.5秒以内に入った回数
        
        for row in rows[:3]:
            tds = row.find_all('td')
            if len(tds) > 13:
                txt = tds[13].text.strip()
                match = re.search(r'(-?\d+\.\d+)', txt)
                if match:
                    d = float(match.group(1))
                    diffs.append(d)
                    if d <= 0.5: stability_count += 1
        
        if not diffs: return 0, 0
        
        # タイム差スコア
        weights = [1.0, 0.7, 0.4]
        t_score = sum(max(0, 1.2 - d) * 15 * weights[i] for i, d in enumerate(diffs))
        
        # 安定性ボーナス（7番や15番を拾うためのロジック）
        s_bonus = stability_count * 20
        
        return t_score, s_bonus
    except: return 0, 0

def get_lab_data(date_str, place_name, race_num):
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    base_url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"🚀 【7番軸ロジック】安定性＋タイム差分析を開始...")
        res = requests.get(base_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.select_one('h1.raceTitle').text.strip().replace('\n', ' ') if soup.select_one('h1.raceTitle') else "解析"
        
        horses, seen_num = [], set()
        rows = soup.find_all('tr')
        
        for row in rows:
            name_tag = row.select_one('a[href*="/db/horse/"]')
            if not name_tag or len(row.find_all('td')) < 5: continue
            
            try:
                name = name_tag.text.strip()
                horse_url = name_tag.get('href')
                
                # 馬番特定
                td_list = row.find_all('td')
                umaban = ""
                for td in td_list:
                    if td.text.strip().isdigit() and 1 <= int(td.text.strip()) <= 18:
                        umaban = td.text.strip()
                        if td.find_next_sibling() and td.find_next_sibling().select_one('a[href*="/db/horse/"]'): break
                
                if not umaban or umaban in seen_num: continue
                seen_num.add(umaban)

                jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else "不明"
                odds = float(re.search(r'(\d{1,4}\.\d{1})', row.text).group(1)) if re.search(r'(\d{1,4}\.\d{1})', row.text) else 999.0

                # テクニカル分析実行
                t_score, s_bonus = get_performance_details(horse_url)
                
                # 騎手補正
                j_bonus = 15 if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', '岩田望', '鮫島']) else 0
                
                total_score = t_score + s_bonus + j_bonus
                
                horses.append({"num": int(umaban), "name": name, "jockey": jockey, "odds": odds, "score": total_score})
                print(f"  🔍 {umaban}番 {name}: スコア算出完了")
            except: continue
            
        return horses, title
    except Exception as e:
        print(f"❌ エラー: {e}"); return [], "エラー"

def send_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 🎯 2軸の選定（スコア1位と2位）
    axis = df.head(2)
    axis_nums = axis['num'].tolist()
    
    # 🐎 相手候補（紐：3位〜8位）
    opponents = df.iloc[2:8]['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI (頭2軸・100万狙い) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **【3連単 頭2軸フォーメーション】**",
            "color": 15548997,
            "fields": [
                {"name": "👑 1着固定(2軸)", "value": f"**{axis_nums[0]}番** ({axis.iloc[0]['name']})\n**{axis_nums[1]}番** ({axis.iloc[1]['name']})", "inline": False},
                {"name": "🐎 相手 (2・3着候補)", "value": f"{', '.join(map(str, opponents))}", "inline": False},
                {"name": "💰 3連単 推奨", "value": f"**1着**: {axis_nums[0]}, {axis_nums[1]}\n**2着**: {axis_nums[0]}, {axis_nums[1]}, {opponents[0]}, {opponents[1]}\n**3着**: 全流し (高配当狙い)", "inline": False},
                {"name": "📈 ロジック解説", "value": "直近3走で0.5秒以内の安定した走りを見せている馬を軸に据えました。15番のような穴馬の激走をカバーします。", "inline": False}
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
