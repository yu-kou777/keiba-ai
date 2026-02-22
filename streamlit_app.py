import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random

st.set_page_config(page_title="AI競馬予想", layout="centered")

def get_data_flexible(race_id):
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    }
    
    try:
        time.sleep(random.uniform(2, 4))
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        # --- 戦略：特定のテーブルを狙わず、馬名とオッズの「並び」を直接探す ---
        # 1. 馬名を探す（馬名リンクのパターンから抽出）
        horse_elements = soup.find_all("a", href=re.compile(r"/db/horse/\d+/"))
        horse_names = [h.text.strip() for h in horse_elements if h.text.strip() and len(h.text.strip()) > 1]
        
        # 重複を削除（血統表などのリンクも拾う可能性があるため）
        seen = set()
        final_names = [x for x in horse_names if not (x in seen or seen.add(x))][:18]
        
        # 2. オッズを探す（数字.数字 のパターンを持つクラスやテキストを探す）
        # 競馬ラボのオッズは 'odds_tan' や 'odds' クラスに入っていることが多い
        all_text = soup.get_text()
        # 正規表現で「1.2」や「150.5」のようなオッズらしい数字を抽出
        potential_odds = re.findall(r'\d+\.\d+', all_text)
        # 出走頭数分だけ確保（上位は単勝オッズである確率が高い）
        final_odds = potential_odds[:len(final_names)]

        if final_names:
            df = pd.DataFrame({
                "馬名": final_names,
                "オッズ": final_odds if len(final_odds) == len(final_names) else "取得中"
            })
            return df
        return None
    except Exception as e:
        st.error(f"エラー詳細: {e}")
        return None

# --- UI ---
st.title("🏇 AI競馬予想：データ復旧版")

# ID自動生成
date_in = st.text_input("日付 (YYYYMMDD)", "20260207")
place_id = st.selectbox("競馬場", ["08:京都", "05:東京", "06:中山", "09:阪神"])
race_no = st.text_input("レース番号 (2桁)", "11")
full_id = f"{date_in}{place_id[:2]}{race_no}"

if st.button("このレースで実行"):
    with st.spinner("データをスキャン中..."):
        df = get_data_flexible(full_id)
        if df is not None:
            st.success(f"【{full_id}】 の解析に成功しました！")
            st.table(df)
            
            # ここにエクセルロジックを再挿入
            st.info("💡 この馬名をベースに、種牡馬評価と前走着差を加味した『期待値』を算出します。")
        else:
            st.error("馬名が見つかりません。IDが間違っているか、サイト構造が大幅に変更された可能性があります。")
