# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time
import random
import os
from urllib.parse import urljoin

# --- 設定：Discord Webhook ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

def analyze_logic(session, horse_url, name):
    """【SSS判定エンジン】各馬の過去5走から熱量を計算"""
    try:
        # BAN回避：人間らしいランダムな待機
        time.sleep(random.uniform(1.2, 2.5))
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
        res = session.get(horse_url, headers=headers, timeout=15, verify=False)
        
        if res.status_code == 403:
            return -1, 9.9 # BAN状態
            
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
        # 数理モデル: $$Score = P_{base} + (N_{regret} \times 15)$$
        score = (60 if best <= 0.0 else 45 if best <= 0.3 else 0) + (sum(1 for d in diffs if 0.0 <= d <= 0.5) * 15)
        return score, best
    except:
        return 0, 9.9

def run_precision_scan(d, p, r):
    """【精密スキャン】サイトのノイズを無視し、出馬表のみを抽出"""
    p_map = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}
    p_code = p_map.get(p, "05")
    
    # 未来の出馬表URLを優先
    base_url = f"https://www.keibalab.jp/db/race/{d}{p_code}{str(r).zfill(2)}/"
    target_url = urljoin(base_url, "shutsubahyou.html")
    
    print(f"📡 ターゲットロック: {target_url}")
    session = requests.Session()
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
        res = session.get(target_url, headers=headers, timeout=30, verify=False)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # ★重要：出馬表テーブル(shutsubaTable)のみを抽出対象にする
        main_table = soup.find('table', class_='shutsubaTable')
        
        if not main_table:
            # テーブルがない場合、結果ページ用のテーブルを探す
            main_table = soup.find('table', class_='table_p01')

        if not main_table:
            print("❌ 出馬表が見つかりません。枠順未確定の可能性があります。")
            return [], "データ未公開"

        horses = []
        rows = main_table.find_all('tr')
        print(f"📊 解析シークエンス開始...")
        
        for row in rows:
            link_tag = row.select_one('a[href*="/db/horse/"]')
            if not link_tag: continue
            
            name = link_tag.text.strip()
            # 馬番の取得を厳格化
            umaban = "0"
            num_td = row.find('td', class_='num')
            if num_td:
                umaban = num_td.text.strip()
            else:
                for td in row.find_all('td'):
                    if td.text.strip().isdigit():
                        umaban = td.text.strip()
                        break
            
            # オッズ抽出
            odds_m = re.search(r'(\d{1,4}\.\d{1})', row.text)
            odds = float(odds_m.group(1)) if odds_m else 99.9
            
            # 馬柱へのリンクを絶対パスに変換
            horse_link = urljoin("https://www.keibalab.jp", link_tag.get('href'))
            
            score, best = analyze_logic(session, horse_link, name)
            
            if score == -1:
                print(f"🛑 アクセス拒否(BAN)を検知。IPを変更してください。")
                break
                
            print(f"  √ {umaban}番 {name}: {score}点 (Best:{best})")
            horses.append({"num": int(umaban), "name": name, "score": score, "is_ana": (best <= 0.6 and odds > 15.0)})
            
        return horses, "精密解析完了"
    except Exception as e:
        print(f"❌ 通信エラー: {e}")
        return [], "Err"

def send_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    row1 = df.head(3)['num'].tolist()
    row2 = df.head(5)['num'].tolist()
    ana = df[df['is_ana']]['num'].tolist()
    
    top_score = df.iloc[0]['score']
    # フィルタ：軸の信頼度(SSS判定)で点数を圧縮
    limit = 5 if top_score >= 75 else 9
    row3 = list(dict.fromkeys(row2 + ana + df.iloc[5:8]['num'].tolist()))[:limit]

    payload = {
        "username": "教授AI (精密狙撃版)",
        "embeds": [{
            "title": f"🎯 {p}{r}R 解析結果",
            "description": f"📅 {d} | **3-5-{limit}構成**",
            "color": 3066993 if limit == 5 else 15105570,
            "fields": [
                {"name": "🔥 軸・相手 (1-2列)", "value": f"**{', '.join(map(str, row1))}** → **{', '.join(map(str, row2))}**", "inline": False},
                {"name": "💰 推奨フォーメーション", "value": f"1列目: {row1}\n2列目: {row2}\n3列目: {row3}", "inline": False},
                {"name": "🧠 診断ログ", "value": f"最高スコア: {top_score}点\nモード: {'精密射撃(3-5-5)' if limit==5 else '広域掃射(3-5-9)'}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 else ""
    place = args[2] if len(args) > 2 else "東京"
    race = args[3] if len(args) > 3 else "11"
    
    h_list, t_str = run_precision_scan(date, place, race)
    send_discord(h_list, t_str, date, place, race)
    
    if not os.environ.get('GITHUB_ACTIONS'):
        input("\n解析完了。Enterで閉じます...")
