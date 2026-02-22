import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：的中率重視・馬連モデル", layout="wide")

# --- 1. データ解析・調教判定エンジン ---
def parse_for_victory(text):
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    race_info = "不明なレース"
    match_r = re.search(r'(\d{1,2}R)', text)
    if match_r:
        for line in text.split('\n'):
            if match_r.group(1) in line:
                race_info = line.strip()
                break

    for i in range(len(tokens)):
        # 馬番(1-18)の判定。周辺の文脈から馬番であることを補強
        if re.match(r'^([1-9]|1[0-8])$', tokens[i]):
            baban = tokens[i]
            name, sire, odds, training = "", "", 0.0, "B" # デフォルトをBに
            
            for j in range(i + 1, min(i + 25, len(tokens))):
                t = tokens[j]
                if not name and re.match(r'^[ァ-ヶー]{2,9}$', t): name = t
                elif name and not sire and re.match(r'^[ァ-ヶー]{2,10}$', t): sire = t
                elif re.match(r'^\d{1,3}\.\d$', t):
                    odds = float(t)
                    break
                # 調教キーワード
                if any(k in t for k in ["A", "S", "◎", "絶好", "良"]): training = "A"

            if name and odds > 0:
                extracted.append({
                    "馬番": baban, "馬名": name, "父": sire, 
                    "オッズ": odds, "調教": training
                })
    return race_info, pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 2. 的中率最大化ロジック ---
def apply_winning_logic(df):
    def score_row(row):
        # 的中率のベーススコア
        score = 50.0
        
        # 人気馬（2番人気など）への加点：オッズ5.0倍以下なら無条件に信頼度アップ
        if row['オッズ'] <= 5.0:
            score += 30
        elif row['オッズ'] <= 10.0:
            score += 15
            
        # 調教加点
        if row['調教'] == "A": score += 20
        
        # 期待値計算
        return (score / 50) * (12 / row['オッズ'])

    df["期待値"] = df.apply(score_row, axis=1)
    return df.sort_values("期待値", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 AI競馬：馬連・的中優先モデル")

# セッション状態の初期化
if "input_text" not in st.session_state:
    st.session_state.input_text = ""

# サイドバー：クリアボタン（確実に消去）
if st.sidebar.button("🗑️ 入力データをクリア"):
    st.session_state.input_text = ""
    st.rerun()

st.info("💡 競馬ラボの出馬表を貼り付けてください。クリアボタンは左側にあります。")

# valueにsession_stateを紐付け
raw_input = st.text_area("コピペエリア", value=st.session_state.input_text, height=300, key="main_input")

# 入力内容をsession_stateに保存（rerun時に消えないように）
st.session_state.input_text = raw_input

if st.button("🚀 最新ロジックで予想"):
    if raw_input:
        race_info, df = parse_for_victory(raw_input)
        if not df.empty:
            df = apply_winning_logic(df)
            
            st.subheader(f"📅 解析：{race_info}")
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 馬連・有力馬ランキング")
                st.dataframe(df[['馬番', '馬名', 'オッズ', '調教', '期待値']].style.highlight_max(axis=0, subset=['期待値']))
            
            with col2:
                st.subheader("AI推奨印（馬連軸）")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 的中率1位")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            st.divider()
            st.subheader("🎯 的中重視の馬連買い目")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【プランA：本線】**\n\n**{h[0]}** ― {', '.join(h[1:5])} (4点)")
                st.caption("最も信頼度の高い軸から、実力上位へ流します。")
            with c2:
                st.warning(f"**【プランB：厚め】**\n\n**{h[0]}, {h[1]}** ― {h[0]}, {h[1]}, {h[2]}, {h[3]} (5点)")
                st.caption("2番人気(6番など)もカバーした、上位混戦用のフォーメーション。")
        else:
            st.error("データを読み取れませんでした。馬番・馬名・オッズが含まれているか確認してください。")
