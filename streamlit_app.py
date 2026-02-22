import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：スマホコピペ完全版", layout="centered")

st.title("🏇 AI競馬：コピペ解析エンジン")
st.caption("エクセル不要。サイトを全選択コピーして貼り付けるだけで予想完了。")

# --- 内部データベース：有力種牡馬 (エクセルの種牡馬50相当) ---
TOP_SIRES = ["キズナ", "エピファネイア", "ロードカナロア", "ドゥラメンテ", "ハーツクライ", 
             "モーリス", "ルーラーシップ", "ハービンジャー", "ディープインパクト", 
             "シニスターミニスタ", "ヘニーヒューズ", "ホッコータルマエ", "ドレフォン"]

def ultra_parse(text):
    """
    どんなに崩れたテキストからも、馬名とオッズをペアリングする
    """
    # 1. 馬名候補の抽出（カタカナ2〜9文字）
    # 競馬ラボの構造上、馬名の後にオッズが来ることが多い
    horse_candidates = re.findall(r'[ァ-ヶー]{2,9}', text)
    # オッズ候補の抽出（数字.数字）
    odds_candidates = re.findall(r'\d{1,3}\.\d', text)
    
    # 重複削除しつつ、実在しそうな馬名に絞り込む（「コース」「タイム」などのキーワードを除外）
    keywords = ["コース", "タイム", "ウェブ", "オッズ", "ペース", "グレード", "ダート", "出馬表"]
    valid_names = [n for n in horse_candidates if n not in keywords and len(n) >= 2]
    
    # 2. 強引にマッピング（馬名とオッズの数が合わなくても、順番に結合）
    data = []
    # 競馬サイトの並び順（馬名が先に出て、少し後にオッズが出る）を利用
    min_len = min(len(valid_names), len(odds_candidates))
    
    # 重複を防ぎつつリスト化
    seen = set()
    for i in range(len(valid_names)):
        name = valid_names[i]
        if name in seen: continue
        
        # この馬のオッズと思われるものを探索（リストの同じ位置付近から）
        odds = 0.0
        if i < len(odds_candidates):
            odds = float(odds_candidates[i])
        
        if odds > 1.0: # オッズが1.0以上なら有効
            data.append({"馬名": name, "オッズ": odds})
            seen.add(name)
            if len(data) >= 18: break # 最大頭数

    return pd.DataFrame(data)

# --- UI ---
st.info("💡 スマホで競馬ラボの『簡易出馬表』を全選択コピーして、下の枠に貼り付けてください。")
raw_text = st.text_area("コピペエリア（ここにペースト）", height=300)

if st.button("AI解析・予想スタート"):
    if raw_text:
        df = ultra_parse(raw_text)
        
        if not df.empty:
            # --- AIスコアリングロジック (エクセルなし版) ---
            def get_score(row):
                score = 50
                # 血統評価（仮：本来は父馬名が必要だが、馬名から推測するか、
                # コピペデータから『父』を抽出する精度を高める必要があります。
                # 現状はオッズと馬名のみで期待値を算出します）
                return score

            df["期待値"] = (50 / 50) * (15 / df["オッズ"])
            res_df = df.sort_values("期待値", ascending=False)
            
            st.success(f"{len(df)}頭を検出！")
            st.subheader("📊 期待値ランキング")
            st.table(res_df.head(10)) # スマホで見やすい表
            
            # 推奨買い目
            st.divider()
            st.subheader("🎯 推奨買い目")
            top_names = res_df.head(3)["馬名"].tolist()
            st.write(f"**本命◎**: {top_names[0]}")
            st.write(f"**相手○**: {top_names[1]}")
            st.write(f"**相手▲**: {top_names[2]}")
        else:
            st.error("データを読み取れませんでした。コピーする範囲を広げてみてください。")
    else:
        st.warning("データを入力してください。")
