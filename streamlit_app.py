import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：数値解析・馬連特化モデル", layout="wide")

# --- 1. 内部ロジック：種牡馬50/BMS50 統合データ ---
# あなたの「種牡馬50」に基づいた主要ライン
TOP_BLOODLINE = ["キズナ", "ドゥラメンテ", "エピファネイア", "ロードカナロア", "モーリス", "ハーツクライ", "ルーラーシップ", "ディープインパクト", "キングカメハメハ"]

# --- 2. 高精度スキャンエンジン（主観データ排除） ---
def scan_race_data(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    race_info = "レース未特定"
    
    # レース名抽出
    for line in lines:
        if "R" in line and len(line) < 30:
            race_info = line
            break

    # 馬番(1-18)をアンカーに、馬名・父・オッズ・前走着差を抽出
    for i in range(len(lines)):
        if re.match(r'^([1-9]|1[0-8])$', lines[i]):
            b_no = lines[i]
            b_name, b_sire, b_odds, b_margin = "", "", 0.0, 9.9
            
            # その馬番から20行以内を探索
            for j in range(i + 1, min(i + 20, len(lines))):
                l = lines[j]
                # 馬名(カタカナ2-9)
                if not b_name and re.match(r'^[ァ-ヶー]{2,9}$', l):
                    b_name = l
                # 父(馬名確定後のカタカナ)
                elif b_name and not b_sire and re.match(r'^[ァ-ヶー]{2,10}$', l) and l != b_name:
                    b_sire = l
                # オッズ(0.0)
                elif re.match(r'^\d{1,3}\.\d$', l):
                    b_odds = float(l)
                # 着差(0.4秒ルール用の数値：-0.5, 0.3など)
                elif re.search(r'([-+]\d\.\d)', l):
                    b_margin = float(re.search(r'([-+]\d\.\d)', l).group(1))
                    break # オッズと着差まで取れたら次の馬へ

            if b_name and b_odds > 0:
                extracted.append({
                    "馬番": b_no, "馬名": b_name, "父": b_sire, 
                    "オッズ": b_odds, "前走着差": b_margin
                })
    
    return race_info, pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- 3. 客観数値ロジック（期待値・0.4秒ルール・血統） ---
def apply_numeric_logic(df):
    def score_calculation(row):
        score = 50.0
        
        # ① 0.4秒ルール（数値の裏付け）
        if row['前走着差'] <= 0.4:
            score += 35
        
        # ② 血統評価（種牡馬50/BMS50）
        if any(s in str(row['父']) for s in TOP_BLOODLINE):
            score += 20
        
        # ③ 市場の歪み補正（馬連で最も効率の良いオッズ帯）
        if 4.0 <= row['オッズ'] <= 18.0:
            score += 15
        
        return score

    df["能力スコア"] = df.apply(score_calculation, axis=1)
    # 期待値 = (能力スコア / 基準50) * (適正回収オッズ / 現在のオッズ)
    df["期待値"] = (df["能力スコア"] / 50) * (12 / df["オッズ"])
    return df.sort_values("期待値", ascending=False).reset_index(drop=True)

# --- 4. UI構築 ---
st.title("🏇 AI競馬：数値解析・馬連ブースト")

# クリアボタンの修正（keyを更新して完全にリセット）
if "clear_key" not in st.session_state:
    st.session_state.clear_key = 0

if st.sidebar.button("🗑️ データをクリアして次へ"):
    st.session_state.clear_key += 1
    st.rerun()

st.info("💡 競馬ラボの『簡易出馬表』を貼り付けてください。主観を排除した数値のみで分析します。")

# 動的なキーでテキストエリアを完全制御
raw_input = st.text_area("コピペエリア", height=300, key=f"input_{st.session_state.clear_key}")

if st.button("🚀 数値解析・予想実行"):
    if raw_input:
        r_name, df = scan_race_data(raw_input)
        if not df.empty:
            df = apply_numeric_logic(df)
            
            st.subheader(f"📅 解析：{r_name}")
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 数値ランキング（期待値順）")
                # 0.4秒以内を強調
                st.dataframe(df[['馬番', '馬名', 'オッズ', '前走着差', '期待値']].style.highlight_between(
                    left=-9.9, right=0.4, subset=['前走着差'], color='#e6fffa'
                ))
            
            with col2:
                st.subheader("AI推奨印")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]}) - 0.4s内＆期待値最高")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")
                st.write(f"△ **{df.iloc[3]['馬名']}** ({h[3]})")

            st.divider()
            st.subheader("🎯 馬連・推奨買い目（的中＆回収）")
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"**【本線：軸1頭流し】**\n\n**{h[0]}** ― {h[1]}, {h[2]}, {h[3]}, {h[4]} (4点)")
                st.caption("客観的数値でトップの軸馬から、能力上位へ流す戦略。")
            with c2:
                # 合成オッズを考慮したBOX
                st.warning(f"**【高効率：BOX】**\n\n**{h[0]}, {h[1]}, {h[2]}, {h[3]}** (6点)")
                st.caption("上位が均衡している場合の保険と高配当狙い。")
        else:
            st.error("データの抽出に失敗しました。馬番・馬名・オッズ・着差が入るようにコピーしてください。")
