import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：最終実績・数値解析", layout="wide")

# --- 1. 究極・データ解析エンジン（読み込みエラー完全対策） ---
def ultimate_scan(text):
    # テキストを徹底的にクリーニング
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # 競馬特有のノイズ単語（これらを馬名から除外）
    NOISE = ["オッズ", "タイム", "上がり", "推定", "指数", "良", "重", "稍", "不", "芝", "ダ", "コース", "確定", "簡易"]

    i = 0
    while i < len(tokens):
        # 馬番(1-18)を探す
        if re.match(r'^([1-9]|1[0-8])$', tokens[i]):
            b_no = int(tokens[i])
            b_name, b_odds = "", 0.0
            margins, up_ranks, times = [], [], []
            
            # その馬番から次の馬番までの範囲（最大50語）を精査
            j = i + 1
            while j < len(tokens):
                t = tokens[j]
                # 次の馬番(単独の1-18)が出たら終了
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 5: break
                
                # ① 馬名の抽出（カタカナ2-9文字でノイズでないもの）
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', t) and t not in NOISE:
                    b_name = t
                # ② オッズ
                elif re.match(r'^\d{1,3}\.\d$', t): b_odds = float(t)
                # ③ 着差
                elif re.match(r'^[-+]\d\.\d$', t): margins.append(float(t))
                # ④ 上がり
                if any(k in t for k in ["①", "②", "③", "上1", "上2", "上3"]): up_ranks.append(1)
                # ⑤ タイム
                t_m = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', t)
                if t_m: times.append(int(t_m.group(1))*60 + int(t_m.group(2)) + int(t_m.group(3))*0.1)
                
                j += 1
            
            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "オッズ": b_odds,
                    "上り実績": 1 if up_ranks else 0,
                    "最小着差": min(margins) if margins else 1.0,
                    "平均着差": sum(margins)/len(margins) if margins else 1.0,
                    "最速タイム": min(times) if times else 999.0
                })
            i = j - 1
        i += 1
    
    df = pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])
    if not df.empty:
        df = df.sort_values("オッズ").reset_index(drop=True)
        df["人気"] = df.index + 1
    return df

# --- 2. 徹底数値ロジック ---
def apply_final_logic(df):
    if df.empty: return df
    field_best = df[df["最速タイム"] < 900]["最速タイム"].min() if not df[df["最速タイム"] < 900].empty else 99.0

    def calculate_score(row):
        score = 50.0
        if row['上り実績'] == 1: score += 25
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 15
        if abs(row['平均着差'] - row['最小着差']) > 1.0: score -= 20
        if row['最速タイム'] < 900 and (row['最速タイム'] - field_best) <= 0.3: score += 20
        if 2 <= row['人気'] <= 5: score += 30
        return score

    df["能力スコア"] = df.apply(calculate_score, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI ---
st.title("🏇 AI競馬：最終実績数値・完全解析")

if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key = st.session_state.get('clear_key', 0) + 1
    st.rerun()

st.info("💡 競馬ラボの『ウェブ新聞』等をすべて選択コピーして貼り付けてください。実績のみで解析します。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.get('clear_key', 0)}")

if st.button("🚀 最新ロジックで分析開始"):
    if raw_input:
        df = ultimate_scan(raw_input)
        if not df.empty:
            df = apply_final_logic(df)
            
            st.subheader("📊 能力ランキング（的中期待度順）")
            st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', '最小着差', '能力スコア']])
            
            h = df["馬番"].tolist()
            st.success(f"**【推奨：馬連流し】** {h[0]} ― {', '.join(map(str, h[1:5]))}")
            fav25 = df[df['人気'].between(2, 5)]['馬番'].tolist()
            st.warning(f"**【推奨：2-5人気BOX】** {', '.join(map(str, sorted(list(set(h[:2] + fav25[:2])))))}")
        else:
            st.error("読み取れません。馬番・馬名・オッズが含まれるようにコピーしてください。")
