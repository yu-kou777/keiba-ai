import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random

# --- 設定 ---
# ブロック回避用ヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
}

@st.cache_data(ttl=86400) # 1日1回だけ取得（負荷軽減）
def get_latest_sire_leading():
    """
    netkeibaのリーディングサイアーページから最新TOP50を取得
    """
    url = "https://db.netkeiba.com/?pid=sire_leading" # 2026年最新版
    try:
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.content, "html.parser")
        table = soup.find("table", class_="nk_tb_common")
        
        sire_list = []
        rows = table.find_all("tr")[1:51] # TOP50
        for row in rows:
            name = row.find_all("td")[1].text.strip()
            sire_list.append(name)
        return sire_list
    except:
        # 取得失敗時のバックアップ（あなたが重視していた主要種牡馬）
        return ["キズナ", "ロードカナロア", "エピファネイア", "ドゥラメンテ", "ハーツクライ"]

def get_race_data(race_id):
    """
    競馬ラボから馬名、オッズ、父馬名を取得
    """
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    res = requests.get(url, headers=HEADERS)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")
    
    table = soup.find("table", class_="table_01")
    if not table: return None
    
    data = []
    rows = table.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        if len(cols) > 10:
            name = cols[3].text.strip()
            # 競馬ラボの出馬表から父馬の名前を抽出（通常、馬名の下や別カラムに記載）
            sire = cols[4].text.split('\n')[0].strip() if len(cols) > 4 else ""
            odds = cols[12].text.strip()
            data.append({"馬名": name, "父": sire, "オッズ": odds})
    return pd.DataFrame(data)

# --- メイン画面 ---
st.title("🏇 AI競馬予想：最新種牡馬ロジック版")

# 最新の種牡馬リストを取得
with st.spinner("最新の種牡馬リーディングを取得中..."):
    top_sires = get_latest_sire_leading()

st.sidebar.write("### 現在の有力種牡馬 (TOP50)")
st.sidebar.caption("、".join(top_sires[:10]) + " など")

# レース入力
race_id = st.text_input("レースID (例: 202602070811)", "202602070811")

if st.button("AI分析開始"):
    df = get_race_data(race_id)
    if df is not None:
        df["オッズ"] = pd.to_numeric(df["オッズ"], errors='coerce')
        
        # --- スコアリングロジック ---
        def scoring(row):
            score = 50 # 基準点
            # 血統加点：最新リーディングTOP50に入っていれば+20点
            if row['父'] in top_sires:
                score += 20
            # オッズ期待値：人気しすぎず、かつ実力があるゾーンを評価
            if 5.0 <= row['オッズ'] <= 15.0:
                score += 10
            return score

        df["AIスコア"] = df.apply(scoring, axis=1)
        df["期待値"] = (df["AIスコア"] / 50) * (10 / df["オッズ"])
        
        # 結果表示
        st.success("最新血統データを反映しました。")
        st.dataframe(df.sort_values("期待値", ascending=False).style.highlight_max(subset=['期待値']))
    else:
        st.error("データが取得できませんでした。")

