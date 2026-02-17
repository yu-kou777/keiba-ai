import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import sys
import re
import time

# ==========================================
# ⚙️ 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_html(url):
    """ブロック回避のためのヘッダー設定"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'EUC-JP'
        return res.text
    except:
        return ""

def find_race_id(date_str, place_name, race_num):
    """爆速でレースIDを特定する（検索範囲を最適化）"""
    y, p, r = date_str[:4], PLACE_MAP.get(place_name, "05"), str(race_num).zfill(2)
    m, d = int(date_str[4:6]), int(date_str[6:8])
    target_date = f"{m}月{d}日"

    print(f"🚀 {target_date} {place_name} {race_num}R を探しています...")

    # 通常、開催は1-3回、日数は1-8日以内に収まることが多いので範囲を絞る
    for kai in range(1, 4): 
        for day in range(1, 10):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            html = get_html(url)
            if target_date in html:
                print(f"✅ 発見しました！ ID: {rid}")
                return rid
            time.sleep(0.1) # サーバー負荷軽減
    return None

def scrape_data(race_id):
    """出馬表または結果ページから馬データを抽出"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    html = get_html(url)
    soup = BeautifulSoup(html, 'html.parser')

    # レース名
    rname = "レース名不明"
    name_elem = soup.find('div', class_='RaceName') or soup.find('h1')
    if name_elem: rname = name_elem.text.strip()

    horses = []
    seen = set()
    # テーブルの行を取得
    rows = soup.select('tr.HorseList') or soup.select('table.RaceTable01 tr')

    for row in rows:
        try:
            tds = row.select('td')
            if len(tds) < 4: continue
            
            # 馬番の抽出
            u_text = row.select_one('td.Umaban').text if row.select_one('td.Umaban') else tds[2].text
            umaban = re.sub(r'\D', '', u_text)
            if not umaban or umaban in seen: continue
            seen.add(umaban)

            # 馬名・騎手・オッズ
            name = (row.select_one('span.HorseName') or row.select_one('a[href*="horse"]')).text.strip()
            jockey = (row.select_one('td.Jockey') or tds[6]).text.strip()
            
            odds_txt = "999"
            o_tag = row.select_one('td.Odds')
            if o_tag and re.match(r'^\d', o_tag.text.strip()):
                odds_txt = o_tag.text.strip()
            
            # ゆーこう式スコア（簡易版）
            odds = float(odds_txt) if odds_txt != "999" else 999.0
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    
    return horses, rname

def send_to_discord(horses, rname, d, p, r):
    if not horses:
        print("❌ 解析できる馬が見つかりませんでした")
        return

    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    msg = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {rname}",
            "description": f"📅 {d} | 解析成功",
            "color": 16753920,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}** ({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "💰 3連単推奨", "value": f"**1着**: {n[0]}\n**2着**: {n[1]}, {n[2]}\n**3着**: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    args = sys.argv
    date, place, race = (args[1], args[2], args[3]) if len(args) > 3 else ("20260222", "東京", "11")
    
    rid = find_race_id(date, place, race)
    if rid:
        h_data, r_name = scrape_data(rid)
        send_to_discord(h_data, r_name, date, place, race)
        print("✅ 全工程完了！Discordを確認してください。")
    else:
        print("❌ 指定されたレースが見つかりませんでした。")
