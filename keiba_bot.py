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
# 👇 ここに必ずDiscordのURLを貼り付けてください！
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

# 会場コード
PLACE_MAP = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04",
    "東京": "05", "中山": "06", "中京": "07", "京都": "08",
    "阪神": "09", "小倉": "10"
}

def find_race_id(date_str, place_name, race_num):
    """
    日付・場所・RからレースIDを総当たりで探す（過去・未来両対応）
    """
    y = date_str[:4]
    p = PLACE_MAP.get(place_name, "05")
    r = str(race_num).zfill(2)
    
    # 日付のフォーマット作成 (例: 20260214 -> 2月14日)
    try:
        m = int(date_str[4:6])
        d = int(date_str[6:8])
        target_date_text = f"{m}月{d}日"
    except:
        print("❌ 日付形式エラー: YYYYMMDDで入力してください")
        return None

    print(f"🔍 '{target_date_text}' の {place_name} {race_num}R を捜索中...")

    # 開催回数(1-6回)と日数(1-12日目)を総当たり
    # ※最近のレースからヒットしやすいよう、逆順などで探索も可能だが今回は順当に
    for kai in range(1, 7):
        for day in range(1, 13):
            race_id = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            
            # まずは出馬表(shutuba)で探す
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(url, headers=headers, timeout=5)
                res.encoding = 'EUC-JP'
                html = res.text

                # ページの中に「指定した日付」があるかチェック
                if target_date_text in html:
                    print(f"✅ 発見しました！ ID: {race_id}")
                    return race_id
                
                # 念のため「結果ページ(result)」もチェック（過去レース用）
                if "レース結果" in html or "払戻" in html:
                     # 結果ページにリダイレクトされている場合も日付があればOK
                     if target_date_text in html:
                        print(f"✅ 発見(結果): {race_id}")
                        return race_id

            except Exception as e:
                continue
                
    print("❌ レースIDが見つかりませんでした。日付や場所が正しいか確認してください。")
    return None

def get_data(race_id):
    """レースデータを取得して解析"""
    # 出馬表URL
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')

    # レース名取得
    r_name_div = soup.find('div', class_='RaceName')
    race_name = r_name_div.text.strip() if r_name_div else "レース名不明"
    
    # 馬データを抽出
    horses = []
    # 出馬表の行(tr)を取得
    rows = soup.select('tr.HorseList')
    
    if not rows:
        # 結果ページ形式かもしれないので別タグをトライ
        rows = soup.select('table.RaceTable01 tr')

    for row in rows:
        try:
            # 馬番・馬名・オッズを取得（ページ形式によってタグが違うので柔軟に）
            umaban_tag = row.select_one('td.Umaban') or row.select_one('td:nth-of-type(1)') # 簡易
            name_tag = row.select_one('span.HorseName') or row.select_one('a[href*="horse"]')
            
            if not umaban_tag or not name_tag: continue

            umaban = umaban_tag.text.strip()
            if not umaban.isdigit(): continue # ヘッダー行などは飛ばす
            
            name = name_tag.text.strip()
            
            # オッズ (人気タグから取得、なければ単勝オッズタグ)
            odds = 99.9
            pop_tag = row.select_one('span.Popular')
            if pop_tag:
                # 人気順がある場合は簡易的にオッズと見なすか、別途オッズ列を探す
                # ここでは簡易ロジックとして、人気タグがある＝出馬表と判断
                odds_tag = row.select_one('td.Odds')
                if odds_tag:
                    try: odds = float(odds_tag.text.strip())
                    except: odds = 99.9
            else:
                # 結果ページの場合、単勝オッズは別の列にあることが多い
                # 簡易的に「オッズ取得失敗」として扱うか、99.9を入れる
                pass

            # ゆーこうロジック簡易版スコア
            score = 0
            if odds < 50:
                score += (100 / odds) # 支持率
            
            # 騎手ボーナス
            jockey_tag = row.select_one('td.Jockey')
            if jockey_tag:
                jockey = jockey_tag.text.strip()
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン', 'ムーア']):
                    score += 15
            else:
                jockey = "-"

            horses.append({
                "馬番": umaban, "馬名": name, "オッズ": odds, "騎手": jockey, "スコア": score
            })
        except:
            continue

    if not horses: return None, race_name

    df = pd.DataFrame(horses)
    df = df.sort_values('スコア', ascending=False)
    return df.head(6).to_dict('records'), race_name

def send_discord(ranks, race_name, date_str, place, r_num):
    if "http" not in DISCORD_WEBHOOK_URL:
        print("⚠️ エラー: Discord URLが設定されていません！keiba_bot.pyの12行目を確認してください。")
        return

    honmei = ranks[0]
    taikou = ranks[1]
    tana = ranks[2]
    
    msg = {
        "username": "ゆーこうAI 🏇",
        "embeds": [{
            "title": f"🎯 AI予想: {place}{r_num}R {race_name}",
            "description": f"📅 {date_str} | 簡易ロジック解析",
            "color": 16776960, # Yellow
            "fields": [
                {"name": "◎ 本命", "value": f"**{honmei['馬番']} {honmei['馬名']}**\n(想定オッズ: {honmei['オッズ']})", "inline": True},
                {"name": "〇 対抗", "value": f"**{taikou['馬番']} {taikou['馬名']}**", "inline": True},
                {"name": "▲ 単穴", "value": f"**{tana['馬番']} {tana['馬名']}**", "inline": True},
                {"name": "🔥 穴・相手", "value": f"{ranks[3]['馬番']}, {ranks[4]['馬番']}, {ranks[5]['馬番']}", "inline": False},
                {"name": "推奨買い目 (3連単F)", "value": f"1着: {honmei['馬番']}\n2着: {taikou['馬番']}, {tana['馬番']}\n3着: 流し ({ranks[3]['馬番']}, {ranks[4]['馬番']}...)", "inline": False}
            ]
        }]
    }
    
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=msg)
        if res.status_code == 204:
            print("✅ Discord通知に成功しました！")
        else:
            print(f"⚠️ Discord通知エラー: {res.status_code}")
    except Exception as e:
        print(f"⚠️ 送信例外: {e}")

if __name__ == "__main__":
    # 引数取得
    if len(sys.argv) > 3:
        d = sys.argv[1]
        p = sys.argv[2]
        r = sys.argv[3]
    else:
        # 手動テスト用
        d = "20260214"
        p = "東京"
        r = "11"

    print(f"🚀 ロボット起動: {d} {p} {r}R を解析します...")
    
    rid = find_race_id(d, p, r)
    if rid:
        data, name = get_data(rid)
        if data:
            send_discord(data, name, d, p, r)
        else:
            print("❌ データ抽出に失敗しました（馬情報が取れませんでした）")
    else:
        print("❌ 終了: IDが見つかりませんでした")
