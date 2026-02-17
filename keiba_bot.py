import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re

# ==========================================
# ⚙️ 設定：Discord Webhook URL（埋め込み済み）
# ==========================================
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

PLACE_MAP = {"東京":"05","中山":"06","京都":"08","阪神":"09","中京":"07","小倉":"10","新潟":"04","福島":"03","札幌":"01","函館":"02"}

def find_race_id(d_str, p_name, r_num):
    """爆速でレースIDを特定"""
    y, p, r = d_str[:4], PLACE_MAP.get(p_name, "05"), str(r_num).zfill(2)
    m, d = int(d_str[4:6]), int(d_str[6:8])
    target_date = f"{m}月{d}日"
    print(f"🚀 {target_date} {p_name} {r_num}R を捜索...")

    for kai in range(1, 7):
        for day in range(1, 13):
            rid = f"{y}{p}{str(kai).zfill(2)}{str(day).zfill(2)}{r}"
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
            try:
                res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
                res.encoding = 'EUC-JP'
                if target_date in res.text:
                    print(f"✅ ID発見: {rid}")
                    return rid
            except: continue
    return None

def get_keiba_data(rid):
    """出馬表または結果から馬を抽出（重複排除）"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    res.encoding = 'EUC-JP'
    soup = BeautifulSoup(res.text, 'html.parser')

    title = soup.find('title').text.split('｜')[0] if soup.find('title') else "競馬予想"
    rows = soup.select('tr.HorseList') or soup.select('table.RaceTable01 tr')
    
    horses = []
    seen = set()
    for row in rows:
        try:
            tds = row.select('td')
            if len(tds) < 4: continue
            
            # 馬番
            u_tag = row.select_one('td.Umaban')
            u_txt = u_tag.text if u_tag else tds[2].text
            umaban = re.sub(r'\D', '', u_txt)
            if not umaban or umaban in seen: continue
            seen.add(umaban)

            # 馬名・騎手・オッズ
            name = (row.select_one('span.HorseName') or row.select_one('a[href*="horse"]')).text.strip()
            jockey = (row.select_one('td.Jockey') or tds[6]).text.strip()
            
            o_tag = row.select_one('td.Odds')
            odds_txt = o_tag.text.strip() if o_tag and re.match(r'^\d', o_tag.text.strip()) else "999"
            odds = float(odds_txt) if odds_txt != "999" else 999.0

            # スコア計算
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎', 'レーン']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村', '鮫島']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    return horses, title

def send_to_discord(horses, title, d, p, r):
    if not horses or len(horses) < 3:
        print("❌ データ不足")
        return

    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI予想 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 解析成功！",
            "color": 16753920,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}** ({top.iloc[0]['jockey']})", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "🔥 紐候補", "value": f"{n[3]}, {n[4]}, {n[5]}", "inline": False},
                {"name": "💰 3連単(本命1頭軸FM)", "value": f"1着: {n[0]}\n2着: {n[1]}, {n[2]}\n3着: {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    # 引数: 日付(20260222) 場所(東京) レース(11)
    d, p, r = (sys.argv[1], sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("20260222", "東京", "11")
    
    rid = find_race_id(d, p, r)
    if rid:
        h_list, r_title = get_keiba_data(rid)
        send_to_discord(h_list, r_title, d, p, r)
        print("✅ 完了！")
    else:
        print("❌ IDが見つかりません。日付などを確認してください。")

