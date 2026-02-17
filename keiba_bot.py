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
    
    # --- 🛠️ 過去ページ(RaceTable01)か出馬表(HorseList)かを自動判別 ---
    is_result = "RaceTable01" in res.text
    rows = soup.select('table.RaceTable01 tr') if is_result else soup.select('tr.HorseList')
    
    horses, seen = [], set()
    for row in rows:
        try:
            tds = row.find_all('td')
            if len(tds) < 5: continue
            
            if is_result:
                # 【過去結果ページ用スキャン】
                umaban = tds[2].text.strip() # 3列目:馬番
                name_tag = tds[3].select_one('a[href*="/horse/"]') # 4列目:馬名
                jockey_tag = tds[6].select_one('a[href*="/jockey/"]') # 7列目:騎手
                # オッズは13列目あたりにあるが、数値抽出で対応
                odds_txt = tds[12].text.strip() if len(tds) > 12 else "999"
            else:
                # 【出馬表ページ用スキャン】
                umaban = row.select_one('td.Umaban').text.strip() if row.select_one('td.Umaban') else ""
                name_tag = row.select_one('span.HorseName')
                jockey_tag = row.select_one('td.Jockey')
                odds_tag = row.select_one('td.Odds')
                odds_txt = odds_tag.text.strip() if odds_tag else "999"

            if not umaban.isdigit() or not name_tag: continue
            if umaban in seen: continue
            seen.add(umaban)

            name = name_tag.text.strip()
            jockey = jockey_tag.text.strip() if jockey_tag else "不明"
            
            # オッズの数値化
            odds = 999.0
            o_match = re.search(r'(\d+\.\d+)', odds_txt)
            if o_match: odds = float(o_match.group(1))

            # 🧠 ゆーこう式スコア計算
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "odds": odds, "score": score})
        except: continue
    
    return horses, title

def send_discord(horses, title, d, p, r):
    if len(horses) < 3:
        print(f"❌ 抽出馬不足({len(horses)}頭)。解析をスキップします。")
        return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 過去データ検証モード",
            "color": 3447003, # Blue
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n(騎手: {top.iloc[0]['jockey']} / 当時オッズ: {top.iloc[0]['odds']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "💰 AI推奨買い目", "value": f"3連単 1着固定流し\n軸: {n[0]}\n相手: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ],
            "footer": {"text": "この予想と実際の結果を照らし合わせて精度を確認してください"}
        }]
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    a = sys.argv
    d, p, r = (a[1], a[2], a[3]) if len(a) > 3 else ("20260215", "京都", "11") # デフォルトを京都記念に設定
    rid = find_race_id(d, p, r)
    if rid:
        h, t = get_data(rid)
        print(f"📊 抽出馬数: {len(h)}頭")
        send_discord(h, t, d, p, r)
        print("✅ 検証用データの送信が完了しました")
    else:
        print("❌ 指定されたレースが見つかりませんでした")
