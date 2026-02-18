# -*- coding: utf-8 -*-
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定：Discord Webhook ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_stealth_headers():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ]
    return {"User-Agent": random.choice(user_agents), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Referer": "https://www.google.com/"}

def analyze_horse_history(session, horse_url, name):
    """
    【馬柱スキャン機能】
    各馬の個別ページへ飛び、過去5走のタイム差を抽出。
    """
    try:
        # 相対パスを絶対パスへ変換
        if not horse_url.startswith("http"):
            full_url = "https://www.keibalab.jp" + horse_url
        else:
            full_url = horse_url
            
        print(f"  🔍 {name} の馬柱(過去5走)をスキャン中...") # 証拠を表示
        time.sleep(random.uniform(0.8, 1.5))
        
        res = session.get(full_url, headers=get_stealth_headers(), timeout=15, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 過去成績テーブルを特定
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows:
            print(f"    ⚠️ {name}: 過去データが見つかりません")
            return 0, False, "データなし"
        
        diffs = []
        for row in rows[:5]: # 直近5走を抽出
            tds = row.find_all('td')
            if len(tds) < 14: continue
            
            # タイム差(着差)のカラムを探す
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = float(re.sub(r'[^\d\.-]', '', txt))
                    break
            
            if val < 5.0:
                diffs.append(val)

        if not diffs: return 0, False, "対象走なし"
        
        # --- スコア計算ロジック ---
        score = 0
        best_diff = min(diffs)
        if best_diff <= 0.0: score += 60      
        elif best_diff <= 0.3: score += 45    
        regret_count = sum(1 for d in diffs if 0.0 <= d <= 0.5)
        score += regret_count * 15            
        
        return score, best_diff
    except Exception as e:
        return 0, 99.9

def get_future_race(d, p, r):
    """
    【未来予測・特化型】
    shutsubahyou.html を強制的に見に行き、未来の出走馬を捕捉。
    """
    if not d: d = time.strftime("%Y%m%d")
    p_code = LAB_PLACE_MAP.get(p, "05")
    # 未来の出馬表URLを生成
    url = f"https://www.keibalab.jp/db/race/{d}{p_code}{str(r).zfill(2)}/shutsubahyou.html"
    
    print(f"📡 未来予測フェーズ始動: {url}")
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=3))
    
    try:
        res = session.get(url, headers=get_stealth_headers(), timeout=30, verify=False)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # レース名
        title_tag = soup.select_one('h1.raceTitle')
        title = title_tag.text.strip().replace('\n', ' ') if title_tag else "未来のレース"
        
        horses = []
        # 出馬表から馬の情報を抽出
        rows = soup.find_all('tr')
        print(f"📊 「{title}」の出走馬を検知しました。解析を開始します。")
        
        for row in rows:
            # 馬の個別ページへのリンクを探す
            link_tag = row.select_one('a[href*="/db/horse/"]')
            if not link_tag: continue
            
            name = link_tag.text.strip()
            # 馬番
            tds = row.find_all('td')
            umaban = "0"
            for i, td in enumerate(tds):
                if td == link_tag.find_parent('td'):
                    if i > 0 and tds[i-1].text.strip().isdigit(): umaban = tds[i-1].text.strip()
                    break
            
            # オッズ（未来の場合、まだ出ていない可能性を考慮）
            odds_m = re.search(r'(\d{1,4}\.\d{1})', row.text)
            odds = float(odds_m.group(1)) if odds_m else 99.9
            
            # --- ここで「馬の履歴（馬柱）」を見に行く ---
            score, best = analyze_horse_history(session, link_tag.get('href'), name)
            
            is_chaos = (best <= 0.6 and odds > 15.0)
            horses.append({"num": int(umaban), "name": name, "score": score, "is_ana": is_chaos, "best": best})
            
        return horses, title
    except Exception as e:
        print(f"❌ 解析失敗: {e}")
        return [], "Err"

def send_result(horses, title, d, p, r):
    if not horses or len(horses) < 3: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # フィルタロジック
    top_score = df.iloc[0]['score']
    gap = top_score - df.iloc[min(3, len(df)-1)]['score']
    limit = 5 if top_score >= 75 and gap >= 15 else 9
    
    row1 = df.head(3)['num'].tolist()
    row2 = df.head(5)['num'].tolist()
    ana = df[df['is_ana']]['num'].tolist()
    row3 = list(dict.fromkeys(row2 + ana + df.iloc[5:8]['num'].tolist()))[:limit]

    payload = {
        "username": "教授AI (未来観測モード) 🏇",
        "embeds": [{
            "title": f"🎯 【未来予測】{p}{r}R {title}",
            "description": f"📅 {d} | **3-5-{limit} 構成**",
            "color": 3066993,
            "fields": [
                {"name": "📊 解析ログ", "value": f"```全頭の過去5走(馬柱)をスキャン完了。\n軸信頼度: {top_score} / 判定: {'精密' if limit==5 else '広域'}```", "inline": False},
                {"name": "🔥 軸・相手", "value": f"**{', '.join(map(str, row1))}** → **{', '.join(map(str, row2))}**", "inline": False},
                {"name": "💰 推奨フォーメーション", "value": f"1列目: {row1}\n2列目: {row2}\n3列目: {row3}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)
    print(f"✅ Discordへ未来の予想を送信しました。")

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 else "" # 指定がなければ今日
    place = args[2] if len(args) > 2 else "東京"
    race = args[3] if len(args) > 3 else "11"
    
    h, t = get_future_race(date, place, race)
    send_result(h, t, date, place, race)
    input("\n解析が完了しました。Enterキーで閉じます...")
