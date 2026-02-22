import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：オメガ指数・予想タイム解析", layout="wide")

# --- 1. 超精密・オメガ指数判別エンジン ---
def ultra_precision_omega_scan(text):
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # 競馬用語・ノイズ排除
    NOISE = ["オッズ", "タイム", "上がり", "推定", "指数", "良", "重", "稍", "不", "芝", "ダ", "コース", "確定", "斤量"]

    i = 0
    while i < len(tokens):
        # 馬番(1-18)を探す
        if re.match(r'^([1-9]|1[0-8])$', tokens[i]):
            b_no = int(tokens[i])
            b_name, b_odds, b_omega = "", 0.0, 0.0
            margins, up_ranks, times = [], [], []
            
            # その馬番から次の馬番まで（最大60単語）を精査
            j = i + 1
            while j < len(tokens):
                t = tokens[j]
                # 次の馬番(単独の1-18)が出たら終了
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 5: break
                
                # A. 馬名の特定（騎手名・ノイズを排除）
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', t) and t not in NOISE:
                    # 斤量の前にある単語は騎手名として無視
                    if j+1 < len(tokens) and re.match(r'^\d{2}\.0$', tokens[j+1]): pass
                    else: b_name = t
                
                # B. 数値解析：オメガ指数とオッズを分離
                if re.match(r'^\d{1,3}\.\d$', t):
                    val = float(t)
                    # オメガ指数：通常70〜125。オッズより前に出現することが多い
                    # すでにオッズ候補が入っている場合は、より「オメガらしい」方を優先
                    if 70.0 <= val <= 135.0 and b_omega == 0.0:
                        b_omega = val
                    else:
                        b_odds = val
                
                # C. 着差（-0.4, +0.9など）
                elif re.match(r'^[-+]\d\.\d$', t): margins.append(float(t))
                # D. 上がり実績
                if any(k in t for k in ["①", "②", "③", "上1", "上2", "上3"]): up_ranks.append(1)
                # E. タイム抽出（予想タイム算出用）
                t_m = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', t)
                if t_m:
                    sec = int(t_m.group(1))*60 + int(t_m.group(2)) + int(t_m.group(3))*0.1
                    times.append(sec)
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

# --- 2. 予想タイム算出 ＆ 統合ロジック ---
def apply_final_logic(df):
    if df.empty: return df
    field_best = df[df["最速タイム"] > 0]["最速タイム"].min() if not df[df["最速タイム"] > 0].empty else 100.0

    def calculate_score(row):
        score = 50.0
        # ① オメガ指数評価 (90以上で特大加点)
        if row['オメガ'] >= 90.0: score += 45
        elif row['オメガ'] >= 80.0: score += 20
            
        # ② 実績：0.4s / 0.9s ルール
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 15
        
        # ③ 安定性：平均と最小の乖離
        if abs(row['平均着差'] - row['最小着差']) > 1.0: score -= 20
        
        # ④ 予想タイム評価
        if row['最速タイム'] > 0:
            # 簡易予想タイム：最速タイムに着差平均を少し加味
            expected_time = row['最速タイム'] + (max(0, row['平均着差']) * 0.2)
            if expected_time <= field_best + 0.3: score += 25
            
        # ⑤ 2番〜5番人気への加点 (相手強化)
        if 2 <= row['人気'] <= 5: score += 30
            
        return score

    df["能力スコア"] = df.apply(calculate_score, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI ---
st.title("🏇 AI競馬：オメガ指数・数値実績解析")

# クリアボタン（確実にリセット）
if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key = st.session_state.get('clear_key', 0) + 1
    st.rerun()

st.info("💡 競馬ラボの出馬表をコピーして貼り付けてください。オメガ90以上と2-5人気を強力に評価します。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.get('clear_key', 0)}")

if st.button("🚀 最新数値ロジックで分析開始"):
    if raw_input:
        df = ultra_precision_omega_scan(raw_input)
        if not df.empty:
            df = apply_final_logic(df)
            
            st.subheader("📊 解析：能力ランキング")
            # オメガ90以上をハイライト
            st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', 'オメガ', '最小着差', '能力スコア']].style.applymap(
                lambda x: 'background-color: #fff3cd' if x >= 90.0 else '', subset=['オメガ']
            ))
            
            col1, col2 = st.columns(2)
            h = df["馬番"].tolist()
            with col1:
                st.subheader("AI評価印")
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 的中率最高")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
            
            with col2:
                st.subheader("🎯 推奨：馬連買い目")
                st.success(f"**【本線流し】** {h[0]} ― {', '.join(map(str, h[1:5]))}")
                # 2-5番人気を確実に含むBOX
                fav25 = df[df['人気'].between(2, 5)]['馬番'].tolist()
                box = sorted(list(set(h[:2] + fav25[:2])))
                st.warning(f"**【2nd列重視BOX】** {', '.join(map(str, box))}")
        else:
            st.error("データを読み取れませんでした。馬名・オメガ指数が含まれているか確認してください。")
