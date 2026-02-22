import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：馬連・連対特化モデル", layout="wide")

# --- 1. 内部ロジック：不変の種牡馬データ（種牡馬50/BMS50ベース） ---
TOP_BLOOD_LIST = ["キズナ", "ドゥラメンテ", "エピファネイア", "ロードカナロア", "モーリス", "ハーツクライ", "ルーラーシップ", "ディープインパクト", "キングカメハメハ"]

# --- 2. 解析エンジン（数値データ最優先） ---
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
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', l):
                    b_name = l
                elif b_name and not b_sire and re.match(r'^[ァ-ヶー]{2,10}$', l) and l != b_name:
                    b_sire = l
                elif re.match(r'^\d{1,3}\.\d$', l):
                    b_odds = float(l)
                elif re.search(r'([-+]\d\.\d)', l):
                    b_margin = float(re.search(r'([-+]\d\.\d)', l).group(1))
                    break

            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "父": b_sire, 
                    "オッズ": b_odds, "前走着差": b_margin
                })
    
    return race_info, pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 3. 2着馬を逃さない「馬連・連対ロジック」 ---
def apply_umaren_logic(df):
    def score_calculation(row):
        # 基礎能力値
        power = 50.0
        
        # ① 0.4秒ルールの強化（2着馬を拾うための階層化）
        if row['前走着差'] <= 0.2: 
            power += 40  # 1着候補
        elif row['前走着差'] <= 0.5: 
            power += 25  # 強力な2着候補（9〜11番を拾う層）
        
        # ② 血統裏付け（2着に粘る底力）
        if any(s in str(row['父']) for s in TOP_BLOOD_LIST):
            power += 20
        
        # ③ 市場評価（過小評価されている馬を補正）
        # 馬連で美味しいオッズ帯（6倍〜20倍）の馬を底上げ
        if 6.0 <= row['オッズ'] <= 20.0:
            power += 10
            
        return power

    df["能力スコア"] = df.apply(score_calculation, axis=1)
    # 的中率重視：能力スコアをベースにランキング
    # 回収率（期待値）は参考として算出
    df["期待値"] = (df["能力スコア"] / 50) * (12 / df["オッズ"])
    
    # 馬連なので「能力スコア（2着以内に来る力）」でソート
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 4. UI構築 ---
st.title("🏇 AI競馬：馬連・連対特化エンジン")

if "clear_key" not in st.session_state:
    st.session_state.clear_key = 0

if st.sidebar.button("🗑️ データをクリアして次へ"):
    st.session_state.clear_key += 1
    st.rerun()

st.info("💡 競馬ラボの出馬表を貼り付けてください。2着馬を逃さない『連対ロジック』で解析します。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.clear_key}")

if st.button("🚀 最新ロジックで予想実行"):
    if raw_input:
        r_name, df = scan_race_data(raw_input)
        if not df.empty:
            df = apply_umaren_logic(df)
            
            st.subheader(f"📅 解析：{r_name}")
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 能力ランキング（2着以内確率順）")
                # スコア順に表示。0.5秒以内をハイライト
                st.dataframe(df[['馬番', '馬名', 'オッズ', '前走着差', '能力スコア']].head(10).style.highlight_between(
                    left=-9.9, right=0.5, subset=['前走着差'], color='#e6fffa'
                ))
            
            with col2:
                st.subheader("AI評価印（馬連想定）")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 軸としての信頼度大")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]}) - 相手筆頭")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
                st.write(f"△ **{df.iloc[3]['馬名']}** ({h[3]})")
                st.write(f"△ **{df.iloc[4]['馬名']}** ({h[4]})")

            st.divider()
            st.subheader("🎯 推奨：馬連フォーメーション")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【鉄板：1頭流し】**\n\n**{h[0]}** ― {h[1]}, {h[2]}, {h[3]}, {h[4]} (4点)")
                st.caption("能力値トップの馬を軸に、粘り込みが期待できる上位へ。")
            with c2:
                st.warning(f"**【堅実：フォーメーション】**\n\n**1頭目：{h[0]}, {h[1]}**\n**2頭目：{h[0]}, {h[1]}, {h[2]}, {h[3]}, {h[4]}**\n(計7点)")
                st.caption("2着漏れを防ぐために、能力上位2頭を軸に据えた構成。")
        else:
            st.error("データの抽出に失敗しました。馬番・馬名・オッズ・着差が入るようにコピーしてください。")
