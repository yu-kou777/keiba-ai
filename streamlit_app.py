import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：実績数値・最終解析モデル", layout="wide")

# --- 1. 競馬ラボ特化型・超精密解析エンジン ---
def super_precision_parse(text):
    # テキストをトークン（単語）に分解
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # 競馬用語の除外リスト
    IGNORE = ["オッズ", "タイム", "上がり", "推定", "指数", "良", "重", "稍", "不", "芝", "ダ", "ペース"]

    i = 0
    while i < len(tokens):
        # 1〜18の馬番を単独で見つけた場合のみ開始
        if re.match(r'^([1-9]|1[0-8])$', tokens[i]):
            b_no = int(tokens[i])
            b_name, b_sire, b_odds = "", "", 0.0
            margins = []
            up_ranks = []
            times = []
            
            # 次の馬番が出るまで（最大60単語）を解析
            j = i + 1
            while j < len(tokens):
                t = tokens[j]
                # 次の馬番の出現を検知してストップ
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 5:
                    break
                
                # ① 馬名：最初に見つけたカタカナ
                if not b_name and re.match(r'^[ァ-ヶー]{2,10}$', t) and t not in IGNORE:
                    b_name = t
                # ② 父名：次に見つけたカタカナ
                elif b_name and not b_sire and re.match(r'^[ァ-ヶー]{2,10}$', t) and t != b_name and t not in IGNORE:
                    b_sire = t
                # ③ オッズ：数値.数値
                elif re.match(r'^\d{1,3}\.\d$', t):
                    b_odds = float(t)
                # ④ 着差：[-+]数値.数値
                elif re.match(r'^[-+]?\d\.\d$', t):
                    margins.append(float(t))
                # ⑤ 上がり順位
                if any(k in t for k in ["①", "②", "③", "上り1", "上り2", "上り3"]):
                    up_ranks.append(1)
                # ⑥ 走破タイム
                t_match = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', t)
                if t_match:
                    sec = int(t_match.group(1))*60 + int(t_match.group(2)) + int(t_match.group(3))*0.1
                    times.append(sec)
                j += 1
            
            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "父": b_sire, "オッズ": b_odds,
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

# --- 2. 実績・時計・2-5番人気 統合ロジック ---
def apply_final_logic(df):
    if df.empty: return df
    field_best = df[df["最速タイム"] < 900]["最速タイム"].min() if not df[df["最速タイム"] < 900].empty else 99.0

    def calculate_score(row):
        score = 50.0
        # ① 上がり3F（1-3位実績）
        if row['上り実績'] == 1: score += 20
        # ② 着差（0.4s / 0.9s）
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 15
        # ③ 安定性（平均と最小の乖離）
        if abs(row['平均着差'] - row['最小着差']) > 1.0: score -= 15
        # ④ 予想タイム（最速タイムの評価）
        if row['最速タイム'] < 900:
            if (row['最速タイム'] - field_best) <= 0.3: score += 20
        # ⑤ 2番〜5番人気加点（相手強化）
        if 2 <= row['人気'] <= 5: score += 30
        return score

    df["能力スコア"] = df.apply(calculate_score, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 AI競馬：数値実績・完全解析モデル")

if "clear_key" not in st.session_state: st.session_state.clear_key = 0
if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key += 1
    st.rerun()

st.info("💡 競馬ラボの出馬表を全選択コピーして貼り付けてください。実績のみで解析します。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.clear_key}")

if st.button("🚀 最新数値ロジックで分析開始"):
    if raw_input:
        df = super_precision_parse(raw_input)
        if not df.empty:
            df = apply_final_logic(df)
            
            st.success("解析成功。以下のデータに基づき予想を算出しました。")
            
            # 結果表示（スマホで見やすく）
            st.subheader("📊 能力ランキング（的中期待度順）")
            st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', '能力スコア']])
            
            # 評価印
            col1, col2 = st.columns(2)
            h = df["馬番"].tolist()
            with col1:
                st.subheader("AI推奨印")
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]})")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
            
            with col2:
                st.subheader("馬連買い目")
                st.success(f"**【本線流し】**\n{h[0]} ― {', '.join(map(str, h[1:5]))}")
                # 2-5番人気を含むBOX
                fav25 = df[df['人気'].between(2, 5)]['馬番'].tolist()
                box = sorted(list(set(h[:2] + fav25[:2])))
                st.warning(f"**【2-5番人気BOX】**\n{', '.join(map(str, box))}")
        else:
            st.error("データの抽出に失敗しました。馬名や数値が含まれているか確認してください。")
