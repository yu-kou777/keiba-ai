import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="究極AI競馬：馬連・的中特化エンジン", layout="wide")

# --- 1. 深層数値解析エンジン ---
def deep_analyze_engine(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    
    # レース名の抽出
    r_info = "レース解析中"
    for line in lines:
        if "R" in line and len(line) < 30:
            r_info = line
            break

    # 馬番(1-18)を起点にデータを構造化
    for i in range(len(lines)):
        if re.match(r'^([1-9]|1[0-8])$', lines[i]):
            b_no = lines[i]
            b_name, b_odds = "", 0.0
            margins = []      # 過去走着差
            times = []        # 過去走タイム
            rank_3f = 5       # 上がり評価
            
            # 馬番から40行以内を精密スキャン
            for j in range(i + 1, min(i + 45, len(lines))):
                l = lines[j]
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', l): b_name = l
                elif re.match(r'^\d{1,3}\.\d$', l): b_odds = float(l)
                
                # 上がり3F 1-3位の検知
                if any(k in l for k in ["①", "②", "③", "上り1", "上り2", "上り3"]):
                    rank_3f = 1
                
                # 着差の抽出 (-0.4, 0.9 など)
                m_match = re.findall(r'([-+]\d\.\d)', l)
                if m_match: margins.extend([float(m) for m in m_match])
                
                # タイムの抽出 (1:23.4 等)
                t_match = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', l)
                if t_match:
                    sec = int(t_match.group(1))*60 + int(t_match.group(2)) + int(t_match.group(3))*0.1
                    times.append(sec)

            if b_name and b_odds > 0:
                best_t = min(times) if times else 999.0
                min_m = min(margins) if margins else 1.0
                avg_m = sum(margins)/len(margins) if margins else 1.0
                
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "オッズ": b_odds,
                    "上り1_3位": rank_3f, "最小着差": min_m, "平均着差": avg_m,
                    "最速タイム": best_t
                })
    
    return r_info, pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 2. 数値・市場 統合ロジック ---
def apply_final_logic(df):
    if df.empty: return df
    
    # フィールド内最速タイム
    field_best = df[df["最速タイム"] < 900]["最速タイム"].min()
    
    def score_calculation(row):
        score = 40.0 # 基礎点
        
        # ① 人気・オッズ評価（市場の信頼度）
        if row['オッズ'] <= 3.5: score += 45  # 1番人気級への絶対評価
        elif row['オッズ'] <= 6.5: score += 30 # 2-3番人気級への高い信頼
        elif row['オッズ'] <= 12.0: score += 15
        
        # ② 上がり3F実績（1-3位）
        if row['上り1_3位'] == 1: score += 20
        
        # ③ 着差判定（0.4s / 0.9s ルール）
        if row['最小着差'] <= 0.4: score += 35
        elif row['最小着差'] <= 0.9: score += 15
        
        # ④ 過去3走ギャップ（安定性）
        # 平均と最小の差が大きい＝ムラ馬（減点）
        if abs(row['平均着差'] - row['最小着差']) > 1.2: score -= 15
        
        # ⑤ タイム評価（同距離最速との比較）
        if row['最速タイム'] < 900:
            diff = row['最速タイム'] - field_best
            if diff <= 0.2: score += 20
            elif diff <= 0.6: score += 10
            
        return score

    df["連対期待スコア"] = df.apply(score_calculation, axis=1)
    # スコア順（的中確率順）にソート
    return df.sort_values("連対期待スコア", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 究極AI競馬：馬連的中・資金増殖モデル")

# クリア機能
if "input_key" not in st.session_state: st.session_state.input_key = 0
if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.input_key += 1
    st.rerun()

st.info("💡 競馬ラボの『ウェブ新聞』等を全選択コピーして貼り付けてください。人気・着差・タイムを多角的に解析します。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.input_key}")

if st.button("🚀 最新ロジックで予想実行"):
    if raw_input:
        r_name, df = deep_analyze_engine(raw_input)
        if not df.empty:
            df = apply_final_logic(df)
            st.subheader(f"📅 解析：{r_name}")
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 連対期待度ランキング")
                # 0.4秒以内と低オッズを視覚化
                st.dataframe(df[['馬番', '馬名', 'オッズ', '最小着差', '連対期待スコア']].head(10))
            
            with col2:
                st.subheader("AI評価印（馬連軸）")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 的中信頼度最高")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            st.divider()
            st.subheader("🎯 馬連特化・推奨買い目")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【鉄板：1頭流し】**\n\n**{h[0]}** ― {h[1]}, {h[2]}, {h[3]}, {h[4]} (4点)")
                st.caption("連対率が最も高い軸馬から、実績上位への安定流し。")
            with c2:
                st.warning(f"**【的中：フォーメーション】**\n\n**{h[0]}, {h[1]}** ― {h[0], h[1], h[2], h[3], h[4]}\n(計7点)")
                st.caption("1番人気と2番人気の両方を軸に据え、2着漏れを防ぐ構成。")
        else:
            st.error("データの抽出に失敗しました。過去走データが含まれるようにコピーしてください。")

