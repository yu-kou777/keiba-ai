import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import re

st.set_page_config(page_title="AI競馬予想", layout="wide")

# --- ブロック回避の3重対策 ---
def get_html_with_evasion(url):
    # ① 正体を毎回変える（User-Agentローテーション）
    ua_list = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ]
    headers = {"User-Agent": random.choice(ua_list)}
    
    # ② 「人間がページを読む時間」を待つ
    time.sleep(random.uniform(3.0, 6.0))
    
    try:
        session = requests.Session()
        # トップページを経由して「不審者」扱いを避ける
        session.get("https://www.keibalab.jp/", headers=headers, timeout=10)
        
        response = session.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            response.encoding = response.apparent_encoding
            return response.text
        else:
            st.error(f"サイトが混み合っています（制限中）: Status {response.status_code}")
            return None
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None

def parse_race_data(html):
    if not html: return None
    soup = BeautifulSoup(html, "html.parser")
    
    # 馬名が入っているリンクを探す
    horse_links = soup.find_all("a", href=re.compile(r"/db/horse/\d+/"))
    
    data = []
    seen_names = set()
    for link in horse_links:
        name = link.text.strip()
        if name and name not in seen_names and len(name) > 1:
            # 親要素(tr)からオッズを探す
            row = link.find_parent("tr")
            odds = "0.0"
            if row:
                # 数字.数字 のパターンを持つテキストを抽出
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                for c in cells:
                    if re.match(r'^\d+\.\d+$', c):
                        odds = c
                        break
            
            data.append({"馬名": name, "オッズ": odds})
            seen_names.add(name)
            
    return pd.DataFrame(data) if data else None

# --- UI ---
st.title("🏇 AI競馬予想：鉄壁ガード版")

race_id = st.text_input("レースID (例: 202602070811)", "202602070811")

if st.button("慎重に分析を開始"):
    with st.spinner("ブロックを回避しながら、ゆっくりデータを読み込んでいます..."):
        html = get_html_with_evasion(f"https://www.keibalab.jp/db/race/{race_id}/")
        df = parse_race_data(html)
        
        if df is not None:
            st.success("データの取得に成功しました！")
            st.dataframe(df)
        else:
            st.warning("現在はサイト側で制限がかかっています。15分ほど空けてからお試しください。")
            st.info("💡 対策案：スマホのテザリングに切り替えてIPを変えると突破できることがあります。")
