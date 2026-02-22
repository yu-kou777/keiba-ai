import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：馬連・調教統合モデル", layout="wide")

# --- 1. データ解析・調教判定エンジン ---
def parse_with_training(text):
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # レース名抽出
    race_info = "不明なレース"
    match_r = re.search(r'(\d{1,2}R)', text)
    if match_r:
        for line in text.split('\n'):
            if match_r.group(1) in line:
                race_info = line.strip()
                break

    for i in range(len(tokens)):
        if re.match(r'^([1-9]|1[0-8])$', tokens[i]):
            baban = tokens[i]
            name, sire, odds, training = "", "", 0.0, "C" # デフォルト評価
            
            # 周辺30トークンをスキャン（調教評価は少し離れている場合があるため）
            for j in range(i + 1, min(i + 30, len(tokens))):
                t = tokens[j]
                # 馬名
                if not name and re.match(r'^[ァ-ヶー]{2,9}$', t): name = t
                # 父
                elif name and not sire and re.match(r'^[ァ-ヶー]{2,10}$', t): sire = t
                # オッズ
                elif re.match(r'^\d{1,3}\.\d$', t): odds = float(t)
                # 調教評価の抜き出し (A, B, ◎, 良 など)
                if t in ["A", "S", "◎", "良", "絶好"]: training = "A"
                elif t in ["B", "○"]: training = "B"
            
            if name and odds > 0:
                extracted.append({
                    "馬番": baban, "馬名": name, "父": sire, 
                    "オッズ": odds, "調教": training
                })
    return race_info, pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 2. 最新・馬連特化ロジック ---
def apply_umaren_logic(df):
    def score_row(row):
        score = 50.0
        # 調教ボーナス (A評価なら大幅加点)
        if row['調教'] == "A": score += 20
        elif row['調教'] == "B": score += 5
        
        # 血統の安定性 (午前のレースで重要)
        stable_sires = ["キズナ", "エピファネイア", "ドゥラメンテ", "ロードカナロア"]
        if any(s in str(row['父']) for s in stable_sires): score += 10
        
        # 期待値補正（馬連の軸として最適な5〜12倍を優遇）
        if 4.0 <= row['オッズ'] <= 15.0: score += 15
        
        return (score / 50) * (10 / row['オッズ'])

    df["期待値"] = df.apply(score_row, axis=1)
    return df.sort_values("期待値", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 AI競馬：馬連・調教統合エンジン")

# サイドバー：クリア機能
if st.sidebar.button("🗑️ データをクリアして次へ"):
    st.session_state["text_area_val"] = ""
    st.rerun()

# 入力エリア
if "text_area_val" not in st.session_state:
    st.session_state["text_area_val"] = ""

st.info("💡 競馬ラボの『簡易出馬表』をすべて選択コピーして貼り付けてください。調教評価も自動で読み取ります。")
raw_input = st.text_area("コピペエリア", value=st.session_state["text_area_val"], height=300, key="input")

if st.button("🚀 最新ロジックで解析"):
    if raw_input:
        race_info, df = parse_with_training(raw_input)
        if not df.empty:
            df = apply_umaren_logic(df)
            
            st.success(f"解析完了：{race_info}")
            
            # 表示
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 馬連・期待値ランキング")
                # 調教評価を色付けして表示
                st.dataframe(df[['馬番', '馬名', 'オッズ', '調教', '期待値']].style.applymap(
                    lambda x: 'background-color: #ffcccc' if x == 'A' else '', subset=['調教']
                ))
            
            with col2:
                st.subheader("AI推奨印")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 調教:{df.iloc[0]['調教']}")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            # 買い目生成
            st.divider()
            st.subheader("🎯 馬連・特化フォーメーション")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【プランA：軸堅実】**\n\n**{h[0]}** ― {', '.join(h[1:5])} (4点)")
                st.caption("調教評価が高く、期待値最大の軸馬から上位へ。")
            with c2:
                st.warning(f"**【プランB：合成重視】**\n\n**{h[0]}, {h[1]}** ― {h[2]}, {h[3]}, {h[4]} (6点)")
                st.caption("上位2頭を軸に、広めにカバーする高配当狙い。")
        else:
            st.error("データを読み取れませんでした。馬番・馬名・オッズ・調教が入っているか確認してください。")
