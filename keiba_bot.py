import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time
import random

# --- Discord接続設定 ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

# 偽装用エージェントリスト
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

def create_session():
    """接続を維持し、切断されても食らいつくセッションを作成"""
    session = requests.Session()
    retries = Retry(
        total=5,  # 5回までリトライ
        backoff_factor=2,  # 待機時間を倍々に増やす (2秒, 4秒, 8秒...)
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def safe_float(value):
    try:
        clean = re.sub(r'[^\d\.-]', '', str(value))
        return float(clean)
    except: return 99.9

def analyze_singularity(session, horse_url, odds):
    """過去3走解析（セッション引き継ぎ版）"""
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        if not horse_url.startswith("http"):
            horse_url = "https://www.keibalab.jp" + horse_url
            
        # サーバー負荷を考慮して少し待機
        time.sleep(random.uniform(1.0, 2.0))
        
        res = session.get(horse_url, headers=headers, timeout=20)
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        
        if not rows: return 0, False, "データなし"
        
        diffs = []
        for row in rows[:3]:
            tds = row.find_all('td')
            if len(tds) < 14: continue
            
            # タイム差抽出
            found_diff = False
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = safe_float(txt)
                    if val < 5.0:
                        diffs.append(val)
                        found_diff = True
                        break
            
            # 着順から補完
            if not found_diff and len(tds) > 11:
                if "1" in tds[11].text.strip(): diffs.append(0.0)

        if not diffs: return 0, False, "タイム差不明"
        
        # 物理スコア計算
        score = sum(60 for d in diffs if d <= 0.3)
        avg_diff = sum(diffs) / len(diffs)
        score += max(0, 1.5 - avg_diff) * 20
        is_chaos = (avg_diff <= 0.8 and odds > 15.0)
        
        return score, is_chaos, f"平均差:{avg_diff:.2f}"
    except Exception:
        return 0, False, "解析エラー"

def get_race_data(date_str, place_name, race_num):
    if not date_str or len(date_str) < 8:
        date_str, place_name, race_num = "20260207", "京都", "11"

    p_code = LAB_PLACE_MAP.get(place_name, "08")
    r_num = str(race_num).zfill(2)
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    
    print(f"📡 観測開始: {url}")
    session = create_session()
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    try:
        # メインレースページ取得
        res = session.get(url, headers=headers, timeout=30)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        t_elem = soup.select_one('h1.raceTitle')
        title = t_elem.text.strip().replace('\n', ' ') if t_elem else "レース名不明"
        print(f"🏁 対象: {title}")
        
        horses = []
        rows = soup.find_all('tr')
        
        print("🔍 全頭スキャン開始...")
        for row in rows:
            name_tag = row.select_one('a[href*="/db/horse/"]')
            if not name_tag: continue
            
            try:
                name = name_tag.text.strip()
                
                # 馬番取得
                umaban = "0"
                tds = row.find_all('td')
                for i, td in enumerate(tds):
                    if td == name_tag.find_parent('td'):
                        if i > 0:
                            prev = tds[i-1].text.strip()
                            if prev.isdigit(): umaban = prev
                        break
                
                if umaban == "0": continue

                # オッズ
                odds = 99.9
                m = re.search(r'(\d{1,4}\.\d{1})', row.text)
                if m: odds = float(m.group(1))
                
                # 騎手
                j_tag = row.select_one('a[href*="/db/jockey/"]')
                jockey = j_tag.text.strip() if j_tag else ""

                # 詳細解析（リトライ機能付きセッションを渡す）
                score, is_chaos, note = analyze_singularity(session, name_tag.get('href'), odds)
                
                # 騎手補正
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']):
                    score += 15
                
                print(f"  √ {umaban}番 {name}: Score {score:.1f}")
                
                horses.append({
                    "num": int(umaban),
                    "name": name,
                    "score": score,
                    "is_ana": is_chaos,
                    "odds": odds
                })
            except: continue
                
        return horses, title
    except Exception as e:
        print(f"❌ 接続エラー: {e}")
        return [], "エラー"

def send_to_discord(horses, title, d, p, r):
    if not horses:
        print("❌ 解析データなし")
        return

    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 24点フォーメーション
    axis = df.head(2)['num'].tolist()
    row2 = df.head(4)['num'].tolist()
    
    ana_list = df[df['is_ana']]['num'].tolist()
    candidates = row2 + ana_list + df.iloc[4:8]['num'].tolist()
    row3 = list(dict.fromkeys(candidates))[:6]

    buy_str = (
        f"**1着**: {', '.join(map(str, axis))}\n"
        f"**2着**: {', '.join(map(str, row2))}\n"
        f"**3着**: {', '.join(map(str, row3))}"
    )
    
    payload = {
        "username": "教授AI (再接続成功) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **通信障害突破・解析完了**",
            "color": 3066993,
            "fields": [
                {"name": "👑 1着軸", "value": f"**{', '.join(map(str, axis))}**", "inline": True},
                {"name": "🐎 2着候補", "value": f"{', '.join(map(str, row2))}", "inline": True},
                {"name": "🌀 3着候補", "value": f"{', '.join(map(str, row3))}", "inline": False},
                {"name": "💰 推奨買い目 (24点)", "value": buy_str, "inline": False}
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
    except:
        date, place, race = "20260207", "京都", "11"
    
    h_list, t_str = get_race_data(date, place, race)
    send_to_discord(h_list, t_str, date, place, race)
