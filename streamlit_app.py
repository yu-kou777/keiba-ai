import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：馬連・資金増殖モデル", layout="wide")

# --- 1. レース名・情報の抽出ロジック ---
def extract_race_info(text):
    # 「○R」や「レース名」を特定
    race_name = "不明なレース"
    match_r = re.search(r'(\d{1,2}R)', text)
    if match_r:
        # レース番号の前後を含めて取得
        lines = text.split('\n')
        for line in lines:
            if match_r.group(1) in line:
                race_name = line.strip()
                break
    return race_name

# --- 2. 解析エンジン ---
def parse_for_umaren(text):
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    for i in range(len(tokens)):
        if re.match(r'^([1-9]|1[0-8])$', tokens[i]):
            baban = tokens[i]
            name, sire, odds = "", "", 0.0
            for j in range(i + 1, min(i + 25, len(tokens))):
                t = tokens[j]
                if not name and re.match(r'^[ァ-ヶー]{2,9}$', t): name = t
                elif name and not sire and re.match(r'^[ァ-ヶー]{2,10}$', t): sire = t
                elif re.match(r'^\d{1,3}\.\d$', t):
                    odds = float(t)
                    break
            if name and odds > 0:
                extracted.append({"馬番": baban, "馬名": name, "父": sire, "オッズ": odds})
    return pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- UI構築 ---
st.title("🏇 AI競馬：馬連特化エンジン")

# サイドバーにクリアボタンを設置（誤操作防止のため）
if st.sidebar.button("🗑️ 入力エリアをクリア"):
    st.session_state["input_content"] = ""
    st.rerun()

# 入力エリア（Session Stateを使用してクリア可能に）
if "input_content" not in st.session_state:
    st.session_state["input_content"] = ""

st.info("💡 競馬ラボの出馬表をコピーして貼り付けてください。")
raw_input = st.text_area("コピペエリア", value=st.session_state["input_content"], height=300, key="main_input")

if st.button("🚀 このレースを解析・予想"):
    if raw_input:
        # レース名を表示
        r_info = extract_race_info(raw_input)
        st.subheader(f"📅 解析対象：{r_info}")
        
        df = parse_for_umaren(raw_input)
        if not df.empty:
            # --- 馬連特化ロジック ---
            def calc_score(row):
                base = 60.0
                # 安定血統ボーナス
                stable_sires = ["キズナ", "エピファネイア", "ロードカナロア", "ドゥラメンテ", "ハーツクライ"]
                if any(s in str(row['父']) for s in stable_sires): base += 15
                # 5-15倍の「馬連で美味しい馬」を優先
                if 5.0 <= row['オッズ'] <= 15.0: base += 10
                return (base / 60) * (10 / row['オッズ'])

            df["期待値"] = df.apply(calc_score, axis=1)
            df = df.sort_values("期待値", ascending=False).reset_index(drop=True)

            # 解析結果の可視化
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 期待値ランキング")
                st.table(df[['馬番', '馬名', 'オッズ', '期待値']].head(10))
            
            with col2:
                st.subheader("AI評価印")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]})")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            # 買い目セクション
            st.divider()
            st.subheader("🎯 馬連・推奨買い目")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【軸1頭流し】**\n\n**{h[0]}** ― {', '.join(h[1:5])} (4点)")
            with c2:
                st.warning(f"**【BOX】**\n\n**{h[0]}, {h[1]}, {h[2]}, {h[3]}** (6点)")
                
            st.divider()
            st.subheader("💎 3連単フォーメーション（参考）")
            st.info(f"1着：{h[0]}, {h[1]} / 2着：{h[0]}, {h[1]}, {h[2]} / 3着：{h[0]}, {h[1]}, {h[2]}, {h[3]}")
        else:
            st.error("馬のデータを読み取れませんでした。")
    else:
        st.warning("データを入力してください。")

