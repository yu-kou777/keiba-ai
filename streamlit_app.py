import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random

st.set_page_config(page_title="AI競馬予想", layout="centered")

def get_data_with_retry(url):
    """
    ブロック回避のためのリトライ機能付きデータ取得
    """
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    for i in range(3): # 最大3回リトライ
        try:
            # ランダムに少し待つ
            time.sleep(random.uniform(1.0, 3.0))
            res = session.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                res.encoding = res.apparent_encoding
                return res.text
            elif res.status_code == 403:
                st.warning(f"サイトから一時的に制限を受けています(403)。{i+1}回目のリトライ...")
        except Exception as e:
            st.error(f"接続失敗: {e}")
        time.sleep(5) # 失敗時は長めに待つ
    return None

def analyze_race(race_id):
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    html = get_data_with_retry(url)
    
    if not html:
        return None
        
    soup = BeautifulSoup(html, "html.parser")
    # 馬名リンクを抽出
    horse_links = soup.find_all("a", href=re.compile(r"/db/horse/\d+/"))
    names = [l.text.strip() for l in horse_links if l.text.strip()][:18]
    
    # オッズ要素を抽出（クラス名が複数ある場合に対応）
    odds_elements = soup.find_all(class_=re.compile(r"odds"))
    odds = [o.text.strip() for o in odds_elements if re.match(r'^\d+\.\d+$', o.text.strip())][:len(names)]
    
    if names:
        df = pd.DataFrame({"馬名": names})
        if len(odds) == len(names):
            df["オッズ"] = odds
        else:
            df["オッズ"] = "取得失敗"
        return df
    return None

# --- メインUI ---
st.title("🏇 AI競馬予想システム")
st.write("ブロック対策・リトライ機能 搭載版")

# ID自動生成
date_in = st.text_input("日付", "20260207")
place_id = st.selectbox("競馬場", ["05:東京", "06:中山", "08:京都", "09:阪神"], index=2)
race_no = st.text_input("レース(2桁)", "11")
current_id = f"{date_in}{place_id[:2]}{race_no}"

if st.button("データ取得実行"):
    with st.spinner("サーバーに負荷をかけないよう慎重に取得中..."):
        result_df = analyze_race(current_id)
        
        if result_df is not None:
            st.success("取得成功！")
            st.table(result_df)
        else:
            st.error("現在、サイトへのアクセスが制限されています。10分ほど時間を空けてから再度お試しください。")
