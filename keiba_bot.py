# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time
import random
import os

# --- 設定：Discord Webhook ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

def analyze_logic(session, url, name):
    """【SSS判定エンジン】馬柱から熱量を計算"""
    try:
        if not url.startswith("http"): url = "https://www.keibalab.jp" + url
        time.sleep(random.uniform(1.0, 1.8))
        res = session.get(url, timeout=15, verify=False)
        if res.status_code == 403: return -1, 9.9
        
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, 9.9
        
        diffs = []
        for row in rows[:5]:
            tds = row.find_all('td')
            if len(tds) < 14: continue
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = float(re.sub(r'[^\d\.-]', '', txt))
                    break
            if val < 5.0: diffs.append(val)
            
        if not diffs: return 0, 9.9
        best = min(diffs)
        # 数理モデル：$$Score = P_{base} + (N_{regret} \times 15)$$
        score = (60 if best <= 0.0 else 45 if best <= 0.3 else 0) + (sum(1 for d in diffs if 0.0 <= d <= 0.5) * 15)
        return score, best
    except: return 0, 9.9

def run_precision_prediction(d, p, r):
    p_map = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}
    p_code = p_map.get(p, "05")
    # 未来の出馬表URLを優先
    url = f"https://www.keibalab.jp/db/race/{d}{p_code}{str(r).zfill(2)}/shutsubahyou.html"
    print(f"📡 ターゲットロック: {url}")
    session = requests.Session()
    
    try:
        res = session.get(url, timeout=30, verify=False)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # ★メインテーブルのみを抽出（ノイズカット）
        table = soup.find('table', class_='shutsubaTable')
        if not table:
            print("⚠️ 出馬表が未公開、または形式が異なります。結果ページを確認します。")
            table = soup.find('table', class_='table_p01')

        if not table: return [], "No Table"

        horses = []
        # 行(tr)ごとに解析。馬番(td.num)を確実に取得
        for row in table.find_all('tr'):
            link = row.select_one('a[href*="/db/horse/"]')
            if not link: continue
            
            name = link.text.strip()
            # 馬番の抽出を強化
            umaban = "0"
            num_td = row.find('td', class_='num')
            if num_td:
                umaban = num_td.text.strip()
            else:
                # numクラスがない場合、最初の数字tdを探す
                for td in row.find_all('td'):
                    if td.text.strip().isdigit():
                        umaban = td.text.strip(); break
            
            # オッズ（未来の場合、まだ出ていない可能性あり）
            odds_m = re.search(r'(\d{1,4}\.\d{1})', row.text)
            odds = float(odds_m.group(1)) if odds_m else 99.9
            
            score, best = analyze_logic(session, link.get('href'), name)
            if score == -1: print(f"🛑 アクセス拒否(BAN)発生: {name}"); break
            
            print(f"  √ {umaban}番 {name}: {score}点 (Best:{best})")
            horses.append({"num": int(umaban), "name": name, "score": score, "is_ana": (best <= 0.6 and odds > 15.0)})
            
        return horses, "解析完了"
    except Exception as e:
        print(f"❌ エラー: {e}"); return [], "Err"

# (send_discord関数は以前と同様、if __name__ == "__main__" も環境検知付き)
