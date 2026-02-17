import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_lab_data(date_str, place_name, race_num):
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    # 競馬ラボURL: https://www.keibalab.jp/db/race/202602070811/
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    print(f"📡 解析ターゲット: {url}")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # レース名取得
        t_tag = soup.select_one('h1.raceTitle')
        title = t_tag.text.strip().replace('\n', ' ') if t_tag else "レース解析"
        print(f"🏇 レース名: {title}")

        horses, seen_num = [], set()
        # 競馬ラボの表（db-race-table）の行を取得
        rows = soup.select('table tr')
        
        for row in rows:
            # 馬名へのリンクがあるか確認
            name_tag = row.select_one('a[href*="/db/horse/"]')
            if not name_tag: continue
            
            tds = row.find_all('td')
            if len(tds) < 4: continue
            
            try:
                name = name_tag.text.strip()
                
                # --- 馬番の取得ロジック ---
                # 馬名セルの「左隣」にある数字を探す（これが最も正確）
                umaban = ""
                name_td = name_tag.find_parent('td')
                all_tds_in_row = list(row.find_all('td'))
                name_idx = all_tds_in_row.index(name_td)
                
                if name_idx > 0:
                    umaban_text = all_tds_in_row[name_idx - 1].text.strip()
                    umaban = re.sub(r'\D', '', umaban_text)

                # 重複や空を排除
                if not umaban or umaban in seen_num: continue
                seen_num.add(umaban)

                # 騎手
                j_tag = row.select_one('a[href*="/db/jockey/"]')
                jockey = j_tag.text.strip() if j_tag else "不明"
                
                # オッズ（行の中から "数字.数字" を探す）
                odds = 999.0
                o_match = re.search(r'(\d{1,3}\.\d{1})', row.text)
                if o_match: odds = float(o_match.group(1))

                # --- 🧠 ゆーこう式スコア計算 ---
                score = (100 / odds) * 1.5 if odds < 900 else 5
                # 注目騎手ボーナス
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'モレイラ', 'ムーア']):
                    score += 15
                elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島', '岩田']):
                    score += 8
                
                horses.append({"num": int(umaban), "name": name, "jockey": jockey, "odds": odds, "score": score})
            except: continue
            
        return horses, title
    except Exception as e:
        print(f"❌ 解析エラー: {e}")
        return [], "エラー"

def send_discord(horses, title, d, p, r):
    if not horses or len(horses) < 3:
        print(f"⚠️ 解析失敗: 抽出できた馬が {len(horses)} 頭でした。")
        return
    
    # スコア順に並び替え
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 精度検証・解析結果",
            "color": 3066993,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n(騎手: {top.iloc[0]['jockey']} / オッズ: {top.iloc[0]['odds']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "🔥 紐候補", "value": f"{', '.join(map(str, n[3:]))}", "inline": False},
                {"name": "💰 AI推奨", "value": f"3連単 1着固定流し\n軸: {n[0]}\n相手: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ],
            "footer": {"text": "KeibaLabクリーンデータを使用して解析完了"}
        }]
    }
    requests.post(DISCORD_URL, json=payload)
    print(f"✅ 解析完了: {len(horses)}頭抽出。Discordに送信しました！")

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 and args[1] != "" else "20260222"
    place = args[2] if len(args) > 2 and args[2] != "" else "東京"
    race = args[3] if len(args) > 3 else "11"
    
    h, t = get_lab_data(date, place, race)
    print(f"📊 最終抽出数: {len(h)} 頭")
    send_discord(h, t, date, place, race)
