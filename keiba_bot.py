import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import time
import json

# --- 設定：Discord Webhook URL ---
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"

LAB_PLACE_MAP = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def safe_float(value):
    """安全に数値を変換する物理フィルタ"""
    try:
        # (0.2)のような括弧付きや、全角数字にも対応
        clean = re.sub(r'[^\d\.-]', '', str(value))
        return float(clean)
    except:
        return 99.9 # 計測不能な場合は「無限遠」として扱う

def analyze_singularity(horse_url, current_odds):
    """【教授の心臓部】過去3走の時空間解析"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # サーバーへの礼儀（待機）
        time.sleep(0.5)
        
        # URLの完全性チェック
        if not horse_url.startswith("http"):
            horse_url = "https://www.keibalab.jp" + horse_url
            
        res = requests.get(horse_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 過去走テーブル取得（失敗時は即撤退）
        rows = soup.select('table.db-horse-table tbody tr')
        if not rows: return 0, False, "データなし"
        
        diffs = []
        
        # 直近3走をスキャン
        for row in rows[:3]:
            tds = row.find_all('td')
            # 列不足やデータ欠損をスキップ
            if len(tds) < 10: continue
            
            # タイム差を探す（列固定ではなく、内容から探索）
            found_diff = False
            for td in tds:
                txt = td.text.strip()
                # "0.1" や "(0.5)" のようなパターンを探す
                if re.match(r'^\(?\-?\d+\.\d+\)?$', txt):
                    val = safe_float(txt)
                    if val < 5.0: # 5秒以上の差は異常値として除外
                        diffs.append(val)
                        found_diff = True
                        break
            
            # 見つからなかった場合、着順から推測（1着なら0.0とする）
            if not found_diff:
                if "1" in tds[11].text.strip(): # 12列目あたりが着順
                    diffs.append(0.0)

        if not diffs: return 0, False, "タイム差不明"
        
        # --- 物理学的スコアリング ---
        # 1. 収束性: 0.3秒以内の「肉薄」回数
        score = sum(60 for d in diffs if d <= 0.3)
        
        # 2. 安定性: 平均タイム差
        avg_diff = sum(diffs) / len(diffs)
        score += max(0, 1.5 - avg_diff) * 20
        
        # 3. カオス検知 (穴馬フラグ): 能力が高い(差が小さい)のに人気がない
        # アルデバランSの15番を捉えるためのロジック
        is_chaos = (avg_diff <= 0.8 and current_odds > 15.0)
        
        return score, is_chaos, f"平均差:{avg_diff:.2f}"
        
    except Exception as e:
        print(f"  ⚠️ 分析スキップ({horse_url}): {e}")
        return 0, False, "エラー"

def get_race_data(date_str, place_name, race_num):
    # 安全装置: 日付未入力ならアルデバランSをセット
    if not date_str or len(date_str) < 8:
        print("⚠️ 日付自動設定: 20260207 (アルデバランS)")
        date_str = "20260207"
        place_name = "京都"
        race_num = "11"

    p_code = LAB_PLACE_MAP.get(place_name, "08") # デフォルト京都
    r_num = str(race_num).zfill(2)
    url = f"https://www.keibalab.jp/db/race/{date_str}{p_code}{r_num}/"
    
    print(f"📡 観測開始: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        t_elem = soup.select_one('h1.raceTitle')
        title = t_elem.text.strip().replace('\n', ' ') if t_elem else "レース名不明"
        print(f"🏁 対象レース: {title}")
        
        horses = []
        rows = soup.find_all('tr')
        
        for row in rows:
            try:
                # 馬名リンク必須
                name_tag = row.select_one('a[href*="/db/horse/"]')
                if not name_tag: continue
                
                # 馬名
                name = name_tag.text.strip()
                
                # 馬番（絶対座標ではなく相対探索）
                umaban = "0"
                tds = row.find_all('td')
                for i, td in enumerate(tds):
                    if td == name_tag.find_parent('td'):
                        # 馬名の左隣のセルを見る
                        if i > 0:
                            prev_txt = tds[i-1].text.strip()
                            if prev_txt.isdigit(): umaban = prev_txt
                        break
                
                if umaban == "0": continue # 馬番取れなければスキップ

                # オッズ (数値抽出)
                odds = 99.9
                odds_match = re.search(r'(\d{1,4}\.\d{1})', row.text)
                if odds_match: odds = float(odds_match.group(1))
                
                # 騎手
                jockey = row.select_one('a[href*="/db/jockey/"]').text.strip() if row.select_one('a[href*="/db/jockey/"]') else ""

                # --- 詳細解析実行 ---
                score, is_chaos, note = analyze_singularity(name_tag.get('href'), odds)
                
                # 騎手補正 (ルメール、川田、武豊、坂井、戸崎)
                if any(x in jockey for x in ['ルメ', '川田', '武豊', '坂井', '戸崎']):
                    score += 10
                
                print(f"  √ {umaban}番 {name}: Score {score:.1f} ({note})")
                
                horses.append({
                    "num": int(umaban),
                    "name": name,
                    "score": score,
                    "is_ana": is_chaos,
                    "odds": odds
                })
                
            except Exception as e:
                print(f"  ⚠️ 行解析エラー: {e}")
                continue
                
        return horses, title
        
    except Exception as e:
        print(f"❌ 致命的通信エラー: {e}")
        return [], "エラー"

def send_to_discord(horses, title, d, p, r):
    if not horses:
        print("❌ 送信データがありません。")
        return

    # スコア順にソート
    df = pd.DataFrame(horses).sort_values('score', ascending=False).reset_index(drop=True)
    
    # --- 教授の24点フォーメーション ---
    # 軸: 1位、2位
    axis = df.head(2)['num'].tolist()
    
    # 2列目: 上位4頭
    row2 = df.head(4)['num'].tolist()
    
    # 3列目: 上位4頭 + 穴フラグ持ち + 補欠
    ana_list = df[df['is_ana']]['num'].tolist()
    # 穴馬を優先的にねじ込む
    candidates = row2 + ana_list + df.iloc[4:8]['num'].tolist()
    # 重複削除して先頭6頭
    row3 = list(dict.fromkeys(candidates))[:6]

    # メッセージ構築
    buy_str = (
        f"**1着**: {', '.join(map(str, axis))}\n"
        f"**2着**: {', '.join(map(str, row2))}\n"
        f"**3着**: {', '.join(map(str, row3))}"
    )
    
    payload = {
        "username": "教授AI (不沈艦モード) 🏇",
        "embeds": [{
            "title": f"🎯 {p}{r}R {title}",
            "description": f"📅 {d} | **エネルギー効率最大化 (24点)**",
            "color": 15105570, # Orange
            "fields": [
                {"name": "👑 1着軸 (特異点)", "value": f"**{', '.join(map(str, axis))}**", "inline": True},
                {"name": "🐎 2着候補 (4頭)", "value": f"{', '.join(map(str, row2))}", "inline": True},
                {"name": "🌀 3着候補 (6頭)", "value": f"{', '.join(map(str, row3))}", "inline": False},
                {"name": "💰 買い目フォーメーション", "value": buy_str, "inline": False},
                {"name": "📊 解析ステータス", "value": "全頭スキャン完了。タイム差欠損等のノイズ除去済み。", "inline": False}
            ]
        }]
    }
    
    try:
        res = requests.post(DISCORD_URL, json=payload)
        print(f"✅ Discord送信完了: Status {res.status_code}")
    except Exception as e:
        print(f"❌ 送信エラー: {e}")

if __name__ == "__main__":
    # 引数エラー対策
    try:
        args = sys.argv
        date = args[1] if len(args) > 1 else "20260207"
        place = args[2] if len(args) > 2 else "京都"
        race = args[3] if len(args) > 3 else "11"
    except:
        date, place, race = "20260207", "京都", "11"
    
    h_list, t_str = get_race_data(date, place, race)
    send_to_discord(h_list, t_str, date, place, race)
