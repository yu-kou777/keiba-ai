import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {"東京":"05","中山":"06","京都":"08","阪神":"09","中京":"07","小倉":"10","新潟":"04","福島":"03","札幌":"01","函館":"02"}

def find_race_id(d_str, p_name, r_num):
    # 日付の形式チェック（ValueError防止）
    if not d_str or len(d_str) < 8:
        print(f"⚠️ 日付設定エラー: '{d_str}'。デフォルト 20260222 を使用します。")
        d_str = "20260222"
    
    y, p, r = d_str[:4], PLACE_MAP.get(p_name, "05"), str(r_num).zfill(2)
    m, d = int(d_str[4:6]), int(d_str[6:8])
    target = f"{m}月{d}日"
    print(f"🚀 {target} {p_name} {r_num}R を捜索中...")
    
    for kai in range(1, 6):
        for day in range(1, 13):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            try:
                res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=5)
                res.encoding = 'EUC-JP'
                if target in res.text:
                    print(f"✅ ID発見: {rid}")
                    return rid
            except: continue
    return None

def get_data(rid):
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    title = soup.find('title').text.split('｜')[0] if soup.find('title') else "競馬予想"
    
    # 🕵️ あらゆる形式の行(tr)を網羅的に取得
    rows = soup.find_all('tr')
    is_result = "RaceTable01" in res.text
    
    horses, seen = [], set()
    for row in rows:
        try:
            tds = row.find_all('td')
            if len(tds) < 5: continue
            
            # --- 🎯 馬番・馬名・騎手の特定 ---
            umaban = ""
            name_tag = row.select_one('a[href*="/horse/"]')
            jockey_tag = row.select_one('a[href*="/jockey/"]')
            
            if not name_tag: continue
            name = name_tag.text.strip()
            
            if is_result:
                # 結果ページは3列目が確実に馬番
                umaban = tds[2].text.strip()
                jockey = tds[6].text.strip() if len(tds) > 6 else "不明"
            else:
                # 出馬表はUmabanクラスまたは馬名の左隣
                u_tag = row.select_one('td.Umaban')
                if u_tag: umaban = u_tag.text.strip()
                else:
                    for i, td in enumerate(tds):
                        if td.select_one('a[href*="/horse/"]'):
                            if i > 0: umaban = tds[i-1].text.strip()
                            break
                jockey = jockey_tag.text.strip() if jockey_tag else "不明"

            # クリーニング
            umaban = re.sub(r'\D', '', umaban)
            if not umaban or not umaban.isdigit() or umaban in seen: continue
            seen.add(umaban)

            # オッズ（行全体から数値を検索。人気順に騙されないように）
            odds = 999.0
            o_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
            if o_match: odds = float(o_match.group(1))

            # 🧠 ゆーこう式スコア計算（精度重視）
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "odds": odds, "score": score})
        except: continue
    
    return horses, title

def send_discord(horses, title, d, p, r):
    if len(horses) < 3:
        print(f"⚠️ 解析失敗: {len(horses)}頭。")
        return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 精度検証モード",
            "color": 3447003,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n(騎手: {top.iloc[0]['jockey']} / オッズ: {top.iloc[0]['odds']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "🔥 紐・穴", "value": f"{n[3]}, {n[4]}, {n[5]}", "inline": False},
                {"name": "💰 検証", "value": f"本命が掲示板に入ったかチェック！", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)
    print("✅ Discord通知完了")

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 else "20260222"
    place = args[2] if len(args) > 2 else "東京"
    race = args[3] if len(args) > 3 else "11"
    
    rid = find_race_id(date, place, race)
    if rid:
        h, t = get_data(rid)
        print(f"📊 抽出馬数: {len(h)}頭")
        send_discord(h, t, date, place, race)
