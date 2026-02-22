import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="完全自立型AI競馬予想", layout="centered")

st.title("🏇 AI競馬予想：コピペ完結エディション")
st.write("エクセル不要！スマホサイトのデータを貼り付けるだけで予想します。")

# --- 内部データベース：最新の有力種牡馬 (エクセルの種牡馬50相当) ---
# 2026年現在の主要な種牡馬リストをプログラムに持たせます
TOP_SIRES = [
    "キズナ", "エピファネイア", "ロードカナロア", "ドゥラメンテ", "ハーツクライ", 
    "モーリス", "ルーラーシップ", "ハービンジャー", "ディープインパクト", 
    "シニスターミニスタ", "ヘニーヒューズ", "ホッコータルマエ", "ドレフォン"
]

def analyze_pasted_text(text):
    """
    ぐちゃぐちゃな貼り付けテキストから、馬名・父名・オッズを抽出する
    """
    # 馬番・馬名を見つけるパターン
    horse_pattern = re.compile(r'(\d{1,2})\s+([ァ-ヶー]{2,9})')
    # オッズを見つけるパターン
    odds_pattern = re.compile(r'(\d{1,3}\.\d)$')
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    results = []
    
    for i, line in enumerate(lines):
        match = horse_pattern.search(line)
        if match:
            baban = match.group(1)
            name = match.group(2)
            
            # 馬名の周辺から「父名」と「オッズ」を探索
            sire = "不明"
            odds = 0.0
            
            # 周囲10行を探索
            for j in range(max(0, i-2), min(len(lines), i+10)):
                search_line = lines[j]
                # 父名の判定（カタカナ2文字以上、かつ馬名とは違う行）
                if sire == "不明" and re.search(r'[ァ-ヶー]{2,10}', search_line) and name not in search_line:
                    sire = search_line
                # オッズの判定
                o_match = odds_pattern.search(search_line)
                if o_match:
                    odds = float(o_match.group(1))
            
            if odds > 0:
                results.append({"馬番": baban, "馬名": name, "父": sire, "オッズ": odds})

    return pd.DataFrame(results).drop_duplicates(subset=['馬名'])

# --- UI ---
st.info("💡 競馬ラボ等の『簡易出馬表』を全選択してコピーし、下に貼り付けてください。")
raw_input = st.text_area("コピペエリア", height=300)

if st.button("AI予想を実行"):
    if raw_input:
        df = analyze_pasted_text(raw_input)
        
        if not df.empty:
            # --- AIスコアリングロジック ---
            def calculate_score(row):
                score = 50 # 基本点
                # 血統加点
                for top_sire in TOP_SIRES:
                    if top_sire in str(row['父']):
                        score += 20
                        break
                # オッズによる期待値加点（7倍〜20倍の中穴を厚遇）
                if 7.0 <= row['オッズ'] <= 25.0:
                    score += 10
                return score

            df["AIスコア"] = df.apply(calculate_score, axis=1)
            # 期待値 = (スコア/基準) / オッズ ※数値が大きいほど「買い」
            df["期待値"] = (df["AIスコア"] / 50) * (15 / df["オッズ"])
            
            # 結果表示
            st.success(f"{len(df)}頭を解析しました！")
            res_df = df.sort_values("期待値", ascending=False)
            
            st.subheader("📊 期待値ランキング（上位ほど推奨）")
            st.table(res_df[['馬番', '馬名', '父', 'オッズ', '期待値']].head(10))
            
            # 買い目生成
            top_3 = res_df.head(3)
            st.divider()
            st.subheader("🎯 推奨買い目")
            st.write(f"**◎ 本命:** {top_3.iloc[0]['馬名']} ({top_3.iloc[0]['馬番']})")
            st.write(f"**馬連BOX:** {', '.join(top_3['馬番'].tolist())}")
            
        else:
            st.error("馬のデータが見つかりません。コピーする範囲を広げてみてください。")
    else:
        st.warning("データを貼り付けてください。")
