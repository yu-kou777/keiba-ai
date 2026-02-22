import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random

st.set_page_config(page_title="AI競馬予想", layout="wide")

# --- 1. 最新の種牡馬ランキングをnetkeibaから取得 ---
@st.cache_data(ttl=86400) # 1日1回だけ実行して負荷を抑える
def get_latest_sires():
    url = "https://db.netkeiba.com/?pid=sire_leading"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # サイトに負荷をかけないよう少し待機
        time.sleep(2)
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.content, "html.parser")
        # テーブルから馬名を抽出（上位50頭）
        rows = soup.select(".nk_tb_common tr")[1:51]
        return [row.find_all("td")[1].text.strip() for row in rows]
    except:
        return ["キズナ", "エピファネイア", "ロードカナロア"] # 失敗時のバックアップ

# --- 2. 競馬ラボからレース詳細（父・母父含む）を取得 ---
def get_detailed_data(race_id):
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(2)
        res = requests.get(url, headers=headers)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 馬名、父名、オッズを抽出
        rows = soup.select(".table_01 tr")[1:]
        data = []
        for row in rows:
            tds = row.find_all("td")
            if len(tds) > 12:
                name = tds[3].text.strip()
                # 血統情報は改行されて入っていることが多いので分割
                blood = tds[4].text.strip().split('\n')
                sire = blood[0].replace('　', '').strip()
                bms = blood[1].replace('　', '').strip() if len(blood) > 1 else ""
                odds = tds[12].text.strip()
                data.append({"馬名": name, "父": sire, "母父": bms, "オッズ": odds})
        return pd.DataFrame(data)
    except:
        return None

# --- メイン画面 ---
st.title("🏇 AI競馬予想：血統・期待値モデル")

# 最新ランキングの準備
top_sires = get_latest_sires()

race_id = st.text_input("レースID (YYYYMMDD + 場所ID + レース)", "202602070811")

if st.button("AI予想を実行"):
    with st.spinner("最新データをスキャン中..."):
        df = get_detailed_data(race_id)
        
        if df is not None:
            # 型変換
            df["オッズ"] = pd.to_numeric(df["オッズ"], errors='coerce')
            
            # --- ロジック適用：AIスコアリング ---
            def scoring(row):
                score = 50 # 基準点
                # 血統加点：最新TOP50にいれば+20点
                if row['父'] in top_sires: score += 20
                # BMS(母父)加点（簡易版）
                if "ディープインパクト" in row['母父']: score += 10
                return score

            df["AIスコア"] = df.apply(scoring, axis=1)
            # 期待値 = (スコア/基準) / (オッズ/平均)
            df["期待値"] = (df["AIスコア"] / 50) * (10 / df["オッズ"])
            
            # 結果表示
            st.success("分析が完了しました！")
            res_df = df.sort_values("期待値", ascending=False)
            
            # スマホで見やすく表示
            st.subheader("📊 期待値ランキング")
            st.dataframe(res_df.style.highlight_max(subset=['期待値'], color='#ffaa00'))
            
            # 買い目提案
            top3 = res_df.head(3)['馬名'].tolist()
            st.warning(f"🎯 【推奨】 {top3[0]} を軸にした馬連・ワイド")
        else:
            st.error("データが空です。IDを再確認してください。")
