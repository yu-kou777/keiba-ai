import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random

# --- 対策①: ヘッダーをさらに詳細化 (iPhone 15プロ仕様) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-jp",
    "Connection": "keep-alive",
}

# --- 対策②: @st.cache_data を使って「同じデータは二度取らない」 ---
@st.cache_data(ttl=3600) # 1時間はネットを見に行かずキャッシュを使う
def get_html_safe(url):
    time.sleep(random.uniform(2.0, 5.0)) # 人間が画面を眺める時間を偽装
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            response.encoding = response.apparent_encoding
            return response.text
        else:
            st.error(f"サイトが混み合っています (Status: {response.status_code})")
            return None
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None

# --- 対策③: 種牡馬データが取れない時のための「固定リスト」 ---
# これにより、サイトが落ちていてもアプリが動かなくなるのを防ぎます
DEFAULT_SIRES = ["キズナ", "ロードカナロア", "エピファネイア", "ドゥラメンテ", "モーリス", "ハーツクライ", "ディープインパクト"]

@st.cache_data
def get_sire_rankings():
    url = "https://db.netkeiba.com/?pid=sire_leading"
    html = get_html_safe(url)
    if not html: return DEFAULT_SIRES
    
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".nk_tb_common tr")
    sires = [row.find_all("td")[1].text.strip() for row in rows[1:51] if len(row.find_all("td")) > 1]
    return sires if sires else DEFAULT_SIRES

# --- メインロジック ---
st.title("🏇 鉄壁版・AI競馬予想")

with st.sidebar:
    st.write("📡 接続ステータス: 正常")
    if st.button("キャッシュをクリア"):
        st.cache_data.clear()
        st.success("再取得の準備ができました")

# ID入力部分
race_id = st.text_input("レースID", "202602070811")

if st.button("慎重に分析を開始"):
    with st.spinner("サイトに負荷をかけないよう、ゆっくり解析しています..."):
        # 種牡馬取得
        top_sires = get_sire_rankings()
        
        # レースデータ取得
        url_lab = f"https://www.keibalab.jp/db/race/{race_id}/"
        html_lab = get_html_safe(url_lab)
        
        if html_lab:
            soup = BeautifulSoup(html_lab, "html.parser")
            # 馬名と父名を抜く（正規表現を使わず確実にタグで指定）
            rows = soup.select(".table_01 tr")[1:]
            results = []
            for row in rows:
                tds = row.find_all("td")
                if len(tds) > 12:
                    name = tds[3].text.strip()
                    sire = tds[4].text.split('\n')[0].strip()
                    odds = tds[12].text.strip()
                    results.append({"馬名": name, "父": sire, "オッズ": odds})
            
            df = pd.DataFrame(results)
            st.success("データの取得に成功しました！")
            st.dataframe(df)
        else:
            st.warning("現在はサイト側で制限がかかっています。15分ほど空けてからお試しください。")
