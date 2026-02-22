import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：オメガ指数・最終解析", layout="wide")

# --- 1. 究極のデータ解析エンジン（読み込みエラー徹底対策） ---
def ultimate_parsing_engine(text):
    # テキストをトークン（単語）にバラバラにする
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # 競馬用語・ノイズ排除リスト
    NOISE = ["オッズ", "タイム", "上がり", "推定", "指数", "良", "重", "稍", "不", "芝", "ダ", "コース", "確定", "斤量"]

    i = 0
    while i < len(tokens):
        # 馬番(1-18)を検知。文字がくっついていても分離（例: "1レアレスト"）
        match_no = re.match(r'^([1-9]|1[0-8])([ァ-ヶー].*)?$', tokens[i])
        
        if match_no:
            b_no = int(match_no.group(1))
            b_name = match_no.group(2) if match_no.group(2) else ""
            b_odds, b_omega = 0.0, 0.0
            margins, up_ranks, times = [], [], []
            
            # その馬から次の馬番までの範囲（最大70単語）を精査
            j = i + 1
            while j < len(tokens):
                t = tokens[j]
                # 次の馬番（単独の1-18）が出たら終了
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 5: break
                
                # A. 馬名の抽出（騎手名を斤量54.0などで判定して除外）
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', t) and t not in NOISE:
                    if j+1 < len(tokens) and re.match(r'^\d{2}\.0$', tokens[j+1]): pass
                    else: b_name = t
                
                # B. オッズ（小さな小数点数値）
                elif re.match(r'^\d{1,3}\.\d$', t) and b_odds == 0.0:
                    val = float(t)
                    if val < 70.0: b_odds = val

                # C. 【重要】オメガ指数の抽出
                # 「芝不」というキーワードの周辺を重点的に探す
                if "芝不" in t or "Ω" in t or "指数" in t:
                    # 前後10単語の中から70〜130の数値をオメガとして採用
                    for k in range(max(0, j-5), min(len(tokens), j+15)):
                        pot_omega = tokens[k]
                        if re.match(r'^\d{2,3}(\.\d)?$', pot_omega):
                            val = float(pot_omega)
                            if 70.0 <= val <= 135.0:
                                b_omega = val
                                break

                # D. 実績数値（着差、上がり、タイム）
                if re.match(r'^[-+]\d\.\d$', t): margins.append(float(t))
                if any(k in t for k in ["①", "②", "③", "上1", "上2", "上3"]): up_ranks.append(1)
                t_m = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', t)
                if t_m: times.append(int(t_m.group(1))*60 + int(t_m.group(2)) + int(t_m.group(3))*0.1)
                
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
        if row['オメガ'] >= 90.0: score += 45
        elif row['オメガ'] >= 80.0: score += 20
        # ② 実績：着差
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 15
        # ③ 戦略：2〜5番人気への加点（相手強化）
        if 2 <= row['人気'] <= 5: score += 30
        return score

    df["能力スコア"] = df.apply(calculate_score, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI ---
st.title("🏇 AI競馬：究極データ解析・オメガ補完版")

if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key = st.session_state.get('clear_key', 0) + 1
    st.rerun()

st.info("💡 競馬ラボの出馬表（芝不データ含む）を貼り付けてください。読み取り結果が下に表示されます。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.get('clear_key', 0)}")

if st.button("🚀 最新ロジックで解析開始"):
    if raw_input:
        df = ultimate_parsing_engine(raw_input)
        if not df.empty:
            # デバッグ表示（読み取った内容を確認）
            st.write("🔍 **読み取りデータ確認（この内容で計算します）**")
            st.dataframe(df[['馬番', '馬名', 'オッズ', 'オメガ', '最小着差']])

            df = apply_winning_logic(df)
            
            st.subheader("📊 能力ランキング")
            st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', 'オメガ', '能力スコア']].style.applymap(
                lambda x: 'background-color: #fff3cd' if x >= 90.0 else '', subset=['オメガ']
            ))
            
            h = df["馬番"].tolist()
            st.success(f"**【推奨馬連】** {h[0]} ― {', '.join(map(str, h[1:5]))}")
        else:
            st.error("データを読み取れません。馬番・馬名・数値が含まれるようにコピーしてください。")
