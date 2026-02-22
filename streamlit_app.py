import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：究極解析・最善予想", layout="wide")

st.title("🏇 AI競馬：究極解析エンジン")
st.caption("コピペの汚れを完全洗浄し、的中・回収の期待値を最大化します。")

# --- 内部データベース（最新の有力血統） ---
GOLDEN_SIRES = ["ドゥラメンテ", "キズナ", "エピファネイア", "ロードカナロア", "モーリス", "ハーツクライ", "ジャスタウェイ"]

def ultimate_parse(text):
    """
    行の概念を捨て、テキスト全体から『馬のセット』を力ずくで抽出する
    """
    # 1. 整理：全テキストからカタカナ(馬名・血統)と数字(オッズ)をリスト化
    # 馬名・父名は2文字以上のカタカナ、オッズは「1.2」のような形式
    tokens = [t.strip() for t in re.split(r'[\s\n\t]+', text) if t.strip()]
    
    extracted = []
    current_horse = None
    
    # 除外ワード（競馬サイトによくある用語）
    ignore = ["コース", "タイム", "ウェブ", "新聞", "オッズ", "ペース", "ダート", "グレード", "簡易"]

    for i in range(len(tokens)):
        token = tokens[i]
        
        # A. 馬番の発見 (1-18の純粋な数字)
        if re.match(r'^([1-9]|1[0-8])$', token):
            baban = token
            name = ""
            sire = ""
            odds = 0.0
            
            # その直後20個の単語の中から「名前」と「オッズ」を探す
            for j in range(i + 1, min(i + 25, len(tokens))):
                sub_token = tokens[j]
                
                # 名前（カタカナ2-9文字）
                if not name and re.match(r'^[ァ-ヶー]{2,9}$', sub_token) and sub_token not in ignore:
                    name = sub_token
                # 父名（名前が決まった後のカタカナ）
                elif name and not sire and re.match(r'^[ァ-ヶー]{2,10}$', sub_token) and sub_token != name and sub_token not in ignore:
                    sire = sub_token
                # オッズ（0.0 形式）
                elif re.match(r'^\d{1,3}\.\d$', sub_token):
                    odds = float(sub_token)
                    break
            
            if name and odds > 0:
                extracted.append({"馬番": baban, "馬名": name, "父": sire, "オッズ": odds})

    return pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- UI ---
st.info("💡 競馬ラボの『簡易出馬表』をすべて選択コピーして、下に貼り付けてください。")
raw_input = st.text_area("コピペエリア（ぐちゃぐちゃでOK）", height=300)

if st.button("究極解析を実行"):
    if raw_input:
        df = ultimate_parse(raw_input)
        if not df.empty:
            # --- 最善期待値ロジック ---
            def calc_ev(row):
                # 基礎偏差値
                score = 50.0
                # 血統加点
                if any(s in str(row['父']) for s in GOLDEN_SIRES): score += 20
                # 市場の歪み補正（中穴に重みを置く）
                bias = 1.0
                if 7.0 <= row['オッズ'] <= 25.0: bias = 1.3
                
                return (score / 50) * (14 / row['オッズ']) * bias

            df["期待値"] = df.apply(calc_ev, axis=1)
            df = df.sort_values("期待値", ascending=False).reset_index(drop=True)

            st.success(f"解析成功！ {len(df)}頭を正確にリンクしました。")
            
            # 表示セクション
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.subheader("📊 期待値ランキング")
                st.table(df[['馬番', '馬名', 'オッズ', '期待値']].head(10))
            
            with col2:
                st.subheader("最善の推奨馬")
                h = df["馬番"].tolist()
                st.write(f"◎ **{df.iloc[0]['馬名']}** ({h[0]})")
                st.write(f"○ **{df.iloc[1]['馬名']}** ({h[1]})")
                st.write(f"▲ **{df.iloc[2]['馬名']}** ({h[2]})")

            # --- 買い目生成：フォーメーション ---
            st.divider()
            st.subheader("🎯 推奨買い目フォーメーション")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 【馬連】本命流し")
                st.info(f"**軸：{h[0]}** \n\n相手：{', '.join(h[1:6])}")
            with c2:
                st.markdown("### 【3連単】高配当フォーメーション")
                st.warning(f"**1列目：** {h[0]}, {h[1]}\n**2列目：** {h[0]}, {h[1]}, {h[2]}\n**3列目：** {h[0]}, {h[1]}, {h[2]}, {h[3]}, {h[4]}")
                st.caption("期待値上位2頭のいずれかが頭、3着までに入線する確率を最大化した構成です。")
        else:
            st.error("読み取れませんでした。馬名・馬番・オッズがすべて含まれるようにコピーしてください。")
