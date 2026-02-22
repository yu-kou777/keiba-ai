import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random

st.set_page_config(page_title="AI競馬予想", layout="wide")

def get_detailed_data_robust(race_id):
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}
    
    try:
        time.sleep(random.uniform(2, 4))
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 1. 出馬表の行をすべて取得
        rows = soup.select("tr")
        data = []
        
        for row in rows:
            tds = row.find_all("td")
            # 競馬ラボの出馬表行は通常10〜15個のセルがある
            if len(tds) > 10:
                text_list = [td.get_text(strip=True) for td in tds]
                
                # 馬名・父・母父・オッズを「位置」ではなく「特徴」で探す
                # 馬名は3番目か4番目にあることが多い
                name = text_list[3] if len(text_list) > 3 else "不明"
                # オッズは「数字.数字」の形式を探す
                odds_val = "0.0"
                for item in text_list:
                    if re.match(r'^\d+\.\d+$', item):
                        odds_val = item
                        break
                
                # 血統情報をパース（父と母父）
                blood_td = tds[4].get_text("\n", strip=True).split("\n") if len(tds) > 4 else ["不明", "不明"]
                sire = blood_td[0] if len(blood_td) > 0 else "不明"
                bms = blood_td[1] if len(blood_td) > 1 else "不明"
                
                if name != "不明":
                    data.append({"馬名": name, "父": sire, "母父": bms, "オッズ": odds_val})
        
        if not data:
            return None
            
        return pd.DataFrame(data).drop_duplicates(subset=['馬名'])
    except Exception as e:
        st.error(f"詳細エラー: {e}")
        return None

# --- UI ---
st.title("🏇 AI競馬予想：エラー完全回避版")

race_id = st.text_input("レースID (例: 202602070811)", "202602070811")

if st.button("AI予想を実行"):
    with st.spinner("データの列を自動判別中..."):
        df = get_detailed_data_robust(race_id)
        
        if df is not None:
            # 安全に数値変換（KeyError回避）
            if "オッズ" in df.columns:
                df["オッズ"] = pd.to_numeric(df["オッズ"], errors='coerce').fillna(0.0)
                
                # スコア計算
                df["AIスコア"] = 50 # 暫定
                # 期待値計算 (0除算回避)
                df["期待値"] = df.apply(lambda x: (x["AIスコア"]/50) * (10/x["オッズ"]) if x["オッズ"] > 0 else 0, axis=1)
                
                st.success("データの読み込みと解析に成功しました！")
                st.dataframe(df.sort_values("期待値", ascending=False))
            else:
                st.error("オッズ列の特定に失敗しました。")
        else:
            st.error("馬データが見つかりません。サイト側でブロックされているか、IDが間違っています。")
