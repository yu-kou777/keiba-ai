import pandas as pd

def analyze_race_data(race_card_df, training_df, past_results_df):
    """
    数学的アプローチによる3連単推奨プログラム
    """
    candidates = []

    for index, horse in race_card_df.iterrows():
        score = 0
        reasons = []

        # --- 1. タイム差ポテンシャル解析 (Time Delta Analysis) ---
        # 過去3走において、着順に関わらず「タイム差0.6秒以内」があるか
        # 物理学でいう「エネルギー準位」が高い状態
        recent_diffs = [horse['1走前着差'], horse['2走前着差'], horse['3走前着差']]
        # データが文字列の場合の処理（省略）をしつつ数値化して判定
        stable_runs = sum(1 for d in recent_diffs if d <= 0.6)
        
        if stable_runs >= 2:
            score += 30 # 非常に安定
            reasons.append("安定ポテンシャル")
        elif stable_runs == 1:
            score += 10

        # --- 2. 上がり3Fのベクトル解析 (Velocity Vector) ---
        # メンバー中、上がり3Fが1位～3位の回数
        # 末脚は「直線の長さ」に依存せず、馬の絶対能力（運動エネルギー）を示す
        if horse['3F平均'] < 37.0: # ダート/芝で閾値は変動させるべきだが今回は簡易化
            score += 20
            reasons.append("高末脚ベクトル")

        # --- 3. 調教データの評価 (Training Intensity) ---
        # 競馬ラボの調教評価を使用
        train_grade = training_df.loc[training_df['馬名'] == horse['馬名'], '評価'].values
        if 'A' in train_grade or 'S' in train_grade:
            score += 25
            reasons.append("調教特異点")

        # --- 4. 騎手×コースの係数 (Jockey Coefficient) ---
        # 勝率10%以上の騎手には重み付け
        jockey_win_rate = horse.get('騎手勝率', 0)
        if jockey_win_rate > 0.15:
            score += 15
        
        # --- 5. オッズの歪み補正 (Value Correction) ---
        # 能力指数が高いのに人気がない（単勝15倍以上など）場合
        # ここが「万馬券」を生むカオス領域
        if horse['独自指数'] >= 90 and horse['前日人気'] > 5:
            score += 15
            reasons.append("過小評価(穴)")

        candidates.append({
            '馬番': horse['馬番'],
            '馬名': horse['馬名'],
            'Score': score,
            '人気': horse['前日人気'],
            '根拠': reasons
        })

    # データフレーム化してスコア順にソート
    df_result = pd.DataFrame(candidates).sort_values('Score', ascending=False)
    return df_result

def generate_betting_slip(df_result):
    """
    3連単フォーメーション構築（少点数・高回収率モデル）
    """
    # スコア上位から役割を決定
    # 軸馬（The Singularity）：スコア1位、2位
    axis_horses = df_result.iloc[0:2]['馬番'].tolist()
    
    # 相手馬（The Variable）：スコア3位～6位
    opponent_horses = df_result.iloc[2:6]['馬番'].tolist()
    
    # 穴馬（The Chaos）：スコア7位以下だが「過小評価」フラグがある馬から1頭
    # ここでは簡易的に7位を穴とする
    hole_horse = df_result.iloc[6:7]['馬番'].tolist()

    # --- 推奨フォーメーション (Calculated Formation) ---
    # パターンA：1着固定（強気）
    # 1着: [軸1]
    # 2着: [軸2, 相手1, 相手2]
    # 3着: [軸2, 相手1, 相手2, 相手3, 穴]
    # 点数: 1 x 3 x 5 = 12点（重複除く調整必要）
    
    print("【教授の推奨：3連単フォーメーション（12点勝負）】")
    print(f"1着固定: {axis_horses[0]}")
    print(f"2着候補: {axis_horses[1]}, {opponent_horses[0]}, {opponent_horses[1]}")
    print(f"3着候補: {axis_horses[1]}, {opponent_horses[0]}, {opponent_horses[1]}, {opponent_horses[2]}, {hole_horse[0]}")
    
    # パターンB：2軸マルチ（保険）
    # [軸1] - [軸2] - [相手全通り] = 相手の数 * 2 (1着2着入れ替え)
    print("\n【教授の抑え：2頭軸マルチ（相手4頭＝24点）】")
    print(f"軸: {axis_horses[0]}, {axis_horses[1]}")
    print(f"相手: {opponent_horses} + {hole_horse}")

# ※ 実際の実行にはCSV読み込み処理が必要です
