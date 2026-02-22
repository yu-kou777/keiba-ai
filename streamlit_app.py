import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：馬連・完全版", layout="wide")

# --- 1. 超堅牢解析エンジン（読み込みエラー対策） ---
def ultra_robust_parse(text):
    # 改行や空白で分割し、空要素を除去
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    i = 0
    while i < len(tokens):
        # 馬番(1-18)を探す。「1レアレスト」のような開始も想定
        token = tokens[i]
        match_no = re.match(r'^([1-9]|1[0-8])([ァ-ヶー]{2,9})?$', token)
        
        if match_no:
            b_no = match_no.group(1)
            b_name = match_no.group(2) if match_no.group(2) else ""
            b_odds = 0.0
            margins = []
            up_rank = 5
            
            # この馬番の後の範囲(次の馬番が出るまで)を探索
            j = i + 1
            while j < len(tokens) and j < i + 50:
                # 次の馬番(単独)が出たら終了
                if re.match(r'^([1-9]|1[0-8])$', tokens[j]) and not re.match(r'^\d+\.\d$', tokens[j]):
                    break
                
                t = tokens[j]
                # 馬名が未取得なら取得
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', t) and t not in ["オッズ", "タイム", "ペース"]:
                    b_name = t
                # オッズ (数値.数値)
                elif re.match(r'^\d{1,3}\.\d$', t):
                    b_odds = float(t)
                # 着差 (-0.4, +0.9など)
                elif re.match(r'^[-+]\d\.\d$', t):
                    margins.append(float(t))
                # 上がり順位
                if any(k in t for k in ["①", "②", "③", "上り1", "上り2", "上り3"]):
                    up_rank = 1
                j += 1
            
            if b_name and b_odds > 0:
                min_m = min(margins) if margins else 1.0
                extracted.append({
                    "馬番": int(b_no), "馬名": b_name, "オッズ": b_odds,
                    "上り1_3位": up_rank, "最小着差": min_m
                })
            i = j - 1
        i += 1
    
    df = pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])
    if not df.empty:
        # オッズ順に並べて人気順を確定
        df = df.sort_values("オッズ").reset_index(drop=True)
        df["人気"] = df.index + 1
    return df

# --- 2. 2番〜5番人気・相手強化ロジック ---
def apply_opponent_logic(df):
    if df.empty: return df
    
    def score_calculation(row):
        # 基礎点は実績(数値)のみから算出
        score = 50.0
        # ① 実績：0.4s / 0.9s ルール
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 20
        # ② 実績：上がり
        if row['上り1_3位'] == 1: score += 20
        # ③ 戦略：2〜5番人気の評価を強制底上げ（相手候補として）
        if 2 <= row['人気'] <= 5:
            score += 35 
            
        return score

    df["連対期待スコア"] = df.apply(score_calculation, axis=1)
    # スコア（的中確率）順にソート
    return df.sort_values("連対期待スコア", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 AI競馬：馬連・2nd列強化（超堅牢版）")

if "input_key" not in st.session_state: st.session_state.input_key = 0
if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.input_key += 1
    st.rerun()

st.info("💡 読み込み精度を極限まで高めました。競馬ラボの『ウェブ新聞』等を全選択コピーして貼り付けてください。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.input_key}")

if st.button("🚀 最新ロジックで予想を実行"):
    if raw_input:
        df = ultra_robust_parse(raw_input)
        if not df.empty:
            df = apply_opponent_logic(df)
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 連対期待度ランキング")
                # 人気順と着差を一覧表示
                st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', '最小着差', '連対期待スコア']])
            
            with col2:
                st.subheader("AI評価印")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]})")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
                st.write(f"△ **{df.iloc[3]['馬名']}** ({h[3]})")

            st.divider()
            st.subheader("🎯 馬連・推奨買い目")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【本線流し】**\n\n**{h[0]}** ― {h[1]}, {h[2]}, {h[3]}, {h[4]} (4点)")
                st.caption("実績最上位から、2〜5番人気の有力馬へ。")
            with c2:
                # 2-5番人気の中で上位評価の馬をBOX
                fav_2_5 = df[df['人気'].between(2, 5)]['馬番'].tolist()
                st.warning(f"**【2-5番人気厚め：BOX】**\n\n**{', '.join(map(str, sorted(list(set(h[:2] + fav_2_5[:2])))))}**")
                st.caption("2番〜5番人気が相手に絡む確率を最大化した構成です。")
        else:
            st.error("データを読み取れませんでした。馬番・馬名・オッズが含まれるようにコピーしてください。")
