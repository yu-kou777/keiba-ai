import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get_time_diff_score(horse_url):
    """馬の個別ページから過去3走のタイム差を取得してスコア化する"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # 1秒待機（マナー＆ブロック防止）
        time.sleep(0.5)
        res = requests.get("https://www.keibalab.jp" + horse_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 過去成績テーブルの「タイム差」列を探す
        rows = soup.select('table.db-horse-table tbody tr')
        diffs = []
        for row in rows[:3]: # 直近3走
            tds = row.find_all('td')
            if len(tds) > 13:
                txt = tds[13].text.strip() # 競馬ラボの個別馬ページでは通常14列目がタイム差
                # 「-0.1」や「0.5」などの数値を抽出
                match = re.search(r'(-?\d+\.\d+)', txt)
                if match:
                    diffs.append(float(match.group(1)))
        
        if not diffs: return 0
        
        # スコア計算：0.0秒（1着）に近いほど高得点。1.0秒以上離されると加点なし。
        # 直近のレースほど重みを大きくする（テクニカル分析の移動平均的な考え方）
        weights = [1.0, 0.7, 0.5]
        total_time_score = 0
        for i, d in enumerate(diffs):
            # 負の値（1着で後続を突き放した場合）はさらに評価
            val = max(0, 1.5 - d) 
            total_time_score += (val * 10) * weights[i]
            
        return total_time_score
    except:
        return 0

def get_lab_data(date_str, place_name, race_num):
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    base_url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"🚀 タイム差分析を開始します（これには少し時間がかかります）...")
        res = requests.get(base_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        title = soup.select_one('h1.raceTitle').text.strip().replace('\n', ' ') if soup.select_one('h1.raceTitle') else "解析中"
        
        horses, seen_num = [], set()
        rows = soup.find_all('tr')
        
        # 抽出対象を絞り込んで巡回
        for row in rows:
            name_tag = row.select_one('a[href*="/db/horse/"]')
            if not name_tag: continue
            
            tds = row.find_all('td')
            if len(tds) < 4: continue
            
            try:
                name = name_tag.text.strip()
                horse_url = name_tag.get('href')
                
                # 馬番特定
                td_list = list(tds)
                name_td = name_tag.find_parent('td')
                name_idx = td_list.index(name_td)
                umaban = re.sub(r'\D', '', td_list[name_idx - 1].text.strip())
                
                if not umaban or umaban in seen_num: continue
                seen_num.add(umaban)

                jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else "不明"
                
                # 1. タイム差スコアの取得（過去3走）
                print(f"  🔍 {umaban}番 {name} の過去3走を分析中...")
                time_score = get_time_diff_score(horse_url)

                # 2. オッズ期待値（サブ要素）
                odds = 999.0
                o_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
                if o_match: odds = float(o_match.group(1))
                
                # 3. 総合判定：タイム差スコアを主軸にする
                # タイム差が良い ＋ 騎手が一流 ＝ 鉄板
                total_score = time_score
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']): total_score += 15
                
                horses.append({
                    "num": int(umaban), "name": name, "jockey": jockey, 
                    "odds": odds, "score": total_score, "time_val": time_score
                })
            except: continue
            
        return horses, title
    except Exception as e:
        print(f"❌ エラー: {e}")
        return [], "エラー"

def send_discord(horses, title, d, p, r):
    if len(horses) < 3: return
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    top = df.head(6)
    n = top['num'].tolist()
    
    payload = {
        "username": "ゆーこうAI (テクニカル分析) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | 過去3走タイム差ベース解析",
            "color": 15277667,
            "fields": [
                {"name": "🥇 ◎ 本命", "value": f"**{n[0]}番 {top.iloc[0]['name']}**\n(近3走の安定度が高い馬)", "inline": False},
                {"name": "🥈 〇 対抗", "value": f"**{n[1]}番**", "inline": True},
                {"name": "🥉 ▲ 単穴", "value": f"**{n[2]}番**", "inline": True},
                {"name": "📈 解析の根拠", "value": f"1着とのタイム差が少ない馬を上位評価しました。\n本命馬のタイム評価点: {top.iloc[0]['time_val']:.1f}", "inline": False},
                {"name": "💰 AI推奨", "value": f"3連複 軸1頭流し: {n[0]} - {n[1]}, {n[2]}, {n[3]}, {n[4]}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_URL, json=payload)
    print("✅ 全頭の過去3走チェック完了。Discordへ送信しました。")

if __name__ == "__main__":
    args = sys.argv
    date = args[1] if len(args) > 1 and args[1] != "" else "20260222"
    place = args[2] if len(args) > 2 and args[2] != "" else "東京"
    race = args[3] if len(args) > 3 else "11"
    
    h, t = get_lab_data(date, place, race)
    send_discord(h, t, date, place, race)
