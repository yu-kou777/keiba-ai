import streamlit as st
import pandas as pd
import re
import numpy as np

st.set_page_config(page_title="AI競馬：実績・時計解析モデル", layout="wide")

# --- 1. 解析エンジン（過去走・タイム・上り抽出） ---
def deep_scan_data(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    
    # 馬番(1-18)をアンカーに、深いデータを抽出
    for i in range(len(lines)):
        if re.match(r'^([1-9]|1[0-8])$', lines[i]):
            b_no = lines[i]
            b_name, b_odds = "", 0.0
            last_3f_rank = 5  # デフォルト
            margins = []      # 近3走の着差
            best_time = 999.0 # 近5走の同距離最速
            
            # その馬番から30行以内を深くスキャン
            for j in range(i + 1, min(i + 40, len(lines))):
                l = lines[j]
                # 馬名
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', l): b_name = l
                # オッズ
                elif re.match(r'^\d{1,3}\.\d$', l): b_odds = float(l)
                
                # 上り3F順位の抽出 (例: ①, ②, ③ または 上り1位など)
                if any(k in l for k in ["①", "上り1", "上り2", "上り3"]): last_3f_rank = 1
                
                # 着差の抽出 (例: -0.4, 0.8)
                margin_match = re.findall(r'([-+]\d\.\d)', l)
                if margin_match: margins.extend([float(m) for m in margin_match])
                
                # 走破タイムの抽出 (例: 1:23.4 や 1.23.4)
                time_match = re.search(r'(\d)[:\.](\d{2})[\.\:](\d)', l)
                if time_match:
                    seconds = int(time_match.group(1))*60 + int(time_match.group(2)) + int(time_match.group(3))*0.1
                    if seconds < best_time: best_time = seconds

            if b_name and b_odds > 0:
                # 近3走着差の平均（ギャップ評価用）
                avg_margin = sum(margins[:3])/len(margins[:3]) if margins else 1.0
                # 0.4s以内、0.9s以内の判定
                recent_performance = min(margins) if margins else 1.0
                
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "オッズ": b_odds,
                    "上り評価": last_3f_rank, "近走最小着差": recent_performance,
                    "平均着差": avg_margin, "最速タイム": best_time
                })
    
    return pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 2. 独自の数値評価ロジック（実績・時計・ギャップ） ---
def apply_deep_logic(df):
    if df.empty: return df
    
    # 全体の最速タイムとの差（偏差）
    min_time_in_field = df["最速タイム"].min()
    
    def score_calculation(row):
        score = 50.0
        
        # ① 上り3Fランク評価 (1-3位なら大幅加点)
        if row['上り評価'] == 1: score += 25
        
        # ② 着差ランク付け（0.4秒以内 / 0.9秒以内）
        if row['近走最小着差'] <= 0.4: score += 35
        elif row['近走最小着差'] <= 0.9: score += 15
        
        # ③ 過去3走のギャップ（安定性）評価
        # 平均着差と最小着差の乖離が大きい＝ムラ馬として警戒（減点）
        if abs(row['平均着差'] - row['近走最小着差']) > 1.0: score -= 15
        
        # ④ 近5走・同距離最速タイム評価
        if row['最速タイム'] < 999:
            time_gap = row['最速タイム'] - min_time_in_field
            if time_gap <= 0.2: score += 20 # メンバー最速クラス
            elif time_gap <= 0.5: score += 10
            
        return score

    df["実績スコア"] = df.apply(score_calculation, axis=1)
    # 期待値計算
    df["期待値"] = (df["実績スコア"] / 50) * (10 / df["オッズ"])
    return df.sort_values("実績スコア", ascending=False).reset_index(drop=True)

# --- 3. UI構築 ---
st.title("🏇 AI競馬：実績・時計ディープ解析エンジン")
st.caption("過去走の着差・上り・持ち時計のみを抽出。主観を廃した実数値予想。")

if "clear_key" not in st.session_state: st.session_state.clear_key = 0
if st.sidebar.button("🗑️ データをクリア"):
    st.session_state.clear_key += 1
    st.rerun()

st.info("💡 競馬ラボの『ウェブ新聞』または『簡易出馬表』を全選択コピーして貼り付けてください。")
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.clear_key}")

if st.button("🚀 ディープ解析・予想実行"):
    if raw_input:
        df = deep_scan_data(raw_input)
        if not df.empty:
            df = apply_deep_logic(df)
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 実績・能力ランキング")
                st.dataframe(df[['馬番', '馬名', 'オッズ', '近走最小着差', '実績スコア']].head(10))
            
            with col2:
                st.subheader("AI推奨印")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 実績No.1")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            st.divider()
            st.subheader("🎯 馬連推奨買い目（数値裏付け）")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【本線流し】** {h[0]} ― {h[1]}, {h[2]}, {h[3]}, {h[4]}")
            with c2:
                # 持ち時計が速い穴馬をピックアップ
                fast_holes = df[(df['オッズ'] >= 10.0) & (df['実績スコア'] >= 60)].head(2)
                if not fast_holes.empty:
                    st.warning(f"**【時計注意：穴馬】** {', '.join(fast_holes['馬番'].tolist())}")
                else:
                    st.warning(f"**【堅実BOX】** {h[0]}, {h[1]}, {h[2]}, {h[3]}")
        else:
            st.error("データを抽出できませんでした。過去走の着差やタイムが含まれるようにコピーしてください。")
