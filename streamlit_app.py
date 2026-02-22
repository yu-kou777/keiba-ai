import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：オメガ・シークエンス解析", layout="wide")

# --- 1. 究極のパターン解析エンジン（芝不・オメガ完全補足） ---
def sequence_parsing_engine(text):
    # テキストをトークン（単語）に分解
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    IGNORE = ["オッズ", "タイム", "上がり", "推定", "指数", "良", "重", "稍", "不", "芝", "ダ", "コース", "確定", "斤量"]

    i = 0
    while i < len(tokens):
        # 馬番(1-18)の検知
        match_no = re.match(r'^([1-9]|1[0-8])$', tokens[i])
        
        if match_no:
            b_no = int(match_no.group(1))
            b_name, b_odds, b_omega = "", 0.0, 0.0
            margins, up_ranks = [], []
            
            j = i + 1
            while j < len(tokens):
                t = tokens[j]
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 5: break
                
                # A. 馬名の特定（騎手名・ノイズ除外）
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', t) and t not in IGNORE:
                    if j+1 < len(tokens) and re.match(r'^\d{2}\.0$', tokens[j+1]): pass
                    else: b_name = t
                
                # B. オッズ
                elif re.match(r'^\d{1,3}\.\d$', t) and b_odds == 0.0:
                    val = float(t)
                    if val < 70.0: b_odds = val

                # C. 【重要：ヒントに基づくオメガ抽出】
                # パターン: 芝不 -> (4つの数字) -> [オメガ] -> [1-18の着順]
                if "芝不" in t:
                    try:
                        # 芝不の5つ先がオメガ、6つ先が着順
                        target_omega = tokens[j+5]
                        target_rank = tokens[j+6]
                        # オメガ（数値）かつ、その次が1-18の着順であるか
                        if re.match(r'^\d{2,3}(\.\d)?$', target_omega) and re.match(r'^([1-9]|1[0-8])$', target_rank):
                            b_omega = float(target_omega)
                    except:
                        pass

                # D. 実績（着差・上がり）
                if re.match(r'^[-+]\d\.\d$', t): margins.append(float(t))
                if any(k in t for k in ["①", "②", "③", "上1", "上2", "上3"]): up_ranks.append(1)
                
                j += 1
            
            if b_name and (b_odds > 0 or b_omega > 0):
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "オッズ": b_odds, "オメガ": b_omega,
                    "上り実績": 1 if up_ranks else 0,
                    "最小着差": min(margins) if margins else 1.0,
                    "平均着差": sum(margins)/len(margins) if margins else 1.0,
                })
            i = j - 1
        i += 1
    
    df = pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])
    if not df.empty:
        df = df.sort_values("オッズ").reset_index(drop=True)
        df["人気"] = df.index + 1
    return df

# --- 2. 独自ロジック（オメガ90以上・2-5人気強化） ---
def apply_winning_logic(df):
    def calculate_score(row):
        score = 50.0
        # ① オメガ指数評価（90以上は特大加点）
        if row['オメガ'] >= 90.0: score += 50
        elif row['オメガ'] >= 80.0: score += 20
        # ② 実績：着差（0.4s/0.9s）
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 15
        # ③ 戦略：2〜5番人気への加点
        if 2 <= row['人気'] <= 5: score += 30
        return score

    df["能力スコア"] = df.apply(calculate_score, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI ---
st.title("🏇 AI競馬：オメガ・シークエンス解析モデル")

if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key = st.session_state.get('clear_key', 0) + 1
    st.rerun()

st.info("💡 競馬ラボの出馬表をコピーして貼り付けてください。芝不からオメガ指数を正確に抽出します...")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.get('clear_key', 0)}")

if st.button("🚀 最新ロジックで解析開始"):
    if raw_input:
        df = sequence_parsing_engine(raw_input)
        if not df.empty:
            # 読み取り確認
            st.write("🔍 **解析データ確認（オメガ指数をチェックしてください）**")
            st.dataframe(df[['馬番', '馬名', 'オッズ', 'オメガ', '最小着差']])

            df = apply_winning_logic(df)
            
            st.subheader("📊 能力ランキング")
            st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', 'オメガ', '能力スコア']].style.applymap(
                lambda x: 'background-color: #fff3cd' if x >= 90.0 else '', subset=['オメガ']
            ))
            
            h = df["馬番"].tolist()
            st.success(f"**【推奨：馬連流し】** {h[0]} ― {', '.join(map(str, h[1:5]))}")
        else:
            st.error("データを読み取れません。馬番・馬名・オメガ指数が含まれるようにコピーしてください。")

