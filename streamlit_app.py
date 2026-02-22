import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="AI競馬予想", layout="centered")

def get_keibalab_data_robust(race_id):
    """
    構造が変わっても抜きやすいよう、正規表現とタグ検索を組み合わせた修正版
    """
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 馬名が入っているリンク（/db/horse/数字/）をすべて探す
        horse_links = soup.find_all("a", href=re.compile(r"/db/horse/\d+/"))
        
        # 重複を除去しながら馬名リストを作成
        horse_names = []
        for link in horse_links:
            name = link.text.strip()
            if name and name not in horse_names:
                horse_names.append(name)
        
        # オッズを探す（"odds_tan" というクラス名が使われていることが多い）
        odds_elements = soup.select(".odds_tan, .odds")
        odds_list = [opt.text.strip() for opt in odds_elements if opt.text.strip()]

        # 最小限のデータを組み立てる
        if not horse_names:
            return None

        # 取得できた分だけでデータフレームを作成
        df = pd.DataFrame({"馬名": horse_names})
        # オッズが取得できていれば結合、できていなければ「調査中」とする
        if len(odds_list) >= len(horse_names):
            df["オッズ"] = odds_list[:len(horse_names)]
        else:
            df["オッズ"] = "確認中"
            
        return df

    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None

# --- メイン画面 ---
st.title("🏇 AI競馬予想システム")

# 日付やレース番号からIDを自動生成する補助機能
with st.expander("設定（レースID生成）"):
    st.write("2026年2月7日 京都11R の場合： 202602070811")
    input_date = st.text_input("日付 (YYYYMMDD)", "20260207")
    input_place = st.selectbox("場所ID", ["05:東京", "06:中山", "08:京都", "09:阪神"], index=2)
    input_race = st.text_input("レース番号 (2桁)", "11")
    auto_id = f"{input_date}{input_place[:2]}{input_race}"

race_id = st.text_input("実行するレースID", value=auto_id)

if st.button("予想を実行"):
    with st.spinner("最新データを解析中..."):
        df = get_keibalab_data_robust(race_id)
        
        if df is not None:
            st.success(f"【{race_id}】 のデータを取得しました！")
            
            # --- ここにエクセルで行っていたロジックを反映 ---
            # 例: アップロードされた「種牡馬50」などの基準をここに数式として入れる
            st.subheader("📊 予想リスト（期待値順）")
            st.table(df) # まずはリストが出るか確認
        else:
            st.error("サイトからデータを取得できませんでした。IDが正しいか、またはサイトが混み合っている可能性があります。")
