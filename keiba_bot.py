import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re

# --- 設定：Discord URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {"東京":"05","中山":"06","京都":"08","阪神":"09","中京":"07","小倉":"10","新潟":"04","福島":"03","札幌":"01","函館":"02"}

def find_race_id(d_str, p_name, r_num):
    y, p, r = d_str[:4], PLACE_MAP.get(p_name, "05"), str(r_num).zfill(2)
    m, d = int(d_str[4:6]), int(d_str[6:8])
    target = f"{m}月{d}日"
    print(f"🚀 {target} {p_name} {r_num}R を捜索中...")
    
    # 検索範囲
    for kai in range(1, 6):
        for day in range(1, 10):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            try:
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
    all_rows = soup.find_all('tr')
    
    # 結果ページかどうか判定（テーブルのクラスなどで簡易判定）
    is_result_page = bool(soup.select('table.RaceTable01'))

    horses, seen = [], set()
    for row in all_rows:
        try:
            # 馬名がある行を探す
            name_tag = row.select_one('a[href*="/horse/"]')
            if not name_tag: continue
            name = name_tag.text.strip()
            
            tds = row.find_all('td')
            umaban = ""

            # --- 🎯 馬番取得：3段構え ---
            
            # 作戦A: クラス名指定
            u_tag = row.select_one('td.Umaban')
            if u_tag:
                umaban = re.sub(r'\D', '', u_tag.text.strip())
            
            # 作戦B: 結果ページなら「3列目(index 2)」が馬番の定位置
            if not umaban and is_result_page and len(tds) > 3:
                txt = tds[2].text.strip()
                if txt.isdigit(): umaban = txt
            
            # 作戦C: 馬名セルの「左隣」を確認
            if not umaban:
                for i, td in enumerate(tds):
                    if td == name_tag.parent: # 馬名の親セル
                        if i > 0:
                            prev_text = tds[i-1].text.strip()
                            if prev_text.isdigit(): umaban = prev_text
                        break

            # 最終チェック: 1~18の数字か？
            if not umaban.isdigit() or not (1 <= int(umaban) <= 18): continue
            
            if umaban in seen: continue
            seen.add(umaban)

            # 騎手
            jockey = "不明"
            j_tag = row.select_one('a[href*="/jockey/"]')
            if j_tag: jockey = j_tag.text.strip()

            # オッズ
            odds = 999.0
            o_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
            if o_match: odds = float(o_match.group(1))

            # スコア
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    
    return horses, title

def send_discord(horses, title, d, p, r):
    # 安全装置: 馬が3頭未満なら送信せずログに残す
    if not horses or len(horses) < 3:
        print(f"⚠️ データ不足: {len(horses)}頭しか見つかりませんでした。スキップします。")
        return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    himo = n[1:5] if len(n) >= 5 else n[1:]
    
    payload = {
        "username": "ゆーこうAI 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 解析成功",
            "color": 16753920,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "💰 3連単推奨", "value": f"1着: {n[0]}\n2着: {n[1]}, {n[2]}\n3着: {', '.join(map(str, himo))}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    a = sys.argv
    d, p, r = (a[1], a[2], a[3]) if len(a) > 3 else ("20260222", "東京", "11")
    rid = find_race_id(d, p, r)
    if rid:
        h, t = get_data(rid)
        print(f"📊 抽出馬数: {len(h)}頭")
        send_discord(h, t, d, p, r)
        print("✅ 全工程完了")
    else:
        print("❌ レースなし")
