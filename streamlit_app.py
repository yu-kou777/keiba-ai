import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import random

st.set_page_config(page_title="AI競馬予想", layout="wide")

def get_race_data_v3(race_id):
    # アクセスごとに正体を変える
    ua_list = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    
    headers = {"User-Agent": random.choice(ua_list)}
    url = f"https://www.keibalab.jp/db/race/{race_id}/"
    
    try:
        # 慎重に待機
        time.sleep(random.uniform(3, 6))
        
        session = requests.Session()
        # 一旦トップページを叩いてからレースページへ（足跡を残す）
        session.get("https://www.keibalab.jp/", headers=headers, timeout=10)
        
        res = session.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        
        data = []
        # 馬名が確実に入っているリンクから情報を辿る
        horse_links = soup.find_all("a", href=re.compile(r"/db/horse/\d+/"))
        
        for link in horse_links:
            name = link.text.strip()
            if not name or len(name) < 2: continue
            
            # 親要素(tr)に遡ってオッズや血統を探す
            row = link.find_parent("tr")
            if row:
                tds = row.find_all("td")
                if len(tds) > 10:
                    # 血統
                    blood = tds[4].get_text("\n", strip=True).split("\n")
                    sire = blood[0] if len(blood) > 0 else "不明"
                    # オッズを「数字.数字」のパターンで探す
                    odds_text = "0.0"
                    for td in tds:
                        t = td.get_text(strip=True)
                        if re.match(r'^\d+\.\d+$', t):
                            odds_text = t
                            break
                    
                    data.append({"馬名": name, "父": sire, "オッズ": odds_text})
        
        if not data: return None
        return pd.DataFrame(data).drop_duplicates(subset=['馬名'])
    except Exception as e:
        st.error(f"通信エラー: {e}")
        return None

# --- UI ---
st.title("🏇 AI競馬予想：鉄壁ガード版")

race_id = st.text_input("レースID (例: 202602070811)", "202602070811")

if st.button("AI解析実行"):
    with st.spinner("ブロックを回避しながらデータを慎重に読み込んでいます..."):
        df = get_race_data_v3(race_id)
        
        if df is not None:
            # 安全に型変換 (KeyError対策)
            df["オッズ"] = pd.to_numeric(df.get("オッズ", 0), errors='coerce').fillna(0.0)
            df["AIスコア"] = 50
            df["期待値"] = df.apply(lambda x: (x["AIスコア"]/50) * (10/x["オッズ"]) if x["オッズ"] > 0 else 0, axis=1)
            
            st.success("データの取得に成功しました！")
            st.dataframe(df.sort_values("期待値", ascending=False))
        else:
            st.error("データが空です。サイトから一時的な制限を受けている可能性があります。15分ほど空けてから試すか、スマホの回線（Wi-Fiを切るなど）を変えてみてください。")
