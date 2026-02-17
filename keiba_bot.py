import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import sys
import re
import json

# ==========================================
# ⚙️ 設定：Discord Webhook URL (埋め込み済み)
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04",
    "東京": "05", "中山": "06", "中京": "07", "京都": "08",
    "阪神": "09", "小倉": "10"
}

def find_race_id(date_str, place_name, race_num):
    """日付・場所・RからレースIDを特定する"""
    y, p, r = date_str[:4], PLACE_MAP.get(place_name, "05"), str(race_num).zfill(2)
    try:
        target_date_text = f"{int(date_str[4:6])}月{int(date_str[6:8])}日"
    except: return None

    print(f"🔍 '{target_date_text}' {place_name} {race_num}R を捜索中...")
    for kai in range(1, 8):
        for day in range(1, 13):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            try:
                res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=5)
                res.encoding = 'EUC-JP'
                if target_date_text in res.text:
                    print(f"✅ ID発見: {rid}")
                    return rid
            except: continue
    return None

def get_data(race_id):
    """馬番重複を完全に防止してデータを取得"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')

    # レース名
    rname = "レース名不明"
    name_elem = soup.find('div', class_='RaceName') or soup.find('h1')
    if name_elem: rname = name_elem.text.strip()

    horses = []
    seen = set() # 重複チェック用

    # 出馬表か結果ページか判定
    rows = soup.select('tr.HorseList')
    if not rows:
        rows = soup.select('table.RaceTable01 tr')
        mode = "result"
    else: mode = "shutuba"

    for row in rows:
        try:
            tds = row.select('td')
            if mode == "shutuba":
                u_tag = row.select_one('td.Umaban')
                umaban = u_tag.text.strip() if u_tag else ""
                n_tag = row.select_one('span.HorseName')
                name = n_tag.text.strip() if n_tag else ""
                o_tag = row.select_one('td.Odds')
                odds_txt = o_tag.text.strip() if o_tag else "999"
                j_tag = row.select_one('td.Jockey')
                jockey = j_tag.text.strip() if j_tag else ""
            else: # 結果ページ
                if len(tds) < 5: continue
                umaban = tds[2].text.strip()
                name = tds[3].text.strip()
                jockey = tds[6].text.strip() if len(tds) > 6 else "不明"
                odds_txt = "999"

            # 馬番のクリーニングと重複排除
            umaban = re.sub(r'\D', '', umaban)
            if not umaban or umaban in seen: continue
            seen.add(umaban)

            # スコア計算 (ゆーこう式 Lite)
            odds = float(odds_txt) if re.match(r'^\d+(\.\d+)?$', odds_txt) else 999.0
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン', 'ムーア']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']): score += 8

            horses.append({"num": int(umaban), "name": name, "odds": odds, "jockey": jockey, "score": score})
        except: continue
    
    if not horses: return None, rname
    return pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True), rname

def send_discord(df, rname, date_str, place, r_num):
    if len(df) < 3: return
    top = df.head(6)
    nums = top['num'].tolist()
    
    # 💰 推奨馬券の構築
    # 馬連流し
    uren = f"**{nums[0]}** － {nums[1]}, {nums[2]}, {nums[3]}"
    # 3連単フォーメーション (◎ 1着固定)
    form1 = f"1着: {nums[0]}\n2着: {nums[1]}, {nums[2]}\n3着: {nums[1]}, {nums[2]}, {nums[3]}, {nums[4]}"
    # 3連単マルチ (◎〇 軸2頭)
    form2 = f"1,2着: {nums[0]} ⇔ {nums[1]}\n3着: {nums[2]}, {nums[3]}, {nums[4]}"

    msg = {
        "username": "ゆーこうAI 🏇",
        "embeds": [{
            "title": f"🎯 {place}{r_num}R {rname}",
            "description": f"📅 {date_str} | 解析完了",
            "color": 16753920,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{nums[0]}番 {top.iloc[0]['name']}** ({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{nums[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{nums[2]}番**", "inline": True},
                {"name": "🔥 穴・相手", "value": f"{nums[3]}, {nums[4]}, {nums[5]}", "inline": False},
                {"name": "💰 推奨馬券", "value": f"**【馬連】**\n{uren}\n\n**【3連単フォーメーション】**\n{form1}\n\n**【3連単マルチ】**\n{form2}", "inline": False}
            ],
            "footer": {"text": "Developed by Yuuki & Hybrid-AI"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    d, p, r = (sys.argv[1], sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("20260222", "東京", "11")
    rid = find_race_id(d, p, r)
    if rid:
        df, name = get_data(rid)
        if df is not None:
            send_discord(df, name, d, p, r)
            print("✅ Discord送信完了")
