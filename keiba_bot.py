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
        print("❌ 日付フォーマットエラー")
        return None

    print(f"🔍 '{target_date_text}' の {place_name} {race_num}R を捜索中...")

    for kai in range(1, 8):
        for day in range(1, 13):
            race_id = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
            try:
                res = requests.get(url, timeout=5)
                res.encoding = 'EUC-JP'
                if target_date_text in res.text and ("出馬表" in res.text or "レース結果" in res.text):
                    print(f"✅ ID発見: {race_id}")
                    return race_id
            except:
                continue
    return None

def get_data(race_id):
    print(f"📡 データ取得開始: ID {race_id}")
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    res = requests.get(url)
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')

    # レース名
    r_name = "レース名不明"
    if soup.find('div', class_='RaceName'):
        r_name = soup.find('div', class_='RaceName').text.strip()
    elif soup.find('h1'):
        r_name = soup.find('h1').text.strip()
    
    print(f"🏇 レース名: {r_name}")

    horses = []
    seen_umaban = set()

    # 行取得
    rows = soup.select('tr.HorseList')
    if not rows: 
        print("ℹ️ 出馬表モードで取得不可 -> 結果モードで試行")
        rows = soup.select('table.RaceTable01 tr')

    print(f"📊 取得した行数: {len(rows)}")

    for i, row in enumerate(rows):
        try:
            # 馬番取得トライ
            umaban = None
            u_tag = row.select_one('td.Umaban')
            if u_tag: 
                umaban = u_tag.text.strip()
            else:
                tds = row.select('td')
                if len(tds) > 3: umaban = tds[2].text.strip() # 結果ページの3列目
            
            # 数字のみ抽出
            if umaban: umaban = re.sub(r'\D', '', umaban)
            
            if not umaban or umaban in seen_umaban: continue
            seen_umaban.add(umaban)

            # 馬名
            name_tag = row.select_one('span.HorseName') or row.select_one('a[href*="horse"]')
            name = name_tag.text.strip() if name_tag else "不明"

            # オッズ
            odds = 999.0
            o_tag = row.select_one('td.Odds')
            if o_tag:
                txt = o_tag.text.strip()
                if re.match(r'^\d+(\.\d+)?$', txt): odds = float(txt)

            # 騎手
            jockey = "不明"
            j_tag = row.select_one('td.Jockey')
            if j_tag: jockey = j_tag.text.strip()

            # スコア計算
            score = 0
            if odds < 900: score += (100 / odds) * 1.5
            else: score += 5
            
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン']): score += 15

            horses.append({
                "馬番": int(umaban), "馬名": name, "オッズ": odds, "騎手": jockey, "スコア": score
            })
        except Exception as e:
            print(f"⚠️ 行解析エラー: {e}")
            continue

    print(f"🐴 抽出できた馬の数: {len(horses)}頭")
    
    if not horses: return None, r_name
    
    df = pd.DataFrame(horses).sort_values('スコア', ascending=False)
    return df, r_name

def send_discord(df, race_name, date_str, place, r_num):
    if len(df) < 3:
        print("❌ エラー: 馬が3頭未満のため予想できません")
        return

    top1 = df.iloc[0]
    top2 = df.iloc[1]
    top3 = df.iloc[2]
    
    # 穴馬リスト作成（空文字対策）
    holes = df.iloc[3:6]['馬番'].tolist()
    hole_str = ", ".join(map(str, holes))
    if not hole_str: hole_str = "なし"

    form1 = f"1着: {top1['馬番']}\n2着: {top2['馬番']}, {top3['馬番']}\n3着: {top2['馬番']}, {top3['馬番']}, {hole_str}"
    form2 = f"1,2着: {top1['馬番']} ⇔ {top2['馬番']}\n3着: {top3['馬番']}, {hole_str}"

    odds_disp = top1['オッズ'] if top1['オッズ'] < 900 else "取得前"

    msg = {
        "username": "ゆーこうAI (Debug)",
        "embeds": [{
            "title": f"🏇 {place}{r_num}R {race_name}",
            "description": f"📅 {date_str} | デバッグモード",
            "color": 5763719,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{top1['馬番']} {top1['馬名']}** ({odds_disp}倍)", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"{top2['馬番']} {top2['馬名']}", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"{top3['馬番']} {top3['馬名']}", "inline": True},
                {"name": "🔥 紐", "value": hole_str, "inline": False},
                {"name": "買い目", "value": form1 + "\n\n" + form2, "inline": False}
            ]
        }]
    }
    
    print("📤 Discordへ送信中...")
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=msg)
        print(f"📩 ステータスコード: {res.status_code}")
        if res.status_code in [200, 204]:
            print("✅ 送信成功！")
        else:
            print(f"❌ 送信失敗: {res.text}")
    except Exception as e:
        print(f"❌ 通信エラー: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 3:
        d, p, r = sys.argv[1], sys.argv[2], sys.argv[3]
    else:
        d, p, r = "20260222", "東京", "11"

    print(f"🚀 開始: {d} {p} {r}R")
    rid = find_race_id(d, p, r)
    if rid:
        df, name = get_data(rid)
        if df is not None:
            send_discord(df, name, d, p, r)
        else:
            print("❌ 馬データが空です")
    else:
        print("❌ レースIDが見つかりません")
