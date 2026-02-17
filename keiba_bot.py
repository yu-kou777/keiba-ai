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
                if target in res.text:
                    print(f"✅ レース発見: {rid}")
                    return rid
            except: continue
    return None

def get_data(rid):
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    title = soup.find('title').text.split('｜')[0] if soup.find('title') else "競馬予想"
    # あらゆるテーブルの「行」をターゲットにする
    rows = soup.find_all('tr')
    
    horses, seen = [], set()
    for row in rows:
        try:
            # 「馬名」が含まれるリンク(aタグ)を探す
            name_tag = row.select_one('a[href*="/horse/"]')
            if not name_tag: continue
            name = name_tag.text.strip()
            if not name or "馬主" in name: continue

            # 馬番を探す (tdのテキストから数字だけを抽出)
            tds = row.find_all('td')
            umaban = ""
            for td in tds:
                txt = td.text.strip()
                if txt.isdigit() and 0 < int(txt) <= 20:
                    umaban = txt
                    break
            
            if not umaban or umaban in seen: continue
            seen.add(umaban)

            # 騎手・オッズ（簡易取得）
            jockey = "騎手不明"
            j_tag = row.select_one('a[href*="/jockey/"]')
            if j_tag: jockey = j_tag.text.strip()
            
            odds = 999.0
            odds_txt = row.text.replace(name, "").replace(jockey, "")
            match = re.search(r'\d+\.\d+', odds_txt)
            if match: odds = float(match.group())

            # ゆーこう式スコア
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    return horses, title

def send_discord(horses, title, d, p, r):
    if not horses or len(horses) < 3:
        print("❌ 解析失敗（馬が見つかりません）"); return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).drop_duplicates('num').reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 解析成功！",
            "color": 16753920,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}** ({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "💰 3連単推奨", "value": f"1着: {n[0]}\n2着: {n[1]}, {n[2]}\n3着: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ]
        }]
    }
    r = requests.post(DISCORD_URL, json=payload)
    if r.status_code in [200, 204]: print("✅ Discord送信成功！")
    else: print(f"❌ Discord送信失敗: {r.status_code}")

if __name__ == "__main__":
    args = sys.argv
    d, p, r = (args[1], args[2], args[3]) if len(args) > 3 else ("20260222", "東京", "11")
    rid = find_race_id(d, p, r)
    if rid:
        h, t = get_data(rid)
        print(f"📊 抽出馬数: {len(h)}頭")
        send_discord(h, t, d, p, r)
    else: print("❌ レースが見つかりません")
