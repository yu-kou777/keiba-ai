import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="AI競馬予想・分析", layout="centered")

# --- ロジック：スコアリング設定 ---
# あなたのエクセル（種牡馬50など）の傾向を反映
TOP_SIRES = ["キズナ", "ロードカナロア", "エピファネイア", "ドゥラメンテ"] # 例

def calculate_ai_score(row):
    """
    エクセルのロジックをPythonで再現
    """
    score = 50 # 基準点
    
    # 1. オッズによる期待値補正
    if row['オッズ'] > 3.0 and row['オッズ'] < 15.0:
        score += 10 # 割安ゾーン
    
    # 2. 血統評価（仮の実装）
    # 実際にはCSVから読み込んだリストと照合します
    for sire in TOP_SIRES:
        if sire in str(row['馬名']): # 簡易的に名前で判定（本番は血統データと照合）
            score += 15
            
    return score

def get_full_analysis(race_id):
    """
    競馬ラボからデータを抜き、独自ロジックで評価する
    """
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 馬名とオッズの抽出
        horse_links = soup.find_all("a", href=re.compile(r"/db/horse/\d+/"))
        odds_elements = soup.select(".odds_tan, .odds")
        
        names = [link.text.strip() for link in horse_links if link.text.strip()][:16]
        odds = [opt.text.strip() for opt in odds_elements if opt.text.strip()][:16]
        
        df = pd.DataFrame({"馬名": names, "オッズ": odds})
        df["オッズ"] = pd.to_numeric(df["オッズ"], errors='coerce')
        
        # --- 最新ロジック適用 ---
        df["AIスコア"] = df.apply(calculate_ai_score, axis=1)
        # 期待値 = (AIスコア / 基準点) / オッズ ※簡易式
        df["期待値"] = (df["AIスコア"] / 50) * (10 / df["オッズ"]) # 独自ロジック
        
        return df.sort_values("期待値", ascending=False)
    except:
        return None

# --- UI部分 ---
st.title("🏇 AI競馬予想：ロジック統合版")

race_id = st.text_input("レースID (例: 202602070811)", "202602070811")

if st.button("AI予想を実行"):
    df_result = get_full_analysis(race_id)
    if df_result is not None:
        st.success("分析完了！")
        
        # 的中率管理のイメージ
        st.subheader("🎯 推奨買い目（期待値順）")
        st.dataframe(df_result[['馬名', 'オッズ', 'AIスコア', '期待値']].style.highlight_max(axis=0, subset=['期待値']))
        
        # 券種別アドバイス
        st.info("💡 馬連：上位3頭ボックス / 3連単：上位頭を1軸に設定")
    else:
        st.error("データの取得に失敗しました。")
