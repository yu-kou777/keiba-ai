import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import sys
import re
import json

# ==========================================
# ⚙️ 設定：Discord Webhook URL
# ==========================================
# 👇 DiscordのURLはそのまま残してください
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04",
    "東京": "05", "中山": "06", "中京": "07", "京都": "08",
    "阪神": "09", "小倉": "10"
}

def find_race_id(date_str, place_name, race_num):
    y = date_str[:4]
    p = PLACE_MAP.get(place_name, "05")
    r = str(race_num).zfill(2)
    try:
        m = int(date_str[4:6])
        d = int(date_str[6:8])
        target_date_text = f"{m}月{d}日"
    except:
        return None

    print(f"🔍 '{target_date_text}' の {place_name} {race_num}R を捜索中...")

    for kai in range(1, 7):
        for day in range(1, 13):
            race_id = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(url, headers=headers, timeout=5)
                res.encoding = 'EUC-JP'
                html = res.text
                if target_date_text in html and ("出馬表" in html or "レース結果" in html):
                    print(f"✅ 発見: {race_id}")
                    return race_id
            except:
                continue
    return None

def get_data(race_id):
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')

    # レース名取得（強化版）
    race_name = "レース名不明"
    # 出馬表ページのタイトル
    r_name_div = soup.find('div', class_='RaceName')
    if r_name_div:
        race_name = r_name_div.text.strip()
    else:
        # 結果ページのタイトル(h1など)
        h1_title = soup.find('h1', class_='RaceName')
        if h1_title:
            race_name = h1_title.text.strip()
        else:
            # ページタイトルから推測
            title_tag = soup.find('title')
            if title_tag:
                race_name = title_tag.text.split('｜')[0]

    # 馬データを抽出
    horses = []
    rows = soup.select('tr.HorseList')
    if not rows:
        rows = soup.select('table.RaceTable01 tr') # 結果ページ用

    for row in rows:
        try:
            umaban_tag = row.select_one('td.Umaban') or row.select_one('td:nth-of-type(1)')
            name_tag = row.select_one('span.HorseName') or row.select_one('a[href*="horse"]')
            if not umaban_tag or not name_tag: continue

            umaban = umaban_tag.text.strip()
            if not umaban.isdigit(): continue
            name = name_tag.text.strip()
            
            # オッズ取得
            odds = 99.9
            # 人気タグがあればそこからオッズ推測（簡易）
            pop_tag = row.select_one('span.Popular')
            odds_tag = row.select_one('td.Odds')
            
            if odds_tag:
                txt = odds_tag.text.strip()
                if txt.replace('.','').isdigit():
                    odds = float(txt)
            
            # ゆーこうロジック簡易版
            score = 0
            if odds < 30: score += (100 / odds)
            
            jockey_tag = row.select_one('td.Jockey')
            if jockey_tag:
                jockey = jockey_tag.text.strip()
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン']):
                    score += 15
            
            horses.append({"馬番": umaban, "馬名": name, "オッズ": odds, "スコア": score})
        except:
            continue

    if not horses: return None, race_name
    
    # ランキング作成
    df = pd.DataFrame(horses)
    df = df.sort_values('スコア', ascending=False)
    return df.head(6).to_dict('records'), race_name

def send_discord(ranks, race_name, date_str, place, r_num):
    if "http" not in DISCORD_WEBHOOK_URL:
        print("⚠️ Discord URL未設定")
        return

    honmei = ranks[0]
    taikou = ranks[1]
    tana = ranks[2]
    
    # オッズが99.9（取得失敗）の場合は表示を変える
    odds_str = f"{honmei['オッズ']}" if honmei['オッズ'] != 99.9 else "取得不可(終了レース)"

    msg = {
        "username": "ゆーこうAI 🏇",
        "embeds": [{
            "title": f"🎯 AI予想: {place}{r_num}R {race_name}",
            "description": f"📅 {date_str} | 簡易ロジック解析",
            "color": 16776960,
            "fields": [
                {"name": "◎ 本命", "value": f"**{honmei['馬番']} {honmei['馬名']}**\n(オッズ: {odds_str})", "inline": True},
                {"name": "〇 対抗", "value": f"**{taikou['馬番']} {taikou['馬名']}**", "inline": True},
                {"name": "▲ 単穴", "value": f"**{tana['馬番']} {tana['馬名']}**", "inline": True},
                {"name": "推奨買い目 (3連単F)", "value": f"1着: {honmei['馬番']}\n2着: {taikou['馬番']}, {tana['馬番']}\n3着: 流し ({ranks[3]['馬番']}...)", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    if len(sys.argv) > 3:
        d, p, r = sys.argv[1], sys.argv[2], sys.argv[3]
    else:
        d, p, r = "20260214", "東京", "11"

    print(f"🚀 {d} {p} {r}R 解析開始")
    rid = find_race_id(d, p, r)
    if rid:
        data, name = get_data(rid)
        if data:
            send_discord(data, name, d, p, r)
            print("✅ 完了")
        else:
            print("❌ データなし")
    else:
        print("❌ ID特定失敗")
