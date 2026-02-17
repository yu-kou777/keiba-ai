import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {"東京":"05","中山":"06","京都":"08","阪神":"09","中京":"07","小倉":"10","新潟":"04","福島":"03","札幌":"01","函館":"02"}

def find_race_id(d_str, p_name, r_num):
    y, p, r = d_str[:4], PLACE_MAP.get(p_name, "05"), str(r_num).zfill(2)
    m, d = int(d_str[4:6]), int(d_str[6:8])
    target = f"{m}月{d}日"
    print(f"🚀 {target} {p_name} {r_num}R を爆速捜索中...")
    
    # 検索効率を上げるため、一般的な開催回数（1-4回）と日数（1-8日）を優先
    for kai in range(1, 5):
        for day in range(1, 10):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            try:
                # タイムアウトを短く設定してサクサク進める
                res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=3)
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
    
    title = soup.find('title').text.split('｜')[0] if soup.find('title') else "予想結果"
    is_result = "RaceTable01" in res.text
    rows = soup.select('tr.HorseList') or soup.select('table.RaceTable01 tr')
    
    horses, seen = [], set()
    for row in rows:
        try:
            tds = row.find_all('td')
            if len(tds) < 5: continue
            
            # --- 🎯 馬番だけを厳密に取得 ---
            if is_result:
                # 結果ページ：3列目が必ず馬番
                umaban = tds[2].text.strip()
                name_tag = tds[3].select_one('a[href*="/horse/"]')
                jockey_tag = tds[6].select_one('a[href*="/jockey/"]')
            else:
                # 出馬表ページ：Umabanクラスを取得
                u_tag = row.select_one('td.Umaban')
                umaban = u_tag.text.strip() if u_tag else ""
                name_tag = row.select_one('span.HorseName')
                jockey_tag = row.select_one('td.Jockey')

            if not umaban.isdigit() or not name_tag: continue
            if umaban in seen: continue
            seen.add(umaban)

            name = name_tag.text.strip()
            jockey = jockey_tag.text.strip() if jockey_tag else "不明"
            
            # オッズ（人気順と間違えないように数値のみ抽出）
            odds = 999.0
            o_match = re.search(r'(\d+\.\d+)', row.text)
            if o_match: odds = float(o_match.group(1))

            # スコア計算
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    return horses, title

def send_discord(horses, title, d, p, r):
    if not horses: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
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
                {"name": "💰 3連単推奨", "value": f"**1着**: {n[0]}\n**2着**: {n[1]}, {n[2]}\n**3着**: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ],
            "footer": {"text": "正しい馬番を取得するように修正しました"}
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
        print("✅ 全工程完了")
    else:
        print("❌ レースが見つかりませんでした")
