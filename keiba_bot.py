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
    """日付・場所・RからレースIDを特定する"""
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

    # 開催回数(1-7)と日数(1-12)を総当たり
    for kai in range(1, 8):
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
    """レースデータを取得・解析（重複防止強化版）"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')

    # レース名取得
    r_name_div = soup.find('div', class_='RaceName')
    if r_name_div:
        race_name = r_name_div.text.strip()
    else:
        h1 = soup.find('h1')
        race_name = h1.text.strip() if h1 else "レース名不明"

    horses = []
    seen_umaban = set() # 🛑 重複チェック用

    # --- モード判定: 出馬表か、結果ページか ---
    # 出馬表テーブルを探す
    shutuba_rows = soup.select('tr.HorseList')
    
    if shutuba_rows:
        # 【Aパターン】未来のレース（出馬表）
        target_rows = shutuba_rows
        mode = "shutuba"
    else:
        # 【Bパターン】過去のレース（結果ページ）
        # 結果テーブル(RaceTable01)のみを厳密に指定
        target_rows = soup.select('table.RaceTable01 tr')
        mode = "result"

    for row in target_rows:
        try:
            umaban = None
            name = None
            odds = 999.0
            jockey = ""

            if mode == "shutuba":
                # 出馬表モードのデータ取得
                u_tag = row.select_one('td.Umaban')
                if u_tag: umaban = u_tag.text.strip()
                
                n_tag = row.select_one('span.HorseName')
                if n_tag: name = n_tag.text.strip()
                
                o_tag = row.select_one('td.Odds')
                if o_tag:
                    txt = o_tag.text.strip()
                    if re.match(r'^\d+(\.\d+)?$', txt): odds = float(txt)
                
                j_tag = row.select_one('td.Jockey')
                if j_tag: jockey = j_tag.text.strip()

            elif mode == "result":
                # 結果モードのデータ取得（列の位置が違うので注意）
                tds = row.select('td')
                if len(tds) < 5: continue # ヘッダー行などをスキップ
                
                # 結果ページの列: 0:着順, 1:枠, 2:馬番, 3:馬名...
                umaban = tds[2].text.strip()
                name = tds[3].text.strip().replace('\n', '')
                
                # 騎手は結果ページの特定列（通常6列目あたり）
                if len(tds) > 6: jockey = tds[6].text.strip()
                
                # 結果ページには「単勝オッズ」がない場合が多いので人気順で代用しない（999とする）
                # ただし、今回は「テスト」なので、着順をヒントにスコア付けしないように注意

            # --- 共通チェック ---
            # 馬番が数字でない、または既に登録済みの場合はスキップ
            if not umaban or not umaban.isdigit(): continue
            if umaban in seen_umaban: continue
            
            # 登録
            seen_umaban.add(umaban)

            # --- 🧠 ゆーこう式AIロジック (Lite Model) ---
            score = 0
            
            # 1. 支持率スコア
            if odds < 900: # オッズが取れている場合
                score += (100 / odds) * 1.5
            else:
                # オッズがない（結果ページなど）場合、騎手だけで簡易スコア
                score += 5 # 基礎点
            
            # 2. 騎手ボーナス
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン', 'ムーア', 'モレイラ']):
                score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島', '岩田']):
                score += 8

            horses.append({
                "馬番": int(umaban), 
                "馬名": name, 
                "オッズ": odds, 
                "騎手": jockey, 
                "スコア": score
            })
        except Exception as e:
            continue

    if not horses: return None, race_name
    
    # スコア順に並べ替え
    df = pd.DataFrame(horses)
    df = df.sort_values('スコア', ascending=False).reset_index(drop=True)
    return df, race_name

def make_recommendation(df):
    """スコアに基づいて重複のない買い目を構築する"""
    if len(df) < 3: return None
    
    # 上位馬を抽出
    top1 = df.iloc[0] # ◎
    top2 = df.iloc[1] # 〇
    top3 = df.iloc[2] # ▲
    
    # 穴候補：上位3頭「以外」から抽出（重複防止）
    main_ids = [top1['馬番'], top2['馬番'], top3['馬番']]
    # 上位3頭以外データを抽出
    others = df[~df['馬番'].isin(main_ids)]
    
    holes = others.head(3)
    hole_nums = holes['馬番'].tolist()
    hole_str = ", ".join(map(str, hole_nums))

    # ヒモ候補リスト（対抗・単穴・穴馬）
    himo_list_nums = [top2['馬番'], top3['馬番']] + hole_nums
    himo_str = ", ".join(map(str, himo_list_nums))
    
    # 3連単フォーメーション構築
    # パターン1: 本命ガチ (1着固定 -> 2,3着流し)
    form1 = f"1着: {top1['馬番']}\n2着: {top2['馬番']}, {top3['馬番']}\n3着: {himo_str}"
    
    # パターン2: 本命・対抗折り返し
    # 穴馬がいる場合のみ追加
    hole_part = f", {hole_str}" if hole_str else ""
    form2 = f"1,2着: {top1['馬番']} ⇔ {top2['馬番']}\n3着: {top3['馬番']}{hole_part}"

    return top1, top2, top3, hole_str, form1, form2

def send_discord(df, race_name, date_str, place, r_num):
    rec = make_recommendation(df)
    if not rec:
        print("❌ データ不足で予想できません")
        return
        
    top1, top2, top3, hole_str, form1, form2 = rec
    
    odds_disp = top1['オッズ'] if top1['オッズ'] < 900 else "取得前"

    msg = {
        "username": "ゆーこうAI (Lite Model)",
        "embeds": [{
            "title": f"🏇 {place}{r_num}R {race_name}",
            "description": f"📅 {date_str} | AI解析結果",
            "color": 5763719, # Green
            "fields": [
                {"name": "🥇 ◎ 本命 (信頼度S)", "value": f"**{top1['馬番']} {top1['馬名']}**\n({top1['騎手']} / {odds_disp}倍)", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{top2['馬番']} {top2['馬名']}**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{top3['馬番']} {top3['馬名']}**", "inline": True},
                {"name": "🔥 激走警戒 (Gap馬)", "value": f"{hole_str}", "inline": False},
                {"name": "🎯 推奨買い目 (3連単)", "value": f"**【本命堅実】**\n{form1}\n\n**【折り返し】**\n{form2}", "inline": False}
            ],
            "footer": {"text": "Developed by Yuuki & Hybrid-AI"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=msg)

if __name__ == "__main__":
    if len(sys.argv) > 3:
        d, p, r = sys.argv[1], sys.argv[2], sys.argv[3]
    else:
        d, p, r = "20260222", "東京", "11" # デフォルト

    print(f"🚀 解析開始: {d} {p} {r}R")
    rid = find_race_id(d, p, r)
    if rid:
        df, name = get_data(rid)
        if df is not None:
            send_discord(df, name, d, p, r)
            print("✅ 予想を送信しました")
        else:
            print("❌ データ抽出失敗")
    else:
        print("❌ レースIDが見つかりませんでした")
