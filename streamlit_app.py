import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：オメガ完全補足モデル", layout="wide")

# --- 1. 競馬ラボ・パターン特化解析エンジン ---
def pattern_omega_parse(text):
    # テキストを単語単位に分解
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # ノイズ排除
    NOISE = ["オッズ", "タイム", "上がり", "推定", "指数", "良", "重", "稍", "不", "芝", "ダ", "コース", "確定", "斤量"]

    i = 0
    while i < len(tokens):
        # 馬番(1-18)を探す
        if re.match(r'^([1-9]|1[0-8])$', tokens[i]):
            b_no = int(tokens[i])
            b_name, b_odds, b_omega = "", 0.0, 0.0
            margins, up_ranks, times = [], [], []
            
            j = i + 1
            while j < len(tokens):
                t = tokens[j]
                # 次の馬番が出たら終了
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 5: break
                
                # ① 馬名の特定（騎手排除：斤量数値との距離で判定）
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', t) and t not in NOISE:
                    if j+1 < len(tokens) and re.match(r'^\d{2}\.0$', tokens[j+1]): pass
                    else: b_name = t
                
                # ② オッズ
                elif re.match(r'^\d{1,3}\.\d$', t) and b_odds == 0.0 and float(t) < 70.0:
                    b_odds = float(t)

                # ③ 【新：最優先】オメガ指数の抽出（芝不パターンの解析）
                if "芝不" in t:
                    # 「芝不 0 0 0 0 [オメガ]」の並びを想定
                    # 芝不のあとに数字が連続しているかチェック
                    search_idx = j + 1
                    num_count = 0
                    while search_idx < len(tokens) and num_count < 5:
                        val_str = tokens[search_idx]
                        if re.match(r'^\d{1,3}$', val_str) or re.match(r'^\d{1,3}\.\d$', val_str):
                            num_count += 1
                            if num_count == 5: # 5番目の数字がオメガ
                                b_omega = float(val_str)
                                break
                        search_idx += 1
                
                # ④ 実績数値の抽出
                if re.match(r'^[-+]\d\.\d$', t): margins.append(float(t))
                if any(k in t for k in ["①", "②", "③", "上1", "上2", "上3"]): up_ranks.append(1)
                t_m = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', t)
                if t_m: times.append(int(t_m.group(1))*60 + int(t_m.group(2)) + int(t_m.group(3))*0.1)
                
                j += 1
            
            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "オッズ": b_odds, "オメガ": b_omega,
                    "上り実績": 1 if up_ranks else 0,
                    "最小着差": min(margins) if margins else 1.0,
                    "平均着差": sum(margins)/len(margins) if margins else 1.0,
                    "最速タイム": min(times) if times else 0.0
                })
            i = j - 1
        i += 1
    
    df = pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])
    if not df.empty:
        df = df.sort_values("オッズ").reset_index(drop=True)
        df["人気"] = df.index + 1
    return df

# --- 2. 独自ロジック（オメガ90以上・2-5人気強化） ---
def apply_final_logic(df):
    if df.empty: return df

    def calculate_score(row):
        score = 50.0
        # ① オメガ指数評価 (90以上特大加点)
        if row['オメガ'] >= 90.0: score += 45
        elif row['オメガ'] >= 80.0: score += 20
        # ② 実績：着差 (0.4s / 0.9s)
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 15
        # ③ 2-5番人気加点 (相手強化)
        if 2 <= row['人気'] <= 5: score += 30
        # ④ 安定性：平均と最小の差
        if abs(row['平均着差'] - row['最小着差']) > 1.0: score -= 20
        return score

    df["能力スコア"] = df.apply(calculate_score, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI ---
st.title("🏇 AI競馬：オメガ完全補足・数値解析")

if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key = st.session_state.get('clear_key', 0) + 1
    st.rerun()

st.info("💡 競馬ラボの出馬表（芝不データ含む）を貼り付けてください。オメガ90以上と2-5人気を強力評価。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.get('clear_key', 0)}")

if st.button("🚀 最新ロジックで分析開始"):
    if raw_input:
        df = pattern_omega_parse(raw_input)
        if not df.empty:
            df = apply_final_logic(df)
            
            st.subheader("📊 解析結果ランキング")
            # オメガ90以上をハイライト
            st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', 'オメガ', '最小着差', '能力スコア']].style.applymap(
                lambda x: 'background-color: #fff3cd' if x >= 90.0 else '', subset=['オメガ']
            ))
            
            h = df["馬番"].tolist()
            st.success(f"**【推奨馬連】** {h[0]} ― {', '.join(map(str, h[1:5]))}")
            fav25 = df[df['人気'].between(2, 5)]['馬番'].tolist()
            st.warning(f"**【2nd列BOX】** {', '.join(map(str, sorted(list(set(h[:2] + fav25[:2])))))}")
        else:
            st.error("データを読み取れません。馬番・馬名・芝不データが含まれるようにコピーしてください。")
