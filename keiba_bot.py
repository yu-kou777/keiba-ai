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
    
    title = soup.find('title').text.split('｜')[0] if soup.find('title') else "予想結果"
    
    # 【改良点】特定のテーブルクラスに頼らず、すべての「行(tr)」を走査する
    all_rows = soup.find_all('tr')
    
    horses, seen = [], set()
    for row in all_rows:
        try:
            # 馬名のリンクがある行だけをターゲットにする
            name_tag = row.select_one('a[href*="/horse/"]')
            if not name_tag: continue
            
            name = name_tag.text.strip()
            if not name: continue

            # 馬番を探す (行の中にある数字だけのセルを探す)
            umaban = ""
            tds = row.find_all('td')
            for td in tds:
                txt = td.text.strip()
                # 1〜18の数字で、かつ「枠」の数字（色付きなど）と区別するため
                # クラス名なども考慮したいが、単純に「最初の数字」が枠、次が馬番のケースが多い
                # ここでは「td.Umaban」クラスがあればそれを、なければ「3番目のセル(結果ページ)」を採用
                if "Umaban" in td.get("class", []):
                    umaban = txt
                    break
            
            # クラスで見つからなかった場合（結果ページなど）、位置で推定
            if not umaban and len(tds) > 2:
                # 結果ページは通常インデックス2が馬番
                txt = tds[2].text.strip()
                if txt.isdigit(): umaban = txt
            
            # まだなければ、行内の最初の「1桁か2桁の数字」を採用（最終手段）
            if not umaban:
                for td in tds:
                    t = td.text.strip()
                    if t.isdigit() and 1 <= int(t) <= 18:
                        umaban = t
                        break

            if not umaban or umaban in seen: continue
            seen.add(umaban)

            # 騎手
            jockey = "不明"
            j_tag = row.select_one('a[href*="/jockey/"]')
            if j_tag: jockey = j_tag.text.strip()

            # オッズ（行全体から小数点を検索）
            odds = 999.0
            # 馬番や着順を誤検知しないよう、"xx.x" の形式を探す
            o_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
            if o_match:
                odds = float(o_match.group(1))

            # スコア計算
            score = (100 / odds) * 1.5 if odds < 900 else 5
            if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): score += 15
            elif any(x in jockey for x in ['松山', '横山武', '西村']): score += 8

            horses.append({"num": int(umaban), "name": name, "jockey": jockey, "score": score})
        except: continue
    
    return horses, title

def send_discord(horses, title, d, p, r):
    if not horses:
        print("❌ エラー: 馬が見つかりません（0件）")
        return
    
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    # 3連単フォーメーション
    himo = []
    if len(n) >= 5: himo = [n[1], n[2], n[3], n[4]]
    else: himo = n[1:] # 馬が少ない場合
    
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
    else:
        print("❌ レースが見つかりませんでした")
