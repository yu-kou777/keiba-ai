import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="究極AI競馬：実績数値・完全解析モデル", layout="wide")

# --- 1. 超堅牢・馬名/血統/数値 抽出エンジン ---
def perfect_parse(text):
    # テキストをトークン化（単語に分解）
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # 競馬用語（馬名と間違えやすいワード）
    IGNORE_WORDS = ["コース", "タイム", "ペース", "グレード", "ダート", "芝", "良", "重", "稍重", "不良", "オッズ", "上がり", "推定", "指数"]

    i = 0
    while i < len(tokens):
        # 馬番(1-18)を探す
        token = tokens[i]
        match_no = re.match(r'^([1-9]|1[0-8])$', token)
        
        if match_no:
            b_no = int(match_no.group(1))
            b_name, b_sire, b_odds = "", "", 0.0
            margins = []      # 近3走着差
            times = []        # 近5走タイム
            up_ranks = []     # 上がり順位
            
            # その馬番から次の馬番まで（最大60単語）を精密スキャン
            j = i + 1
            while j < len(tokens) and j < i + 60:
                t = tokens[j]
                # 次の馬番が出てきたら終了
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 10: break
                
                # ① 馬名の特定 (カタカナ2-9文字、無視ワードにない)
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', t) and t not in IGNORE_WORDS:
                    b_name = t
                # ② 父馬の特定 (馬名の後に出るカタカナ)
                elif b_name and not b_sire and re.match(r'^[ァ-ヶー]{2,10}$', t) and t != b_name and t not in IGNORE_WORDS:
                    b_sire = t
                # ③ オッズ (0.0形式)
                elif re.match(r'^\d{1,3}\.\d$', t):
                    b_odds = float(t)
                # ④ 着差 (-0.4, +1.2等)
                elif re.match(r'^[-+]\d\.\d$', t):
                    margins.append(float(t))
                # ⑤ 上がり順位 (①, ②, ③, 上り1位等)
                if any(k in t for k in ["①", "②", "③", "上1", "上2", "上3"]):
                    up_ranks.append(1)
                # ⑥ 走破タイム (1:23.4 等)
                t_match = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', t)
                if t_match:
                    sec = int(t_match.group(1))*60 + int(t_match.group(2)) + int(t_match.group(3))*0.1
                    times.append(sec)
                j += 1
            
            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "父": b_sire, "オッズ": b_odds,
                    "上がり1_3位": 1 if up_ranks else 0,
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

# --- 2. ご指定の数値ロジック完全実装 ---
def apply_deep_logic(df):
    if df.empty: return df
    field_best = df[df["最速タイム"] < 900]["最速タイム"].min() if not df[df["最速タイム"] < 900].empty else 999.0

    def calculate_score(row):
        score = 50.0
        # ① 上がり3ハロン評価 (1-3位実績あり)
        if row['上がり1_3位'] == 1: score += 20
        # ② 着差判定 (0.4s以内 / 0.9s以内)
        if row['最小着差'] <= 0.4: score += 40
        elif row['最小着差'] <= 0.9: score += 15
        # ③ 過去3走ギャップ評価 (安定性)
        if abs(row['平均着差'] - row['最小着差']) > 1.0: score -= 20
        # ④ 最速タイム評価
        if row['最速タイム'] < 900 and field_best < 900:
            if (row['最速タイム'] - field_best) <= 0.3: score += 20
        # ⑤ 2番〜5番人気への加点 (2列目強化)
        if 2 <= row['人気'] <= 5: score += 30
        return score

    df["能力スコア"] = df.apply(calculate_score, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 究極AI競馬：実績・数値・時計解析エンジン")

# クリアボタン
if "input_key" not in st.session_state: st.session_state.input_key = 0
if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.input_key += 1
    st.rerun()

st.info("💡 競馬ラボの『ウェブ新聞』を全選択コピーして貼り付けてください。数値実績のみで解析します。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.input_key}")

if st.button("🚀 最新数値ロジックで分析開始"):
    if raw_input:
        df = perfect_parse(raw_input)
        if not df.empty:
            df = apply_deep_logic(df)
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 能力偏差値ランキング")
                st.dataframe(df[['馬番', '馬名', '父', '人気', 'オッズ', '最小着差', '能力スコア']])
            
            with col2:
                st.subheader("AI評価印（実績重視）")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 数値最高")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
                st.write(f"△ **{df.iloc[3]['馬名']}** ({h[3]})")

            st.divider()
            st.subheader("🎯 馬連・推奨買い目")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【本線流し】**\n\n**{h[0]}** ― {', '.join(map(str, h[1:5]))} (4点)")
            with c2:
                fav25 = df[df['人気'].between(2, 5)]['馬番'].tolist()
                st.warning(f"**【2nd列強化：BOX】**\n\n{', '.join(map(str, sorted(list(set(h[:2] + fav25[:2])))))}")
                st.caption("2-5番人気の実力馬を軸に絡めた、的中率優先の構成。")
        else:
            st.error("データを読み取れませんでした。馬番・馬名・数値が含まれるようにコピーしてください。")
