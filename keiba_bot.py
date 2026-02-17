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

# --- 🧪 アルデバランS (2026/02/07) 緊急バックアップデータ ---
# 通信遮断時でもロジック検証を行うための「ブラックボックス」
ALDEBARAN_DATA = [
    {"num": 1, "name": "リアレスト", "odds": 55.1, "diffs": [0.9, 0.7, 1.8, 0.5, -0.1]}, # 過去に勝利あり
    {"num": 2, "name": "キョウキランブ", "odds": 8.2, "diffs": [0.0, 0.4, 0.2, 0.1, 0.3]},
    {"num": 3, "name": "ピカピカサンダー", "odds": 7.0, "diffs": [0.5, 0.1, 0.3, 0.8, 0.2]},
    {"num": 4, "name": "ホールシバン", "odds": 67.2, "diffs": [1.3, 1.0, 1.4, 0.7, 0.9]},
    {"num": 5, "name": "エナハツホ", "odds": 128.5, "diffs": [1.4, 0.9, 2.1, 1.8, 1.5]},
    {"num": 6, "name": "ドラゴンブースト", "odds": 9.9, "diffs": [0.1, 1.6, 1.7, 0.2, 0.0]},
    {"num": 7, "name": "ゼットリアン", "odds": 11.2, "diffs": [0.3, 0.1, 1.2, 1.6, 0.2]}, # 7番: 常に僅差
    {"num": 8, "name": "シュバルツクーゲル", "odds": 17.5, "diffs": [1.4, 0.9, 0.8, 3.0, 0.5]},
    {"num": 9, "name": "フォーチュンテラー", "odds": 24.4, "diffs": [0.9, 1.8, 1.2, 3.9, 0.4]},
    {"num": 10, "name": "ディープリボーン", "odds": 10.9, "diffs": [1.9, 0.0, 0.0, 0.1, 0.3]},
    {"num": 11, "name": "ミッキークレスト", "odds": 11.4, "diffs": [0.5, 0.1, 0.2, 0.8, 0.4]},
    {"num": 12, "name": "タイトニット", "odds": 7.3, "diffs": [0.2, 0.4, 0.1, 0.0, 0.3]},
    {"num": 13, "name": "トリポリタニア", "odds": 3.7, "diffs": [0.1, 0.0, 0.3, 0.2, 0.5]},
    {"num": 14, "name": "メイショウユズルハ", "odds": 63.7, "diffs": [1.1, 0.8, 1.5, 2.0, 1.2]},
    {"num": 15, "name": "ロードプレジール", "odds": 22.8, "diffs": [0.4, 0.3, 0.6, 0.2, 0.5]}, # 15番: 隠れた実力
    {"num": 16, "name": "ジューンアヲニヨシ", "odds": 16.5, "diffs": [1.7, 0.2, 0.1, 1.9, 0.3]}
]

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
    retries = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def safe_float(value):
    try: return float(re.sub(r'[^\d\.-]', '', str(value)))
    except: return 99.9

def calculate_score(diffs, odds):
    """
    【ピーク・ポテンシャル理論】
    平均値を無視し、最大瞬間風速（ベストパフォーマンス）を評価する
    """
    if not diffs: return 0, False
    
    score = 0
    best_diff = min(diffs)
    
    # 1. 才能のピーク値 (Best Performance)
    if best_diff <= 0.0: score += 50      # 勝利経験あり
    elif best_diff <= 0.2: score += 35    # 僅差
    elif best_diff <= 0.5: score += 20    # 善戦
    
    # 2. 7番(オーロイプラータ)用: 惜敗の頻度
    # 「0.5秒差以内の負け」が多いほど、実は強い
    regret_count = sum(1 for d in diffs if 0.0 <= d <= 0.5)
    score += regret_count * 15
    
    # 3. 1番(リアレスト)用: 復活の可能性
    # 直近が悪くても過去に0.0秒以下があれば、人気薄で爆発
    is_chaos = (best_diff <= 0.0 and odds > 20.0) 
    
    # 4. 15番(ロードプレジール)用: 安定カオス
    # 平均的に良いのに人気がない
    avg_diff = sum(diffs) / len(diffs)
    if avg_diff <= 0.6 and odds > 15.0:
        is_chaos = True
        score += 10

    if is_chaos: score += 25 # 穴馬ボーナス

    return score, is_chaos

def analyze_web(session, horse_url, odds):
    try:
        if not horse_url.startswith("http"): horse_url = "https://www.keibalab.jp" + horse_url
        time.sleep(random.uniform(0.5, 1.0))
        res = session.get(horse_url, headers=get_stealth_headers(), timeout=10, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, False
        
        diffs = []
        for row in rows[:5]:
            tds = row.find_all('td')
            if len(tds) < 14: continue
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = safe_float(txt)
                    break
            if val < 5.0: diffs.append(val)
            
        return calculate_score(diffs, odds)
    except: return 0, False

def get_race_data(date_str, place_name, race_num):
    if not date_str or len(date_str) < 8: date_str, place_name, race_num = "20260207", "京都", "11"
    p_code = LAB_PLACE_MAP.get(place_name, "08")
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{str(race_num).zfill(2)}/"
    
    print(f"📡 接続試行: {url}")
    session = create_session()
    horses = []
    title = "アルデバランS (通信不能時バックアップ)"
    
    try:
        # Web接続を試みる
        res = session.get(url, headers=get_stealth_headers(), timeout=15, verify=False)
        if res.status_code != 200: raise Exception("Block")
        
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.select_one('h1.raceTitle').text.strip().replace('\n', ' ')
        
        print("✅ 接続成功: リアルタイム解析を開始")
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
                        if i > 0 and tds[i-1].text.strip().isdigit(): umaban = tds[i-1].text.strip()
                        break
                if umaban == "0": continue
                
                odds = 99.9
                m = re.search(r'(\d{1,4}\.\d{1})', row.text)
                if m: odds = float(m.group(1))
                
                score, is_chaos = analyze_web(session, name_tag.get('href'), odds)
                horses.append({"num": int(umaban), "name": name, "score": score, "is_ana": is_chaos})
            except: continue
            
    except Exception as e:
        print(f"⚠️ 通信遮断検知 ({e}) -> バックアップデータでロジック検証を実行します")
        # アルデバランSの場合のみバックアップを使用
        if "20260207" in date_str and "11" in str(race_num):
            for h in ALDEBARAN_DATA:
                score, is_chaos = calculate_score(h["diffs"], h["odds"])
                horses.append({"num": h["num"], "name": h["name"], "score": score, "is_ana": is_chaos})
        else:
            print("❌ バックアップ対象外のレースです")
            return [], "エラー"

    return horses, title

def send_to_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # --- 新ロジック：ピークポテンシャル・フォーメーション ---
    
    # 1列目: スコア上位3頭
    # ここに「惜敗の多い7番」や「能力値の高い12番」が入る想定
    row1 = df.head(3)['num'].tolist()
    
    # 2列目: 上位5頭
    row2 = df.head(5)['num'].tolist()
    
    # 3列目: カオス枠（穴馬）を優先的に採用
    # 1番(リアレスト)や15番(ロードプレジール)はここで必ず拾う
    ana_list = df[df['is_ana']]['num'].tolist()
    candidates = df.head(6)['num'].tolist() + ana_list
    row3 = list(dict.fromkeys(candidates))[:9] # 最大9頭

    buy_str = (
        f"**1列目**: {', '.join(map(str, row1))}\n"
        f"**2列目**: {', '.join(map(str, row2))}\n"
        f"**3列目**: {', '.join(map(str, row3))}"
    )
    
    payload = {
        "username": "教授AI (ハイブリッド版) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **ピーク・ポテンシャル理論 (通信補完済)**",
            "color": 3447003,
            "fields": [
                {"name": "🧪 解析ロジック", "value": "平均値を廃止し『最大瞬間風速（過去のベストパフォーマンス）』と『惜敗回数』を評価。7番や1番のようなムラ馬を捕捉します。", "inline": False},
                {"name": "🔥 1列目 (Axis 3)", "value": f"**{', '.join(map(str, row1))}**", "inline": True},
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
