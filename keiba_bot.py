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
        # テクニカル分析：直近のタイム差を重視
        weights = [1.0, 0.7, 0.4]
        score = 0
        for i, d in enumerate(diffs):
            # 1.0秒以内なら評価対象
            val = max(0, 1.0 - d) 
            score += (val * 20) * weights[i]
        return score
    except: return 0

def get_lab_data(date_str, place_name, race_num):
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    base_url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"🚀 【精度向上】テクニカル・タイム差スキャン開始...")
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

                # タイム差スコア
                time_score = get_time_diff_score(horse_url)

                # 💡 期待値（穴馬）加点：オッズが高く、タイム差が良い馬を優遇
                ana_bonus = 0
                if odds >= 15.0 and time_score > 5:
                    ana_bonus = time_score * 0.5

                # 騎手補正
                j_bonus = 15 if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', '岩田', '鮫島']) else 0
                
                total_score = time_score + ana_bonus + j_bonus
                
                horses.append({
                    "num": int(umaban), "name": name, "jockey": jockey, 
                    "odds": odds, "score": total_score, "is_ana": (odds >= 15.0)
                })
                print(f"  🔍 {umaban}番 {name}: 分析完了")
            except: continue
            
        return horses, title
    except Exception as e:
        print(f"❌ エラー: {e}"); return [], "エラー"

def send_discord(horses, title, d, p, r):
    if len(horses) < 5:
        print("⚠️ 抽出馬が少なすぎるため送信をスキップしました。"); return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 👑 頭2軸（上位2頭）
    axis = df.head(2)['num'].tolist()
    # 🐎 相手（3位〜7位）
    opponents = df.iloc[2:7]['num'].tolist()
    # 穴馬フラグ（オッズ15倍以上でスコア上位）
    ana_list = [str(h['num']) for _, h in df.iterrows() if h['is_ana'] and h['num'] in (axis + opponents)]
    ana_str = ", ".join(ana_list) if ana_list else "特になし"
    
    payload = {
        "username": "ゆーこうAI (テクニカル2軸) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **【3連単 頭2軸フォーメーション】**",
            "color": 15548997, # Red/Pink
            "fields": [
                {"name": "👑 1着固定(2軸)", "value": f"**{axis[0]}番** ({df.iloc[0]['name']})\n**{axis[1]}番** ({df.iloc[1]['name']})", "inline": False},
                {"name": "🐎 2・3着候補 (紐)", "value": f"{', '.join(map(str, opponents))}", "inline": False},
                {"name": "💰 推奨買い目: 3連單", "value": f"**1着**: {axis[0]}, {axis[1]}\n**2着**: {axis[0]}, {axis[1]}, {opponents[0]}, {opponents[1]}\n**3着**: 全流し or 紐5頭", "inline": False},
                {"name": "⚠️ 注目穴馬", "value": ana_str, "inline": False}
            ],
            "footer": {"text": "アルデバランSの114万馬券(7-15-1)を狙える広域ロジック"}
        }]
    }
    res = requests.post(DISCORD_URL, json=payload)
    if res.status_code == 204:
        print("✅ Discord通知を送信しました。")
    else:
        print(f"❌ Discord送信失敗 (Status: {res.status_code}): {res.text}")

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 and args[1] != "" else "20260222"
    place = args[2] if len(args) > 2 and args[2] != "" else "東京"
    race = args[3] if len(args) > 3 else "11"
    h, t = get_lab_data(date, place, race)
    send_discord(h, t, date, place, race)
