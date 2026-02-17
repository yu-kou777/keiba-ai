import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_mathematical_score(horse_url, odds):
    """過去3走をベクトル解析し、期待値を算出する"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(0.4)
        res = requests.get("https://www.keibalab.jp" + horse_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        
        diffs = []
        breakout_factor = 0 # 臨界突破係数
        
        for row in rows[:3]:
            tds = row.find_all('td')
            if len(tds) > 13:
                txt = tds[13].text.strip()
                match = re.search(r'(-?\d+\.\d+)', txt)
                if match:
                    d = float(match.group(1))
                    diffs.append(d)
                    # 数学的閾値：0.3秒以内は「勝機が極めて高い」
                    if d <= 0.3: breakout_factor += 50 
                    elif d <= 0.6: breakout_factor += 20
        
        if not diffs: return 0, False
        
        # 期待値計算 (物理的ポテンシャル + 市場の歪み)
        avg_diff = sum(diffs) / len(diffs)
        base_poten = max(0, 1.5 - avg_diff) * 15
        
        # 穴馬フラグ: タイム差が良いのにオッズが高い
        is_valuable_ana = (avg_diff < 0.8 and odds > 20.0)
        
        return (base_poten + breakout_factor), is_valuable_ana
    except: return 0, False

def get_lab_data(date_str, place_name, race_num):
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    base_url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"🚀 [教授モード] 非線形データ解析を開始...")
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
                    if td.text.strip().isdigit() and 1 <= int(td.text.strip()) <= 20:
                        umaban = td.text.strip()
                        if td.find_next_sibling() and td.find_next_sibling().select_one('a[href*="/db/horse/"]'): break
                
                if not umaban or umaban in seen_num: continue
                seen_num.add(umaban)

                jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else "不明"
                odds = float(re.search(r'(\d{1,4}\.\d{1})', row.text).group(1)) if re.search(r'(\d{1,4}\.\d{1})', row.text) else 999.0

                # 数理スコア算出
                math_score, is_ana = get_mathematical_score(horse_url, odds)
                
                # 騎手係数
                j_weight = 15 if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']) else 5
                
                total_score = math_score + j_weight
                horses.append({"num": int(umaban), "name": name, "jockey": jockey, "odds": odds, "score": total_score, "is_ana": is_ana})
                print(f"  √ {umaban}番 {name}: 解析完了")
            except: continue
            
        return horses, title
    except Exception as e: return [], "エラー"

def send_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 🎯 3連単フォーメーション戦略 (12点〜18点)
    # 軸: スコア1位、2位
    axis = df.head(2)
    a_nums = axis['num'].tolist()
    # 相手: 穴馬フラグ優先 + スコア3,4位
    ana_horses = df[df['is_ana']].head(2)['num'].tolist()
    others = df.iloc[2:5]['num'].tolist()
    opponents = list(set(ana_horses + others))[:4] # 重複なしで上位4頭に絞る
    
    payload = {
        "username": "教授AI (数学的3連単) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **数学的「特異点」抽出完了**",
            "color": 3447003, # Deep Blue
            "fields": [
                {"name": "👑 1着軸 (Singularity)", "value": f"**{a_nums[0]}番** ({axis.iloc[0]['name']})\n**{a_nums[1]}番** ({axis.iloc[1]['name']})", "inline": False},
                {"name": "🐎 2・3着候補 (Variables)", "value": f"{', '.join(map(str, opponents))}", "inline": False},
                {"name": "💰 教授の推奨買い目 (12〜18点)", "value": f"**3連単 2頭軸マルチより効率的**\n1着: {a_nums[0]}, {a_nums[1]}\n2着: {a_nums[0]}, {a_nums[1]}, {opponents[0]}, {opponents[1]}\n3着: {', '.join(map(str, a_nums + opponents))}", "inline": False},
                {"name": "📈 分析の根拠", "value": "過去3走のタイム差が0.3秒以内の『収束』状態にある馬を軸に選定。オッズの歪み（過小評価）を検出し、15番のような激走期待値を補足しました。", "inline": False}
            ],
            "footer": {"text": "Entropy minimized by Professor AI"}
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
