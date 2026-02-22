import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：実績数値・タイム解析モデル", layout="wide")

# --- 1. 超堅牢トークン解析エンジン ---
def ultra_robust_parse(text):
    # テキストを空白や改行で完全にバラバラにする
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    extracted = []
    
    # レース名の抽出
    r_info = "レース未特定"
    for line in text.split('\n')[:20]:
        if "R" in line or "クラス" in line or "歳上" in line:
            r_info = line.strip()
            break

    i = 0
    while i < len(tokens):
        # 馬番(1-18)を探す
        token = tokens[i]
        match_no = re.match(r'^([1-9]|1[0-8])$', token)
        
        if match_no:
            b_no = int(match_no.group(1))
            b_name, b_odds = "", 0.0
            margins = []      # 過去走着差
            times = []        # 過去走走破タイム
            up_3f_ranks = []  # 上がり順位
            
            # その馬番から次の馬番までの範囲をスキャン
            j = i + 1
            while j < len(tokens) and j < i + 60:
                t = tokens[j]
                # 次の馬番が出てきたら終了（ただしオッズの数値と誤認しないようチェック）
                if re.match(r'^([1-9]|1[0-8])$', t) and j > i + 5:
                    break
                
                # 馬名
                if not b_name and re.match(r'^[ァ-ヶー]{2,10}$', t) and t not in ["オッズ", "タイム", "上がり"]:
                    b_name = t
                # オッズ
                elif re.match(r'^\d{1,3}\.\d$', t):
                    b_odds = float(t)
                # 着差 (-0.4, +0.9など)
                elif re.match(r'^[-+]\d\.\d$', t):
                    margins.append(float(t))
                # 上がり順位 (①, ②, ③など)
                if any(k in t for k in ["①", "②", "③", "上り1", "上り2", "上り3"]):
                    up_3f_ranks.append(1)
                # 走破タイム (1:23.4形式)
                t_match = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', t)
                if t_match:
                    sec = int(t_match.group(1))*60 + int(t_match.group(2)) + int(t_match.group(3))*0.1
                    times.append(sec)
                j += 1
            
            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "オッズ": b_odds,
                    "上がり1_3位": 1 if up_3f_ranks else 0,
                    "過去3走着差": margins[:3],
                    "最速タイム": min(times) if times else 999.0
                })
            i = j - 1
        i += 1
    
    df = pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])
    if not df.empty:
        df = df.sort_values("オッズ").reset_index(drop=True)
        df["人気"] = df.index + 1
    return r_info, df

# --- 2. 実績・時計・ギャップ・人気 統合ロジック ---
def apply_deep_logic(df):
    if df.empty: return df
    
    # 全体の最速タイム（距離比較用）
    field_best = df[df["最速タイム"] < 900]["最速タイム"].min() if not df[df["最速タイム"] < 900].empty else 999.0

    def score_calculation(row):
        score = 50.0
        
        # ① 上がり3ハロン評価 (1-3位実績あり)
        if row['上がり1_3位'] == 1: score += 20
        
        # ② 1着との差 (0.4s以内 / 0.9s以内)
        margins = row['過去3走着差']
        if margins:
            best_m = min(margins)
            if best_m <= 0.4: score += 40
            elif best_m <= 0.9: score += 20
            
            # ③ 過去3走ギャップ（安定性）評価
            avg_m = sum(margins) / len(margins)
            if abs(avg_m - best_m) > 1.0: score -= 20 # 激走と惨敗の差が激しい馬を警戒
            
        # ④ 過去5走最速タイム評価
        if row['最速タイム'] < 900 and field_best < 900:
            time_gap = row['最速タイム'] - field_best
            if time_gap <= 0.2: score += 25 # メンバー最速級
            elif time_gap <= 0.6: score += 10
            
        # ⑤ 2番〜5番人気への加点 (2列目候補の強化)
        if 2 <= row['人気'] <= 5:
            score += 30
            
        return score

    df["能力スコア"] = df.apply(score_calculation, axis=1)
    return df.sort_values("能力スコア", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 AI競馬：実績数値・タイム解析モデル")
st.caption("過去3走着差・上がり・5走最速タイム・安定性を数値で一括評価。")

# クリアボタン
if "input_key" not in st.session_state: st.session_state.input_key = 0
if st.sidebar.button("🗑️ 全データをクリア"):
    st.session_state.input_key += 1
    st.rerun()

st.info("💡 競馬ラボの『ウェブ新聞』等を全選択コピーして貼り付けてください。実績のみで解析します。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.input_key}")

if st.button("🚀 実績数値ロジックで分析開始"):
    if raw_input:
        r_info, df = ultra_robust_parse(raw_input)
        if not df.empty:
            df = apply_deep_logic(df)
            st.subheader(f"📅 解析対象：{r_info}")
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 能力偏差値ランキング")
                # スコア順に表示
                st.dataframe(df[['馬番', '馬名', '人気', 'オッズ', '能力スコア']])
            
            with col2:
                st.subheader("AI推奨印（実績ベース）")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 実績最高値")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            st.divider()
            st.subheader("🎯 馬連・推奨買い目（2列目強化）")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【軸1頭流し】**\n\n**{h[0]}** ― {', '.join(map(str, h[1:5]))}")
                st.caption("実績値が最も高い馬から、2〜5番人気を含む上位勢へ。")
            with c2:
                # 2-5番人気のうち評価が高い馬を抽出
                fav25 = df[df['人気'].between(2, 5)]['馬番'].tolist()
                box_targets = sorted(list(set(h[:2] + fav25[:2])))
                st.warning(f"**【2nd列強化：馬連BOX】**\n\n{', '.join(map(str, box_targets))}")
                st.caption("2番〜5番人気の実力馬を絡めた、的中率重視のBOX構成。")
        else:
            st.error("データを読み取れませんでした。馬名・着差・タイムが入るようにコピーしてください。")
