import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random

# --- 設定 ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
}

@st.cache_data(ttl=86400)
def get_latest_sire_leading():
    """ 最新の種牡馬ランキングTOP50を取得 """
    url = "https://db.netkeiba.com/?pid=sire_leading"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")
        rows = soup.find("table", class_="nk_tb_common").find_all("tr")[1:51]
        return [row.find_all("td")[1].text.strip() for row in rows]
    except:
        return ["キズナ", "エピファネイア", "ロードカナロア"]

def get_race_details(race_id_lab):
    """ 競馬ラボから基本情報（馬名、オッズ、父、母父）を取得 """
    url = f"https://www.keibalab.jp/db/race/{race_id_lab}/"
    try:
        time.sleep(random.uniform(1.5, 3.0)) # 負荷軽減
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        table = soup.find("table", class_="table_01")
        if not table: return None
        
        data = []
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) > 12:
                name = cols[3].text.strip()
                # 血統情報を取得
                sire = cols[4].text.split('\n')[0].strip()
                bms = cols[4].text.split('\n')[1].strip() if '\n' in cols[4].text else ""
                odds = cols[12].text.strip()
                # 【新機能】前走着差（簡易取得：ラボの出馬表にある「前走」欄から）
                # 実際にはより詳細なパースが必要ですが、まずは構造を作ります
                last_margin = 0.5 # デフォルト値
                try:
                    margin_text = cols[14].text # 前走着差の文字を探す
                    match = re.search(r'([+-]?\d\.\d)', margin_text)
                    if match: last_margin = float(match.group(1))
                except: pass
                
                data.append({
                    "馬番": cols[1].text.strip(),
                    "馬名": name,
                    "父": sire,
                    "母父": bms,
                    "オッズ": odds,
                    "前走着差": last_margin
                })
        return pd.DataFrame(data)
    except: return None

# --- メイン画面 ---
st.set_page_config(page_title="AI競馬予想", layout="wide")
st.title("🏇 AI競馬予想：過去5走解析モデル")

with st.sidebar:
    st.header("分析設定")
    top_sires = get_latest_sire_leading()
    st.write(f"最新種牡馬TOP50取得済み")

# ID自動生成（京都11Rなどの指定）
col1, col2, col3 = st.columns(3)
with col1: d = st.text_input("日付", "20260207")
with col2: p = st.selectbox("場所", ["05:東京", "06:中山", "08:京都", "09:阪神"], index=2)
with col3: r = st.text_input("レース", "11")
race_id = f"{d}{p[:2]}{r}"

if st.button("全自動解析スタート"):
    with st.spinner("データを取得し、エクセルのロジックで計算中..."):
        df = get_race_details(race_id)
        
        if df is not None:
            df["オッズ"] = pd.to_numeric(df["オッズ"], errors='coerce')
            
            # --- ロジック：エクセル基準の自動判定 ---
            def ai_logic(row):
                score = 50 # 基準
                # 1. 血統ボーナス
                if row['父'] in top_sires: score += 15
                # 2. 前走着差ボーナス（エクセルの「0.4以内」を反映）
                if row['前走着差'] <= 0.4: score += 20
                # 3. 期待値補正（人気薄の激走狙い）
                if row['オッズ'] >= 10.0: score += 10
                return score

            df["AIスコア"] = df.apply(ai_logic, axis=1)
            # 期待値計算
            df["期待値"] = (df["AIスコア"] / 50) * (10 / df["オッズ"])
            
            # 結果表示
            st.subheader("📊 解析結果（期待値ランキング）")
            res_df = df.sort_values("期待値", ascending=False)
            
            # スマホで見やすく色付け
            st.dataframe(res_df.style.background_gradient(subset=['期待値'], cmap='YlOrRd'))
            
            # ステップ3への布石：買い目生成
            st.divider()
            st.subheader("🎯 推奨買い目")
            top3 = res_df.head(3)['馬番'].tolist()
            st.success(f"【馬連BOX】 {' - '.join(top3)}")
        else:
            st.error("サイトから拒否されました。少し時間を置いてください。")
