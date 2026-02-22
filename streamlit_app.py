import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="究極AI競馬：馬連・的中ロジック", layout="wide")

# --- 1. 内部ロジック定数（あなたのデータに基づく設定） ---
# 種牡馬50/BMS50の主要馬
TOP_BLOOD = ["キズナ", "ドゥラメンテ", "ロードカナロア", "エピファネイア", "ハーツクライ", "モーリス", "ルーラーシップ"]

# --- 2. 解析・判定エンジン ---
def analyze_with_logic(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    
    # 馬番を起点に情報を1セットにする
    for i in range(len(lines)):
        if re.match(r'^([1-9]|1[0-8])$', lines[i]):
            b_no = lines[i]
            b_name, b_odds, b_train, b_margin = "", 0.0, "B", 1.0
            b_sire = ""
            
            for j in range(i + 1, min(i + 20, len(lines))):
                l = lines[j]
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', l): b_name = l
                elif b_name and not b_sire and re.match(r'^[ァ-ヶー]{2,10}$', l): b_sire = l
                elif re.match(r'^\d{1,3}\.\d$', l): b_odds = float(l)
                # 着差の抽出
                margin_match = re.search(r'([-+]\d\.\d)', l)
                if margin_match: b_margin = float(margin_match.group(1))
                # 調教評価
                if any(k in l for k in ["A", "S", "◎", "絶好"]): b_train = "A"
            
            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "父": b_sire, 
                    "オッズ": b_odds, "調教": b_train, "前走着差": b_margin
                })
    return pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 3. 独自のスコアリングロジック (FT列 & 3並び再現) ---
def apply_custom_logic(df):
    def score_calculation(row):
        score = 50.0
        # ① 0.4秒ルール（最優先）
        if row['前走着差'] <= 0.4: score += 30
        
        # ② 種牡馬評価
        if any(s in str(row['父']) for s in TOP_BLOOD): score += 20
        
        # ③ 調教評価
        if row['調教'] == "A": score += 15
        
        # ④ FT列（激走サイン）: 人気薄(15倍〜)×血統 or 調教良
        if row['オッズ'] >= 15.0 and (row['調教'] == "A" or any(s in str(row['父']) for s in TOP_BLOOD)):
            score += 25
            
        # ⑤ 3並び（鉄板軸）補正: 人気・調教・着差が揃った場合
        if row['オッズ'] <= 5.0 and row['調教'] == "A" and row['前走着差'] <= 0.2:
            score += 40
            
        return score

    df["AIスコア"] = df.apply(score_calculation, axis=1)
    df["期待値"] = (df["AIスコア"] / 50) * (12 / df["オッズ"])
    return df.sort_values("期待値", ascending=False).reset_index(drop=True)

# --- UI ---
st.title("🏇 究極AI競馬：馬連・的中ブースト")

# クリアボタンの修正（session_stateとキーの変更）
if "input_key" not in st.session_state:
    st.session_state.input_key = 0

if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.input_key += 1
    st.rerun()

st.info("💡 競馬ラボの出馬表をコピーして貼り付けてください。馬連に特化した独自の期待値で分析します。")

# キーを動的に変えることで入力を確実にクリア
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.input_key}")

if st.button("🚀 このレースを解析・予想"):
    if raw_input:
        df = analyze_with_logic(raw_input)
        if not df.empty:
            df = apply_custom_logic(df)
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 解析：期待値ランキング")
                st.dataframe(df[['馬番', '馬名', 'オッズ', '調教', '前走着差', '期待値']])
            
            with col2:
                st.subheader("AI評価印")
                h = df["馬番"].tolist()
                # 3並びチェック
                is_3narabi = df.iloc[0]['AIスコア'] > 110
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) " + ("【鉄板軸】" if is_3narabi else ""))
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            st.divider()
            st.subheader("🎯 馬連・推奨買い目（的中重視）")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【軸1頭流し】**\n\n**{h[0]}** ― {h[1]}, {h[2]}, {h[3]}, {h[4]} (4点)")
                st.caption("鉄板軸から期待値上位への安定流し。")
            with c2:
                # FT列（激走馬）がいるかチェック
                gekisou = df[df['オッズ'] >= 15.0].head(2)
                if not gekisou.empty:
                    st.warning(f"**【激走注意！馬連】**\n\n**{h[0]}** ― {', '.join(gekisou['馬番'].tolist())}")
                    st.caption("FT列(激走サイン)が出ている穴馬への高配当狙い。")
                else:
                    st.warning(f"**【上位BOX】**\n\n{h[0]}, {h[1]}, {h[2]}, {h[3]} (6点)")
        else:
            st.error("データの読み取りに失敗しました。")
