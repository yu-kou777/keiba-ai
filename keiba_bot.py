import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def analyze_singularity(horse_url, odds):
    """過去3走のタイム差からエネルギー値を算出（エラー回避版）"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # サーバー負荷軽減のため待機
        time.sleep(0.5)
        res = requests.get("https://www.keibalab.jp" + horse_url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 過去走テーブルの取得（存在確認）
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, False
        
        diffs = []
        for row in rows[:3]:
            tds = row.find_all('td')
            # 列数が足りない場合はスキップ
            if len(tds) < 14: continue
            
            # タイム差の抽出（正規表現で数値のみ抜く）
            txt = tds[13].text.strip()
            m = re.search(r'(-?\d+\.\d+)', txt)
            if m: diffs.append(float(m.group(1)))
        
        if not diffs: return 0, False
        
        # --- 教授の特異点ロジック ---
        # 1. タイム差0.3秒以内の「凝縮」を高評価
        score = sum(50 for d in diffs if d <= 0.3)
        # 2. 0.6秒以内なら加点（安定性）
        score += sum(20 for d in diffs if 0.3 < d <= 0.6)
        
        # 3. 穴馬フラグ：能力があるのにオッズが高い（市場の歪み）
        is_ana = (min(diffs) <= 0.5 and odds > 15.0)
        
        return score, is_ana
    except Exception as e:
        print(f"  ⚠️ 詳細分析スキップ: {e}")
        return 0, False

def get_race_data(date_str, place_name, race_num):
    # 日付エラー防止
    if not date_str or len(date_str) < 8: date_str = "20260207"
    
    p_code = LAB_PLACE_MAP.get(place_name, "05")
    r_num = str(race_num).zfill(2)
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    
    print(f"📡 観測開始: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            print(f"❌ 接続失敗: Status {res.status_code}")
            return [], "接続エラー"
            
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        t_elem = soup.select_one('h1.raceTitle')
        title = t_elem.text.strip().replace('\n', ' ') if t_elem else "レース解析"
        
        horses = []
        rows = soup.find_all('tr')
        
        print(f"🔍 データ抽出中...")
        for row in rows:
            try:
                # 馬名リンクがある行のみ対象
                name_tag = row.select_one('a[href*="/db/horse/"]')
                if not name_tag: continue
                
                tds = row.find_all('td')
                if len(tds) < 5: continue
                
                name = name_tag.text.strip()
                horse_url = name_tag.get('href')
                
                # --- 馬番の堅牢な取得 ---
                # 馬名セルの「左隣」にある数字を探す（これが最も確実）
                umaban = "0"
                for i, td in enumerate(tds):
                    if td == name_tag.find_parent('td'):
                        if i > 0:
                            prev_text = tds[i-1].text.strip()
                            if prev_text.isdigit(): umaban = prev_text
                        break
                
                # オッズ取得（数値が含まれるセルを検索）
                odds = 999.0
                match_odds = re.search(r'(\d{1,4}\.\d{1})', row.text)
                if match_odds: odds = float(match_odds.group(1))
                
                # 騎手名
                jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else "不明"

                # 詳細分析へ
                score, is_ana = analyze_singularity(horse_url, odds)
                
                # 騎手ボーナス（ルメール、川田、武豊、坂井、戸崎）
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']):
                    score += 15
                
                horses.append({
                    "num": int(umaban),
                    "name": name,
                    "score": score,
                    "is_ana": is_ana,
                    "odds": odds
                })
                print(f"  √ {umaban}番 {name}: 解析完了 (Score: {score})")
                
            except Exception as e:
                # 1頭のエラーで全体を止めない
                continue
                
        return horses, title
    except Exception as e:
        print(f"❌ 重大エラー: {e}")
        return [], "エラー"

def send_to_discord(horses, title, d, p, r):
    if not horses:
        print("⚠️ 送信データがありません。")
        return

    # スコア順にソート
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # 軸（トップ2）
    axis = df.head(2)
    axis_nums = axis['num'].tolist()
    
    # 2列目（トップ3＋穴馬）
    row2_candidates = df.head(3)['num'].tolist()
    
    # 3列目（トップ5＋穴フラグ持ち）
    ana_list = df[df['is_ana']]['num'].tolist()
    row3_candidates = list(set(df.head(5)['num'].tolist() + ana_list))[:6] # 最大6頭
    
    # フォーマット作成
    msg_title = f"🎯 {p}{r}R {title}"
    axis_str = ", ".join(map(str, axis_nums))
    row2_str = ", ".join(map(str, row2_candidates))
    row3_str = ", ".join(map(str, row3_candidates))
    
    # 推奨買い目（1着-2着-3着）
    kai_me = f"1着: {axis_str}\n2着: {row2_str}\n3着: {row3_str}"
    
    payload = {
        "username": "教授AI (物理的3連単) 🏇",
        "embeds": [{
            "title": msg_title,
            "description": f"📅 {d} | **エネルギー効率最大化モデル**",
            "color": 3066993,
            "fields": [
                {"name": "👑 1着軸 (特異点)", "value": f"**{axis_str}**", "inline": True},
                {"name": "🐎 2列目 (イベント地平線)", "value": f"**{row2_str}**", "inline": True},
                {"name": "🌀 3列目 (カオス領域)", "value": f"{row3_str}", "inline": False},
                {"name": "💰 教授の推奨フォーメーション", "value": kai_me, "inline": False},
                {"name": "📈 解析サマリー", "value": "軸馬の2着・3着漏れをカバーしつつ、タイム差の収束（0.3秒以内）が見られる馬を2列目に厚く配置しました。", "inline": False}
            ]
        }]
    }
    
    try:
        res = requests.post(DISCORD_URL, json=payload)
        print(f"✅ Discord送信完了: {res.status_code}")
    except Exception as e:
        print(f"❌ Discord送信失敗: {e}")

if __name__ == "__main__":
    args = sys.argv
    # 引数がない場合はアルデバランSをデフォルトに
    date = args[1] if len(args) > 1 else "20260207"
    place = args[2] if len(args) > 2 else "京都"
    race = args[3] if len(args) > 3 else "11"
    
    h_list, t_str = get_race_data(date, place, race)
    send_to_discord(h_list, t_str, date, place, race)
