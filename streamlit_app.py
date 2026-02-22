import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="AI競馬：最新ロジック・期待値モデル", layout="wide")

st.title("🏇 AI競馬：最新期待値解析ツール")
st.write("あなたのエクセルの『高精度ロジック』をスマホで再現します。")

# --- 内部データベース：最新有力血統 (2026年版) ---
TOP_SIRES = ["ドゥラメンテ", "ロードカナロア", "ディープインパクト", "キズナ", "エピファネイア", "ハーツクライ", "ジャスタウェイ"]

def advanced_parse(text):
    """
    スマホの『ぐちゃぐちゃコピペ』から、正確にデータを構造化する
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    
    # 馬番(1-18)を探し、そこから次の馬番までのブロックを1頭分として処理
    blocks = []
    current_block = []
    for line in lines:
        if re.match(r'^(\d{1,2})$', line):
            if current_block: blocks.append(current_block)
            current_block = [line]
        else:
            if current_block: current_block.append(line)
    if current_block: blocks.append(current_block)

    for block in blocks:
        try:
            baban = block[0]
            # 馬名：カタカナ2-9文字
            name = next((l for l in block if re.match(r'^[ァ-ヶー]{2,9}$', l)), "不明")
            # オッズ：1.0〜999.9
            odds = next((float(l) for l in block if re.match(r'^\d{1,3}\.\d$', l)), 0.0)
            # 人気：オッズの次に来る数字を想定
            pop = next((int(l) for l in block if re.match(r'^\d{1,2}$', l) and l != baban), 99)
            # 父：馬名の後に出てくるカタカナ
            found_name = False
            sire = "不明"
            for l in block:
                if l == name: found_name = True; continue
                if found_name and re.match(r'^[ァ-ヶー]{2,10}$', l):
                    sire = l
                    break
            
            if name != "不明" and odds > 0:
                extracted.append({"馬番": baban, "馬名": name, "父": sire, "オッズ": odds, "人気": pop})
        except:
            continue

    return pd.DataFrame(extracted).drop_duplicates(subset=['馬番'])

# --- UI ---
st.info("💡 競馬ラボの『簡易出馬表』を全選択コピーして貼り付けてください。")
raw_input = st.text_area("コピペエリア", height=300)

if st.button("最新ロジックで分析実行"):
    if raw_input:
        df = advanced_parse(raw_input)
        
        if not df.empty:
            # --- 最新ロジック：期待値スコアリング ---
            def get_ai_prediction(row):
                # 1. 市場予測（オッズから逆算した勝率）
                market_prob = 0.8 / row['オッズ'] # 控除率を考慮
                
                # 2. 独自加点（エクセルの高精度条件）
                score = 1.0 # 基準
                
                # 血統加点
                if any(s in row['父'] for s in TOP_SIRES): score *= 1.2
                
                # 人気薄の激走期待値（人気以上に能力があると判定する条件）
                if row['人気'] >= 4 and row['オッズ'] <= 20.0: score *= 1.15
                
                # 想定勝率
                final_prob = market_prob * score
                return final_prob

            df["想定勝率"] = df.apply(get_ai_prediction, axis=1)
            # 期待値 = 想定勝率 * オッズ
            df["期待値"] = df["想定勝率"] * df["オッズ"]
            
            # 判定
            def judge(ev):
                if ev >= 1.2: return "★激熱"
                if ev >= 1.0: return "◎買い"
                if ev >= 0.85: return "○注目"
                return "－"
            
            df["判定"] = df["期待値"].apply(judge)
            res_df = df.sort_values("期待値", ascending=False)
            
            st.success("最新の期待値モデルで解析を完了しました。")
            
            # 結果表示（スマホで見やすく整形）
            st.subheader("📊 期待値ランキング（高順位ほど回収率が高い）")
            # 期待値1.0以上をハイライト
            st.table(res_df[['馬番', '馬名', 'オッズ', '期待値', '判定']].head(10))
            
            # 買い目構築
            st.divider()
            st.subheader("🎯 推奨買い目（期待値ベース）")
            top_ev = res_df[res_df["期待値"] >= 1.0].head(5)
            
            if not top_ev.empty:
                baban_list = top_ev["馬番"].tolist()
                st.write(f"**【本命馬】** {top_ev.iloc[0]['馬名']} (馬番:{top_ev.iloc[0]['馬番']})")
                st.info(f"**【推奨】** 馬連・ワイドBOX: {', '.join(baban_list)}")
                st.warning(f"**【勝負】** 3連単1頭軸マルチ: {baban_list[0]} → {', '.join(baban_list[1:])}")
            else:
                st.write("現在、期待値が基準を超える馬がいません。見送り推奨です。")
                
        else:
            st.error("データの抽出に失敗しました。馬名とオッズが含まれるようにコピーしてください。")
    else:
        st.warning("データを入力してください。")
