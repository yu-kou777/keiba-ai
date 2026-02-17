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
    for kai in range(1, 7):
        for day in range(1, 13):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            try:
                res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
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
    
    # テーブルの種類を判定
    is_result = "RaceTable01" in res.text
    rows = soup.select('tr.HorseList') or soup.select('table.RaceTable01 tr')
    
    horses, seen = [], set()
    for row in rows:
        try:
            tds = row.find_all('td')
            if len(tds) < 5: continue
            
            # --- 厳密な馬番取得ロジック ---
            if is_result:
                # 結果ページは「3番目の列」が絶対に馬番
                umaban = tds[2].text.strip()
                name_tag = tds[3].select_one('a[href*="/horse/"]')
                jockey_tag = tds[6].select_one('a[href*="/jockey/"]')
            else:
                # 出馬表はクラス名で指定
                u_tag = row.select_one('td.Umaban')
                umaban = u_tag.text.strip() if u_tag else ""
                name_tag = row.select_one('span.HorseName')
                jockey_tag = row.select_one('td.Jockey')

            if not umaban.isdigit() or not name_tag: continue
            
            name = name_tag.text.strip()
            jockey = jockey_tag.text.strip() if jockey_tag else "不明"
            
            # 重複防止
            if umaban in seen: continue
            seen.add(umaban)

            # オッズ取得（人気順に惑わされないように数値のみ）
            odds = 999.0
            o_match = re.search(r'\d+\.\d+', row.text)
            if o_match: odds = float(o_match.group())

            # ゆーこう式スコア（期待値計算）
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    return horses, title

def send_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 解析成功！",
            "color": 16753920,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}** ({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "💰 3連単推奨", "value": f"**1着**: {n[0]}\n**2着**: {n[1]}, {n[2]}\n**3着**: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    a = sys.argv
    d, p, r = (a[1], a[2], a[3]) if len(a) > 3 else ("20260222", "東京", "11")
    rid = find_race_id(d, p, r)
    if rid:
        h, t = get_data(rid)
        send_discord(h, t, d, p, r)
