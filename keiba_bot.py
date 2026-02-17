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
    
    # 検索範囲（開催1-5回、日数1-9日）
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
    
    title = soup.find('title').text.split('｜')[0] if soup.find('title') else "競馬予想"
    
    # --- モード判定（ここを強化）---
    shutuba_rows = soup.select('tr.HorseList')
    result_rows = soup.select('table.RaceTable01 tr')
    
    if shutuba_rows:
        rows = shutuba_rows
        mode = "shutuba"
        print("ℹ️ 解析モード: 出馬表")
    elif result_rows:
        rows = result_rows
        mode = "result"
        print("ℹ️ 解析モード: レース結果")
    else:
        return [], title

    horses, seen = [], set()
    for row in rows:
        try:
            tds = row.find_all('td')
            # 結果ページはヘッダー行などが混じるので列数でガード
            if len(tds) < 5: continue
            
            # --- データ抽出 ---
            if mode == "result":
                # 結果ページ：3列目が馬番(tds[2])、4列目が馬名(tds[3])、7列目が騎手(tds[6])
                umaban = tds[2].text.strip()
                name = tds[3].text.strip().replace('\n', '')
                jockey = tds[6].text.strip().replace('\n', '')
            else:
                # 出馬表：クラス名で指定
                u_tag = row.select_one('td.Umaban')
                umaban = u_tag.text.strip() if u_tag else ""
                n_tag = row.select_one('span.HorseName')
                name = n_tag.text.strip() if n_tag else ""
                j_tag = row.select_one('td.Jockey')
                jockey = j_tag.text.strip() if j_tag else ""

            # クリーニング
            umaban = re.sub(r'\D', '', umaban)
            if not umaban or umaban in seen: continue
            seen.add(umaban)

            # オッズ（数値のみ抽出）
            odds = 999.0
            # 行全体のテキストから小数点を検索
            o_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
            if o_match:
                # 馬番や着順をオッズと間違えないよう、文脈など考慮したいが
                # 簡易的に、値が小さすぎる(1.0未満)や大きすぎる(馬番?)を排除したいが
                # ここでは見つかった小数を信じる（簡易ロジック）
                pass 
            
            # 出馬表ならtd.Oddsがある
            o_tag = row.select_one('td.Odds')
            if o_tag:
                otxt = o_tag.text.strip()
                if re.match(r'^\d+(\.\d+)?$', otxt): odds = float(otxt)

            # スコア計算
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    
    return horses, title

def send_discord(horses, title, d, p, r):
    if not horses:
        print("❌ エラー: 馬データが0件でした")
        return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    # 3連単フォーメーション
    himo = []
    if len(n) >= 5: himo = [n[1], n[2], n[3], n[4]]
    
    payload = {
        "username": "ゆーこうAI 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 解析完了",
            "color": 16753920,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "💰 3連単推奨", "value": f"1着: {n[0]}\n2着: {n[1]}, {n[2]}\n3着: {', '.join(map(str, himo))}", "inline": False}
            ]
        }]
    }
    res = requests.post(DISCORD_URL, json=payload)
    if res.status_code in [200, 204]: print("✅ Discord通知成功！")
    else: print(f"❌ Discord送信失敗: {res.status_code}")

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
        print("❌ レースが見つかりませんでした")
