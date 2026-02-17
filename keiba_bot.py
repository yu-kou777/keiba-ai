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
import statistics

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
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

def create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def safe_float(value):
    try:
        return float(re.sub(r'[^\d\.-]', '', str(value)))
    except: return 99.9

def analyze_potential_energy(session, horse_url, odds):
    """
    【大穴・7番捕獲ロジック】
    勝ち星よりも「惜敗（タイム差0.1-0.5）」を過大評価し、
    潜在エネルギーの高い馬をスコア上位に押し上げる。
    """
    try:
        if not horse_url.startswith("http"): horse_url = "https://www.keibalab.jp" + horse_url
        time.sleep(random.uniform(1.0, 2.0))
        
        res = session.get(horse_url, headers=get_stealth_headers(), timeout=20, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, False, "データなし"
        
        diffs = []
        for row in rows[:4]: # 直近4走を見る
            tds = row.find_all('td')
            if len(tds) < 14: continue
            
            # タイム差取得
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = safe_float(txt)
                    break
            
            # 見つからなければ着順から補完
            if val == 99.9 and len(tds) > 11:
                rank_txt = tds[11].text.strip()
                if rank_txt.isdigit():
                    rank = int(rank_txt)
                    if rank == 1: val = -0.1 # 勝ち
                    elif rank <= 3: val = 0.2
                    else: val = 1.0

            if val < 5.0: diffs.append(val)

        if not diffs: return 0, False, "不明"
        
        # --- 教授の「惜敗係数」計算 ---
        score = 0
        
        # 1. 「負けて強し」ボーナス (0.0秒〜0.5秒差負けを最大評価)
        # 7番のような「勝てないが強い馬」を拾うための核心
        regret_count = sum(1 for d in diffs if 0.0 <= d <= 0.5)
        score += regret_count * 40 
        
        # 2. 安定度 (標準偏差的な考え)
        avg_diff = sum(diffs) / len(diffs)
        if avg_diff < 0.6: score += 30
        
        # 3. 爆発トリガー (大穴フラグ)
        # 「平均タイム差が良い」かつ「オッズが甘い(10倍以上)」
        # 15番のような馬をここで検知
        is_chaos = (avg_diff < 0.9 and odds > 10.0)
        if is_chaos: score += 20 # 穴馬補正

        return score, is_chaos, f"平均差:{avg_diff:.2f}"
        
    except Exception: return 0, False, "エラー"

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

                score, is_chaos, note = analyze_potential_energy(session, name_tag.get('href'), odds)
                
                # 騎手補正 (少し控えめに)
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井']): score += 5
                
                print(f"  √ {umaban}番 {name}: {score} ({note})")
                horses.append({"num": int(umaban), "name": name, "score": score, "is_ana": is_chaos})
            except: continue
                
        return horses, title
    except Exception as e:
        print(f"❌ エラー: {e}"); return [], "エラー"

def send_to_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # --- 教授の「3頭クエーサー」戦略 ---
    # 1列目: スコア上位3頭（ここに7番を入れる！）
    head_3 = df.head(3)['num'].tolist()
    
    # 2列目: 上位3頭 + 穴フラグ持ち1頭
    ana_list = df[df['is_ana']]['num'].tolist()
    row2 = list(dict.fromkeys(head_3 + ana_list[:1])) # 重複除いて最大4頭
    
    # 3列目: 上位 + 穴 + 補欠
    row3 = list(dict.fromkeys(head_3 + ana_list + df.iloc[3:7]['num'].tolist()))[:7]

    buy_str = (
        f"**1着**: {', '.join(map(str, head_3))}\n"
        f"**2着**: {', '.join(map(str, row2))}\n"
        f"**3着**: {', '.join(map(str, row3))}"
    )
    
    payload = {
        "username": "教授AI (3頭戦略モード) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **大穴捕獲・3頭頭フォーメーション**",
            "color": 16711680, # Red
            "fields": [
                {"name": "👑 1着候補 (3頭)", "value": f"**{', '.join(map(str, head_3))}**\n(7番のような惜敗組を格上げ)", "inline": False},
                {"name": "🐎 2着・3着ゾーン", "value": f"**2着**: {', '.join(map(str, row2))}\n**3着**: {', '.join(map(str, row3))}", "inline": False},
                {"name": "💰 推奨買い目", "value": buy_str, "inline": False},
                {"name": "📈 教授の狙い", "value": "『勝ってはいないがタイム差が優秀』な馬を1列目に固定。15番などのカオス（穴馬）を2・3列目で網羅し、10万〜100万クラスの配当を狙い撃ちます。", "inline": False}
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
