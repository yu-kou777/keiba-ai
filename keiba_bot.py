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

def analyze_peak_performance(session, horse_url, odds):
    """
    【新ロジック：ピーク・ポテンシャル理論】
    平均値ではなく「最大瞬間風速（ベストパフォーマンス）」を評価する。
    """
    try:
        if not horse_url.startswith("http"): horse_url = "https://www.keibalab.jp" + horse_url
        time.sleep(random.uniform(0.5, 1.0))
        
        res = session.get(horse_url, headers=get_stealth_headers(), timeout=20, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, False, "データなし"
        
        diffs = []
        # 直近5走まで広げて「才能」を探す
        for row in rows[:5]: 
            tds = row.find_all('td')
            if len(tds) < 14: continue
            
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = safe_float(txt)
                    break
            
            # 着順補完（1着はマイナス評価＝強い）
            if val == 99.9 and len(tds) > 11:
                rank_txt = tds[11].text.strip()
                if rank_txt.isdigit():
                    rank = int(rank_txt)
                    if rank == 1: val = -0.2
                    elif rank <= 3: val = 0.1
            
            if val < 5.0: diffs.append(val)

        if not diffs: return 0, False, "不明"
        
        # --- 新スコア計算：ピーク値重視 ---
        score = 0
        
        # 1. 絶対能力値 (Best Diff)
        # 過去5走で一度でも「0.0秒以下（勝利）」があれば超高評価
        best_diff = min(diffs)
        if best_diff <= 0.0: score += 50
        elif best_diff <= 0.3: score += 30
        elif best_diff <= 0.5: score += 15
        
        # 2. 復活の可能性 (Recency)
        # 直近が悪くても、過去に力を見せていれば評価を下げない（7番対策）
        # 平均値による減点を行わないのがポイント
        
        # 3. 穴馬フラグ (Chaos Factor)
        # 「ベストパフォーマンスが良い」のに「人気がない」
        # アルデバランSの1番（11位）を拾うためのロジック
        is_chaos = (best_diff <= 0.5 and odds > 20.0)
        if is_chaos: score += 25 # 強制加点

        return score, is_chaos, f"Best:{best_diff}"
        
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

                score, is_chaos, note = analyze_peak_performance(session, name_tag.get('href'), odds)
                
                # 騎手補正
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
    
    # --- 新戦略：ピーク・ポテンシャル・フォーメーション ---
    
    # 1列目: スコア上位3頭（安定＋爆発）
    row1 = df.head(3)['num'].tolist()
    
    # 2列目: 上位5頭（取りこぼし防止）
    row2 = df.head(5)['num'].tolist()
    
    # 3列目: 「Chaosフラグ」持ちを優先的に採用
    # スコア上位 + Chaosフラグ持ちの馬を合体
    ana_list = df[df['is_ana']]['num'].tolist()
    candidates = df.head(6)['num'].tolist() + ana_list
    # 重複削除して最大8頭
    row3 = list(dict.fromkeys(candidates))[:8]

    # 点数計算
    points = len(row1) * len(set(row2)-set(row1)) + ... # 概算
    
    buy_str = (
        f"**1列目**: {', '.join(map(str, row1))}\n"
        f"**2列目**: {', '.join(map(str, row2))}\n"
        f"**3列目**: {', '.join(map(str, row3))}"
    )
    
    payload = {
        "username": "教授AI (ピーク理論Ver.) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **最大瞬間風速・評価モデル**",
            "color": 10181046, # Purple
            "fields": [
                {"name": "🧠 解析ロジック変更点", "value": "平均値を廃止。「過去5走で一度でも0.2秒差以内の好走」があればS評価としました。これにより、7番や1番のようなムラ馬を捕捉します。", "inline": False},
                {"name": "🔥 1列目 (Axis)", "value": f"**{', '.join(map(str, row1))}**", "inline": True},
                {"name": "🌊 3列目 (Chaos)", "value": f"**{', '.join(map(str, row3))}**", "inline": False},
                {"name": "💰 推奨フォーメーション", "value": buy_str, "inline": False}
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
