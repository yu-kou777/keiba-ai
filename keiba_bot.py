import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_time_diff_score(horse_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(0.4)
        res = requests.get("https://www.keibalab.jp" + horse_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        diffs = []
        for row in rows[:3]: # 直近3走
            tds = row.find_all('td')
            if len(tds) > 13:
                txt = tds[13].text.strip()
                match = re.search(r'(-?\d+\.\d+)', txt)
                if match: diffs.append(float(match.group(1)))
        
        if not diffs: return 0
        weights = [1.0, 0.8, 0.5]
        score = 0
        for i, d in enumerate(diffs):
            val = max(0, 1.2 - d) # タイム差1.2秒以内を評価
            score += (val * 15) * weights[i]
        return score
    except: return 0

def get_lab_data(date_str, place_name, race_num):
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    base_url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"🚀 【特大配当狙い】テクニカル・穴馬スキャン開始...")
        res = requests.get(base_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.select_one('h1.raceTitle').text.strip().replace('\n', ' ') if soup.select_one('h1.raceTitle') else "解析"
        
        horses, seen_num = [], set()
        rows = soup.find_all('tr')
        
        for row in rows:
            name_tag = row.select_one('a[href*="/db/horse/"]')
            if not name_tag: continue
            tds = row.find_all('td')
            if len(tds) < 5: continue
            
            try:
                name = name_tag.text.strip()
                horse_url = name_tag.get('href')
                
                # 馬番特定
                td_list = list(tds)
                name_td = name_tag.find_parent('td')
                name_idx = td_list.index(name_td)
                umaban = re.sub(r'\D', '', td_list[name_idx - 1].text.strip())
                if not umaban or umaban in seen_num: continue
                seen_num.add(umaban)

                jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else "不明"
                
                # オッズ
                odds = 999.0
                o_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
                if o_match: odds = float(o_match.group(1))

                # 1. タイム差スコア (過去3走)
                time_score = get_time_diff_score(horse_url)

                # 2. 期待値（穴馬）ボーナス 
                # 「タイム差が良いのに人気がない馬」に爆発的な加点
                under_value_bonus = 0
                if odds > 20.0 and time_score > 10:
                    under_value_bonus = time_score * 0.8 # 穴馬への偏重

                # 3. 騎手補正
                j_bonus = 15 if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', '岩田', '鮫島']) else 0
                
                total_score = time_score + under_value_bonus + j_bonus
                
                horses.append({
                    "num": int(umaban), "name": name, "jockey": jockey, 
                    "odds": odds, "score": total_score, "is_ana": (odds > 20.0)
                })
                print(f"  🔍 {umaban}番 {name}: 判定終了")
            except: continue
            
        return horses, title
    except Exception as e:
        print(f"❌ エラー: {e}"); return [], "エラー"

def send_discord(horses, title, d, p, r):
    if len(horses) < 5: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 頭2軸（上位2頭）
    top2 = df.head(2)
    axis = top2['num'].tolist()
    
    # 相手候補（3〜7位）
    opponents = df.iloc[2:8]['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI (100万馬券狙い) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **【3連単 1着2頭軸フォーメーション】**",
            "color": 15158332, # Red
            "fields": [
                {"name": "👑 1着軸 (2頭)", "value": f"**{axis[0]}番** ({df.iloc[0]['name']})\n**{axis[1]}番** ({df.iloc[1]['name']})", "inline": False},
                {"name": "🐎 相手 (紐)", "value": f"{', '.join(map(str, opponents))}", "inline": False},
                {"name": "💰 推奨買い目: 3連単(2軸)", "value": f"**1着**: {axis[0]}, {axis[1]}\n**2着**: {axis[0]}, {axis[1]}, {opponents[0]}, {opponents[1]}\n**3着**: 全て ({axis[0]}, {axis[1]}, {', '.join(map(str, opponents))})", "inline": False},
                {"name": "⚠️ 穴馬フラグ", "value": f"今回検出された注目の穴馬: **{', '.join([str(h['num']) for h in horses if h['is_ana'] and h['score'] > 15])}**", "inline": False}
            ],
            "footer": {"text": "アルデバランSの114万馬券を教訓に、タイム差重視の穴馬ロジックを強化しました。"}
        }]
    }
    requests.post(DISCORD_URL, json=payload)
    print("✅ 2軸フォーメーションで送信完了。")

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 and args[1] != "" else "20260222"
    place = args[2] if len(args) > 2 and args[2] != "" else "東京"
    race = args[3] if len(args) > 3 else "11"
    h, t = get_lab_data(date, place, race)
    send_discord(h, t, date, place, race)
