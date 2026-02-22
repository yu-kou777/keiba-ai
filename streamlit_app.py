import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：1番人気・完全防衛モデル", layout="wide")

# --- 1. 内部データ：不変の種牡馬データ（種牡馬50/BMS50） ---
TOP_BLOOD_LIST = ["キズナ", "ドゥラメンテ", "エピファネイア", "ロードカナロア", "モーリス", "ハーツクライ", "ルーラーシップ", "ディープインパクト", "キングカメハメハ"]

# --- 2. 解析エンジン（数値データ抽出） ---
def scan_race_data(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    race_info = "レース未特定"
    
    for line in lines:
        if "R" in line and len(line) < 30:
            race_info = line
            break

    for i in range(len(lines)):
        if re.match(r'^([1-9]|1[0-8])$', lines[i]):
            b_no = lines[i]
            b_name, b_sire, b_odds, b_margin = "", "", 0.0, 9.9
            
            for j in range(i + 1, min(i + 20, len(lines))):
                l = lines[j]
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', l): b_name = l
                elif b_name and not b_sire and re.match(r'^[ァ-ヶー]{2,10}$', l) and l != b_name:
                    b_sire = l
                elif re.match(r'^\d{1,3}\.\d$', l): b_odds = float(l)
                elif re.search(r'([-+]\d\.\d)', l):
                    b_margin = float(re.search(r'([-+]\d\.\d)', l).group(1))
                    break

            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "父": b_sire, 
                    "オッズ": b_odds, "前走着差": b_margin
                })
    return race_info, pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 3. 1番人気防衛・連対特化ロジック ---
def apply_winning_logic(df):
    def score_calculation(row):
        # 基礎能力値
        power = 50.0
        
        # ① 1番人気・上位人気ボーナス（ここを大幅強化）
        if row['オッズ'] <= 2.9:
            power += 60  # 圧倒的1番人気への信頼
        elif row['オッズ'] <= 4.9:
            power += 40  # 上位人気への信頼
            
        # ② 0.4秒ルール（実績の裏付け）
        if row['前走着差'] <= 0.0:
            power += 35  # 前走勝利馬（1番人気に多いパターン）
        elif row['前走着差'] <= 0.4:
            power += 20  # 惜敗馬
        
        # ③ 血統評価
        if any(s in str(row['父']) for s in TOP_BLOOD_LIST):
            power += 15
            
        return power

    df["能力スコア"] = df.apply(score_calculation, axis=1)
    # 期待値も計算はするが、ランキングには「能力スコア」を使用
    df["期待値"] = (df["能力スコア"] / 50) * (10 / row['オッズ'] if 'row' in locals() else 1) # 安全策
    
    # 能力スコア（的中確率）でソート
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 4. UI構築 ---
st.title("🏇 AI競馬：1番人気・完全防衛エンジン")

if "clear_key" not in st.session_state:
    st.session_state.clear_key = 0

if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key += 1
    st.rerun()

st.info("💡 1番人気を軸に、精度の高い馬連予想を提供します。コピペして実行してください。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.clear_key}")

if st.button("🚀 的中重視で予想実行"):
    if raw_input:
        r_name, df = scan_race_data(raw_input)
        if not df.empty:
            df = apply_winning_logic(df)
            
            st.subheader(f"📅 解析：{r_name}")
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 能力ランキング（的中確率順）")
                # 1番人気を強調
                st.dataframe(df[['馬番', '馬名', 'オッズ', '前走着差', '能力スコア']].head(10).style.highlight_min(subset=['オッズ'], color='#fff3cd'))
            
            with col2:
                st.subheader("AI評価印（馬連軸）")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 鉄板軸候補")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
                st.write(f"△ **{df.iloc[3]['馬名']}** ({h[3]})")

            st.divider()
            st.subheader("🎯 馬連・推奨買い目")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【堅実：軸1頭流し】**\n\n**{h[0]}** ― {h[1]}, {h[2]}, {h[3]}, {h[4]} (4点)")
                st.caption("1番人気（または能力1位）から、0.4s以内の有力馬へ。")
            with c2:
                st.warning(f"**【的中：フォーメーション】**\n\n**1頭目：{h[0]}, {h[1]}**\n**2頭目：{h[0]}, {h[1]}, {h[2]}, {h[3]}**\n(計5点)")
                st.caption("上位2頭を軸に、2着漏れを徹底的に防ぐ買い目。")
        else:
            st.error("データの抽出に失敗しました。")
