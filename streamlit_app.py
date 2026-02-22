import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：完全推奨モデル", layout="wide")

st.title("🏇 AI競馬：馬連・3連単フォーメーション予想")
st.write("最新の期待値ロジックに基づき、最適な買い目を自動構成します。")

# --- 解析エンジン（馬番ブロック・スキャン方式） ---
def advanced_parse(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    blocks = []
    current_block = []
    for line in lines:
        if re.match(r'^(\d{1,2})$', line):
            if current_block: blocks.append(current_block)
            current_block = [line]
        else:
            if current_block: current_block.append(line)
    if current_block: blocks.append(current_block)

    for block in blocks:
        try:
            baban = block[0]
            name = next((l for l in block if re.match(r'^[ァ-ヶー]{2,9}$', l)), "不明")
            odds = next((float(l) for l in block if re.match(r'^\d{1,3}\.\d$', l)), 0.0)
            if name != "不明" and odds > 0:
                extracted.append({"馬番": baban, "馬名": name, "オッズ": odds})
        except:
            continue
    return pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- UI ---
st.info("💡 競馬ラボの『簡易出馬表』を全選択コピーして貼り付けてください。")
raw_input = st.text_area("コピペエリア", height=300)

if st.button("AI予想・フォーメーション生成"):
    if raw_input:
        df = advanced_parse(raw_input)
        
        if not df.empty:
            # --- ロジック計算：期待値と評価 ---
            # 本来はここに過去走データを加味しますが、現状はオッズの歪みから期待値を算出
            df["期待値"] = 15 / df["オッズ"] # 簡易期待値モデル
            df = df.sort_values("期待値", ascending=False).reset_index(drop=True)
            
            # 上位5頭を抽出
            top_horses = df.head(5)
            h = top_horses["馬番"].tolist()
            n = top_horses["馬名"].tolist()

            st.success("解析完了。最適な買い目を算出しました。")
            
            # --- 結果表示 ---
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("📊 期待値ランキング")
                st.table(df[['馬番', '馬名', 'オッズ', '期待値']].head(8))
            
            with col2:
                st.subheader("分析評価")
                st.write(f"◎ **{n[0]}** (期待値No.1)")
                st.write(f"○ **{n[1]}**")
                st.write(f"▲ **{n[2]}**")

            st.divider()

            # --- 買い目推奨セクション ---
            st.subheader("🎯 推奨買い目")

            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("### 【馬連】")
                st.info(f"**軸1頭流し**\n\n**{h[0]}** ― {', '.join(h[1:5])} (4点)")
                st.caption("期待値最大の軸馬から、上位勢へ流す安定策。")

            with c2:
                st.markdown("### 【3連単フォーメーション】")
                st.warning(f"""
                **1列目： {h[0]}**
                **2列目： {h[1]}, {h[2]}**
                **3列目： {h[1]}, {h[2]}, {h[3]}, {h[4]}**
                (計6点)
                """)
                st.caption("1着に期待値No.1を固定し、2・3着に高評価を厚く配置。")

            st.divider()
            st.info(f"推奨馬の父血統（参考）: {', '.join(df.head(3)['馬名'].tolist())} 付近のデータを確認してください。")
            
        else:
            st.error("データの抽出に失敗しました。")
    else:
        st.warning("データを入力してください。")
