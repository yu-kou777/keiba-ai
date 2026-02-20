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

def analyze_horse_history(session, horse_url, name):
    """【馬柱スキャン】個別ページへ飛び、過去5走の数値を抽出"""
    try:
        if not horse_url.startswith("http"):
            url = "https://www.keibalab.jp" + horse_url
        else:
            url = horse_url
            
        # 連続アクセスによるBAN回避（スマホならこれくらいでOK）
        time.sleep(random.uniform(1.2, 2.5))
        
        res = session.get(url, timeout=15, verify=False)
        if res.status_code == 403:
            print(f"  🛑 制限検知: {name} のデータを読み込めません")
            return 0, 9.9
            
        soup = BeautifulSoup(res.text, 'html.parser')
        # 過去成績のテーブル行を特定
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, 9.9
        
        diffs = []
        for row in rows[:5]:
            tds = row.find_all('td')
            if len(tds) < 14: continue
            # タイム差（着差）を抽出
            val = 99.9
            for td in tds:
                txt = td.text.strip()
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = float(re.sub(r'[^\d\.-]', '', txt))
                    break
            if val < 5.0: diffs.append(val)
            
        if not diffs: return 0, 9.9
        best = min(diffs)
        # トモユキ式スコア：ピーク能力 + 惜敗ボーナス
        score = (60 if best <= 0.0 else 45 if best <= 0.3 else 0) + (sum(1 for d in diffs if 0.0 <= d <= 0.5) * 15)
        return score, best
    except:
        return 0, 9.9

def run_precision_scan(d, p, r):
    """【精密スキャン】メインの出馬表テーブルのみを抽出"""
    p_map = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}
    p_code = p_map.get(p, "05")
    url = f"https://www.keibalab.jp/db/race/{d}{p_code}{str(r).zfill(2)}/shutsubahyou.html"
    
    print(f"📡 照準を固定: {url}")
    session = requests.Session()
    
    try:
        res = session.get(url, timeout=30, verify=False)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # ★ここが重要：メインの出馬表テーブル(class="shutsubaTable")を特定
        main_table = soup.find('table', class_='shutsubaTable')
        
        if not main_table:
            # 未来すぎて出馬表がない場合、結果ページを試す
            url_alt = url.replace("shutsubahyou.html", "")
            res = session.get(url_alt, timeout=30, verify=False)
            soup = BeautifulSoup(res.text, 'html.parser')
            main_table = soup.find('table', class_='table_p01') # 結果用テーブル

        if not main_table:
            print("❌ テーブルが見つかりません。")
            return [], "データ未公開"

        horses = []
        # テーブル内の「馬データへのリンク」がある行だけを処理
        rows = main_table.find_all('tr')
        for row in rows:
            link_tag = row.select_one('a[href*="/db/horse/"]')
            if not link_tag: continue
            
            name = link_tag.text.strip()
            # 馬番の取得ロジックを強化
            umaban = "0"
            for td in row.find_all('td'):
                txt = td.text.strip()
                if txt.isdigit():
                    umaban = txt
                    break
            
            # オッズ
            odds_m = re.search(r'(\d{1,4}\.\d{1})', row.text)
            odds = float(odds_m.group(1)) if odds_m else 99.9
            
            # 過去5走スキャン
            score, best = analyze_horse_history(session, link_tag.get('href'), name)
            
            print(f"  √ {umaban}番 {name}: {score}点 (Best:{best})")
            horses.append({"num": int(umaban), "name": name, "score": score, "is_ana": (best <= 0.6 and odds > 15.0)})
            
        return horses, "精密解析結果"
    except Exception as e:
        print(f"❌ 解析エラー: {e}")
        return [], "Err"

# (send関数は前回と同じなため省略、if __name__ == "__main__" も環境検知付きを継続)
