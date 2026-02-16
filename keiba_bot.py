import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import sys
import re

# ==========================================
# ⚙️ 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

# 会場コードマップ
PLACE_MAP = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04",
    "東京": "05", "中山": "06", "中京": "07", "京都": "08",
    "阪神": "09", "小倉": "10"
}

def get_race_id_from_url(url):
    """URLからレースIDを抽出"""
    match = re.search(r'race_id=(\d+)', url)
    if match:
        return match.group(1)
    return None

def find_today_race_id(date_str, place_name, race_num):
    """
    日付と場所からNetkeibaのレースIDを探索する
    """
    y = date_str[:4]
    p = PLACE_MAP.get(place_name, "05")
    r = str(race_num).zfill(2)
    
    # 開催回数(1-6)と日数(1-12)を総当たりして、該当するレースを探す
    # (スマートな方法ではないが、確実に見つけるための力技)
    print(f"🔍 {date_str} {place_name} {race_num}R のIDを探索中...")
    
    # 最新に近い開催から逆順または順に探す
    for kai in range(1, 7):
        for day in range(1, 13):
            race_id = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
            try:
                # ヘッダー情報を偽装しないと弾かれることがあるため設定
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(url, headers=headers, timeout=5)
                res.encoding = 'EUC-JP'
                
                # ページ内に「日付」が含まれているかチェック
                # Netkeibaの日付形式: 2026年2月14日
                target_date_format = f"{int(date_str[4:6])}月{int(date_str[6:8])}日"
                
                if target_date_format in res.text and "出馬表" in res.text:
                    return race_id
            except:
                continue
    return None

def analyze_race(race_id):
    """レースデータを取得して簡易ロジックで解析"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')

    race_name_elem = soup.find('div', class_='RaceName')
    race_name = race_name_elem.text.strip() if race_name_elem else "レース名取得不可"
    
    print(f"🏇 解析開始: {race_name}")

    horses = []
    rows = soup.select('tr.HorseList')

    for row in rows:
        try:
            umaban = row.select_one('td.Umaban').text.strip()
            name = row.select_one('span.HorseName').text.strip()
            
            # オッズ取得 (人気順のタグから推測、またはオッズタグ)
            odds_span = row.select_one('td.Tx-C span.Popular')
            if odds_span:
                ninki = float(odds_span.text.strip())
                # 簡易的なオッズ推定（人気から逆算は難しいので、オッズ単体があればそれを優先）
                odds_txt = row.select_one('td.Odds').text.strip()
                odds = float(odds_txt) if odds_txt and odds_txt.replace('.','').isdigit() else 99.9
            else:
                odds = 99.9
            
            # ゆーこうロジック（簡易版）
            # オッズ30倍以下をターゲット、そこから期待値を算出
            score = 0
            if odds < 30:
                score += (100 / odds) # 支持率
            
            # 騎手ボーナス
            jockey = row.select_one('td.Jockey').text.strip()
            if any(x in jockey for x in ['ルメール', '川田', '武豊', '坂井', '戸崎', 'レーン', 'ムーア']):
                score += 15
                
            horses.append({
                "馬番": umaban, "馬名": name, "オッズ": odds, "騎手": jockey, "スコア": score
            })
        except:
            continue

    df = pd.DataFrame(horses)
    if df.empty: return None, race_name
    
    df = df.sort_values('スコア', ascending=False)
    return df.head(6).to_dict('records'), race_name

def send_discord(ranks, race_name, date_str, place, r_num):
    if "http" not in DISCORD_WEBHOOK_URL:
        print("⚠️ Discord URL未設定")
        return

    honmei = ranks[0]
    taikou = ranks[1]
    tana = ranks[2]
    
    # 3連単フォーメーション推奨
    # 1着: ◎
    # 2着: 〇, ▲
    # 3着: 〇, ▲, △(4-6位)
    
    msg = {
        "username": "ゆーこうAI 🏇",
        "embeds": [{
            "title": f"🎯 AI予想: {place}{r_num}R {race_name}",
            "description": f"📅 {date_str} | 簡易ロジック解析結果",
            "color": 15844367,
            "fields": [
                {"name": "◎ 本命", "value": f"**{honmei['馬番']} {honmei['馬名']}**\n(オッズ: {honmei['オッズ']})", "inline": True},
                {"name": "〇 対抗", "value": f"**{taikou['馬番']} {taikou['馬名']}**\n(オッズ: {taikou['オッズ']})", "inline": True},
                {"name": "▲ 単穴", "value": f"**{tana['馬番']} {tana['馬名']}**", "inline": True},
                {"name": "💰 推奨買い目 (3連単FM)", "value": f"1着: {honmei['馬番']}\n2着: {taikou['馬番']}, {tana['馬番']}\n3着: {taikou['馬番']}, {tana['馬番']}, {ranks[3]['馬番']}, {ranks[4]['馬番']}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    # GitHub Actionsからの引数を受け取る
    # 引数: python keiba_bot.py 20260222 東京 11
    if len(sys.argv) > 3:
        d = sys.argv[1]
        p = sys.argv[2]
        r = sys.argv[3]
    else:
        # テスト用デフォルト
        d = datetime.datetime.now().strftime('%Y%m%d')
        p = "東京"
        r = "11"

    rid = find_today_race_id(d, p, r)
    if rid:
        data, name = analyze_race(rid)
        if data:
            send_discord(data, name, d, p, r)
            print("✅ 送信完了")
    else:
        print("❌ レースが見つかりませんでした")
