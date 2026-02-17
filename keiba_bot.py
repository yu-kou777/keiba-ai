import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

# 競馬ラボ用 場所コード (JRA標準)
LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_lab_data(date_str, place_name, race_num):
    """競馬ラボからデータを取得する"""
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    
    # 競馬ラボのURL形式: https://www.keibalab.jp/db/race/YYYYMMDDPPRR/
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    print(f"🚀 競馬ラボをスキャン中: {url}")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        if res.status_code != 200:
            print("❌ レースページが見つかりません（URLエラー）")
            return [], "レース不明"
            
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # レース名取得
        title = "競馬解析"
        t_tag = soup.select_one('h1.raceTitle')
        if t_tag: title = t_tag.text.strip().replace('\n', ' ')

        # 🐎 馬データ抽出 (競馬ラボの表形式に対応)
        horses = []
        # 競馬ラボの出走表/結果表の共通クラスを探す
        rows = soup.select('table.db-race-table tbody tr') or soup.select('table.raceTable tr')
        
        seen_num = set()
        for row in rows:
            tds = row.find_all('td')
            if len(tds) < 5: continue
            
            try:
                # 競馬ラボの標準的な並び: [着順] [枠] [馬番] [馬名] ...
                # 出馬表の場合は[枠] [馬番] [馬名]
                
                # 馬番を探す
                umaban = ""
                for td in tds:
                    txt = td.text.strip()
                    if txt.isdigit() and 1 <= int(txt) <= 18:
                        # 馬名の左側にある数字を優先
                        umaban = txt
                        if td.find_next_sibling().select_one('a[href*="/db/horse/"]'):
                            break
                
                if not umaban or umaban in seen_num: continue
                
                # 馬名
                name_tag = row.select_one('a[href*="/db/horse/"]')
                if not name_tag: continue
                name = name_tag.text.strip()
                
                # 騎手
                jockey = "不明"
                j_tag = row.select_one('a[href*="/db/jockey/"]')
                if j_tag: jockey = j_tag.text.strip()
                
                # オッズ (競馬ラボは'td.odds'など明確)
                odds = 999.0
                odds_txt = row.text
                o_match = re.search(r'(\d+\.\d+)', odds_txt)
                if o_match: odds = float(o_match.group(1))

                seen_num.add(umaban)
                
                # 🧠 スコア計算 (ゆーこう式)
                score = (100 / odds) * 1.5 if odds < 900 else 5
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
                elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']): score += 8

                horses.append({"num": int(umaban), "name": name, "jockey": jockey, "odds": odds, "score": score})
            except: continue
            
        return horses, title
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        return [], "エラー"

def send_discord(horses, title, d, p, r):
    if not horses or len(horses) < 3:
        print(f"⚠️ 解析失敗: {len(horses)}頭。データが不足しています。")
        return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI (KeibaLab版) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 競馬ラボ・クリーン解析",
            "color": 15277667, # Pink/Red
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n(騎手: {top.iloc[0]['jockey']} / オッズ: {top.iloc[0]['odds']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "🔥 紐候補", "value": f"{', '.join(map(str, n[3:]))}", "inline": False}
            ],
            "footer": {"text": "競馬ラボのクリーンなデータを元に解析しました"}
        }]
    }
    requests.post(DISCORD_URL, json=payload)
    print("✅ Discord通知完了")

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 else "20260222"
    place = args[2] if len(args) > 2 else "東京"
    race = args[3] if len(args) > 3 else "11"
    
    h_list, r_title = get_lab_data(date, place, race)
    print(f"📊 抽出馬数: {len(h_list)}頭")
    send_discord(h_list, r_title, date, place, race)
