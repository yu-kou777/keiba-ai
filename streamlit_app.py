import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：馬連・相手強化モデル", layout="wide")

# --- 1. 深層数値解析エンジン（オッズ評価を排除し、順位のみ利用） ---
def deep_analyze_engine(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    
    for i in range(len(lines)):
        if re.match(r'^([1-9]|1[0-8])$', lines[i]):
            b_no = lines[i]
            b_name, b_odds = "", 0.0
            margins = []      
            rank_3f = 5       
            
            for j in range(i + 1, min(i + 45, len(lines))):
                l = lines[j]
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', l): b_name = l
                elif re.match(r'^\d{1,3}\.\d$', l): b_odds = float(l)
                if any(k in l for k in ["①", "②", "③", "上り1", "上り2", "上り3"]): rank_3f = 1
                m_match = re.findall(r'([-+]\d\.\d)', l)
                if m_match: margins.extend([float(m) for m in m_match])

            if b_name and b_odds > 0:
                min_m = min(margins) if margins else 1.0
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "オッズ": b_odds,
                    "上り1_3位": rank_3f, "最小着差": min_m
                })
    
    df = pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])
    if not df.empty:
        # オッズ順に並べて「人気順」を付与
        df = df.sort_values("オッズ").reset_index(drop=True)
        df["人気"] = df.index + 1
    return df

# --- 2. 2番〜5番人気・強化ロジック ---
def apply_opponent_logic(df):
    if df.empty: return df
    
    def score_calculation(row):
        # 基礎点は実績のみから算出
        score = 50.0
        
        # ① 着差判定（0.4s / 0.9s ルール）- 数値評価の核
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 20
        
        # ② 上がり3F実績
        if row['上り1_3位'] == 1: score += 20

        # ③ 【重要】2番〜5番人気への加点（2列目候補の強化）
        # 1番人気の盲信はせず、2〜5番人気を「相手」として強力に拾う
        if 2 <= row['人気'] <= 5:
            score += 30  # 相手候補としての評価を底上げ
            
        return score

    df["連対期待スコア"] = df.apply(score_calculation, axis=1)
    # 最終的な期待値は「実績スコア」をベースに算出
    return df.sort_values("連対期待スコア", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 AI競馬：馬連・2列目（相手）強化モデル")

if "input_key" not in st.session_state: st.session_state.input_key = 0
if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.input_key += 1
    st.rerun()

st.info("💡 2番〜5番人気の実力馬を相手候補として強力に評価するロジックです。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.input_key}")

if st.button("🚀 2列目強化ロジックで予想実行"):
    if raw_input:
        df = deep_analyze_engine(raw_input)
        if not df.empty:
            df = apply_opponent_logic(df)
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 連対期待度（実績＋人気補正）")
                # 2-5番人気を視覚化
                st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', '最小着差', '連対期待スコア']].head(10))
            
            with col2:
                st.subheader("AI評価印")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]})")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
                st.write(f"△ **{df.iloc[3]['馬名']}** ({h[3]})")

            st.divider()
            st.subheader("🎯 馬連・推奨フォーメーション")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【軸1頭流し】**\n\n**{h[0]}** ― {h[1]}, {h[2]}, {h[3]}, {h[4]} (4点)")
                st.caption("実績最上位から、2〜5番人気を含む有力馬へ。")
            with c2:
                # 2-5番人気の中で、まだ上位にいない馬をピックアップ
                sub_opponents = df[df['人気'].between(2, 5)]['馬番'].tolist()
                st.warning(f"**【2列目厚め：BOX】**\n\n**{', '.join(h[:3])}, {', '.join([x for x in sub_opponents if x not in h[:3]][:1])}**")
                st.caption("2番〜5番人気を確実に網羅する馬連BOX。")
        else:
            st.error("データを抽出できませんでした。")
