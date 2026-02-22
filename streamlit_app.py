import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：スマホコピペ専用", layout="centered")

st.title("🏇 AI競馬：スマホコピペ解析")
st.write("競馬ラボ等のサイトを『全選択』して、下の枠に貼り付けてください。")

def super_parse(text):
    # 1. 改行やタブを整理
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    horses = []
    # 2. キーワードで馬名とオッズを抽出
    # 競馬ラボの構造： [馬番] [馬名] ... [オッズ]
    for i in range(len(lines)):
        # 馬番と馬名のセットを探す (例: "11 ミッキークレスト")
        name_match = re.match(r'^(\d{1,2})\s+([ァ-ヶー]{2,10})', lines[i])
        if name_match:
            baban = name_match.group(1)
            name = name_match.group(2)
            
            # その馬名の後、次の馬名が出てくるまでの間に「オッズ」があるはず
            odds = None
            for j in range(i + 1, min(i + 20, len(lines))):
                # 次の馬番が出てきたら中断
                if re.match(r'^\d{1,2}\s+[ァ-ヶー]{2,10}', lines[j]):
                    break
                # 「数字.数字」というオッズ形式を探す
                odds_match = re.search(r'^(\d{1,3}\.\d)$', lines[j])
                if odds_match:
                    odds = float(odds_match.group(1))
                    break
            
            if odds:
                horses.append({"馬番": baban, "馬名": name, "オッズ": odds})

    return pd.DataFrame(horses)

# --- UI ---
paste_data = st.text_area("ここに貼り付け（長押し→ペースト）", height=400)

if st.button("AI解析・予想を実行"):
    if paste_data:
        df = super_parse(paste_data)
        
        if not df.empty:
            st.success(f"解析成功！ {len(df)}頭を検出しました。")
            
            # --- エクセルロジック適用 ---
            # 期待値 = (AIスコア50 / 50) * (10 / オッズ)
            df["期待値"] = (10 / df["オッズ"])
            df = df.sort_values("期待値", ascending=False)
            
            st.subheader("📊 期待値ランキング")
            st.table(df) # スマホで見やすい表形式
            
            # 買い目
            top3 = df.head(3)["馬番"].tolist()
            st.warning(f"🎯 推奨BOX: {', '.join(top3)}")
        else:
            st.error("馬のデータが見つかりません。")
            st.info("【コツ】馬の名前とオッズの数字が両方入るようにコピーしてください。")
    else:
        st.warning("データを貼り付けてください。")
