import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(page_title="AI競馬予想", layout="centered")

# --- スクレイピング関数 ---
def get_keibalab_odds(race_id):
    """
    競馬ラボの「簡易出馬表」ページから馬名とオッズを抜く
    """
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 簡易出馬表のテーブルを探す
        table = soup.find("table", class_="table_01")
        if not table:
            return None
            
        data = []
        rows = table.find_all("tr")[1:] # ヘッダー以外を取得
        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 10:
                baban = cols[1].text.strip() # 馬番
                name = cols[3].text.strip()  # 馬名
                odds = cols[12].text.strip() # 単勝オッズ
                data.append({"馬番": baban, "馬名": name, "オッズ": odds})
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"エラー発生: {e}")
        return None

# --- メイン画面 ---
st.title("🏇 AI競馬予想システム")

with st.form("input_form"):
    # 例: 202602070811 (2026年2月7日 京都11R)
    race_id = st.text_input("競馬ラボ レースIDを入力", value="202602070811")
    submitted = st.form_submit_button("データ取得＆予想")

if submitted:
    with st.spinner("競馬ラボからデータを取得中..."):
        df = get_keibalab_odds(race_id)
        
        if df is not None:
            st.success("データの取得に成功しました！")
            
            # 期待値計算のシミュレーション（ここを最新ロジックへ育てます）
            df["オッズ"] = pd.to_numeric(df["オッズ"], errors='coerce')
            df["予測勝率(%)"] = [10, 8, 15, 5, 2, 7, 6, 20, 3, 5, 4, 6, 2, 3, 2, 2][:len(df)] # 仮
            df["期待値"] = (df["予測勝率(%)"] / 100) * df["オッズ"]
            df["判定"] = df["期待値"].apply(lambda x: "★買い" if x > 1.0 else "－")
            
            st.dataframe(df.sort_values("期待値", ascending=False))
        else:
            st.error("データが見つかりませんでした。IDを確認してください。")
