import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：コピペ解析モード", layout="centered")

st.title("🏇 AI競馬：コピペ解析エディション")
st.write("サイトからコピーした内容を、下の枠に貼り付けてください。")

# --- データの抽出ロジック（貼り付けられた文字から抜き出す） ---
def parse_copied_text(raw_text):
    # 馬名とオッズを抽出するためのパターン
    # 競馬ラボのコピーデータから「馬番」「馬名」「オッズ」を特定
    lines = raw_text.split('\n')
    extracted_data = []
    
    # 馬名の後ろに来るオッズ（例：1.2 や 15.5）を探す
    # 競馬ラボのテキスト構造に合わせた抽出
    current_horse = None
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 馬名の特定（2〜9文字の漢字・カタカナ・アルファベット）
        # ※ここをあなたのエクセルの馬名リストと照合するように後で強化できます
        name_match = re.match(r'^[1-9][0-9]?\s+(.+)$', line) # 「1 リアレスト」のような形式
        if name_match:
            current_horse = name_match.group(1).split()[0]
            continue
            
        # オッズの特定（例：49.9 や 8.2）
        odds_match = re.search(r'^(\d+\.\d+)$', line)
        if odds_match and current_horse:
            extracted_data.append({
                "馬名": current_horse,
                "オッズ": float(odds_match.group(1))
            })
            current_horse = None # リセット

    return pd.DataFrame(extracted_data)

# --- UI部分 ---
# スマホで貼り付けやすいよう、高さを確保したテキストエリア
paste_data = st.text_area("ここにサイトの出馬表を丸ごと貼り付け", height=300, placeholder="競馬ラボの『簡易出馬表』を全選択してコピーしたものをここに貼り付けてください...")

if st.button("貼り付けデータから予想を実行"):
    if paste_data:
        with st.spinner("貼り付けられたテキストを解析中..."):
            df = parse_copied_text(paste_data)
            
            if not df.empty:
                st.success(f"{len(df)}頭の馬を検出しました！")
                
                # --- ここにエクセルのロジックを適用 ---
                # 例：AIスコアを50点として期待値を出す
                df["AIスコア"] = 50
                df["期待値"] = (df["AIスコア"] / 50) * (10 / df["オッズ"])
                
                st.subheader("📊 解析結果（期待値順）")
                st.dataframe(df.sort_values("期待値", ascending=False))
                
                # 買い目表示
                top_horses = df.sort_values("期待値", ascending=False).head(3)["馬名"].tolist()
                st.warning(f"🎯 推奨軸馬: {top_horses[0]}")
            else:
                st.error("馬のデータが見つかりませんでした。貼り付ける範囲を変えてみてください（馬名とオッズが含まれるように）。")
    else:
        st.warning("テキストエリアにデータが入力されていません。")

# --- 補足説明 ---
with st.expander("スマホでのコピー＆ペーストのコツ"):
    st.write("""
    1. 競馬ラボの『簡易出馬表』ページを開く。
    2. 画面のどこかを長押しして『すべて選択』、または馬名のあたりから下まで指でなぞって『コピー』。
    3. このアプリに戻り、上の枠の中を **1回タップしてから長押し** して『ペースト（貼り付け）』を選択。
    4. 文字が大量に入ったら、青いボタンを押す。
    """)
