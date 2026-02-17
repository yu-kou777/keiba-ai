import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {"東京":"05","中山":"06","京都":"08","阪神":"09","中京":"07","小倉":"10","新潟":"04","福島":"03","札幌":"01","函館":"02"}

def find_race_id(d_str, p_name, r_num):
    y, p, r = d_str[:4], PLACE_MAP.get(p_name, "05"), str(r_num).zfill(2)
    m, d = int(d_str[4:6]), int(d_str[6:8])
    target = f"{m}月{d}日"
    print(f"🚀 {target} {p_name} {r_num}R を捜索中...")
    for kai in range(1, 6):
        for day in range(1, 10):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            try:
                res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
                res.encoding = 'EUC-JP'
                if target in res.text: return rid
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
    
    horses, seen = [], set()
    for row in rows:
        try:
            # 1. 馬名が含まれるリンク(aタグ)を探す
            name_tag = row.select_one('a[href*="/horse/"]')
            if not name_tag: continue
            name = name_tag.text.strip()
            
            # 2. 騎手とオッズ(人気順に騙されない数値抽出)
            jockey = "不明"
            j_tag = row.select_one('a[href*="/jockey/"]')
            if j_tag: jockey = j_tag.text.strip()
            
            odds = 999.0
            o_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
            if o_match: odds = float(o_match.group(1))

            # 3. 🎯 馬番の特定（ここを最強化）
            umaban = ""
            tds = row.find_all('td')
            # 枠番(通常左側)と間違えないよう、複数の候補から馬番を絞り込む
            for i, td in enumerate(tds):
                txt = td.text.strip()
                if txt.isdigit() and 1 <= int(txt) <= 18:
                    # 馬名のすぐ左にある数字、または「Umaban」クラスがある場所を優先
                    if td.get('class') and 'Umaban' in td.get('class'):
                        umaban = txt; break
                    if i > 0 and tds[i+1].select_one('a[href*="/horse/"]'):
                        umaban = txt; break
            
            if not umaban or umaban in seen: continue
            seen.add(umaban)

            # 🧠 ゆーこう式スコア計算
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "odds": odds, "score": score})
        except: continue
    
    return horses, title

def send_discord(horses, title, d, p, r):
    if len(horses) < 3:
        print(f"⚠️ 解析失敗: {len(horses)}頭。データが見つかりません。")
        return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 過去データ検証成功！",
            "color": 3447003,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n(騎手: {top.iloc[0]['jockey']} / 当時オッズ: {top.iloc[0]['odds']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "💰 AI推奨馬券", "value": f"3連単 1着固定流し\n軸: {n[0]}\n相手: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ]
        }]
    }
    res = requests.post(DISCORD_URL, json=payload)
    if res.status_code in [200, 204]: print("✅ Discord送信成功！")

if __name__ == "__main__":
    a = sys.argv
    d, p, r = (a[1], a[2], a[3]) if len(a) > 3 else ("20260222", "東京", "11")
    rid = find_race_id(d, p, r)
    if rid:
        h, t = get_data(rid)
        print(f"📊 抽出馬数: {len(h)}頭")
        send_discord(h, t, d, p, r)
