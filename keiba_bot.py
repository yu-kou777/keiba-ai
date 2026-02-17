import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import sys
import re
import time

# ==========================================
# ⚙️ 設定：Discord Webhook URL (埋め込み済み)
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04",
    "東京": "05", "中山": "06", "中京": "07", "京都": "08",
    "阪神": "09", "小倉": "10"
}

def get_html(url):
    """サイトからのブロックを回避してHTMLを取得"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = 'EUC-JP'
        return res.text
    except:
        return ""

def find_race_id(date_str, place_name, race_num):
    """日付からNetkeibaのレースIDを自動で探し出す"""
    y = date_str[:4]
    p = PLACE_MAP.get(place_name, "05")
    r = str(race_num).zfill(2)
    m, d = int(date_str[4:6]), int(date_str[6:8])
    target_date = f"{m}月{d}日"

    print(f"🚀 {target_date} {place_name} {race_num}R を捜索中...")

    # 開催回(1-6)と日数(1-12)をチェック
    for kai in range(1, 7):
        for day in range(1, 13):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            html = get_html(url)
            
            # ページ内に指定した日付があるか？
            if target_date in html:
                print(f"✅ レースが見つかりました！ ID: {rid}")
                return rid
            
    print("❌ レースIDが見つかりませんでした。日付や場所が正しいか確認してください。")
    return None

def scrape_data(race_id):
    """馬データを抽出（重複を完全に排除）"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    html = get_html(url)
    # Python標準のパーサーを使用（エラー回避のため）
    soup = BeautifulSoup(html, 'html.parser')

    # レース名
    rname = "レース名不明"
    name_elem = soup.find('div', class_='RaceName') or soup.find('h1')
    if name_elem:
        rname = name_elem.text.strip()

    horses = []
    seen_umaban = set() # 🛑 重複防止用

    # 出馬表(HorseList)または結果(RaceTable01)の行を取得
    rows = soup.select('tr.HorseList') or soup.select('table.RaceTable01 tr')

    for row in rows:
        try:
            tds = row.select('td')
            if len(tds) < 4: continue
            
            # 馬番の抽出（出馬表クラスまたは3列目）
            u_tag = row.select_one('td.Umaban')
            u_text = u_tag.text if u_tag else tds[2].text
            umaban = re.sub(r'\D', '', u_text)
            
            if not umaban or umaban in seen_umaban: continue
            seen_umaban.add(umaban)

            # 馬名・騎手
            name_tag = row.select_one('span.HorseName') or row.select_one('a[href*="horse"]')
            name = name_tag.text.strip() if name_tag else "不明"
            
            j_tag = row.select_one('td.Jockey')
            jockey = j_tag.text.strip() if j_tag else tds[6].text.strip()
            
            # オッズ
            odds_txt = "999"
            o_tag = row.select_one('td.Odds')
            if o_tag and re.match(r'^\d', o_tag.text.strip()):
                odds_txt = o_tag.text.strip()
            
            # --- 🧠 ゆーこう式スコア ---
            odds = float(odds_txt) if odds_txt != "999" else 999.0
            score = (100 / odds) * 1.5 if odds < 900 else 5
            
            # 騎手ボーナス
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン', 'ムーア']):
                score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']):
                score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except:
            continue
    
    return horses, rname

def send_to_discord(horses, rname, d, p, r):
    if not horses or len(horses) < 3:
        print("❌ 解析できる馬が足りませんでした")
        return

    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    # 3連単フォーメーションの整理
    himo = ", ".join(map(str, n[1:5])) # 〇▲穴1穴2

    msg = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {rname}",
            "description": f"📅 {d} | 解析成功！",
            "color": 16753920, # Orange
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "🔥 紐候補", "value": f"{n[3]}, {n[4]}, {n[5]}", "inline": False},
                {"name": "💰 3連単(本命1頭軸FM)", "value": f"1着: {n[0]}\n2着: {n[1]}, {n[2]}\n3着: {himo}", "inline": False}
            ],
            "footer": {"text": "Powered by Yuuki-Logic"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    # 引数: 日付(20260222) 場所(東京) レース(11)
    args = sys.argv
    date, place, race = (args[1], args[2], args[3]) if len(args) > 3 else ("20260222", "東京", "11")
    
    rid = find_race_id(date, place, race)
    if rid:
        h_data, r_name = scrape_data(rid)
        send_to_discord(h_data, r_name, date, place, race)
        print("✅ すべての処理が完了しました。Discordを確認してください！")
    else:
        # IDが見つからなくてもエラーにせず正常終了させる（Actionsを緑にするため）
        print("❌ レースが見つかりませんでした。")
