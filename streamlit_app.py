import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：能力偏差値モデル", layout="wide")

st.title("🏇 AI競馬：的中・回収バランスモデル")
st.write("アルデバランSの反省を活かし、能力偏差値と期待値の二軸で解析します。")

# --- 高精度解析エンジン ---
def analyze_data(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    data = []
    # 馬番を起点にブロック化
    for i, line in enumerate(lines):
        if re.match(r'^(\d{1,2})$', line):
            baban = line
            # 周辺から馬名、オッズ、前走着差らしき数値を抽出
            name = next((l for l in lines[i:i+10] if re.match(r'^[ァ-ヶー]{2,9}$', l)), "不明")
            odds = next((float(l) for l in lines[i:i+15] if re.match(r'^\d{1,3}\.\d$', l)), 0.0)
            
            # 【重要】着差データの抽出（例: -0.3 や 0.5）
            margin = 0.5
            for l in lines[i:i+20]:
                match = re.search(r'([-+]\d\.\d)', l)
                if match:
                    margin = float(match.group(1))
                    break
            
            if name != "不明" and odds > 0:
                data.append({"馬番": baban, "馬名": name, "オッズ": odds, "前走着差": margin})
    return pd.DataFrame(data).drop_duplicates(subset=['馬番'])

# --- UI ---
st.info("💡 競馬ラボの『簡易出馬表』を全選択コピーして貼り付けてください。")
raw_input = st.text_area("コピペエリア", height=300)

if st.button("最新ロジックで再解析"):
    if raw_input:
        df = analyze_data(raw_input)
        if not df.empty:
            # --- 最新ロジック：能力スコアリング ---
            def calculate_power_score(row):
                score = 50 # 基準
                # 前走着差による加点（あなたのエクセルロジックを強化）
                if row['前走着差'] <= 0.0: score += 25 # 前走勝ち
                elif row['前走着差'] <= 0.4: score += 15 # 惜敗
                # オッズによるフィルター
                if row['オッズ'] < 5.0: score -= 5 # 過剰人気警戒
                return score

            df["能力スコア"] = df.apply(calculate_power_score, axis=1)
            # 期待値計算：能力に対してオッズが甘い馬を抽出
            df["期待値"] = (df["能力スコア"] / 50) * (15 / df["オッズ"])
            df = df.sort_values("期待値", ascending=False).reset_index(drop=True)

            # 結果表示
            st.success("最新の能力偏差値モデルで再構築しました。")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("📊 期待値ランキング")
                st.table(df[['馬番', '馬名', 'オッズ', '前走着差', '期待値']].head(8))
            
            with col2:
                st.subheader("推奨馬")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}**")
                st.write(f"○ **{df.iloc[1]['馬名']}**")
                st.write(f"▲ **{df.iloc[2]['馬名']}**")

            # --- 買い目推奨：フォーメーション ---
            st.divider()
            st.subheader("🎯 買い目フォーメーション案")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 【馬連】期待値重視")
                st.info(f"**軸1頭流し**\n\n**{h[0]}** ― {', '.join(h[1:5])}")
            
            with c2:
                st.markdown("### 【3連単】フォーメーション")
                st.warning(f"**1列目：** {h[0]}, {h[1]}\n\n**2列目：** {h[0]}, {h[1]}, {h[2]}\n\n**3列目：** {h[0]}, {h[1]}, {h[2]}, {h[3]}, {h[4]}")
                st.caption("上位2頭が競り合う形を想定したフォーメーション。")
        else:
            st.error("データ抽出に失敗しました。")
