#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Driving Dynamics Analyzer (DDA)  --  Version 1.5
=================================================

仕様書 "Driving Dynamics Analyzer プログラム仕様書 Version 1.0" に基づく実装。
作成者: JL7KHN

Version 1.5 での主な変更点 (Sensor Server起動導線の見直し):
    [課題] 従来はセットアップ画面に「📡 Sensor Serverアプリを起動」ボタンを常設していたが、
        Chromeの仕様上(BROWSABLEカテゴリ非対応アプリはintent経由で起動できない)、多くの
        環境でこのボタンは実質的に機能せず、押しても何も起きない/失敗案内が出るだけで
        あった。また、DDA起動時に1回だけ行う接続テスト(test_connect())の結果が
        「シミュレーションモード」だった場合、その後スマホでSensor Serverを起動しても
        画面上はその事実に気付きにくかった。
    [対策] 起動直後に常設していた起動ボタンを廃止し、代わりにセットアップ画面に
        「Sensor Serverアプリが起動していません」という明確なワーニングを表示するように
        変更した。ワーニングは /api/state (SensorInterface.simulate/診断情報)を数秒おきに
        ポーリングして判定し、Sensor Serverアプリ側で配信が開始され接続が確立できた
        場合は自動的に消える(手動でのページ再読み込みは不要)。ワーニング内には
        手動起動の案内・パッケージ名・F-Droidリンクを引き続き明記する。

Version 1.4 での主な変更点 (スコアリングの偏り是正 + レポート強化):
    [課題] 従来のスコアリングは「100点からの線形減点」のみで構成されており、
        閾値をわずかに超えただけでも急激にスコアが落ちる一方、イベントが無い
        穏やかな区間でも基礎点が90点止まりで、優良運転を積極的に加点する仕組みが
        無かったため、「下がりやすいが加算されにくい」という偏った体感になっていた。
    [対策] ScoringEngineを以下の3点で是正した(危険側=大幅な閾値超過で0点に達する
        境界は従来と同一のまま変更していない。安全性の判断基準は変えていない):
        1) 減点カーブをべき乗(Config.SCORE_SOFTEN_POWER, 既定1.6)で緩和し、閾値を
           わずかに超えた程度の軽微な逸脱では大きく減点しないようにした。
        2) イベント非該当(穏やかな)区間の基礎点をConfig.SCORE_NEUTRAL_FLOORとして
           90→96へ引き上げ、危険な挙動が無かったこと自体をより高く評価するようにした。
        3) セッションを通じて高スコア(Config.SCORE_EXCELLENCE_THRESHOLD以上)を維持
           できた場合、その割合に応じて総合スコアへ「優良運転ボーナス」
           (Config.SCORE_EXCELLENCE_BONUS_MAX、既定+8点上限)を加点する仕組みを新設した。
        いずれも設定パネル(⚙)から調整可能(TUNABLE_PARAMSに追加)。
    [レポート] 走行終了後にAI分析用txtレポート(report/DDA_Report_v{Ver}_*.txt)を
        必ず出力するよう、内部の各セクション生成・ファイル書き込みを個別にフォールバック
        保護し、万一詳細生成に失敗しても最低限のサマリーを含むレポートが必ず1つ残る
        ようにした。ファイル名にもバージョン番号を含めるようにした。
    [簡易レポート画面] 走行終了直後の画面(簡易レポート)の情報量を増やし、
        ドライバー/車両/モード/走行時間、イベント種別ごとの件数・平均スコア、
        スコア内訳(G制御/ジャーク/荷重移動/整定性/一貫性)の平均値、優良運転ボーナスの
        内訳を追加表示するようにした。あわせて、スコア内訳(今回走行)と運転特性プロファイル
        (蓄積データ)の2種類をレーダーチャート(Canvas, 追加ライブラリ不要)で可視化できる
        ようにした。
    [表示] 画面ヘッダーおよび簡易レポート画面にバージョン番号を明記した
        (Config.APP_VERSION、既存のUI要素で自動反映)。

Version 1.3 での主な変更点 (タイヤグリップ限界検出のロバスト性強化):
    タイヤロック/グリップ喪失検出(TireLockDetector)を、縦横独立の固定閾値による
    二値判定から、摩擦円(トラクションサークル)に基づく連続的な「グリップ利用率」
    (TUR: Traction Utilization Ratio)評価へと全面刷新した。[1]〜[7]は各対策の対応番号。
    [1] 摩擦円ベースの連成評価: 縦横Gを合成したTUR = sqrt((Gx/mu_long)^2+(Gy/mu_lat)^2)
        を主判定に採用。トレイルブレーキング等、各軸単独では閾値未満でも合成では
        限界に達している状況を検出できるようにした。TURは検出の有無に関わらず常時
        算出し、UI(現在値・セッション最高値)とイベント/レポートに反映する。
    [2] 適応グリップ包絡線: mu_long_max/mu_lat_maxを固定値ではなく、蓄積走行ログの
        制動/コーナリングG実績値の上側パーセンタイル(既定95%点)から
        ドライバー×車両×モード毎に推定し、既存の適応キャリブレーション基盤
        (DrivingProfileAnalyzer/AdaptiveProfileStore)へ統合した。
    [3] 荷重移動バイアス: 制動によるフロントへの荷重移動量(lt_long)に応じて、
        後輪ロック判定のヨー角速度閾値を動的に下げ、リアが軽くなり後輪が
        ロックしやすくなる物理傾向を反映した。
    [4] 過渡区間の傾き判定: 従来の定常円旋回近似(ヨー比)はコーナー入口/
        トレイルブレーキングのような過渡状態で誤差が出ることが分かっていたため、
        ヨー角加速度から定常/過渡を判別し、過渡区間ではGyの立ち上がりに対する
        ヨーレートの追従度(勾配比)でアンダーステア傾向を評価するようにした。
    [5] ジャダー非依存のグリップ頭打ち検出: ハイドロプレーニング等、ABS的な脈動
        (ジャダー)を伴わない滑らかな滑走を、TURが高水準にある状態でのG伸びの
        頭打ち/低下(GRIP_PLATEAU)として独立に検出し、ジャダー検出とOR運用する
        ことで単一障害点を減らした。
    [6] GPS/IMUクロスバリデーション: GPS速度の実減速とIMU積分から予測される
        減速を比較し、タイヤの摩擦力が速度低下に変換されていない(=滑走)兆候を
        独立した物理的証拠として検出信頼度に反映した。
    [7] 受信レートゲーティング: センサ受信品質がGOOD未満(バースト/欠損あり)の間は
        ジャダーRMSに基づく前輪/後輪ロック分類のみを無効化し、その他の検出系統
        (ジャーク・TUR・プラトー)は継続動作させる粒度の細かいゲーティングとした。
    上記に伴い、DrivingEventに peak_tur(イベント内最大グリップ利用率)を追加し、
    走行終了後のレポート(report/*.txt)にもセッション最高グリップ利用率と
    使用したmu_long_max/mu_lat_max(適応値/既定値)を明記するようにした。

Version 1.2 での主な変更点:
    - 走行終了後、外部LLM(Claude/ChatGPT等)にそのまま読み込ませて分析させるための
      txtレポートを自動生成(本体スクリプトと同じフォルダ配下の report/ に保存、
      ファイル名は日付時刻付き、7日で自動削除)。GPS座標・時刻を明記し、読み込んだAI
      自身が道路形状や当時の天候を調べたうえで分析できるようにプロンプトをテンプレ化。
      レポート画面からダウンロード可能。
    - 画面右上に設定(⚙)ボタンを追加。フィルタ時定数・ジャーク/荷重移動の採点基準など
      主要パラメータの調整と、ドライバー×車両×モード毎の自動補正(学習)進捗状況の
      確認ができる(次回セッション開始時から反映、config_overrides.jsonへ永続化)。
    - LowPassFilterのtauがモジュール読み込み時の値に固定されてしまい、設定変更が
      新しいセッションにも反映されない潜在バグを修正。
    - 画面に現在のバージョンと作成者(JL7KHN)を表示。

Version 1.1 での主な変更点:
    - ドライバー選択の編集・削除機能を追加(車両と同様の操作性に統一)、登録上限を2名に修正
    - センサ時刻スキュー・受信品質(バースト受信/欠損)に基づく信頼度(confidence)を
      イベント/周期統計/総合スコアに反映(加重平均化)。データが無い場合は "N/A" を返す
    - ヨーレートをデバイス座標系ではなく車両座標系(姿勢補正後)で算出するよう修正
    - GPS速度の鮮度チェックを追加(タイヤ限界判定での誤用を防止)
    - イベント確定処理・周期集計・ドライバーDB保存(ファイルI/O)をロック保持中から
      ロック解放後に移し、HTTPポーリング/SSE応答のブロッキングを解消
    - 取得ループのスリープをドリフト補正方式に変更(絶対時刻基準)
    - センサ長時間無応答時に解析処理を一時停止し、凍結データからの誤イベント生成を防止。
      復帰時にイベント検出の内部状態・波形バッファを破棄してから再開(ギャップ跨ぎの
      誤イベント連結を防止)
    - ポーリング(150ms fetch)をServer-Sent Events (SSE) に置き換え、通信回数を削減
      (非対応環境向けにポーリングへの自動フォールバックあり)
    - イベントスコアの内訳(G制御/ジャーク/荷重移動/整定性/一貫性)を算出しUIに表示

対象環境:
    Android + Pydroid 3 (推奨: Google Pixel 8a, 縦画面)
    Windows / Raspberry Pi でも実行可能 (センサ未接続時はシミュレーションモードで動作)

構成 (1ファイル / 論理モジュール分割):
    1.  Configuration
    2.  Vehicle Database
    3.  Driver Database
    4.  Sensor Interface
    5.  Calibration
    6.  Sensor Fusion
    7.  Coordinate Transformation
    8.  Signal Processing
    9.  Vehicle Dynamics
    10. Event Detection
    11. Event Analysis
    12. Periodic Analysis
    13. Scoring Engine
    14. Driver Behavior Analysis
    15. Data Storage
    16. HTML Generator
    17. HTTP/SSE Interface (簡易 HTTP + Server-Sent Events)
    18. Main Control

起動:
    python DrivingAnalyzer.py
    起動後、表示される http://<ip>:8080/ にスマートフォンのブラウザでアクセスする。

依存:
    標準ライブラリのみで動作する。実センサへはスマホの「Sensor Server」アプリ経由で接続し、
    無ければ自動的にシミュレーションモードへフォールバックする。
"""

import base64
import hashlib
import json
import math
import os
import socket
import struct
import threading
import time
import uuid
import webbrowser
from urllib.parse import urlparse, parse_qs, quote
from collections import deque
from dataclasses import dataclass, field, asdict, fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, List, Dict, Any, Tuple

# =========================================================================
# 0. Android/APK 対応 (Version 1.5.1 追加分)
# =========================================================================
# 本ファイルはWindows/Raspberry Pi/Pydroid3に加え、buildozer(python-for-android)で
# ビルドしたAndroid APKからも同一ロジックで動作させる。APK環境では __file__ が指す
# 場所(APKから展開された private データ領域)が機種/Androidバージョンによっては
# 書き込みに制約がある場合があるため、実際に書き込み可能なディレクトリを起動時に
# 検証してデータ保存先(APP_DIR)として採用する。判定順序:
#   1. python-for-androidが提供する android.storage.app_storage_path()
#      (アプリ専用の書き込み可能領域。Android実機で最優先)
#   2. 従来通り __file__ の場所 (Windows/Raspberry Pi/Pydroid3ではこれが使われる)
# どちらも書き込みテストに失敗した場合は最終手段として(2)にフォールバックする
# (スコアリング・センサー融合・検出ロジック等、既存の解析処理には一切手を加えていない)。
def _resolve_app_dir() -> str:
    candidates = []
    try:
        from android.storage import app_storage_path  # type: ignore
        candidates.append(app_storage_path())
    except Exception:
        pass
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            probe = os.path.join(c, ".dda_write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return c
        except Exception:
            continue
    return os.path.dirname(os.path.abspath(__file__))


def _is_android() -> bool:
    """python-for-androidでビルドされたAPK内で実行中かどうかを判定する。"""
    try:
        import android  # noqa: F401
        return True
    except Exception:
        return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ


# =========================================================================
# 1. Configuration
# =========================================================================

class Config:
    """モードごとの閾値・スコア係数など、システム全体の定数を保持する。"""

    GRAVITY = 9.80665  # m/s^2

    # 内部解析周期の目標 (Hz) -- 実サンプリングレートは端末依存、dtは実測値を使用する
    TARGET_HZ_MIN = 50
    TARGET_HZ_MAX = 100

    # --- キャリブレーション (§15) ---
    # 仕様書の初期値例 (σa,max=0.015G, ωmax=2deg/s) は実機の残留ジャイロバイアス
    # (安価なMEMSジャイロでは1〜2deg/s程度残ることが珍しくない) に対して厳しすぎ、
    # キャリブレーションが完了しないケースがあったため、やや緩和し静止確認時間を延長した。
    STATIC_ACCEL_STD_MAX = 0.015          # G
    STATIC_GYRO_MAX_DEG_S = 3.5           # deg/s (仕様書初期値2.0deg/sから緩和)
    STATIC_CONFIRM_TIME_SEC = 3.0         # sec (仕様書初期値2.5secから延長し安定化)

    # --- フィルタ時定数 (§22) ---
    LPF_TAU_SEC = 0.10

    # --- dt異常判定 (§86) ---
    DT_MIN = 1.0 / 300.0   # 300Hz以上は異常とみなす
    DT_MAX = 0.5           # 0.5秒以上の欠測は異常

    # --- イベント閾値 (§34) : {mode: (trigger_G, ) } ---
    EVENT_TRIGGER_G = {
        "STREET":   0.25,
        "MOUNTAIN": 0.30,
        "CIRCUIT":  0.40,
    }
    EVENT_RELEASE_RATIO = 0.5   # Release = Trigger * 0.5

    # --- Pre/Post trigger buffer (§41) ---
    PRE_TRIGGER_SEC = 2.0
    POST_TRIGGER_SEC = 3.0

    # --- 30秒周期解析 (§50) ---
    PERIODIC_WINDOW_SEC = 30.0

    # --- スコア更新のチャタリング防止 (§55) ---
    MIN_EVENT_HOLD_SEC = 0.5
    EVENT_COOLDOWN_SEC = 0.75

    # --- 総合スコア重み (§53) ---
    ALPHA_PERIODIC = 0.6   # Periodic 60% / Event 40%

    # --- モード別 30秒スコア係数 (§52) ---
    PERIODIC_WEIGHTS = {
        "STREET":   dict(smooth=0.25, brake=0.20, accel=0.15, corner=0.15, load=0.15, consistency=0.10),
        "MOUNTAIN": dict(smooth=0.15, brake=0.15, accel=0.10, corner=0.25, load=0.20, consistency=0.15),
        "CIRCUIT":  dict(smooth=0.10, brake=0.20, accel=0.15, corner=0.25, load=0.20, consistency=0.10),
    }

    # --- クセ判定 (§56, §64) ---
    MIN_EVENTS_FOR_HABIT = 5
    RECOMMENDED_EVENTS_FOR_HABIT = 10
    HABIT_CONFIDENCE_TARGET_N = 20

    # --- 運転指紋 EMA (§62) ---
    FINGERPRINT_EMA_LAMBDA = 0.1

    # --- Jerk / 荷重移動の正規化上限 (スコア計算用の基準値) ---
    JERK_LIMIT_G_PER_S = 3.0
    # 荷重移動は「静荷重に対する移動割合(無次元, ΔW/W = G*h/L)」で統一評価する。
    # これは車両質量に依存せず、重心高の入力有無に関わらず同一スケールになる。
    #   典型値: 0.3G制動で約0.06, 0.5G旋回で約0.17, 1.0Gで約0.19〜0.33
    LOAD_TRANSFER_RATE_LIMIT = 2.0     # [1/s] 荷重移動係数の変化率の攻撃的側基準
    LOAD_TRANSFER_LIMIT_SUM = 0.7      # 前後+左右合成ピーク係数の基準 (周期スコア用)

    # --- 車両重心高が未入力の場合の正規化基準 (§29) ---
    REF_CG_HEIGHT_MM = 500.0

    # --- 路面外乱 (うねり・段差) リジェクト ---
    # 重力除去後のGz(垂直方向, 本来はほぼ0)を高域通過的に監視し、
    # 短時間RMSが閾値を超えた区間を「路面外乱」として扱う。
    ROAD_FILTER_ENABLED = True
    ROAD_VIB_TAU_FAST_SEC = 0.03      # 振動抽出用の速いLPF時定数
    ROAD_VIB_TAU_SLOW_SEC = 0.35      # 振動抽出用の遅いLPF時定数 (基準ライン)
    ROAD_VIB_WINDOW_SEC = 0.20        # RMS評価窓
    ROAD_VIB_HOLD_SEC = 0.25          # 一度検出したら最低この時間は「荒れ」を維持
    # 路面外乱パラメータはモード別。サーキットは縁石・路面うねりが「走行の一部」で
    # 常時振動が大きいため、閾値を上げて過検出を防ぎ、かつ適応平滑化を弱める
    # (=バンプを踏みながらの本物の高G旋回でピークGを削らない)。イベント抑制も
    # サーキットでは無効化し、縁石を踏んだ瞬間の正当なブレーキ/旋回を取りこぼさない。
    ROAD_VIB_RMS_THRESHOLD_G_BY_MODE = {"STREET": 0.06, "MOUNTAIN": 0.08, "CIRCUIT": 0.13}
    ROAD_ADAPTIVE_TAU_BOOST_BY_MODE = {"STREET": 3.0, "MOUNTAIN": 2.0, "CIRCUIT": 1.0}
    ROAD_SUPPRESS_EVENTS_BY_MODE = {"STREET": True, "MOUNTAIN": True, "CIRCUIT": False}
    ROAD_VIB_RMS_THRESHOLD_G = 0.06   # 後方互換用デフォルト (モード未指定時)
    ROAD_ADAPTIVE_TAU_BOOST = 3.0     # 後方互換用デフォルト

    # --- タイヤロック / グリップ喪失 検出 (主にCIRCUIT) ---
    # スマホIMU(加速度+ジャイロ)とGPS速度のみで、車輪速センサ無しに推定する簡易検出。
    # 誤検出を避けるため既定ではCIRCUITモードでのみ有効。
    TIRE_LOCK_ENABLED = True
    TIRE_LOCK_MODES = ("CIRCUIT",)
    # 制動ロック(ABSジャダー/スキッド)
    LOCK_BRAKE_G = 0.55            # これ以上の減速中のみ制動ロックを判定
    LOCK_JUDDER_TAU_FAST = 0.008   # 縦Gの高周波(ジャダー)抽出用の速いLPF時定数(~20Hz)
    LOCK_JUDDER_TAU_SLOW = 0.20    # 縦Gの基準線用の遅いLPF時定数
    LOCK_JUDDER_WIN_SEC = 0.25     # ジャダーRMS評価窓
    LOCK_JUDDER_RMS_G = 0.05       # 縦G高周波RMSの閾値(平常時~0.01に対し余裕5倍)
    LOCK_COLLAPSE_JERK = 4.0       # 減速中に|Gx|が急減(グリップ喪失)するjerk閾値[G/s]
    # 制動ロック時の前後輪判定: ロック中に発生するヨー角速度で切り分ける。
    #   前輪ロック → 操舵不能で直進(ヨー小), 後輪ロック → 車尾が流れヨー急増。
    LOCK_REAR_YAW_DEG_S = 12.0     # これ以上のヨーを伴う制動ロック → 後輪ロック(オーバー傾向)
    # コーナリング時のグリップ喪失(アンダー/オーバー)
    SLIP_LAT_G = 0.5               # これ以上の横G中のみ判定
    SLIP_MIN_SPEED_MPS = 8.0       # 期待ヨーレート算出に必要な最低速度[m/s]
    SLIP_YAW_RATIO_UNDER = 0.6     # 実測ヨー/期待ヨー がこの値未満 → アンダーステア傾向
    SLIP_YAW_RATIO_OVER = 1.6      # 実測ヨー/期待ヨー がこの値超  → オーバーステア傾向
    SLIP_YAW_SPIKE_DEG_S = 35.0    # 速度不明時のフォールバック: ヨー角速度スパイク閾値
    TIRE_LOCK_HOLD_SEC = 0.6       # 一度検出したら最低この時間は警告を保持
    ROAD_EVENT_CONFIDENCE_PENALTY = 0.6  # 影響度100%のイベントの信頼度低下係数

    # --- [1][3] 摩擦円(トラクションサークル)ベースの連成グリップ評価 ---
    # 縦横を独立閾値で判定するのではなく、"今どれだけタイヤの摩擦力を使い切って
    # いるか" を Traction Utilization Ratio (TUR) という連続量で評価する。
    #   TUR = sqrt( (Gx/mu_long_max)^2 + (Gy/mu_lat_max)^2 )
    # TUR>=1.0 で理論上のグリップ上限(摩擦円の外周)に到達。GRIP_TUR_WARN以上を
    # 「限界接近」の一次ゲートとして使い、そのうえで縦横それぞれの詳細判定
    # (前輪/後輪ロック、アンダー/オーバー等)へ進む。LOCK_BRAKE_G/SLIP_LAT_G は
    # mu推定が不当に小さい場合の過検出を防ぐ下限フロアとして引き続き使用する。
    GRIP_TUR_WARN = 0.85     # この比率を超えたら「グリップ限界接近」として評価対象にする
    GRIP_TUR_LIMIT = 1.00    # この比率を超えたら理論上の限界到達/超過 (UI表示の閾値)
    # mu_long_max / mu_lat_max の既定値 ([2]の適応推定が効くまでのフォールバック)。
    # 一般公道タイヤの実用的なグリップレンジを想定した保守的な初期値。
    GRIP_MU_LONG_MAX_DEFAULT = 0.75   # G (制動方向)
    GRIP_MU_LAT_MAX_DEFAULT = 0.70    # G (旋回方向、一般に制動よりやや小さい)

    # --- [2] 適応グリップ包絡線 (蓄積ログの上側パーセンタイルから mu_max を推定) ---
    # kartracingtelemetry等のテレメトリ解析で使われる「実測パーセンタイル方式の
    # グリップ包絡線」と同じ考え方。固定μではなく、そのドライバー・車両・タイヤ・
    # 路面条件で実際に記録された最大級のGを「実証済みグリップ上限」とみなす。
    GRIP_ENVELOPE_PCTL = 95              # 実績グリップの上側%点をmu_maxの推定値とする
    GRIP_MU_LONG_CLAMP = (0.35, 1.3)     # 推定値のクランプ範囲 [G] (異常値の暴走防止)
    GRIP_MU_LAT_CLAMP = (0.35, 1.3)

    # --- [3] 荷重移動を用いた前後軸グリップ配分バイアス ---
    # 制動でフロントに荷重移動するほど、リアは軽くなりロックしやすくなる。
    # lt_long(前後荷重移動係数)に応じて後輪ロック判定のヨー閾値を動的に下げる
    # (=より小さいヨーでも後輪ロック傾向ありと判定する)。
    LOCK_REAR_YAW_LT_SENSITIVITY = 0.5   # lt_longに応じてヨー閾値を最大何割下げるか(0-1)
    LOCK_REAR_YAW_LT_REF = 0.30          # この荷重移動係数で下げ幅が最大(以降は頭打ち)
    LOCK_REAR_YAW_MIN_DEG_S = 5.0        # ヨー閾値の下限 (下げすぎによる誤検出防止)

    # --- [4] 過渡区間(トレイルブレーキング/コーナー入口)での傾き基準判定 ---
    # 定常円旋回近似(ヨー比方式)は「ヨーレートが横Gに追従し切った定常状態」でしか
    # 精度が出ないとコード内でも既知の限界としていた。ヨー角加速度が大きい過渡区間
    # では、比率ではなく「Gyの立ち上がりにヨーレートが追従できているか」を短時間の
    # 傾き(勾配)で評価する方がロバスト。
    YAW_ACCEL_STEADY_DEG_S2 = 40.0   # これ未満なら「定常」とみなし従来のratio方式を使う
    TRANSIENT_GY_MIN_G_PER_S = 0.3   # この程度以上Gyが立ち上がっている区間のみ過渡評価の対象
    TRANSIENT_UNDER_RATIO = 0.5      # 過渡時: ヨー角加速度/期待ヨー角加速度 がこの比未満→アンダー傾向

    # --- [5] ジャダーを伴わない「グリップ頭打ち」検出 (ハイドロプレーニング等) ---
    # ドライバーがまだ強く操作入力を続けている(=合成Gが十分な勾配で立ち上がって
    # きた)にも関わらず、直近の伸びが頭打ち/低下に転じ、かつ既にTURが高水準に
    # あるケースを、ジャダーRMSに依存しない独立系統として検出する。
    PLATEAU_BUILDUP_MIN_SLOPE_G_S = 0.8   # この勾配以上で「まだ強めている」とみなす立ち上がり基準
    PLATEAU_WIN_SEC = 0.30                # 直近勾配の評価窓
    PLATEAU_MIN_TUR = 0.75                # このTUR以上でのみ評価 (低G域の頭打ちは無視)
    PLATEAU_HOLD_SEC = 0.5

    # --- [6] GPS速度とIMU積分のクロスバリデーション (制動時の速度整合性チェック) ---
    # 強い制動G中、GPS速度から求めた実減速がIMU積分による予測減速より明らかに
    # 小さい場合、摩擦力が速度低下に変換されていない(=タイヤが滑っている)ことを
    # 示す、ジャダー検出とは独立した物理的証拠になる。GPSは粗い(~1Hz程度)ため、
    # 判定にはある程度の時間窓を要する点に留意 (データ不足時は評価をスキップする)。
    SPEED_XCHECK_WIN_SEC = 2.0        # GPS速度履歴を保持する窓 (この範囲内で評価)
    SPEED_XCHECK_MIN_GX = 0.4         # この程度以上の平均縦Gがある区間のみチェック対象
    SPEED_XCHECK_RATIO_WARN = 0.6     # 実減速/IMU予測減速 がこの比未満 → 速度不整合(滑走疑い)
    SPEED_XCHECK_CONF_PENALTY = 0.5   # 整合(=滑っていない可能性)時に信頼度へ掛ける下限係数

    # --- [7] 受信レート不足時のジャダー系検出ゲーティング ---
    # ジャダー帯域(概ね8〜20Hz)を正しく捉えるにはナイキストから最低でも40Hz、
    # 余裕を見て60Hz以上が望ましい。既存の受信品質判定(SensorInterface, GOOD/
    # DEGRADED/INVALID)がこの帯域不足を概ねカバーしているため、新規の実効レート
    # 監視は追加せず、data_quality_factorがGOOD(=1.0)未満の間はジャダーRMSに基づく
    # 前輪/後輪ロック分類のみを無効化する(他の検出系統は継続動作させる)。

    # --- 異常長時間セッションでのメモリ増大に対する安全弁 (通常は発動しない) ---
    MAX_STORED_EVENTS = 20000
    MAX_STORED_PERIODIC = 5000

    # --- 残留オフセットの緩やかな自動補正 (§21) ---
    # 走行中、G・Jerk・ジャイロ角速度がいずれも小さい「穏やかな」区間を検出し、
    # そこでの残留Gを極めて緩やかなEMAでオフセットに反映する。校正直後は
    # ゼロだが、長時間走行でのセンサ温度ドリフト等をゆっくり補正する目的。
    OFFSET_EMA_LAMBDA = 0.002
    OFFSET_CALM_G_MAX = 0.03
    OFFSET_CALM_JERK_MAX = 0.15
    OFFSET_CALM_GYRO_MAX_DEG_S = 3.0

    # --- Sensor Server (https://github.com/UmerCodez/SensorServer) 連携 ---
    # 実センサはスマホの「Sensor Server」アプリ (F-Droid配布) のWebSocket配信から
    # 取得する。アプリ画面に表示されるIP・ポートに合わせて以下を書き換えること。
    # 同一端末上で動かす場合は、アプリ設定で「Local Host」を有効にすると
    # host="127.0.0.1" で接続できる。接続できない場合はシミュレーションへ移行する。
    SENSOR_SERVER_ENABLED = True
    SENSOR_SERVER_HOST = "127.0.0.1"
    SENSOR_SERVER_PORT = 8081
    SENSOR_SERVER_GPS_ENABLED = True
    SENSOR_SERVER_CONNECT_TIMEOUT = 3.0
    # Sensor Serverアプリをできる限り自動起動しようと試みるか (ベストエフォート)。
    # 「アプリを開く」ところまでで、アプリ内の「Start」ボタンを自動で押すことは
    # 保証しない (Sensor Server自体にその機能が無いため)。
    SENSOR_SERVER_AUTO_LAUNCH = True
    SENSOR_SERVER_PACKAGE_NAME = "github.umer0586.sensorserver"
    # アプリ起動intentが解決できない場合(未インストール/ブラウザがintentスキーム非対応等)の
    # 代替遷移先。Chrome公式のS.browser_fallback_url仕組みを使う (developer.chrome.com/docs/android/intents)。
    SENSOR_SERVER_FDROID_URL = "https://f-droid.org/packages/github.umer0586.sensorserver/"
    # 接続はしているが実データが届かない状態(STALE)の判定閾値と、連続STALE検出時に
    # UIへ警告を出すまでの連続回数。
    SENSOR_STALE_SEC = 1.5
    SENSOR_STALE_STREAK_ALERT = 5
    # レビュー指摘①: 加速度計とジャイロは別スレッド/別レートで届くため、read()
    # 時点で必ずしも同時刻のデータとは限らない。両者の最終更新時刻差(スキュー)が
    # この値を超えるサンプルは「時刻的に対応していない」とみなし信頼度を下げる。
    SENSOR_SKEW_WARN_SEC = 0.05    # これを超えたら信頼度を減点し始める
    SENSOR_SKEW_MAX_SEC = 0.30     # これを超えたら信頼度ほぼ0扱い
    GPS_STALE_SEC = 3.0            # これより古いGPSは速度依存判定(タイヤ限界等)で信用しない
    # Sensor ServerのGPSエンドポイントは「位置が変化した時だけ」自動送信する仕様のため、
    # 停車中や電波状況によっては何もしないと座標を受信できないことがある(公式Wiki記載)。
    # これを避けるため、下記間隔で明示的に"getLastKnownLocation"を要求し続ける。
    GPS_POLL_INTERVAL_SEC = 2.0
    # レビュー指摘②: センサが長時間無応答のまま処理を続けると、凍結した(更新されない)
    # 加速度・ジャイロ値から実際には起きていないイベントやスコアを生成しかねない。
    # ここまで連続STALEが続いたら、そのサンプルの解析(イベント検出・スコアリング)を
    # 完全にスキップして「何もしない」状態にする(=データが疑わしい間はセッションを
    # 汚染しない)。新しいデータが届けば即座に(次サンプルから)再開する。
    SENSOR_STALE_PAUSE_STREAK = 150
    # SSE (Server-Sent Events) 配信間隔。ポーリング(旧: 150ms fetch)よりバッテリー/
    # 帯域を抑えつつ、UIの体感更新頻度は維持または向上させる。
    SSE_INTERVAL_SEC = 0.1
    # --- 受信品質モニタリング (バースト受信/欠損の検出) ---
    # タイヤロック判定は8〜20Hz帯のジャダーを見るため、単発でもこの程度の
    # パケット間隔が空くと当該帯域の情報が失われうる、という考え方に基づく閾値。
    SENSOR_TARGET_RATE_HZ = 100.0
    SENSOR_RATE_DEGRADED_RATIO = 0.5    # 実効レートが目標の何%を下回ったらDEGRADED扱いか
    SENSOR_MAX_GAP_DEGRADED_MS = 50.0   # これを超えるパケット間隔(=最短20Hzの半周期相当)でDEGRADED
    SENSOR_MAX_GAP_INVALID_MS = 150.0   # これを超えたらINVALID(ジャダー検出は無意味と判断)

    # --- スマホの物理的な設置向きに応じた軸マッピング ---
    # Androidセンサー座標系 (端末を自然な向き=縦持ちで正面から見た状態) は:
    #   X: 画面右方向、Y: 画面上方向 (受話口側)、Z: 画面手前方向 (使用者側)
    # forward/left/up の各キーに "+x"/"-x"/"+y"/"-y"/"+z"/"-z" のいずれかを指定する。
    # デフォルトは「縦向き設置、画面上端(受話口側)を進行方向(フロントガラス側)に
    # 向けている」場合の設定。前後Gと左右Gが入れ替わって見える場合は、まず
    # forwardとleftの軸(x/y)を入れ替えてみること。値の符号が逆な場合は
    # +/-を反転させること。この変換は実センサー(Sensor Server)のみに適用し、
    # シミュレーションモードのデモデータには適用しない。
    MOUNT_AXIS_MAP = {"forward": "+y", "left": "-x", "up": "+z"}

    # データ保存先。Android(APK)実行時はアプリ専用の書き込み可能領域、
    # それ以外(Windows/Raspberry Pi/Pydroid3)は従来通りスクリプトが置かれた
    # フォルダ配下 (__file__基準) を使う (_resolve_app_dir() が自動判定)。
    APP_DIR = _resolve_app_dir()
    DATA_DIR = os.path.join(APP_DIR, "dda_data")
    LOG_DIR = os.path.join(DATA_DIR, "logs")   # 走行ログ専用フォルダ (起動時に自動作成)
    REPORT_DIR = os.path.join(APP_DIR, "report")   # LLM分析用レポート(txt)の出力先
    HTTP_PORT = 8080

    # --- 走行ログの自動削除 (保持期間) ---
    LOG_RETENTION_DAYS = 7
    REPORT_RETENTION_DAYS = 7   # reportフォルダ内のtxtも同様に7日で自動削除

    APP_VERSION = "1.5"
    APP_AUTHOR = "JL7KHN"

    # --- 実走ログからの自動分析・自動補正 (適応キャリブレーション) ---
    ADAPTIVE_ENABLED = True
    ADAPTIVE_MIN_SESSIONS = 3        # これ未満のセッション数なら補正せず既定値
    ADAPTIVE_MIN_EVENTS = 20         # 分布推定に必要な最小イベント数
    ADAPTIVE_EMA_LAMBDA = 0.3        # 新推定を既存へ混ぜる係数(0=据置,1=即置換)
    ADAPTIVE_TRIGGER_PCTL = 15       # 検出閾値=ピークGの下側%点
    ADAPTIVE_NORM_PCTL = 90          # 正規化上限=観測値の上側%点
    ADAPTIVE_TRIGGER_CLAMP = (0.15, 0.60)
    ADAPTIVE_JERK_CLAMP = (1.5, 8.0)
    ADAPTIVE_LT_RATE_CLAMP = (0.8, 5.0)     # 荷重移動係数変化率の正規化上限 [1/s]

    # --- セッション最大G 表示 ---
    MAXG_MIN_G = 0.15                # これ未満は最大G候補としない (ノイズ床)

    # --- Version 1.4: スコアリング緩和 (「下がりやすいが加算されにくい」への対策) ---
    # 旧実装は全スコアが「100点からの線形減点」のみで構成されており、
    #   ・閾値をわずかに超えただけでも(乗数が大きいため)急激にスコアが落ちる
    #   ・イベントが発生しない穏やかな区間でも基礎点が90点止まり(100点に届かない)
    #   ・セッション全体を通して安全運転を維持しても、それを積極的に評価し加点する
    #     仕組みが一切無い
    # という3点により、「下がりやすいのに上がりにくい」という偏った体感になっていた。
    # 以下の定数でこれを是正する。従来との後方互換のため、危険側(閾値を大幅に超過
    # した場合に0点へ達する境界)は変更せず、軽微な逸脱への寛容さと、優良運転への
    # 加点のみを新設する。
    SCORE_SOFTEN_POWER = 1.6        # 1.0=従来の線形減点と同一。大きいほど軽微な逸脱に寛容
    SCORE_NEUTRAL_FLOOR = 96.0      # 該当イベント無し(穏やかな)区間の基礎点 (旧90.0)
    SCORE_EXCELLENCE_THRESHOLD = 82.0   # この点数以上を「優良」の判定材料として使う
    SCORE_EXCELLENCE_BONUS_MAX = 8.0    # 優良運転が続いた場合に総合スコアへ加点する上限値

    # --- Version 1.5: Sensor Server起動状況のワーニング表示関連 ---
    # セットアップ画面で「未起動」ワーニングを再判定するポーリング間隔。
    SENSOR_SERVER_CHECK_POLL_SEC = 3.0

    # --- 設定パネル(画面右上の⚙)から調整できるパラメータ一覧 ---
    # key: Config属性名, label/desc: UI表示用, min/max/step: 入力範囲, kind: "float"
    # ここに載っている属性のみ /api/config 経由での変更を許可する(ホワイトリスト)。
    TUNABLE_PARAMS = [
        {"key": "LPF_TAU_SEC", "label": "G値フィルタ時定数(秒)",
         "desc": "値を小さくすると加速/旋回Gの立ち上がりが速く(敏感に)なる代わりにノイズが増える。"
                 "大きくすると滑らかになる代わりに反応が鈍くなる。",
         "min": 0.02, "max": 0.5, "step": 0.01},
        {"key": "JERK_LIMIT_G_PER_S", "label": "ジャーク上限(G/秒)",
         "desc": "この値を基準にジャークスコアを採点する。小さくするほど厳しい採点になる。",
         "min": 0.5, "max": 10.0, "step": 0.1},
        {"key": "LOAD_TRANSFER_RATE_LIMIT", "label": "荷重移動変化率上限(1/秒)",
         "desc": "この値を基準に荷重移動スコアを採点する。小さくするほど厳しい採点になる。",
         "min": 0.2, "max": 8.0, "step": 0.1},
        {"key": "OFFSET_EMA_LAMBDA", "label": "残留オフセット補正の速さ",
         "desc": "停車中/定常走行中にG=0の基準点をどれだけ早く追従補正するか。"
                 "大きくすると素早く補正されるが、緩やかな加減速を誤って0側に吸い込みやすくなる。",
         "min": 0.0002, "max": 0.02, "step": 0.0002},
        {"key": "OFFSET_CALM_G_MAX", "label": "オフセット補正: 静穏判定Gしきい値",
         "desc": "このG以下の時だけ「静穏」とみなしオフセット補正の対象にする。",
         "min": 0.01, "max": 0.15, "step": 0.005},
        {"key": "MAXG_MIN_G", "label": "最大G表示の下限(ノイズ床)",
         "desc": "このG未満の変化は「最大G」の候補として表示しない。",
         "min": 0.05, "max": 0.5, "step": 0.01},
        {"key": "GRIP_TUR_WARN", "label": "グリップ利用率 警告閾値",
         "desc": "推定グリップ上限に対する使用率(TUR)がこの値を超えたら、"
                 "グリップ限界接近としてタイヤロック/グリップ喪失の詳細判定を開始する。"
                 "小さくするほど早期(低G)から警告するようになる。",
         "min": 0.5, "max": 1.0, "step": 0.01},
        {"key": "GRIP_MU_LONG_MAX_DEFAULT", "label": "制動方向グリップ上限の既定値(G)",
         "desc": "適応学習(走行データ蓄積)が効くまでの初期値。タイヤ/路面が良ければ"
                 "大きく、雨天や摩耗タイヤでは小さく調整する。",
         "min": 0.3, "max": 1.3, "step": 0.05},
        {"key": "GRIP_MU_LAT_MAX_DEFAULT", "label": "旋回方向グリップ上限の既定値(G)",
         "desc": "適応学習が効くまでの初期値。",
         "min": 0.3, "max": 1.3, "step": 0.05},
        {"key": "SCORE_SOFTEN_POWER", "label": "減点カーブの緩やかさ",
         "desc": "1.0で従来通りの線形減点。大きくするほど、閾値をわずかに超えた程度の"
                 "軽微な逸脱に対する減点が緩やかになる(大きく逸脱した場合は従来通りしっかり減点)。",
         "min": 1.0, "max": 3.0, "step": 0.1},
        {"key": "SCORE_NEUTRAL_FLOOR", "label": "イベント無し区間の基礎点",
         "desc": "急な制動/加速/旋回が無かった30秒区間の基礎点。高くするほど"
                 "穏やかな走行が総合スコアに反映されやすくなる。",
         "min": 80.0, "max": 100.0, "step": 1.0},
        {"key": "SCORE_EXCELLENCE_BONUS_MAX", "label": "優良運転ボーナス上限(点)",
         "desc": "高スコアを維持できた走行に対し、総合スコアへ加点する上限値。"
                 "0にすると加点機能を無効化できる。",
         "min": 0.0, "max": 15.0, "step": 0.5},
    ]


def ensure_data_dir():
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    os.makedirs(Config.REPORT_DIR, exist_ok=True)


def _config_overrides_path() -> str:
    return os.path.join(Config.DATA_DIR, "config_overrides.json")


def load_config_overrides():
    """起動時に、設定パネルから保存された調整値(TUNABLE_PARAMSのみ)をConfigへ反映する。"""
    data = load_json(_config_overrides_path(), {})
    allowed = {p["key"] for p in Config.TUNABLE_PARAMS}
    for k, v in data.items():
        if k in allowed:
            setattr(Config, k, v)


def save_config_overrides(updates: Dict[str, float]) -> Dict[str, float]:
    """TUNABLE_PARAMSに含まれるキーのみ検証(範囲クランプ)してConfigに適用し、
    ファイルへ永続化する(次回起動時にも引き継がれる)。"""
    by_key = {p["key"]: p for p in Config.TUNABLE_PARAMS}
    current = load_json(_config_overrides_path(), {})
    applied = {}
    for k, v in updates.items():
        p = by_key.get(k)
        if p is None:
            continue  # ホワイトリスト外は無視
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        fv = max(p["min"], min(p["max"], fv))
        setattr(Config, k, fv)
        current[k] = fv
        applied[k] = fv
    save_json(_config_overrides_path(), current)
    return applied


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# =========================================================================
# 2. Vehicle Database  (§6, 最大10台)
# =========================================================================

@dataclass
class Vehicle:
    vehicle_id: str
    name: str
    maker: str = ""
    model: str = ""
    mass_kg: float = 1200.0
    wheelbase_mm: float = 2600.0
    tread_front_mm: float = 1500.0
    tread_rear_mm: float = 1500.0
    weight_dist_front_pct: Optional[float] = None
    cg_height_mm: Optional[float] = None   # 未入力なら None -> 正規化荷重移動を使用 (§29)
    drive_type: str = "FF"                 # FF/FR/AWD
    tire_size: str = ""
    tire_brand: str = ""
    tire_type: str = ""
    tire_pressure_front_kpa: Optional[float] = None
    tire_pressure_rear_kpa: Optional[float] = None


class VehicleDatabase:
    MAX_VEHICLES = 10

    def __init__(self, path: str):
        self.path = path
        raw = load_json(path, [])
        self.vehicles: Dict[str, Vehicle] = {v["vehicle_id"]: Vehicle(**v) for v in raw}

    def save(self):
        save_json(self.path, [asdict(v) for v in self.vehicles.values()])

    def add(self, **kwargs) -> Vehicle:
        if len(self.vehicles) >= self.MAX_VEHICLES:
            raise ValueError("車両は最大10台までです")
        vid = kwargs.pop("vehicle_id", None) or str(uuid.uuid4())[:8]
        v = Vehicle(vehicle_id=vid, **kwargs)
        self.vehicles[vid] = v
        self.save()
        return v

    def update(self, vehicle_id: str, **kwargs) -> Vehicle:
        """既存車両を上書き更新する。vehicle_id は不変。渡されたフィールドのみ
        置き換え、未指定(None)のフィールドは現状維持する。"""
        v = self.vehicles.get(vehicle_id)
        if v is None:
            raise ValueError("指定された車両が見つかりません")
        valid = {f.name for f in fields(Vehicle)} - {"vehicle_id"}
        for key, val in kwargs.items():
            if key in valid and val is not None:
                setattr(v, key, val)
        self.save()
        return v

    def remove(self, vehicle_id: str) -> None:
        """車両を削除する。最後の1台は削除させない(セッションが車両必須のため)。"""
        if vehicle_id not in self.vehicles:
            raise ValueError("指定された車両が見つかりません")
        if len(self.vehicles) <= 1:
            raise ValueError("最後の1台は削除できません")
        del self.vehicles[vehicle_id]
        self.save()

    def get(self, vehicle_id: str) -> Optional[Vehicle]:
        return self.vehicles.get(vehicle_id)

    def list(self) -> List[Vehicle]:
        return list(self.vehicles.values())


# =========================================================================
# 3. Driver Database  (§5, 最大4名)
# =========================================================================

@dataclass
class DriverStats:
    session_count: int = 0
    event_count: int = 0
    # 運転指紋 (§61) 0-100
    fingerprint: Dict[str, float] = field(default_factory=lambda: {
        "smoothness": 50.0, "brake_control": 50.0, "accel_control": 50.0,
        "cornering_control": 50.0, "load_transfer_control": 50.0,
        "jerk_control": 50.0, "consistency": 50.0, "lr_symmetry": 50.0,
    })
    # (driver_id, vehicle_id, mode) 毎の統計 (§66)
    by_vehicle_mode: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class Driver:
    driver_id: str
    display_name: str
    stats: DriverStats = field(default_factory=DriverStats)


class DriverDatabase:
    MAX_DRIVERS = 2

    def __init__(self, path: str):
        self.path = path
        raw = load_json(path, [])
        self.drivers: Dict[str, Driver] = {}
        for d in raw:
            stats = DriverStats(**d.get("stats", {}))
            self.drivers[d["driver_id"]] = Driver(d["driver_id"], d["display_name"], stats)

    def save(self):
        out = []
        for d in self.drivers.values():
            out.append({"driver_id": d.driver_id, "display_name": d.display_name,
                        "stats": asdict(d.stats)})
        save_json(self.path, out)

    def add(self, display_name: str, driver_id: Optional[str] = None) -> Driver:
        if len(self.drivers) >= self.MAX_DRIVERS:
            raise ValueError(f"ドライバーは最大{self.MAX_DRIVERS}名までです")
        did = driver_id or str(uuid.uuid4())[:8]
        d = Driver(did, display_name)
        self.drivers[did] = d
        self.save()
        return d

    def update(self, driver_id: str, display_name: Optional[str] = None) -> Driver:
        """既存ドライバーを上書き更新する(名称変更)。driver_id は不変。
        統計(stats)は保持したまま display_name のみ差し替える。"""
        d = self.drivers.get(driver_id)
        if d is None:
            raise ValueError("指定されたドライバーが見つかりません")
        if display_name:
            d.display_name = display_name
        self.save()
        return d

    def remove(self, driver_id: str) -> None:
        """ドライバーを削除する。最後の1名は削除させない(セッションがドライバー必須のため)。"""
        if driver_id not in self.drivers:
            raise ValueError("指定されたドライバーが見つかりません")
        if len(self.drivers) <= 1:
            raise ValueError("最後の1名は削除できません")
        del self.drivers[driver_id]
        self.save()

    def get(self, driver_id: str) -> Optional[Driver]:
        return self.drivers.get(driver_id)

    def list(self) -> List[Driver]:
        return list(self.drivers.values())


# =========================================================================
# 4. Sensor Interface
# =========================================================================

class SensorSample:
    __slots__ = ("t", "ax", "ay", "az", "gx", "gy", "gz", "lat", "lon", "speed", "gps_ok",
                 "accel_age", "gyro_age", "gps_age", "data_quality_factor")

    def __init__(self, t, ax, ay, az, gx, gy, gz, lat=None, lon=None, speed=None, gps_ok=False,
                 accel_age=0.0, gyro_age=0.0, gps_age=None, data_quality_factor=1.0):
        self.t = t
        self.ax, self.ay, self.az = ax, ay, az   # raw accelerometer (m/s^2), device frame
        self.gx, self.gy, self.gz = gx, gy, gz   # raw gyroscope (rad/s), device frame
        self.lat, self.lon, self.speed = lat, lon, speed
        self.gps_ok = gps_ok
        # 各センサの「最終更新からの経過時間」[s]。加速度計とジャイロは別スレッド/別
        # レートで届くため、read()時点で両者が必ずしも同時刻のデータとは限らない
        # (レビュー指摘①)。取得元が持つ実際の受信時刻からの経過を見て、乖離が
        # 大きいサンプルの信頼度を下げるために使う。シミュレーションモードでは
        # 常に0(=常に新鮮)。
        self.accel_age = accel_age
        self.gyro_age = gyro_age
        self.gps_age = gps_age
        # 受信パケット間隔の統計(バースト受信/欠損)から求めた品質係数(0-1)。
        # 「単一スレッドか」ではなく「センサのサンプリング周期と受信時刻の対応が
        # 保証されているか」が本質、という指摘に基づく計装 (§SensorServerSource.quality)。
        self.data_quality_factor = data_quality_factor


class MiniWebSocketClient:
    """
    標準ライブラリのみで実装した最小WebSocketクライアント (RFC6455の必要最小限)。
    「Sensor Server」アプリ (https://github.com/UmerCodez/SensorServer, F-Droid配布)
    からのテキストフレーム受信専用に使う。追加のpipインストールが一切不要。
    """

    def __init__(self, host, port, path, timeout=5.0):
        self.host = host
        self.port = port
        self.path = path
        self.timeout = timeout
        self.sock = None
        self._buf = bytearray()

    def connect(self):
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        s.sendall(req.encode())

        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocketハンドシェイク中に接続が閉じられました")
            resp += chunk
        header, _, rest = resp.partition(b"\r\n\r\n")
        status_line = header.split(b"\r\n", 1)[0]
        if b"101" not in status_line:
            raise ConnectionError(f"WebSocketハンドシェイク失敗: {status_line!r}")

        accept_key = base64.b64encode(
            hashlib.sha1(key.encode() + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()
        ).decode()
        if accept_key.encode() not in header:
            raise ConnectionError("Sec-WebSocket-Acceptの検証に失敗しました")

        self.sock = s
        self._buf = bytearray(rest)

    def _recv_exact(self, n):
        while len(self._buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket接続が閉じられました")
            self._buf.extend(chunk)
        data = bytes(self._buf[:n])
        del self._buf[:n]
        return data

    def recv(self):
        """1件のテキストメッセージを返す (Ping/Pongは内部で処理して読み飛ばす)。"""
        while True:
            b1, b2 = self._recv_exact(2)
            fin = (b1 & 0x80) != 0
            opcode = b1 & 0x0F
            masked = (b2 & 0x80) != 0
            length = b2 & 0x7F

            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]

            mask_key = self._recv_exact(4) if masked else None
            payload = bytearray(self._recv_exact(length))
            if mask_key:
                for i in range(len(payload)):
                    payload[i] ^= mask_key[i % 4]

            if opcode == 0x9:   # Ping -> Pong
                self._send_frame(0xA, bytes(payload))
                continue
            if opcode == 0xA:   # Pong (無視)
                continue
            if opcode == 0x8:   # Close
                raise ConnectionError("WebSocketサーバーから切断されました (Close frame)")
            if opcode in (0x1, 0x0):  # Text
                if not fin:
                    raise ConnectionError("フラグメント化されたフレームは非対応です")
                return payload.decode("utf-8", errors="replace")
            # その他のopcodeは無視して次のフレームへ

    def _send_frame(self, opcode, payload: bytes):
        header = bytes([0x80 | opcode])
        length = len(payload)
        mask_key = os.urandom(4)
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", length)
        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask_key + masked_payload)

    def send_text(self, text: str):
        """クライアント→サーバーへのテキストフレーム送信 (例: GPSの"getLastKnownLocation")。"""
        self._send_frame(0x1, text.encode("utf-8"))

    def close(self):
        try:
            if self.sock:
                self._send_frame(0x8, b"")
                self.sock.close()
        except Exception:
            pass


class SensorServerSource:
    """
    「Sensor Server」アプリ (https://github.com/UmerCodez/SensorServer) にWebSocketで
    接続し、加速度・ジャイロ・GPSをリアルタイム取得するバックエンド。
    あらかじめスマホでSensor Serverアプリを起動し、
    Config.SENSOR_SERVER_HOST / PORT をアプリ画面に表示されるIP・ポートに合わせる。
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._lock = threading.Lock()
        self._latest_accel = (0.0, 0.0, Config.GRAVITY)
        self._latest_gyro = (0.0, 0.0, 0.0)
        self._latest_gps = (None, None, None)
        self._accel_connected = False
        self._gyro_connected = False
        self._last_accel_t = 0.0
        self._last_gyro_t = 0.0
        self._last_gps_t = 0.0
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []
        # 受信品質モニタリング用: 直近の受信間隔(パケット間隔)を保持する。
        # 「単一スレッドか否か」自体は本質ではなく、Sensor Serverの実サンプリング
        # 周期とDDAの受信時刻の対応関係が保証されていないことが本質的なリスク、
        # という指摘に基づく計装。フルのtimestamp付きリサンプラーへの置き換えは
        # 大規模改修になるため、まずは「実際にバースト受信/欠損が起きているか」を
        # 定量的に確認できるようにする。
        self._accel_intervals: deque = deque(maxlen=200)
        self._gyro_intervals: deque = deque(maxlen=200)

    def test_connect(self) -> Optional[str]:
        """起動確認用の同期接続テスト。成功ならNone、失敗なら理由の文字列を返す。"""
        path = "/sensor/connect?type=android.sensor.accelerometer"
        try:
            client = MiniWebSocketClient(self.host, self.port, path,
                                          timeout=Config.SENSOR_SERVER_CONNECT_TIMEOUT)
            client.connect()
            client.close()
            return None
        except Exception as e:
            return f"{type(e).__name__}: {e}"

    def start(self):
        self._stop.clear()
        t1 = threading.Thread(target=self._run_sensor_loop,
                               args=("android.sensor.accelerometer", "accel"), daemon=True)
        t2 = threading.Thread(target=self._run_sensor_loop,
                               args=("android.sensor.gyroscope", "gyro"), daemon=True)
        t1.start()
        t2.start()
        self._threads = [t1, t2]
        if Config.SENSOR_SERVER_GPS_ENABLED:
            t3 = threading.Thread(target=self._run_gps_loop, daemon=True)
            t3.start()
            self._threads.append(t3)

    def stop(self):
        self._stop.set()

    @staticmethod
    def _extract_values(parsed):
        """Sensor Serverの応答形式ゆれ (JSON配列 [x,y,z] か、
        {"values":[x,y,z], ...} のJSONオブジェクトか) の両方に対応する。"""
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return parsed.get("values")
        return None

    def _run_sensor_loop(self, sensor_type: str, kind: str):
        path = f"/sensor/connect?type={sensor_type}"
        while not self._stop.is_set():
            try:
                client = MiniWebSocketClient(self.host, self.port, path,
                                              timeout=Config.SENSOR_SERVER_CONNECT_TIMEOUT)
                client.connect()
                if kind == "accel":
                    self._accel_connected = True
                else:
                    self._gyro_connected = True
                while not self._stop.is_set():
                    msg = client.recv()
                    values = self._extract_values(json.loads(msg))
                    if not values or len(values) < 3:
                        continue
                    with self._lock:
                        now = time.monotonic()
                        if kind == "accel":
                            self._latest_accel = (values[0], values[1], values[2])
                            if self._last_accel_t:
                                self._accel_intervals.append(now - self._last_accel_t)
                            self._last_accel_t = now
                        else:
                            self._latest_gyro = (values[0], values[1], values[2])
                            if self._last_gyro_t:
                                self._gyro_intervals.append(now - self._last_gyro_t)
                            self._last_gyro_t = now
            except Exception:
                if kind == "accel":
                    self._accel_connected = False
                else:
                    self._gyro_connected = False
                if not self._stop.is_set():
                    time.sleep(2.0)  # 再接続まで少し待つ

    def _run_gps_loop(self):
        while not self._stop.is_set():
            try:
                client = MiniWebSocketClient(self.host, self.port, "/gps",
                                              timeout=Config.SENSOR_SERVER_CONNECT_TIMEOUT)
                client.connect()

                # Sensor Serverの/gpsは「位置が変化した時だけ」自動でメッセージを送る仕様
                # (公式Wiki: Getting Data From GPS)。屋内・停車中・GPS感度が低い環境では
                # 位置が全く更新されず、何もしないとセッション中ずっと座標を一度も受信
                # できないことがある。これが「ログのGPSが常にnull」の主因と考えられる。
                # 対策として、接続直後 + 一定間隔で明示的に"getLastKnownLocation"を
                # 要求するプロセス(公式Wiki推奨のワークアラウンド)を別スレッドで回す。
                stop_pinger = threading.Event()

                def _pinger():
                    try:
                        client.send_text("getLastKnownLocation")
                    except Exception:
                        return
                    while not stop_pinger.wait(Config.GPS_POLL_INTERVAL_SEC):
                        if self._stop.is_set():
                            return
                        try:
                            client.send_text("getLastKnownLocation")
                        except Exception:
                            return

                pinger_thread = threading.Thread(target=_pinger, daemon=True)
                pinger_thread.start()
                try:
                    while not self._stop.is_set():
                        msg = client.recv()
                        data = json.loads(msg)
                        if not isinstance(data, dict):
                            continue
                        lat = data.get("latitude")
                        lon = data.get("longitude")
                        speed = data.get("speed")
                        if lat is not None and lon is not None:
                            with self._lock:
                                self._latest_gps = (lat, lon, speed)
                                self._last_gps_t = time.monotonic()
                finally:
                    stop_pinger.set()
            except Exception:
                if not self._stop.is_set():
                    time.sleep(5.0)

    def _quality_for(self, intervals: deque) -> Dict[str, Any]:
        """直近の受信間隔から、実効受信レート・ジッタ・最大パケット間隔を計算する。
        バースト受信(まとめて到着)や欠損があると max_gap_ms が跳ね上がるため、
        「配信は継続しているが実質的にタイヤロック判定に使えない品質」を検出できる。"""
        if len(intervals) < 3:
            return {"rate_hz": None, "jitter_ms": None, "max_gap_ms": None, "n": len(intervals)}
        vals = list(intervals)
        mean_iv = sum(vals) / len(vals)
        var_iv = sum((v - mean_iv) ** 2 for v in vals) / len(vals)
        jitter_ms = math.sqrt(var_iv) * 1000.0
        max_gap_ms = max(vals) * 1000.0
        rate_hz = (1.0 / mean_iv) if mean_iv > 1e-6 else None
        return {"rate_hz": rate_hz, "jitter_ms": jitter_ms, "max_gap_ms": max_gap_ms, "n": len(vals)}

    def quality(self) -> Dict[str, Any]:
        with self._lock:
            accel_q = self._quality_for(self._accel_intervals)
            gyro_q = self._quality_for(self._gyro_intervals)
        return {"accel": accel_q, "gyro": gyro_q}

    def sample(self):
        with self._lock:
            ax, ay, az = self._latest_accel
            gx, gy, gz = self._latest_gyro
            now = time.monotonic()
            accel_age = (now - self._last_accel_t) if self._last_accel_t else None
            gyro_age = (now - self._last_gyro_t) if self._last_gyro_t else None
        return ax, ay, az, gx, gy, gz, accel_age, gyro_age

    def gps(self):
        with self._lock:
            lat, lon, speed = self._latest_gps
            gps_age = (time.monotonic() - self._last_gps_t) if self._last_gps_t else None
        return lat, lon, speed, gps_age

    @property
    def connected(self) -> bool:
        return self._accel_connected and self._gyro_connected


def _remap_axes(x: float, y: float, z: float, axis_map: Dict[str, str]):
    """MOUNT_AXIS_MAP設定に従い、デバイス座標系(x,y,z)を(forward,left,up)へ
    並べ替える。加速度・ジャイロどちらにも同じ変換を使う (物理軸は共通のため)。"""
    src = {"x": x, "y": y, "z": z}

    def pick(spec: str) -> float:
        sign = -1.0 if spec[0] == "-" else 1.0
        axis = spec[-1]
        return sign * src[axis]

    return pick(axis_map["forward"]), pick(axis_map["left"]), pick(axis_map["up"])


class SensorInterface:
    """
    実センサへはスマホの「Sensor Server」アプリ (WebSocket配信) 経由でのみ接続する。
    接続できない環境 (PCでの開発・検証、アプリ未起動・IP/ポート不一致など) では
    自動的に _SimulatedSensorSource にフォールバックする。

    重要: シミュレーションモードは「加速→ブレーキ→右旋回→左旋回」を12秒周期で
    自動生成するデモ用データであり、実センサの代わりではない。フォールバックの
    理由 (sim_reason) を必ず記録し、起動時ログとHTML UI双方に明示することで、
    「実機を机に置いているのにGボールが動く」といった誤解を防ぐ。
    """

    def __init__(self, simulate: Optional[bool] = None):
        self.status = {
            "accelerometer": "unknown", "gyroscope": "unknown", "gps": "unknown",
        }
        self._sensor_server: Optional[SensorServerSource] = None
        self.sim_reason: Optional[str] = None
        # 接続はしているが実データが届かない状態(STALE)の連続検出回数。
        self._stale_streak = 0
        self._last_stale_age: Optional[float] = None

        if simulate is None:
            if Config.SENSOR_SERVER_AUTO_LAUNCH:
                self._try_launch_sensor_server_app()
            simulate = not self._try_init_sensor_server()

        self.simulate = simulate
        if self.simulate:
            self._sim = _SimulatedSensorSource()
            self.status = {"accelerometer": "simulated", "gyroscope": "simulated", "gps": "simulated"}
            if self.sim_reason is None:
                self.sim_reason = "手動でシミュレーションモードが指定されました"

    def _try_launch_sensor_server_app(self):
        """
        Sensor Serverアプリをベストエフォートで開こうと試みる。
        あくまで「アプリを起動する」ところまでで、アプリ内の「Start」ボタンを自動で
        押すことまでは保証しない (Sensor Server自体にその機能が公式には無いため)。
        失敗しても致命的ではないので例外は握りつぶす。

        APK(python-for-android)実行時 [Version 1.5.1 追加]:
            旧来の "intent://...#Intent;...;end" (Chrome専用のIntent URIスキーム)は、
            Chrome自身が仲介した場合のみ解釈される特殊記法であり、ネイティブアプリの
            プロセスから webbrowser.open() 経由で呼んでも Uri.parse() されるだけで
            正しくアプリ起動Intentとして解釈されないため機能しない。
            APK内ではpyjnius経由でAndroidのPackageManager#getLaunchIntentForPackage()を
            直接使い、確実にアプリを起動できるようにする。
        それ以外の環境(Windows/Raspberry Pi/Pydroid3等)では、従来通りのChrome向け
        Intent URIをベストエフォートで試みる(Chrome以外では通常失敗するが無害)。
        """
        launched = False
        try:
            from jnius import autoclass, cast  # python-for-android 同梱のpyjnius
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = cast("android.app.Activity", PythonActivity.mActivity)
            pm = activity.getPackageManager()
            launch_intent = pm.getLaunchIntentForPackage(Config.SENSOR_SERVER_PACKAGE_NAME)
            if launch_intent is not None:
                activity.startActivity(launch_intent)
                launched = True
        except Exception:
            pass
        if not launched:
            try:
                uri = (f"intent://#Intent;action=android.intent.action.MAIN;"
                       f"category=android.intent.category.LAUNCHER;"
                       f"package={Config.SENSOR_SERVER_PACKAGE_NAME};end")
                webbrowser.open(uri)
            except Exception:
                pass
        try:
            time.sleep(1.5)  # アプリの起動を少し待つ
        except Exception:
            pass

    def _try_init_sensor_server(self) -> bool:
        """Sensor Serverアプリ (WebSocket配信) への接続を試みる。"""
        if not Config.SENSOR_SERVER_ENABLED:
            self.sim_reason = "Sensor Server連携はConfig.SENSOR_SERVER_ENABLEDで無効化されています"
            return False
        source = SensorServerSource(Config.SENSOR_SERVER_HOST, Config.SENSOR_SERVER_PORT)
        fail_reason = source.test_connect()
        if fail_reason is not None:
            self.sim_reason = (
                f"Sensor Serverアプリ ({Config.SENSOR_SERVER_HOST}:{Config.SENSOR_SERVER_PORT}) "
                f"への接続に失敗しました ({fail_reason})。スマホでSensor Serverアプリを起動し、"
                f"画面に表示されるIP・ポートに Config.SENSOR_SERVER_HOST/PORT を合わせてください。"
            )
            return False
        source.start()
        self._sensor_server = source
        self.status = {"accelerometer": "sensor-server", "gyroscope": "sensor-server",
                        "gps": "sensor-server" if Config.SENSOR_SERVER_GPS_ENABLED else "disabled"}
        return True

    @staticmethod
    def _quality_level(q: Dict[str, Any]) -> str:
        """accel/gyro片方のquality()結果からGOOD/DEGRADED/INVALID/UNKNOWNを判定する。"""
        max_gap = q.get("max_gap_ms")
        rate = q.get("rate_hz")
        if max_gap is None or rate is None:
            return "UNKNOWN"   # サンプル数がまだ足りない(起動直後等)
        if max_gap > Config.SENSOR_MAX_GAP_INVALID_MS:
            return "INVALID"
        if (max_gap > Config.SENSOR_MAX_GAP_DEGRADED_MS
                or rate < Config.SENSOR_TARGET_RATE_HZ * Config.SENSOR_RATE_DEGRADED_RATIO):
            return "DEGRADED"
        return "GOOD"

    @staticmethod
    def _quality_factor(level: str) -> float:
        """タイヤロック等の高周波検出に対する信頼度への掛け目。"""
        return {"GOOD": 1.0, "DEGRADED": 0.5, "INVALID": 0.0, "UNKNOWN": 1.0}.get(level, 1.0)

    def diagnostics(self) -> Dict[str, Any]:
        """接続はしているが実際にはデータが来ていない(STALE)状態を判別するための
        簡易診断情報。UIに表示し、設定ミスや購読の問題に早く気付けるようにする。
        あわせて、受信間隔から求めた「受信品質」(バースト受信/欠損の検出)も返す。"""
        if self._sensor_server is not None:
            ss = self._sensor_server
            now = time.monotonic()
            with ss._lock:
                accel_age = (now - ss._last_accel_t) if ss._last_accel_t else None
                gyro_age = (now - ss._last_gyro_t) if ss._last_gyro_t else None
            stale = (self._stale_streak >= Config.SENSOR_STALE_STREAK_ALERT)
            q = ss.quality()
            accel_level = self._quality_level(q["accel"])
            gyro_level = self._quality_level(q["gyro"])
            # 悪い方(GOOD > DEGRADED > INVALID > UNKNOWN)を全体の受信品質とする。
            order = {"INVALID": 0, "DEGRADED": 1, "UNKNOWN": 2, "GOOD": 3}
            overall_level = min([accel_level, gyro_level], key=lambda lv: order[lv])
            return {
                "backend": "sensor-server",
                "accel_connected": ss._accel_connected,
                "gyro_connected": ss._gyro_connected,
                "accel_age_sec": accel_age,
                "gyro_age_sec": gyro_age,
                "stale": stale,
                "stale_streak": self._stale_streak,
                "accel_quality": q["accel"],
                "gyro_quality": q["gyro"],
                "data_quality_level": overall_level,
            }
        return {"backend": "simulate", "data_quality_level": "GOOD"}

    def _update_stale(self, age: Optional[float]):
        """1サンプル分のSTALE判定。データが古い/未受信なら連続失敗回数を加算し、
        新鮮なデータが来たら0にリセットする。"""
        self._last_stale_age = age
        if age is None or age > Config.SENSOR_STALE_SEC:
            self._stale_streak += 1
        else:
            self._stale_streak = 0

    @property
    def is_paused(self) -> bool:
        """センサが長時間(目安: 数秒)無応答のとき True。呼び出し側はこの間、
        凍結データからの誤ったイベント/スコア生成を避けるため解析処理を止める。
        シミュレーションモードでは常に False。"""
        return (not self.simulate) and self._stale_streak >= Config.SENSOR_STALE_PAUSE_STREAK

    def read(self) -> SensorSample:
        t = time.monotonic()
        if self.simulate:
            ax, ay, az, gx, gy, gz = self._sim.sample(t)
            lat, lon, speed = self._sim.gps(t)
            return SensorSample(t, ax, ay, az, gx, gy, gz, lat, lon, speed, gps_ok=True,
                                 accel_age=0.0, gyro_age=0.0, gps_age=0.0)

        # --- Sensor Server 一本 ---
        ss = self._sensor_server
        ax, ay, az, gx, gy, gz, accel_age, gyro_age = ss.sample()
        lat, lon, speed, gps_age = ss.gps()
        self._update_stale(accel_age)
        q = ss.quality()
        dq_level = min([self._quality_level(q["accel"]), self._quality_level(q["gyro"])],
                        key=lambda lv: {"INVALID": 0, "DEGRADED": 1, "UNKNOWN": 2, "GOOD": 3}[lv])
        dq_factor = self._quality_factor(dq_level)
        ax, ay, az = _remap_axes(ax, ay, az, Config.MOUNT_AXIS_MAP)
        gx, gy, gz = _remap_axes(gx, gy, gz, Config.MOUNT_AXIS_MAP)
        return SensorSample(t, ax, ay, az, gx, gy, gz, lat, lon, speed, gps_ok=(lat is not None),
                             accel_age=(accel_age or 0.0), gyro_age=(gyro_age or 0.0), gps_age=gps_age,
                             data_quality_factor=dq_factor)


class _SimulatedSensorSource:
    """開発・動作確認用の疑似走行データ生成器 (ブレーキ/加速/旋回イベントを周期的に発生させる)。"""

    def __init__(self):
        self.t0 = time.monotonic()

    def sample(self, t):
        dt = t - self.t0
        # 起動直後 (~5秒) は静止フェーズとする (実車が発進前に停止している状況を模擬し、
        # キャリブレーションに必要な静止確認時間を確実に確保するため)
        if dt < 5.0:
            cycle = -1.0  # どの分岐にも該当しない値
        else:
            cycle = (dt - 5.0) % 12.0
        ax = ay = 0.0
        if 0.0 <= cycle < 1.0:            # 加速
            ax = 3.0 * math.sin(math.pi * cycle)
        elif 3.0 <= cycle < 4.2:    # ブレーキ
            ax = -5.0 * math.sin(math.pi * (cycle - 3.0) / 1.2)
        elif 5.0 <= cycle < 7.0:    # 右旋回
            ay = -4.0 * math.sin(math.pi * (cycle - 5.0) / 2.0)
        elif 7.5 <= cycle < 9.5:    # 左旋回 (切り返し)
            ay = 4.5 * math.sin(math.pi * (cycle - 7.5) / 2.0)

        # 路面外乱 (段差) のシミュレーション: 垂直方向に短い高周波の衝撃を混入させる。
        # あえてブレーキイベントの最中 (cycle 3.5-3.75) に発生させ、「ブレーキ中に
        # 段差を踏んだ場合でもイベントが破綻しないか」を検証できるようにする。
        # 注意: 最後の静止区間 (cycle 9.5-12.0) には重ねない (キャリブレーション用の
        # 唯一の長い静止窓のため、ここに外乱を入れるとキャリブレーションが完了しなくなる)。
        az_bump = 0.0
        if 3.5 <= cycle < 3.75:
            az_bump = 3.5 * math.sin(2 * math.pi * 18.0 * (cycle - 3.5))
            ax += 0.15 * math.sin(2 * math.pi * 18.0 * (cycle - 3.5))
            ay += 0.10 * math.sin(2 * math.pi * 18.0 * (cycle - 3.5))

        noise = lambda a: a + (math.sin(dt * 37.0) * 0.01)
        az = Config.GRAVITY + noise(az_bump)
        return noise(ax), noise(ay), az, 0.0, 0.0, 0.0

    def gps(self, t):
        dt = t - self.t0
        lat = 38.2682 + dt * 0.00001
        lon = 140.8694 + dt * 0.00001
        speed = 15.0
        return lat, lon, speed


# =========================================================================
# 5. Calibration  (§14-17, §21)
# =========================================================================

class Calibration:
    def __init__(self):
        self.done = False
        self.offset = (0.0, 0.0, 0.0)          # Ox, Oy, Oz (残留オフセット, G単位)
        self.gravity_vec = (0.0, 0.0, Config.GRAVITY)
        # 固定長リングバッファ (O(1)追記で古いサンプルが自然に落ちる)。
        self._buf: deque = deque(maxlen=400)
        self._static_since: Optional[float] = None

    def feed(self, s: SensorSample) -> bool:
        """静止判定 -> 十分な静止データが得られたら True を返しキャリブレーション完了。"""
        gyro_mag_deg = math.degrees(math.sqrt(s.gx ** 2 + s.gy ** 2 + s.gz ** 2))
        self._buf.append(s)

        if len(self._buf) < 5:
            return False

        recent = list(self._buf)   # deque はスライス不可のため list 化
        accel_mags = [math.sqrt(b.ax ** 2 + b.ay ** 2 + b.az ** 2) for b in recent[-50:]]
        mean_a = sum(accel_mags) / len(accel_mags)
        var_a = sum((a - mean_a) ** 2 for a in accel_mags) / len(accel_mags)
        std_a_g = math.sqrt(var_a) / Config.GRAVITY

        is_static = (std_a_g < Config.STATIC_ACCEL_STD_MAX) and (gyro_mag_deg < Config.STATIC_GYRO_MAX_DEG_S)

        if is_static:
            if self._static_since is None:
                self._static_since = s.t
            elif s.t - self._static_since >= Config.STATIC_CONFIRM_TIME_SEC:
                self._finalize()
                return True
        else:
            self._static_since = None
        return False

    def _finalize(self):
        window = list(self._buf)[-100:]
        n = len(window)
        ax = sum(b.ax for b in window) / n
        ay = sum(b.ay for b in window) / n
        az = sum(b.az for b in window) / n
        mag = math.sqrt(ax ** 2 + ay ** 2 + az ** 2) or Config.GRAVITY
        self.gravity_vec = (ax, ay, az)
        # 校正直後の残留オフセットは定義上ゼロ (gravity_vecそのものが校正窓の平均
        # だから)。以降は update_offset_if_calm() が走行中の穏やかな区間を使って
        # ゆっくり補正していく (センサの温度ドリフト等、校正直後には検出しようが
        # ないバイアスを走行中に補うため)。
        self.offset = (0.0, 0.0, 0.0)
        self.done = True

    def update_offset_if_calm(self, gx: float, gy: float, jerk_xy: float, gyro_deg_s: float):
        """G・Jerk・ジャイロ角速度がいずれも小さい区間でのみ、残留オフセットを
        極めて緩やかなEMAで更新する (§21)。急加減速・旋回中には絶対に呼ばない。"""
        if (abs(gx) < Config.OFFSET_CALM_G_MAX and abs(gy) < Config.OFFSET_CALM_G_MAX
                and jerk_xy < Config.OFFSET_CALM_JERK_MAX
                and gyro_deg_s < Config.OFFSET_CALM_GYRO_MAX_DEG_S):
            ox, oy, oz = self.offset
            lam = Config.OFFSET_EMA_LAMBDA
            self.offset = ((1 - lam) * ox + lam * gx, (1 - lam) * oy + lam * gy, oz)


# =========================================================================
# 6/7. Sensor Fusion & Coordinate Transformation  (簡易相補フィルタ)
# =========================================================================

class Orientation:
    """
    重力方向を基準としたロール・ピッチ姿勢を相補フィルタで推定し、
    デバイス座標系 -> 車両座標系 (X:前方向, Y:左方向, Z:上方向) への変換に使用する。
    (簡易実装。フルクォータニオン積分の代わりに roll/pitch のみ追跡し、
     ヨーは車両運動評価上前提としない = スマホの車内固定姿勢を仮定)
    """

    def __init__(self, gravity_vec):
        gx, gy, gz = gravity_vec
        self.roll = math.atan2(gy, gz)
        self.pitch = math.atan2(-gx, math.sqrt(gy ** 2 + gz ** 2))
        self._alpha = 0.98  # ジャイロ積分 : 加速度補正 の重み

    def update(self, s: SensorSample, dt: float):
        if dt <= 0:
            return
        # ジャイロ積分によるロール・ピッチ更新 (デバイス座標系, 簡易近似)
        self.roll += s.gx * dt
        self.pitch += s.gy * dt
        # 加速度から求めた重力方向で低周波ドリフトを補正
        mag = math.sqrt(s.ax ** 2 + s.ay ** 2 + s.az ** 2)
        if mag > 1e-6:
            roll_acc = math.atan2(s.ay, s.az)
            pitch_acc = math.atan2(-s.ax, math.sqrt(s.ay ** 2 + s.az ** 2))
            self.roll = self._alpha * self.roll + (1 - self._alpha) * roll_acc
            self.pitch = self._alpha * self.pitch + (1 - self._alpha) * pitch_acc

    def to_vehicle_frame(self, ax, ay, az):
        """デバイス座標系の加速度を、推定姿勢を使って車両座標系 (X前,Y左,Z上) へ回転する。"""
        cr, sr = math.cos(self.roll), math.sin(self.roll)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        # ピッチ補正 (X-Z面)
        x1 = ax * cp + az * sp
        z1 = -ax * sp + az * cp
        # ロール補正 (Y-Z面)
        y2 = ay * cr - z1 * sr
        z2 = ay * sr + z1 * cr
        return x1, y2, z2


# =========================================================================
# 8. Signal Processing
# =========================================================================

class LowPassFilter:
    """一次IIRローパスフィルタ (§22)。 alpha = dt / (tau + dt)
    update() 呼び出し時に tau を一時的に上書きできる (路面外乱時の適応平滑化に使用)。"""

    def __init__(self, tau=None, initial=0.0):
        # tau未指定時はConfig.LPF_TAU_SECを「呼び出し時点」で読む。
        # (default引数値としてConfig.LPF_TAU_SECを直接書くと、Python の仕様上
        #  モジュール読み込み時の値がクラス定義に焼き付いてしまい、設定パネルからの
        #  実行時変更(Config.LPF_TAU_SECの書き換え)が新しいセッションにも反映されない
        #  バグになるため、ここで明示的に読み直す)
        self.tau = tau if tau is not None else Config.LPF_TAU_SEC
        self.y = initial
        self._init = False

    def update(self, x, dt, tau=None):
        if not self._init:
            self.y = x
            self._init = True
            return self.y
        t = tau if tau is not None else self.tau
        alpha = dt / (t + dt) if (t + dt) > 0 else 1.0
        self.y = alpha * x + (1 - alpha) * self.y
        return self.y


class RoadDisturbanceFilter:
    """
    路面のうねり・段差など「ドライバーにはどうしようもない外乱」を検出する。

    考え方:
        ブレーキ/加速/旋回による前後・左右Gの変化は、路面の凹凸による
        垂直方向(Z軸, 重力除去後)の急峻な振動を伴わない。
        逆に段差・うねりは、垂直方向に短時間・高周波の振動を生じる。
        この性質を使い、垂直方向の「速いLPF」と「遅いLPF」の差分(=振動成分)の
        短時間RMSを監視し、閾値超過を路面外乱として検出する。

    検出結果は、
        - Gx/Gyフィルタの一時的な平滑化強化 (適応フィルタ)
        - 新規イベントトリガの抑制
        - イベント/周期統計からの外乱区間サンプルの除外
    に利用する。
    """

    def __init__(self):
        self._fast = LowPassFilter(tau=Config.ROAD_VIB_TAU_FAST_SEC)
        self._slow = LowPassFilter(tau=Config.ROAD_VIB_TAU_SLOW_SEC)
        self._window = deque()   # (t, vib_value)
        self._hold_until = 0.0

    def update(self, t: float, dt: float, vertical_g: float, mode: str = "STREET"):
        if not Config.ROAD_FILTER_ENABLED:
            return False, 0.0

        fast = self._fast.update(vertical_g, dt)
        slow = self._slow.update(vertical_g, dt)
        vib = fast - slow

        self._window.append((t, vib))
        while self._window and (t - self._window[0][0]) > Config.ROAD_VIB_WINDOW_SEC:
            self._window.popleft()

        if self._window:
            rms = math.sqrt(sum(v * v for _, v in self._window) / len(self._window))
        else:
            rms = 0.0

        # モード別閾値: サーキットは縁石/うねりが常態なので高めにして過検出を防ぐ。
        thresh = Config.ROAD_VIB_RMS_THRESHOLD_G_BY_MODE.get(mode, Config.ROAD_VIB_RMS_THRESHOLD_G)
        if rms > thresh:
            self._hold_until = t + Config.ROAD_VIB_HOLD_SEC

        active = t < self._hold_until
        return active, rms


class TireLockDetector:
    """
    車輪速センサ無しに、スマホIMU(加速度+ジャイロ)とGPS速度のみでタイヤの
    ロック/グリップ喪失を推定する検出器 (主にCIRCUITモード向け)。Version 1.3で、
    縦横独立の固定閾値による二値判定から、摩擦円(トラクションサークル)に基づく
    連続的な「グリップ利用率」評価へ全面刷新した (以下の[1]〜[7]は各対策に対応)。

    中核指標 [1][2]: Traction Utilization Ratio (TUR)
        TUR = sqrt( (Gx/mu_long_max)^2 + (Gy/mu_lat_max)^2 )
        タイヤが生成できる合成力の大きさは概ね楕円(縦横で長さの異なる摩擦円)に
        制限される、という物理(Circle/Ellipse of Forces)に基づく。mu_long_max/
        mu_lat_maxは固定値ではなく、蓄積走行ログの実績Gの上側パーセンタイルから
        ドライバー×車両×モード毎に推定した適応値(未蓄積時はConfig既定値)を
        外部から注入できる(コンストラクタ引数 / set_mu())。TURは検出の有無に
        関わらず毎サンプル算出し、UIでの連続的な「今どれだけグリップを使って
        いるか」の可視化に使う。

    検出ロジック (TUR > GRIP_TUR_WARN の区間でのみ詳細分類へ進む):
      A) 制動方向のグリップ喪失:
         深い減速中 (Gx < -LOCK_BRAKE_G) に、
           - 縦Gの高周波振動RMS(ジャダー)が閾値超過 → 制動ロック。
             前後輪の切り分けはヨー角速度で行うが、[3]荷重移動(lt_long)により
             フロントへ荷重が寄るほどリアは軽くロックしやすくなるため、
             後輪ロックのヨー閾値をlt_longに応じて動的に下げる。
               ヨー小 → "BRAKE_LOCK_FRONT" (前輪ロック=操舵不能で直進)
               ヨー大 → "BRAKE_LOCK_REAR"  (後輪ロック=車尾が流れオーバー傾向)
           - もしくは減速が急に緩む (Gx方向へ大きな正jerk) → "BRAKE_SLIP"
           - [7] ジャダーRMSに基づく前後輪分類は、受信品質がGOOD(judder_valid)の
             間のみ採用し、品質低下時はBRAKE_SLIP判定のみ(ジャダー非依存)を使う。
      B) コーナリング時のグリップ喪失 (アンダー/オーバー):
         横G > SLIP_LAT_G のとき、ヨー角加速度から定常/過渡を判別する([4])。
           - 定常(ヨー角加速度が小さい): 従来通り期待ヨーレート比で判定。
           - 過渡(トレイルブレーキング/コーナー入口等): 比率方式は誤差が
             出るため、Gyの立ち上がり勾配に対するヨー角加速度の追従度で
             アンダーステア傾向のみを評価する(オーバーは過渡では過検出
             しやすいため定常判定に委ねる)。
         速度が取れない場合は、ヨー角速度スパイクで "SPIN" をフォールバック判定。
      C) ジャダー非依存の「グリップ頭打ち」検出 ([5], GRIP_PLATEAU):
         ハイドロプレーニング等、ABS的な脈動を伴わない滑らかな滑走を、
         TURが高水準にある状態での合成G伸びの頭打ち/低下として独立検出する。

      信頼度補正 ([6]): 強い制動中、GPS速度の実減速がIMU積分による予測減速より
      明らかに小さい場合、摩擦力が速度に変換されていない独立した物理的証拠として
      検出の信頼度を補正する(データ不足時は補正なし)。

    注意 (原理的な限界): 車輪速・操舵角センサが無いため物理的な確定検出ではなく
    「兆候の推定」である。ジャダー周波数(概ね8〜20Hz)は取得レートに依存し、
    B)の過渡判定も操舵角なしでの簡易近似であることに変わりはない。しきい値は
    車両・装着位置・タイヤ・路面に応じて要調整(mu_max系は[2]の適応学習で自動化)。
    """

    def __init__(self, mu_long_max=None, mu_lat_max=None):
        self._fast = LowPassFilter(tau=Config.LOCK_JUDDER_TAU_FAST)
        self._slow = LowPassFilter(tau=Config.LOCK_JUDDER_TAU_SLOW)
        self._win = deque()   # (t, vib)
        self._hold_until = 0.0
        self._type = None
        self._last_confidence = 1.0
        # [1][2] mu_long_max/mu_lat_max は呼び出し時点でConfigを読む (LowPassFilterの
        # tau固定バグと同じ理由: モジュール読み込み時の値に固定させないため、
        # デフォルト引数値としてではなく本体で評価する)。
        self.mu_long_max = mu_long_max if mu_long_max is not None else Config.GRIP_MU_LONG_MAX_DEFAULT
        self.mu_lat_max = mu_lat_max if mu_lat_max is not None else Config.GRIP_MU_LAT_MAX_DEFAULT
        # [4] 過渡/定常判定用 (ヨー角加速度の推定)
        self._yaw_accel_lpf = LowPassFilter(tau=0.05)
        self._prev_yaw_rate = None
        self._prev_gy_filt = 0.0
        # [5] グリップ頭打ち検出用 (合成Gの短時間傾き追跡)
        self._g_trend_win = deque()   # (t, gxy)
        self._prev_gxy_slope = None
        # [6] GPS/IMUクロスバリデーション用の履歴
        self._gx_hist = deque()       # (t, gx_filt)
        self._speed_hist = deque()    # (t, gps_speed)

    def set_mu(self, mu_long_max, mu_lat_max):
        """[2]の適応推定値をセッション途中でも反映できるようにする(現状はセッション
        開始時のみ呼ばれるが、将来のリアルタイム再学習にも対応できる形にしておく)。"""
        if mu_long_max is not None:
            self.mu_long_max = mu_long_max
        if mu_lat_max is not None:
            self.mu_lat_max = mu_lat_max

    def reset(self):
        """センサ無応答からの再開時に呼ぶ。ギャップを跨いだ古いサンプルが
        ジャダー窓・傾き窓・速度クロスチェック窓に混入し、再開直後に誤検出
        するのを防ぐ(EventDetector.reset()と同じ考え方)。"""
        self._win.clear()
        self._hold_until = 0.0
        self._type = None
        self._prev_yaw_rate = None
        self._prev_gy_filt = 0.0
        self._g_trend_win.clear()
        self._prev_gxy_slope = None
        self._gx_hist.clear()
        self._speed_hist.clear()

    def _speed_consistency(self):
        """[6] 直近SPEED_XCHECK_WIN_SEC秒程度のGPS速度変化とIMU積分による予測減速を
        比較する。実減速がIMU予測より明らかに小さい場合、摩擦力が速度低下に
        変換されていない(=タイヤが滑っている)可能性を示す独立した物理的証拠に
        なる。データ不足(GPS更新が疎/未取得)の場合はNoneを返し判定を行わない。"""
        if len(self._speed_hist) < 2:
            return None
        t0, s0 = self._speed_hist[0]
        t1, s1 = self._speed_hist[-1]
        span = t1 - t0
        if span < 0.5:
            return None
        actual_decel = (s0 - s1) / span   # m/s^2, 正=実際に減速できている
        relevant = [gx for tt, gx in self._gx_hist if t0 <= tt <= t1]
        if len(relevant) < 2:
            return None
        expected_decel = -(sum(relevant) / len(relevant)) * Config.GRAVITY
        if expected_decel < Config.SPEED_XCHECK_MIN_GX * Config.GRAVITY:
            return None   # 十分な制動Gが無い区間は評価対象外
        if expected_decel <= 1e-6:
            return None
        return actual_decel / expected_decel

    def update(self, t, dt, gx_filt, gy_filt, jx_filt, jy_filt, gx_raw, yaw_rate, speed, mode,
               lt_long=0.0, judder_valid=True):
        """1サンプル処理。
        戻り値: (active, type, long_vib_rms, tur, confidence)
            active    : このサンプル時点で警告を表示すべきか
            type      : 検出種別 (BRAKE_LOCK_FRONT/REAR, BRAKE_SLIP, UNDERSTEER,
                         OVERSTEER, SPIN, GRIP_PLATEAU のいずれか) または None
            long_vib_rms : 縦G高周波RMS (表示・デバッグ用、既存互換)
            tur       : [1][2] Traction Utilization Ratio。対象モード外/無効時は0.0。
                         アクティブ検出の有無によらず常に算出する。
            confidence: この判定の信頼度(0-1)。[6][7]の補正を反映(非アクティブ時は1.0)。
        """
        if not Config.TIRE_LOCK_ENABLED or mode not in Config.TIRE_LOCK_MODES:
            return False, None, 0.0, 0.0, 1.0

        # --- ジャダー(縦G高周波)抽出。レート不足でも計算自体は行うが、
        #     詳細分類への採用は judder_valid でゲートする ([7])。---
        fast = self._fast.update(gx_raw, dt)
        slow = self._slow.update(gx_raw, dt)
        vib = fast - slow
        self._win.append((t, vib))
        while self._win and (t - self._win[0][0]) > Config.LOCK_JUDDER_WIN_SEC:
            self._win.popleft()
        vib_rms = math.sqrt(sum(v * v for _, v in self._win) / len(self._win)) if self._win else 0.0

        # --- [1] 摩擦円(トラクションサークル)ベースの連成グリップ利用率 (TUR) ---
        mu_l = max(0.05, self.mu_long_max)
        mu_t = max(0.05, self.mu_lat_max)
        tur = math.sqrt((gx_filt / mu_l) ** 2 + (gy_filt / mu_t) ** 2)

        # --- [4] ヨー角加速度 (過渡/定常判定用)。ノイズが乗りやすいため軽くLPF。---
        raw_yaw_accel = ((yaw_rate - self._prev_yaw_rate) / dt
                          if (self._prev_yaw_rate is not None and dt > 0) else 0.0)
        yaw_accel = self._yaw_accel_lpf.update(raw_yaw_accel, dt)
        self._prev_yaw_rate = yaw_rate

        # --- [6] GPS/IMUクロスバリデーション用の履歴更新 ---
        self._gx_hist.append((t, gx_filt))
        while self._gx_hist and t - self._gx_hist[0][0] > Config.SPEED_XCHECK_WIN_SEC:
            self._gx_hist.popleft()
        if speed is not None:
            self._speed_hist.append((t, speed))
            while self._speed_hist and t - self._speed_hist[0][0] > Config.SPEED_XCHECK_WIN_SEC:
                self._speed_hist.popleft()

        detected = None
        conf = 1.0
        plateau_flag = False

        # ===== A) 制動方向のグリップ喪失 =====
        # [3] 荷重移動バイアス: 制動でフロントに荷重が寄るほどリアが軽くなり
        #    ロックしやすくなるため、後輪ロックのヨー閾値をlt_longに応じて下げる。
        lt_ratio = min(1.0, max(0.0, lt_long) / Config.LOCK_REAR_YAW_LT_REF)
        rear_yaw_thresh = max(Config.LOCK_REAR_YAW_MIN_DEG_S,
                              Config.LOCK_REAR_YAW_DEG_S *
                              (1.0 - Config.LOCK_REAR_YAW_LT_SENSITIVITY * lt_ratio))
        # [1] 一次ゲート: Gx単独閾値ではなくTUR(合成利用率)を主判定にする。
        #    LOCK_BRAKE_Gは、mu推定が不当に小さい場合の過検出を防ぐ下限フロア。
        if gx_filt < -Config.LOCK_BRAKE_G and tur > Config.GRIP_TUR_WARN:
            if judder_valid and vib_rms > Config.LOCK_JUDDER_RMS_G:
                if math.degrees(abs(yaw_rate)) > rear_yaw_thresh:
                    detected = "BRAKE_LOCK_REAR"
                else:
                    detected = "BRAKE_LOCK_FRONT"
            elif jx_filt > Config.LOCK_COLLAPSE_JERK:
                detected = "BRAKE_SLIP"
            if not judder_valid:
                conf *= 0.7   # [7] ジャダー判定が使えない間は信頼度を下げる

        # ===== B) コーナリング時のグリップ喪失 (アンダー/オーバー) =====
        if detected is None and abs(gy_filt) > Config.SLIP_LAT_G and tur > Config.GRIP_TUR_WARN:
            a_lat = abs(gy_filt) * Config.GRAVITY
            yaw = abs(yaw_rate)
            is_steady = abs(math.degrees(yaw_accel)) < Config.YAW_ACCEL_STEADY_DEG_S2
            if speed and speed > Config.SLIP_MIN_SPEED_MPS:
                yaw_exp = a_lat / speed
                if is_steady:
                    # 定常円旋回近似(従来方式)。過渡が収まっている区間でのみ使う。
                    if yaw_exp > 1e-3:
                        ratio = yaw / yaw_exp
                        if ratio < Config.SLIP_YAW_RATIO_UNDER:
                            detected = "UNDERSTEER"
                        elif ratio > Config.SLIP_YAW_RATIO_OVER:
                            detected = "OVERSTEER"
                else:
                    # [4] 過渡区間: 比率ではなく「Gyの立ち上がりにヨーレートが
                    #    追従できているか」を勾配で評価する(トレイルブレーキング/
                    #    コーナー入口で定常近似が破綻する弱点への対策)。
                    gy_rate = (gy_filt - self._prev_gy_filt) / dt if dt > 0 else 0.0
                    if gy_rate > Config.TRANSIENT_GY_MIN_G_PER_S:
                        yaw_accel_expected = gy_rate * Config.GRAVITY / speed
                        if yaw_accel_expected > 1e-3:
                            transient_ratio = yaw_accel / yaw_accel_expected
                            if transient_ratio < Config.TRANSIENT_UNDER_RATIO:
                                detected = "UNDERSTEER"
                    conf *= 0.85  # 過渡判定は定常判定より不確実性が高いことを明示
            elif math.degrees(yaw) > Config.SLIP_YAW_SPIKE_DEG_S:
                detected = "SPIN"

        # ===== C) [5] ジャダーを伴わない「グリップ頭打ち」検出 =====
        # 縦横どちらの軸でも、ドライバーがまだ強めている(合成Gが十分な勾配で
        # 立ち上がってきた)にも関わらず、直近の伸びが頭打ち/低下に転じ、かつ
        # 既にTURが高水準にあるケースを、ジャダー非依存の独立系統として検出する。
        gxy_now = math.sqrt(gx_filt ** 2 + gy_filt ** 2)
        self._g_trend_win.append((t, gxy_now))
        while self._g_trend_win and (t - self._g_trend_win[0][0]) > Config.PLATEAU_WIN_SEC:
            self._g_trend_win.popleft()
        if detected is None and tur > Config.PLATEAU_MIN_TUR and len(self._g_trend_win) >= 3:
            pts = list(self._g_trend_win)
            span = pts[-1][0] - pts[0][0]
            if span > 0:
                slope = (pts[-1][1] - pts[0][1]) / span
                if (self._prev_gxy_slope is not None
                        and self._prev_gxy_slope > Config.PLATEAU_BUILDUP_MIN_SLOPE_G_S
                        and slope < 0.15 * self._prev_gxy_slope):
                    detected = "GRIP_PLATEAU"
                    plateau_flag = True
                self._prev_gxy_slope = slope
        self._prev_gy_filt = gy_filt

        # ===== [6] GPS/IMUクロスバリデーションによる信頼度補正 =====
        if detected in ("BRAKE_LOCK_FRONT", "BRAKE_LOCK_REAR", "BRAKE_SLIP"):
            sc = self._speed_consistency()
            if sc is not None:
                if sc < Config.SPEED_XCHECK_RATIO_WARN:
                    # GPS上の減速がIMU予測より明らかに小さい → 独立証拠が検出を裏付ける
                    conf = min(1.0, conf * 1.15)
                else:
                    # 整合している(=あまり滑っていない可能性) → 信頼度をやや下げる
                    conf *= (Config.SPEED_XCHECK_CONF_PENALTY
                             + (1 - Config.SPEED_XCHECK_CONF_PENALTY) * min(1.0, sc))

        if detected is not None:
            self._hold_until = t + (Config.PLATEAU_HOLD_SEC if plateau_flag else Config.TIRE_LOCK_HOLD_SEC)
            self._type = detected
            self._last_confidence = round(max(0.0, min(1.0, conf)), 2)
        active = t < self._hold_until
        return (active, (self._type if active else None), vib_rms, round(tur, 3),
                (self._last_confidence if active else 1.0))


class RingBuffer:
    def __init__(self, maxlen_sec: float, hz_hint: float = 80.0):
        self.buf = deque(maxlen=int(maxlen_sec * hz_hint * 1.5) + 10)

    def append(self, item):
        self.buf.append(item)

    def slice_seconds(self, t_now, seconds):
        """t属性を持つオブジェクト(DynamicsSample)のリストを対象にスライスする。"""
        return [x for x in self.buf if t_now - x.t <= seconds]


# =========================================================================
# 9. Vehicle Dynamics  (§20-32)
# =========================================================================

class DynamicsSample:
    __slots__ = ("t", "dt", "gx", "gy", "gz", "gxy", "gxyz", "theta",
                 "jx", "jy", "jxy", "lt_long", "lt_lat", "lt_long_rate", "lt_lat_rate",
                 "road_disturbance", "road_vib_rms",
                 "yaw_rate", "long_vib_rms", "tire_lock", "tire_lock_type",
                 "sensor_reliability", "tur", "tire_lock_confidence")

    def __init__(self):
        # 安全のためデフォルト値で初期化しておく (process()は常に全属性を
        # 上書きしてから返すが、将来の変更で代入漏れが起きても未定義属性
        # アクセスによるクラッシュを防ぐ)。
        self.t = 0.0
        self.dt = 0.0
        self.gx = self.gy = self.gz = 0.0
        self.gxy = self.gxyz = self.theta = 0.0
        self.jx = self.jy = self.jxy = 0.0
        self.lt_long = self.lt_lat = 0.0
        self.lt_long_rate = self.lt_lat_rate = 0.0
        self.road_disturbance = False
        self.road_vib_rms = 0.0
        self.yaw_rate = 0.0            # 車両Z軸(鉛直・上方向)まわり角速度 [rad/s] (ヨーレート)
        self.long_vib_rms = 0.0        # 縦G高周波RMS (タイヤロック判定用)
        self.tire_lock = False
        self.tire_lock_type = None     # BRAKE_LOCK_FRONT/REAR/BRAKE_SLIP/UNDERSTEER/OVERSTEER/SPIN/GRIP_PLATEAU
        # 加速度計とジャイロの受信時刻スキューに基づく、このサンプル単体の信頼度
        # (0.0-1.0)。1.0=時刻的に整合、0.0=スキューが大きく信用できない。
        self.sensor_reliability = 1.0
        # Traction Utilization Ratio ([1][2])。タイヤの推定グリップ上限に対する
        # 現在の合成G使用率。tire_lockの有無に関わらず常時算出する連続量。
        self.tur = 0.0
        # このサンプル時点でのタイヤロック/グリップ喪失判定の信頼度(0-1)。
        self.tire_lock_confidence = 1.0


class VehicleDynamicsEngine:
    def __init__(self, vehicle: Optional[Vehicle], mu_long_max: Optional[float] = None,
                 mu_lat_max: Optional[float] = None):
        self.vehicle = vehicle
        self.lpf_x = LowPassFilter()
        self.lpf_y = LowPassFilter()
        self.lpf_z = LowPassFilter()
        self.prev_gx = 0.0
        self.prev_gy = 0.0
        self.prev_lt_long = 0.0
        self.prev_lt_lat = 0.0
        self.prev_t: Optional[float] = None
        self.road_filter = RoadDisturbanceFilter()
        # [2]: 蓄積走行ログから推定したmu_long_max/mu_lat_max(適応値)を、
        # 未蓄積(None)ならConfig既定値を使ってTireLockDetectorへ渡す。
        self.tire_lock = TireLockDetector(mu_long_max=mu_long_max, mu_lat_max=mu_lat_max)
        self.mode = "STREET"   # start_session で実モードを設定する

    def set_vehicle(self, vehicle: Optional[Vehicle]):
        self.vehicle = vehicle

    def process(self, s: SensorSample, orientation: Orientation, calib: Calibration) -> Optional[DynamicsSample]:
        if self.prev_t is None:
            self.prev_t = s.t
            return None
        dt = s.t - self.prev_t
        self.prev_t = s.t
        if dt < Config.DT_MIN or dt > Config.DT_MAX:
            return None  # 異常dtは破棄 (§86)

        orientation.update(s, dt)
        vx, vy, vz = orientation.to_vehicle_frame(s.ax, s.ay, s.az)

        gvx, gvy, gvz = calib.gravity_vec
        vgx, vgy, vgz = orientation.to_vehicle_frame(gvx, gvy, gvz)

        dyn_x = vx - vgx
        dyn_y = vy - vgy
        dyn_z = vz - vgz

        gx = dyn_x / Config.GRAVITY
        gy = dyn_y / Config.GRAVITY
        gz = dyn_z / Config.GRAVITY

        ox, oy, oz = calib.offset
        gx -= ox
        gy -= oy
        gz -= oz

        # LPF前の生の縦G。タイヤロックのジャダー(高周波)判定に使う
        # (LPF後だと高周波成分が失われ、ロック振動が検出できないため)。
        raw_gx = gx

        # --- 路面外乱 (うねり・段差) 検出 ---
        # 重力除去後の垂直方向Gz(平滑化前の生値)を監視する。ブレーキ/加速/旋回は
        # 垂直方向にこのような急峻な振動を生まないため、路面由来の外乱と切り分けられる。
        road_disturbance, road_vib_rms = self.road_filter.update(s.t, dt, gz, self.mode)

        # 外乱検出中はGx/Gyのフィルタを一時的に強め、段差由来のスパイクを減衰させる。
        # ただしモード別: サーキットはブースト倍率1.0(実質無効)にして、バンプを踏み
        # ながらの本物の高G旋回でピークGを削らないようにする。
        tau_mult = Config.ROAD_ADAPTIVE_TAU_BOOST_BY_MODE.get(self.mode, 1.0)
        tau_boost = (Config.LPF_TAU_SEC * tau_mult
                     if (road_disturbance and tau_mult > 1.0) else None)

        gx = self.lpf_x.update(gx, dt, tau=tau_boost)
        gy = self.lpf_y.update(gy, dt, tau=tau_boost)
        gz = self.lpf_z.update(gz, dt, tau=tau_boost)

        gxy = math.sqrt(gx ** 2 + gy ** 2)
        gxyz = math.sqrt(gx ** 2 + gy ** 2 + gz ** 2)
        theta = math.degrees(math.atan2(gy, gx)) if (gx or gy) else 0.0

        jx = (gx - self.prev_gx) / dt
        jy = (gy - self.prev_gy) / dt
        jxy = math.sqrt(jx ** 2 + jy ** 2)
        self.prev_gx, self.prev_gy = gx, gy

        gyro_deg_s = math.degrees(math.sqrt(s.gx ** 2 + s.gy ** 2 + s.gz ** 2))
        calib.update_offset_if_calm(gx, gy, jxy, gyro_deg_s)

        lt_long, lt_lat = self._load_transfer(gx, gy)
        lt_long_rate = (lt_long - self.prev_lt_long) / dt
        lt_lat_rate = (lt_lat - self.prev_lt_lat) / dt
        self.prev_lt_long, self.prev_lt_lat = lt_long, lt_lat

        # ヨーレート = 車両の鉛直(up)軸まわり角速度。従来は s.gz (デバイス座標系Z軸)を
        # そのまま流用していたが、端末が水平でない(前上がり/横傾き)場合は
        # device Z ≠ vehicle Z となり誤差が生じる(レビュー指摘②)。
        # 姿勢(roll/pitch)推定で得た同じ回転を角速度ベクトルにも適用し、
        # 車両座標系(X前,Y左,Z上)まわりの角速度に変換したうえでZ成分を使う。
        _, _, yaw_rate = orientation.to_vehicle_frame(s.gx, s.gy, s.gz)

        # --- センサ時刻スキューに基づく信頼度 (レビュー指摘①) ---
        # 加速度計とジャイロは別スレッド/別レートで届くため、このサンプルの
        # 加速度とジャイロが「実際には別時刻に取得されたもの」である可能性がある。
        # 両者の最終更新時刻の差が大きいほど、Jerkや荷重移動レートなど時間微分量の
        # 精度が落ちるとみなし、サンプル単体の信頼度を下げる。
        skew = abs((s.accel_age or 0.0) - (s.gyro_age or 0.0))
        if skew <= Config.SENSOR_SKEW_WARN_SEC:
            sensor_reliability = 1.0
        elif skew >= Config.SENSOR_SKEW_MAX_SEC:
            sensor_reliability = 0.0
        else:
            span = Config.SENSOR_SKEW_MAX_SEC - Config.SENSOR_SKEW_WARN_SEC
            sensor_reliability = 1.0 - (skew - Config.SENSOR_SKEW_WARN_SEC) / span
        # 受信品質(バースト受信/欠損)による減点もあわせて反映する。「単一スレッドが
        # 原因」ではなく「受信時刻とセンササンプリング周期の対応が保証されない」ことが
        # 本質、という指摘に基づく (SensorServerSource.quality)。特にタイヤロックの
        # ジャダー検出(8〜20Hz)に効いてくる。
        sensor_reliability *= s.data_quality_factor

        # GPS品質ゲーティング(レビュー指摘⑫の簡易版): 取得から
        # Config.GPS_STALE_SEC 以上経過した速度は、位置更新が止まっている可能性が
        # あるため「速度不明」として扱い、タイヤ限界判定(期待ヨーレート計算)に使わない。
        speed_for_tire = s.speed if (s.gps_age is None or s.gps_age <= Config.GPS_STALE_SEC) else None

        # --- [7] 受信レート不足時のジャダー系検出ゲーティング ---
        # data_quality_factorがGOOD(=1.0)未満の間は、ジャダーRMSに基づく前輪/後輪
        # ロック分類のみを無効化する(TireLockDetector内部でジャーク/TUR/プラトー等
        # の他系統は継続動作させる、粒度の細かいゲーティング)。既存の受信品質判定
        # (SensorInterface._quality_level, GOOD/DEGRADED/INVALID)をそのまま再利用し、
        # ここで新たにレート監視を二重実装しない。
        judder_valid = s.data_quality_factor >= 0.999

        tl_active, tl_type, long_vib, tur, tl_conf = self.tire_lock.update(
            s.t, dt, gx, gy, jx, jy, raw_gx, yaw_rate, speed_for_tire, self.mode,
            lt_long=lt_long, judder_valid=judder_valid)

        d = DynamicsSample()
        d.t, d.dt = s.t, dt
        d.gx, d.gy, d.gz = gx, gy, gz
        d.gxy, d.gxyz, d.theta = gxy, gxyz, theta
        d.jx, d.jy, d.jxy = jx, jy, jxy
        d.lt_long, d.lt_lat = lt_long, lt_lat
        d.lt_long_rate, d.lt_lat_rate = lt_long_rate, lt_lat_rate
        d.road_disturbance, d.road_vib_rms = road_disturbance, road_vib_rms
        d.yaw_rate, d.long_vib_rms = yaw_rate, long_vib
        d.tire_lock, d.tire_lock_type = tl_active, tl_type
        d.sensor_reliability = sensor_reliability
        d.tur = tur
        d.tire_lock_confidence = tl_conf
        return d

    def _geom(self):
        """荷重移動計算に使う幾何量 (重心高h, ホイールベースL, 平均トレッドT) を
        メートル単位で返す。重心高が未入力なら基準値(REF_CG_HEIGHT_MM)で代替する。"""
        v = self.vehicle
        h = ((v.cg_height_mm if (v and v.cg_height_mm is not None) else Config.REF_CG_HEIGHT_MM)) / 1000.0
        L = (v.wheelbase_mm if v else 2600.0) / 1000.0
        T = (((v.tread_front_mm + v.tread_rear_mm) / 2.0) if v else 1500.0) / 1000.0
        return h, L, T

    def _load_transfer(self, gx, gy):
        """§27-29: 荷重移動を「静荷重に対する移動割合」= 無次元係数で返す。

        定義:  ΔW/W = (前後) G_x * h / L ,  (左右) G_y * h / T
        (G_x, G_y は重力加速度で正規化した加速度[G]。式から車両質量 m は
         キャンセルするため、この係数は質量にも重心高入力の有無にも依存せず
         常に同一スケールになる = 旧実装の単位非一貫性/便宜的×1000を解消)。

        重心高が未入力の場合は基準重心高で代替するが、返す量の「単位・スケール」は
        入力有無で一切変わらない (差は幾何値の実測 vs 代替という精度差のみ)。
        物理的なkg換算値が必要な場合は load_transfer_kg() を使う (表示専用)。
        """
        h, L, T = self._geom()
        lt_long = gx * h / L if L else 0.0
        lt_lat = gy * h / T if T else 0.0
        return lt_long, lt_lat

    def load_transfer_kg(self, gx, gy):
        """荷重移動を物理量(kgf)で返す (表示専用)。質量が必要なので概算値。
        ΔW = m * G * h / L。スコアリングには使わない (質量依存で車両間比較が
        歪むため)。UIで実感的な数値を見せたいとき等に利用する。"""
        v = self.vehicle
        m = v.mass_kg if v else 1200.0
        lt_long, lt_lat = self._load_transfer(gx, gy)
        return m * lt_long, m * lt_lat

    def load_transfer_is_estimated_mass(self) -> bool:
        """重心高が実測入力されているか (True=実測幾何, False=基準値代替)。
        単位・スケールはどちらでも同一。データ精度の区別用フラグ。"""
        return self.vehicle is not None and self.vehicle.cg_height_mm is not None


# =========================================================================
# 10. Event Detection  (§33-40)
# =========================================================================

EVENT_TYPES = ["BRAKE", "ACCEL", "LEFT_CORNER", "RIGHT_CORNER", "COMBINED", "TRANSITION"]


class EventDetector:
    def __init__(self, mode: str, trigger_g: Optional[float] = None):
        self.set_mode(mode, trigger_g)
        self._active: Dict[str, bool] = {k: False for k in EVENT_TYPES}
        self._last_gy_sign = 0
        self._sign_change_t: Optional[float] = None

    def set_mode(self, mode: str, trigger_g: Optional[float] = None):
        """trigger_g を渡すと既定閾値の代わりに使う (適応キャリブレーションの補正値)。"""
        self.mode = mode
        self.t_on = trigger_g if trigger_g is not None else Config.EVENT_TRIGGER_G.get(mode, 0.30)
        self.t_off = self.t_on * Config.EVENT_RELEASE_RATIO

    def update(self, d: DynamicsSample) -> List[str]:
        """開始したイベント種別のリストを返す (終了判定は EventTracker 側で行う)。

        路面外乱(うねり・段差)検出中は「新規イベントの開始」のみ抑制する。
        既に進行中のイベントは、路面外乱の有無に関わらず正常にリリース判定を行う
        (ブレーキ中にたまたま段差を踏んだ場合にイベントが不自然に途切れないようにするため)。
        """
        started = []
        # 路面外乱による新規イベント抑制はモード別。サーキットでは縁石を踏んだ
        # 瞬間に始まる正当なブレーキ/旋回を取りこぼさないよう抑制しない。
        suppress_enabled = Config.ROAD_SUPPRESS_EVENTS_BY_MODE.get(self.mode, True)
        suppress_new = d.road_disturbance and suppress_enabled

        if not suppress_new:
            if d.gx < -self.t_on and not self._active["BRAKE"]:
                self._active["BRAKE"] = True
                started.append("BRAKE")
            if d.gx > self.t_on and not self._active["ACCEL"]:
                self._active["ACCEL"] = True
                started.append("ACCEL")
            if d.gy > self.t_on and not self._active["LEFT_CORNER"]:
                self._active["LEFT_CORNER"] = True
                started.append("LEFT_CORNER")
            if d.gy < -self.t_on and not self._active["RIGHT_CORNER"]:
                self._active["RIGHT_CORNER"] = True
                started.append("RIGHT_CORNER")
            if d.gxy > self.t_on * 1.3 and abs(d.gx) > self.t_on * 0.5 and abs(d.gy) > self.t_on * 0.5 \
                    and not self._active["COMBINED"]:
                self._active["COMBINED"] = True
                started.append("COMBINED")

            # 切り返し (§40): 横Gの符号反転を1.5秒以内に検出
            sign = 1 if d.gy > self.t_on else (-1 if d.gy < -self.t_on else 0)
            if sign != 0:
                if self._last_gy_sign != 0 and sign != self._last_gy_sign:
                    started.append("TRANSITION")
                self._last_gy_sign = sign

        # 終了判定 (release threshold) -- 路面外乱の有無に関わらず常に評価する
        if self._active["BRAKE"] and d.gx > -self.t_off:
            self._active["BRAKE"] = False
        if self._active["ACCEL"] and d.gx < self.t_off:
            self._active["ACCEL"] = False
        if self._active["LEFT_CORNER"] and d.gy < self.t_off:
            self._active["LEFT_CORNER"] = False
        if self._active["RIGHT_CORNER"] and d.gy > -self.t_off:
            self._active["RIGHT_CORNER"] = False
        if self._active["COMBINED"] and d.gxy < self.t_off * 1.3:
            self._active["COMBINED"] = False

        return started

    def active_types(self) -> List[str]:
        return [k for k, v in self._active.items() if v]

    def reset(self):
        """レビュー指摘(センサ無応答からの解析再開時のコーナーケース): 一時停止中に
        内部状態(どのイベントが「進行中」か)が古いサンプルのまま固まってしまうと、
        再開直後に数秒分のギャップを挟んだ波形が1つのイベントとして誤って
        つながってしまう恐れがある。再開時に必ず呼び出し、進行中扱いを解除する。"""
        self._active = {k: False for k in EVENT_TYPES}
        self._last_gy_sign = 0
        self._sign_change_t = None


# =========================================================================
# 11. Event Analysis  (§42-49)
# =========================================================================

@dataclass
class DrivingEvent:
    event_id: str
    event_type: str
    start_t: float
    end_t: float
    duration: float
    peak_g: float
    peak_jerk: float
    avg_g: float
    rms_g: float
    peak_load_transfer: float
    peak_load_transfer_rate: float
    settling_time: Optional[float]
    overshoot: Optional[float]
    g_vector_angle: float
    entry_slope: float
    exit_slope: float
    score: float = 0.0
    confidence: float = 1.0
    road_disturbance_ratio: float = 0.0
    lat: Optional[float] = None
    lon: Optional[float] = None
    speed: Optional[float] = None
    # スコアの内訳(G制御/ジャーク/荷重移動/整定性/一貫性)。UIで「なぜこの点数か」を
    # 示すために保持する。_finalize_event() で score と同時に埋める。
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    # [1][2] このイベント区間内でのTraction Utilization Ratio最大値。
    # 「実際にグリップ限界をどれだけ使い切っていたか」を示す連続量(1.0=推定上限到達)。
    peak_tur: float = 0.0


class EventAnalyzer:
    @staticmethod
    def analyze(event_type: str, waveform: List[DynamicsSample], gps: Optional[SensorSample]) -> DrivingEvent:
        n_total = len(waveform)
        n_rough = sum(1 for d in waveform if d.road_disturbance)
        disturbance_ratio = (n_rough / n_total) if n_total else 0.0

        # 路面外乱区間を除いたサンプルが半数以上残る場合は、特徴量計算からは
        # 外乱区間を除外する (ただし波形自体は破棄せず全区間を保持する)。
        clean = [d for d in waveform if not d.road_disturbance]
        feature_source = clean if len(clean) >= max(1, n_total // 2) else waveform

        if event_type in ("BRAKE", "ACCEL"):
            series = [d.gx for d in feature_source]
        elif event_type in ("LEFT_CORNER", "RIGHT_CORNER", "TRANSITION"):
            series = [d.gy for d in feature_source]
        else:
            series = [d.gxy for d in feature_source]

        abs_series = [abs(x) for x in series]
        peak_g = max(abs_series) if abs_series else 0.0
        avg_g = sum(abs_series) / len(abs_series) if abs_series else 0.0
        rms_g = math.sqrt(sum(x ** 2 for x in abs_series) / len(abs_series)) if abs_series else 0.0
        peak_jerk = max((d.jxy for d in feature_source), default=0.0)
        # [1][2] このイベント中に実際にどれだけグリップを使い切っていたかの最大値。
        peak_tur = max((d.tur for d in feature_source), default=0.0)

        lt_series = [d.lt_long if event_type in ("BRAKE", "ACCEL") else d.lt_lat for d in feature_source]
        lt_abs = [abs(x) for x in lt_series]
        peak_lt = max(lt_abs) if lt_abs else 0.0
        lt_rate_series = [d.lt_long_rate if event_type in ("BRAKE", "ACCEL") else d.lt_lat_rate
                           for d in feature_source]
        peak_lt_rate = max((abs(x) for x in lt_rate_series), default=0.0)

        settling_time, overshoot = EventAnalyzer._settling(feature_source, lt_series)

        theta = waveform[-1].theta if waveform else 0.0
        entry_slope = EventAnalyzer._slope(abs_series[: max(1, len(abs_series) // 3)])
        exit_slope = EventAnalyzer._slope(abs_series[-max(1, len(abs_series) // 3):])

        duration = waveform[-1].t - waveform[0].t if len(waveform) > 1 else 0.0

        # 外乱の影響割合に応じてイベントの信頼度を下げる (完全な路面ノイズ混入時は最大60%減)。
        # あわせて、このイベント区間のセンサ時刻スキュー信頼度(sensor_reliability, ①)も
        # 掛け合わせる。
        avg_sensor_reliability = ((sum(d.sensor_reliability for d in waveform) / n_total)
                                   if n_total else 1.0)
        confidence = max(0.0, (1.0 - disturbance_ratio * Config.ROAD_EVENT_CONFIDENCE_PENALTY)
                          * avg_sensor_reliability)

        return DrivingEvent(
            event_id=str(uuid.uuid4())[:8],
            event_type=event_type,
            start_t=waveform[0].t if waveform else 0.0,
            end_t=waveform[-1].t if waveform else 0.0,
            duration=duration,
            peak_g=peak_g, peak_jerk=peak_jerk, avg_g=avg_g, rms_g=rms_g,
            peak_load_transfer=peak_lt, peak_load_transfer_rate=peak_lt_rate,
            settling_time=settling_time, overshoot=overshoot,
            g_vector_angle=theta, entry_slope=entry_slope, exit_slope=exit_slope,
            confidence=confidence, road_disturbance_ratio=round(disturbance_ratio, 3),
            lat=(gps.lat if gps else None), lon=(gps.lon if gps else None),
            speed=(gps.speed if gps else None),
            peak_tur=round(peak_tur, 3),
        )

    @staticmethod
    def _slope(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        return (values[-1] - values[0]) / max(1, len(values) - 1)

    @staticmethod
    def _settling(waveform, lt_series):
        if not lt_series:
            return None, None
        peak_idx = max(range(len(lt_series)), key=lambda i: abs(lt_series[i]))
        lt_peak = lt_series[peak_idx]
        threshold = 0.1 * abs(lt_peak)
        settling_time = None
        for i in range(peak_idx, len(lt_series)):
            if abs(lt_series[i]) < threshold:
                settling_time = waveform[i].t - waveform[peak_idx].t
                break
        reverse_max = 0.0
        for i in range(peak_idx, len(lt_series)):
            if (lt_peak > 0 and lt_series[i] < 0) or (lt_peak < 0 and lt_series[i] > 0):
                reverse_max = max(reverse_max, abs(lt_series[i]))
        overshoot = (reverse_max / abs(lt_peak)) if lt_peak else None
        return settling_time, overshoot


# =========================================================================
# 12. Periodic Analysis  (§50-51)
# =========================================================================

@dataclass
class PeriodicStat:
    t_start: float
    t_end: float
    mean_gx: float; mean_gy: float
    peak_gx: float; peak_gy: float
    rms_gx: float; rms_gy: float
    peak_gxy: float
    jerk_rms: float; peak_jerk: float
    event_count: int
    mean_load_transfer: float
    peak_load_transfer: float
    consistency: float
    lr_balance: float
    road_roughness_pct: float = 0.0
    score: float = 0.0
    confidence: float = 1.0


class PeriodicAnalyzer:
    def __init__(self):
        self.window: List[DynamicsSample] = []
        self.t_window_start: Optional[float] = None
        self.recent_event_gy: List[float] = []

    def add(self, d: DynamicsSample):
        if self.t_window_start is None:
            self.t_window_start = d.t
        self.window.append(d)

    def ready(self, t_now) -> bool:
        return self.t_window_start is not None and (t_now - self.t_window_start) >= Config.PERIODIC_WINDOW_SEC

    def flush(self, events_in_window: List[DrivingEvent]) -> PeriodicStat:
        w_all = self.window
        n_total = len(w_all)
        n_rough = sum(1 for d in w_all if d.road_disturbance)
        road_roughness_pct = (100.0 * n_rough / n_total) if n_total else 0.0

        # スムーズさ・Jerk等のスコアに路面外乱を巻き込まないよう、外乱区間を除いた
        # サンプル集合を優先的に使う (残存が半数未満なら全区間にフォールバック)。
        clean = [d for d in w_all if not d.road_disturbance]
        w = clean if len(clean) >= max(1, n_total // 2) else w_all

        gx = [d.gx for d in w] or [0.0]
        gy = [d.gy for d in w] or [0.0]
        gxy = [d.gxy for d in w] or [0.0]
        jxy = [d.jxy for d in w] or [0.0]
        lt = [abs(d.lt_long) + abs(d.lt_lat) for d in w] or [0.0]

        def rms(vals):
            return math.sqrt(sum(v ** 2 for v in vals) / len(vals))

        left_events = [e.avg_g for e in events_in_window if e.event_type == "LEFT_CORNER"]
        right_events = [e.avg_g for e in events_in_window if e.event_type == "RIGHT_CORNER"]
        lr_balance = 100.0
        if left_events and right_events:
            xl = sum(left_events) / len(left_events)
            xr = sum(right_events) / len(right_events)
            d_lr = abs(xl - xr) / (((abs(xl) + abs(xr)) / 2.0) or 1e-6)
            lr_balance = max(0.0, min(100.0, 100.0 * (1 - d_lr)))

        consistency = 100.0
        durations = [e.duration for e in events_in_window]
        if len(durations) >= 2 and sum(durations) > 0:
            mean_d = sum(durations) / len(durations)
            var_d = sum((x - mean_d) ** 2 for x in durations) / len(durations)
            cv = math.sqrt(var_d) / abs(mean_d) if mean_d else 0.0
            consistency = max(0.0, min(100.0, 100.0 * (1 - cv)))

        # このウィンドウの信頼度: 路面外乱の割合(既存のイベント信頼度と同じ考え方)に加え、
        # レビュー指摘①のセンサ時刻スキュー由来の信頼度(sensor_reliability)も反映する。
        avg_reliability = (sum(d.sensor_reliability for d in w_all) / n_total) if n_total else 1.0
        confidence = max(0.0, min(1.0,
            (1.0 - (road_roughness_pct / 100.0) * Config.ROAD_EVENT_CONFIDENCE_PENALTY) * avg_reliability))

        stat = PeriodicStat(
            t_start=w_all[0].t if w_all else 0.0, t_end=w_all[-1].t if w_all else 0.0,
            mean_gx=sum(gx) / len(gx), mean_gy=sum(gy) / len(gy),
            peak_gx=max(gx, key=abs), peak_gy=max(gy, key=abs),
            rms_gx=rms(gx), rms_gy=rms(gy), peak_gxy=max(gxy),
            jerk_rms=rms(jxy), peak_jerk=max(jxy),
            event_count=len(events_in_window),
            mean_load_transfer=sum(lt) / len(lt), peak_load_transfer=max(lt),
            consistency=consistency, lr_balance=lr_balance,
            road_roughness_pct=round(road_roughness_pct, 1),
            confidence=round(confidence, 3),
        )
        self.window = []
        self.t_window_start = None
        return stat


# =========================================================================
# 13. Scoring Engine  (§43-54)
# =========================================================================

class ScoringEngine:
    def __init__(self, mode: str, jerk_limit: Optional[float] = None,
                 lt_rate_limit: Optional[float] = None):
        self.mode = mode
        # 適応キャリブレーションの補正上限。未指定ならConfig既定値。
        self.jerk_limit = jerk_limit if jerk_limit is not None else Config.JERK_LIMIT_G_PER_S
        self.lt_rate_limit = lt_rate_limit if lt_rate_limit is not None else Config.LOAD_TRANSFER_RATE_LIMIT
        # Version 1.4: total_score()呼び出し直後の内訳(ボーナス加点の透明性確保用)。
        self.last_base_score: Optional[float] = None
        self.last_bonus: float = 0.0

    def set_mode(self, mode: str):
        self.mode = mode

    def _clip(self, v):
        return max(0.0, min(100.0, v))

    @staticmethod
    def _soft_penalty(ratio: float) -> float:
        """Version 1.4: 減点カーブの緩和 (「下がりやすい」への対策)。

        ratio は「実測値 / 従来の線形減点式で0点に達する値」(0=問題なし、
        1.0=従来式でもちょうど0点になる超過量)。Config.SCORE_SOFTEN_POWER (>1) で
        べき乗することで、ratioが小さい(=閾値をわずかに超えた程度の軽微な逸脱)領域では
        従来の線形式より大幅に減点を抑え、ratioが1に近づく大きな逸脱では従来同様
        しっかり減点する(ratio>=1で0点に達する境界は従来と同一)。
        power=1.0を指定すれば従来の線形減点と完全に一致する(後方互換)。"""
        if ratio <= 0:
            return 0.0
        power = max(1.0, Config.SCORE_SOFTEN_POWER)
        return 100.0 * min(1.0, ratio ** power)

    def _event_score_components(self, ev: DrivingEvent) -> Dict[str, float]:
        """個別イベントのスコアを要素ごとに算出する。score_event()はこの合計を
        返すだけの薄いラッパーとし、内訳(UI表示用)はここから個別に取得できるようにする。
        Version 1.4: 各成分は「実測値/従来式で0点になる基準値」の比率(ratio)を
        _soft_penalty()に渡す形へ統一し、閾値をわずかに超えた程度では大きく
        減点しないよう緩和した(基準値=従来の乗数の逆数。大幅超過時に0点へ
        達する境界は従来と同一で、危険側の判定基準は変えていない)。"""
        s_j = self._clip(100.0 - self._soft_penalty(ev.peak_jerk / self.jerk_limit))
        s_l = self._clip(100.0 - self._soft_penalty(ev.peak_load_transfer_rate / self.lt_rate_limit))
        # オーバーシュート: 従来式 (overshoot*40) は overshoot=2.5 で0点相当 -> 基準値2.5
        s_c = self._clip(100.0 - self._soft_penalty((ev.overshoot or 0.0) / 2.5))

        if self.mode == "CIRCUIT":
            s_g = 85.0  # サーキットでは大きなG自体を減点しない (§44, §46)
            s_l = self._clip(s_l + 15.0)
        elif self.mode == "STREET":
            # 従来式 (excess*150) は excess=0.6667G で0点相当 -> 基準値0.6667
            s_g = self._clip(100.0 - self._soft_penalty(max(0.0, ev.peak_g - 0.3) / 0.6667))
        else:  # MOUNTAIN
            # 従来式 (excess*100) は excess=1.0Gで0点相当 -> 基準値1.0
            s_g = self._clip(100.0 - self._soft_penalty(max(0.0, ev.peak_g - 0.5) / 1.0))

        # 整定時間: 従来式 (settling_time*20) は5.0秒で0点相当 -> 基準値5.0
        s_t = self._clip(100.0 - self._soft_penalty((ev.settling_time or 0.0) / 5.0))

        weights = dict(g=0.25, j=0.25, l=0.20, t=0.15, c=0.15)
        total = (weights["g"] * s_g + weights["j"] * s_j + weights["l"] * s_l
                 + weights["t"] * s_t + weights["c"] * s_c)
        # 日本語ラベル付きでフロントエンドにそのまま渡せる形にしておく。
        return {
            "G制御": round(s_g, 1), "ジャーク": round(s_j, 1), "荷重移動": round(s_l, 1),
            "整定性": round(s_t, 1), "一貫性": round(s_c, 1),
            "_total": round(self._clip(total), 1),
        }

    def score_event(self, ev: DrivingEvent) -> float:
        return self._event_score_components(ev)["_total"]

    def score_event_breakdown(self, ev: DrivingEvent) -> Dict[str, float]:
        """UI表示用の内訳(合計スコアを除く)。"""
        comps = self._event_score_components(ev)
        comps.pop("_total", None)
        return comps

    def score_periodic(self, stat: PeriodicStat) -> float:
        """Version 1.4: 「該当イベント無し(穏やかな)区間」の基礎点を、旧来の固定90点から
        Config.SCORE_NEUTRAL_FLOOR(既定96点)へ引き上げた。急制動/急加速/急旋回が
        一切無かったこと自体、安全運転として積極的に評価すべきであり、100点に届かない
        神学的な理由は無いため(ただし満点=100は「データ上、より良い状態が無かった」
        ことの確認が取れないため、わずかに余白を残す)。各減点成分も_soft_penalty()で
        緩和している。"""
        w = Config.PERIODIC_WEIGHTS[self.mode]
        neutral = Config.SCORE_NEUTRAL_FLOOR
        # 従来式 (jerk_rms*60) は jerk_rms=1.667で0点相当 -> 基準値1.667
        s_smooth = self._clip(100.0 - self._soft_penalty(stat.jerk_rms / 1.667))
        if stat.peak_gx < 0:
            s_brake = self._clip(100.0 - self._soft_penalty(max(0.0, -stat.peak_gx - 0.3) / 1.0))
        else:
            s_brake = neutral
        if stat.peak_gx > 0:
            s_accel = self._clip(100.0 - self._soft_penalty(max(0.0, stat.peak_gx - 0.3) / 1.0))
        else:
            s_accel = neutral
        s_corner = self._clip(100.0 - self._soft_penalty(max(0.0, abs(stat.peak_gy) - 0.35) / 1.0))
        s_load = self._clip(100.0 - self._soft_penalty(
            stat.peak_load_transfer / Config.LOAD_TRANSFER_LIMIT_SUM))
        s_consistency = stat.consistency

        score = (w["smooth"] * s_smooth + w["brake"] * s_brake + w["accel"] * s_accel
                 + w["corner"] * s_corner + w["load"] * s_load + w["consistency"] * s_consistency)
        return round(self._clip(score), 1)

    def total_score(self, periodic: List[Tuple[float, float]],
                     events: List[Tuple[float, float]]) -> Optional[float]:
        """periodic/events は (score, confidence) のペアのリスト。
        レビュー指摘⑬⑭: これまでconfidence(信頼度)は算出するだけでスコアに一切
        反映されていなかった。ここでは信頼度で重み付けした加重平均を使う:
            WeightedScore = Σ(score_i * confidence_i) / Σ(confidence_i)
        データが無い場合は "80点" という架空の既定値を返さず None (=N/A) を返す
        (レビュー指摘㉛: 「データが無い=80点」は評価器として危険)。

        Version 1.4: セッションを通じて高スコア(Config.SCORE_EXCELLENCE_THRESHOLD以上)を
        維持できた割合に応じ、「優良運転ボーナス」(最大Config.SCORE_EXCELLENCE_BONUS_MAX点)を
        加点する(「加算されにくい」への対策)。単発の高スコアだけで満額ボーナスに
        ならないよう、対象サンプル数が少ないうちはボーナスを比例的に減衰させる。
        呼び出し側がボーナス内訳を表示できるよう、直近の計算結果を
        self.last_base_score / self.last_bonus に保持する。"""
        def _weighted(items: List[Tuple[float, float]]) -> Optional[float]:
            if not items:
                return None
            total_c = sum(c for _, c in items)
            if total_c <= 1e-6:
                return sum(s for s, _ in items) / len(items)
            return sum(s * c for s, c in items) / total_c

        s_period = _weighted(periodic)
        s_event = _weighted(events)
        if s_period is None and s_event is None:
            self.last_base_score = None
            self.last_bonus = 0.0
            return None
        if s_period is None:
            base_total = s_event
        elif s_event is None:
            base_total = s_period
        else:
            base_total = Config.ALPHA_PERIODIC * s_period + (1 - Config.ALPHA_PERIODIC) * s_event
        base_total = self._clip(base_total)

        all_items = list(periodic) + list(events)
        bonus = 0.0
        if all_items and Config.SCORE_EXCELLENCE_BONUS_MAX > 0:
            good = sum(1 for s, _ in all_items if s >= Config.SCORE_EXCELLENCE_THRESHOLD)
            good_ratio = good / len(all_items)
            # サンプル数が少ないうち(目安8件未満)はボーナスを比例的に抑制し、
            # 走行開始直後の1〜2件の好調だけで満額ボーナスにならないようにする。
            n_factor = min(1.0, len(all_items) / 8.0)
            bonus = round(Config.SCORE_EXCELLENCE_BONUS_MAX * good_ratio * n_factor, 2)

        self.last_base_score = round(base_total, 1)
        self.last_bonus = bonus
        return round(self._clip(base_total + bonus), 1)


# =========================================================================
# 14. Driver Behavior Analysis  (§56-65)
# =========================================================================

class DriverBehaviorAnalyzer:
    def __init__(self, driver: Driver):
        self.driver = driver

    def update_fingerprint(self, event: DrivingEvent, periodic: Optional[PeriodicStat]):
        fp = self.driver.stats.fingerprint
        lam = Config.FINGERPRINT_EMA_LAMBDA

        def ema(key, new_value):
            fp[key] = round((1 - lam) * fp[key] + lam * new_value, 1)

        ema("jerk_control", max(0.0, min(100.0, 100 - event.peak_jerk * 30)))
        ema("load_transfer_control",
            max(0.0, min(100.0, 100.0 * (1 - event.peak_load_transfer_rate / Config.LOAD_TRANSFER_RATE_LIMIT))))
        if event.event_type == "BRAKE":
            ema("brake_control", event.score)
        elif event.event_type == "ACCEL":
            ema("accel_control", event.score)
        elif event.event_type in ("LEFT_CORNER", "RIGHT_CORNER", "TRANSITION"):
            ema("cornering_control", event.score)
        if periodic:
            ema("smoothness", 100 - periodic.jerk_rms * 60)
            ema("consistency", periodic.consistency)
            ema("lr_symmetry", periodic.lr_balance)

    def detect_habits(self, events: List[DrivingEvent]) -> List[Dict[str, Any]]:
        habits = []
        if len(events) < Config.MIN_EVENTS_FOR_HABIT:
            return [{"text": "分析データ不足", "confidence": 0}]

        n = len(events)
        confidence = min(1.0, n / Config.HABIT_CONFIDENCE_TARGET_N)

        brakes = [e for e in events if e.event_type == "BRAKE"]
        if len(brakes) >= Config.MIN_EVENTS_FOR_HABIT:
            avg_jerk = sum(e.peak_jerk for e in brakes) / len(brakes)
            if avg_jerk > 1.5:
                habits.append({"text": "ブレーキ初期入力が強め", "strength": "HIGH",
                                "confidence": round(confidence * 100)})
            else:
                habits.append({"text": "スムーズなブレーキ操作", "strength": "MEDIUM",
                                "confidence": round(confidence * 100)})

        left = [e for e in events if e.event_type == "LEFT_CORNER"]
        right = [e for e in events if e.event_type == "RIGHT_CORNER"]
        if len(left) >= 3 and len(right) >= 3:
            jl = sum(e.peak_jerk for e in left) / len(left)
            jr = sum(e.peak_jerk for e in right) / len(right)
            if abs(jl - jr) > 0.3:
                side = "左" if jl > jr else "右"
                habits.append({"text": f"{side}旋回時のJerkが反対側より高い", "strength": "MEDIUM",
                                "confidence": round(confidence * 100)})

        transitions = [e for e in events if e.event_type == "TRANSITION"]
        if len(transitions) >= 3:
            avg_settle = sum((e.settling_time or 0.0) for e in transitions) / len(transitions)
            if avg_settle < 0.6:
                habits.append({"text": "切り返し後のG収束が速い", "strength": "MEDIUM",
                                "confidence": round(confidence * 100)})

        lt_values = [e.peak_load_transfer for e in events]
        if len(lt_values) >= Config.MIN_EVENTS_FOR_HABIT:
            mean_lt = sum(lt_values) / len(lt_values)
            var_lt = sum((x - mean_lt) ** 2 for x in lt_values) / len(lt_values)
            cv = (math.sqrt(var_lt) / mean_lt) if mean_lt else 1.0
            if cv < 0.25:
                habits.append({"text": "荷重移動の再現性が高い", "strength": "MEDIUM",
                                "confidence": round(confidence * 100)})

        if not habits:
            habits.append({"text": "分析データ不足", "confidence": round(confidence * 100)})
        return habits


# =========================================================================
# 15. Data Storage  (§72-74)
# =========================================================================

class DataStorage:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        # 走行ログは専用の logs フォルダ (プログラムフォルダ配下) に保管する。
        self.sessions_dir = Config.LOG_DIR
        os.makedirs(self.sessions_dir, exist_ok=True)

    def save_session(self, session: Dict[str, Any]):
        path = os.path.join(self.sessions_dir, f"{session['session_id']}.json")
        save_json(path, session)

    def list_sessions(self) -> List[str]:
        return sorted(f for f in os.listdir(self.sessions_dir) if f.endswith(".json"))

    def load_session(self, filename: str) -> Optional[Dict[str, Any]]:
        return load_json(os.path.join(self.sessions_dir, filename), None)

    def load_sessions(self, driver_id: Optional[str] = None,
                      vehicle_id: Optional[str] = None,
                      mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """条件一致の走行ログを新しい順に読み込んで返す (自動分析用)。"""
        out = []
        for fn in sorted(self.list_sessions(), reverse=True):
            rec = self.load_session(fn)
            if not rec:
                continue
            if driver_id and rec.get("driver_id") != driver_id:
                continue
            if vehicle_id and rec.get("vehicle_id") != vehicle_id:
                continue
            if mode and rec.get("mode") != mode:
                continue
            out.append(rec)
        return out

    def _log_epoch(self, filename: str, rec: Optional[Dict[str, Any]]) -> float:
        if rec and isinstance(rec.get("start_time"), (int, float)):
            return float(rec["start_time"])
        stem = filename[:-5] if filename.endswith(".json") else filename
        try:
            return time.mktime(time.strptime(stem, "%Y%m%d_%H%M%S"))
        except Exception:
            try:
                return os.path.getmtime(os.path.join(self.sessions_dir, filename))
            except Exception:
                return time.time()

    def prune_old_logs(self, retention_days: Optional[int] = None) -> List[str]:
        """保持期間を過ぎた走行ログを削除し、削除ファイル名を返す。"""
        days = retention_days if retention_days is not None else Config.LOG_RETENTION_DAYS
        if not days or days <= 0:
            return []
        cutoff = time.time() - days * 86400.0
        removed = []
        for fn in self.list_sessions():
            rec = self.load_session(fn)
            if self._log_epoch(fn, rec) < cutoff:
                try:
                    os.remove(os.path.join(self.sessions_dir, fn))
                    removed.append(fn)
                except OSError:
                    pass
        return removed


def _percentile(sorted_vals: List[float], pctl: float) -> float:
    """線形補間パーセンタイル (numpy非依存, sorted_valsは昇順前提)。"""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pctl / 100.0)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _dist_stats(vals: List[float]) -> Dict[str, float]:
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0, "p50": 0.0, "p90": 0.0, "max": 0.0}
    s = sorted(vals)
    mean = sum(s) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in s) / n)
    return {"n": n, "mean": round(mean, 3), "std": round(std, 3),
            "p50": round(_percentile(s, 50), 3), "p90": round(_percentile(s, 90), 3),
            "max": round(s[-1], 3)}


class DrivingProfileAnalyzer:
    """蓄積走行ログから運転特性分布を集計し、検出閾値と正規化上限の推奨補正値を算出。"""

    @staticmethod
    def analyze(sessions: List[Dict[str, Any]], mode: str) -> Optional[Dict[str, Any]]:
        if len(sessions) < Config.ADAPTIVE_MIN_SESSIONS:
            return None
        peak_g, peak_jerk, lt_rate = [], [], []
        brake_g, accel_g, corner_g = [], [], []
        for s in sessions:
            for e in s.get("events", []):
                pg = abs(e.get("peak_g", 0.0))
                if pg > 0:
                    peak_g.append(pg)
                pj = abs(e.get("peak_jerk", 0.0))
                if pj > 0:
                    peak_jerk.append(pj)
                lr = abs(e.get("peak_load_transfer_rate", 0.0))
                if lr > 0:
                    lt_rate.append(lr)
                et = e.get("event_type", "")
                if et == "BRAKE":
                    brake_g.append(pg)
                elif et == "ACCEL":
                    accel_g.append(pg)
                elif et in ("LEFT_CORNER", "RIGHT_CORNER"):
                    corner_g.append(pg)
        if len(peak_g) < Config.ADAPTIVE_MIN_EVENTS:
            return None

        def clamp(v, lo_hi):
            return max(lo_hi[0], min(lo_hi[1], v))

        trigger = clamp(_percentile(sorted(peak_g), Config.ADAPTIVE_TRIGGER_PCTL),
                        Config.ADAPTIVE_TRIGGER_CLAMP)
        jerk_lim = clamp(_percentile(sorted(peak_jerk), Config.ADAPTIVE_NORM_PCTL)
                         if peak_jerk else Config.JERK_LIMIT_G_PER_S, Config.ADAPTIVE_JERK_CLAMP)
        lt_lim = clamp(_percentile(sorted(lt_rate), Config.ADAPTIVE_NORM_PCTL)
                       if lt_rate else Config.LOAD_TRANSFER_RATE_LIMIT, Config.ADAPTIVE_LT_RATE_CLAMP)

        corrections = {"event_trigger_g": round(trigger, 3),
                       "jerk_limit_g_per_s": round(jerk_lim, 3),
                       "lt_rate_limit": round(lt_lim, 3)}

        # --- [2] 適応グリップ包絡線 (mu_long_max/mu_lat_max) ---
        # 制動方向は「実際にタイヤ限界まで使われたG」を最も反映しやすい brake_g の
        # 上側パーセンタイルを使う(加速は多くの市販車でエンジン出力律速となり、
        # タイヤグリップの真の上限を過小評価しやすいため採用しない)。
        # 旋回方向は corner_g (左右コーナー実績)を使う。十分なサンプル数が
        # ある場合のみ推定し、不足時はキーを含めずConfig既定値へフォールバックさせる
        # (AdaptiveProfileStore.update()のEMAブレンドは欠損キーを許容する)。
        min_n = max(5, Config.ADAPTIVE_MIN_EVENTS // 4)
        if len(brake_g) >= min_n:
            corrections["mu_long_max"] = round(
                clamp(_percentile(sorted(brake_g), Config.GRIP_ENVELOPE_PCTL),
                      Config.GRIP_MU_LONG_CLAMP), 3)
        if len(corner_g) >= min_n:
            corrections["mu_lat_max"] = round(
                clamp(_percentile(sorted(corner_g), Config.GRIP_ENVELOPE_PCTL),
                      Config.GRIP_MU_LAT_CLAMP), 3)

        return {
            "mode": mode, "n_sessions": len(sessions), "n_events": len(peak_g),
            "updated_at": time.time(),
            "corrections": corrections,
            "distribution": {"peak_g": _dist_stats(peak_g), "brake_g": _dist_stats(brake_g),
                             "accel_g": _dist_stats(accel_g), "corner_g": _dist_stats(corner_g),
                             "peak_jerk": _dist_stats(peak_jerk), "lt_rate": _dist_stats(lt_rate)},
        }


class AdaptiveProfileStore:
    """ドライバー×車両×モード毎の補正プロファイルをJSON永続化。新推定はEMAで混合。"""

    def __init__(self, path: str):
        self.path = path
        self.data: Dict[str, Any] = load_json(path, {})

    @staticmethod
    def _key(driver_id, vehicle_id, mode):
        return f"{driver_id}|{vehicle_id}|{mode}"

    def get(self, driver_id, vehicle_id, mode):
        return self.data.get(self._key(driver_id, vehicle_id, mode))

    def get_corrections(self, driver_id, vehicle_id, mode):
        prof = self.get(driver_id, vehicle_id, mode)
        return prof.get("corrections") if prof else None

    def update(self, driver_id, vehicle_id, analysis):
        key = self._key(driver_id, vehicle_id, analysis["mode"])
        lam = Config.ADAPTIVE_EMA_LAMBDA
        prev = self.data.get(key)
        new_corr = analysis["corrections"]
        if prev and "corrections" in prev:
            blended = {k: round(prev["corrections"].get(k, v) * (1 - lam) + v * lam, 3)
                       for k, v in new_corr.items()}
        else:
            blended = dict(new_corr)
        analysis = dict(analysis)
        analysis["corrections"] = blended
        self.data[key] = analysis
        save_json(self.path, self.data)
        return analysis


# =========================================================================
# 16/17. HTML Generator & HTTP Interface
# =========================================================================

HTML_PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>Driving Dynamics Analyzer</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; background:#0d1117; color:#e6edf3; font-family:'Segoe UI',sans-serif; }
  header { padding:10px 14px; background:#161b22; border-bottom:1px solid #30363d; position:relative; }
  header h1 { font-size:16px; margin:0; letter-spacing:1px; }
  header .sub { font-size:11px; color:#8b949e; margin-top:2px; }
  .setup { padding:14px; }
  select, button { width:100%; padding:10px; margin:6px 0; background:#21262d; color:#e6edf3;
                    border:1px solid #30363d; border-radius:6px; font-size:15px; }
  button.primary { background:#238636; border:none; font-weight:bold; }
  button.stop { background:#da3633; border:none; font-weight:bold; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:10px 14px; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px; text-align:center; }
  .card .label { font-size:11px; color:#8b949e; }
  .card .value { font-size:24px; font-weight:bold; margin-top:4px; }
  .score-big { text-align:center; padding:10px; }
  .score-big .value { font-size:56px; font-weight:bold; color:#3fb950; }
  canvas { display:block; margin:0 auto; background:#010409; border-radius:8px; }
  .event-box { margin:10px 14px; padding:10px; background:#161b22; border:1px solid #30363d; border-radius:8px; }
  .event-box .type { font-weight:bold; color:#58a6ff; }
  .habit-list { margin:10px 14px; padding:10px; background:#161b22; border-radius:8px; font-size:13px; }
  .habit-list li { margin:4px 0; }
  .hidden { display:none; }
  .status-bar { font-size:11px; color:#8b949e; padding:4px 14px; }
</style>
</head>
<body>
<header>
  <button type="button" id="settingsBtn" onclick="openSettings()"
    style="position:absolute; top:8px; right:10px; width:auto; padding:6px 10px; font-size:16px;
           background:#21262d; border:1px solid #30363d; border-radius:6px; color:#e6edf3;"
    title="設定・学習状況">⚙</button>
  <h1>DRIVING DYNAMICS ANALYZER</h1>
  <div class="sub" id="subline">Driver / Vehicle / Mode を選択してください</div>
  <div style="font-size:10px; color:#6e7681; margin-top:2px;">
    Ver <span id="appVersion">-</span> &nbsp;|&nbsp; by <span id="appAuthor">-</span>
  </div>
</header>

<div id="settingsPanel" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
     z-index:50; align-items:flex-start; justify-content:center; overflow-y:auto;">
  <div style="background:#161b22; border:1px solid #30363d; border-radius:10px; padding:16px;
       margin:30px 12px; max-width:480px; width:100%;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
      <div style="font-size:15px; font-weight:bold; color:#e6edf3;">設定 / 学習進捗</div>
      <button type="button" onclick="closeSettings()"
        style="width:auto; padding:4px 10px; background:#21262d; border:1px solid #30363d;
               border-radius:6px; color:#e6edf3;">✕</button>
    </div>
    <div style="font-size:12px; color:#8b949e; margin-bottom:8px;">
      走行前に調整してください(変更は次回のセッション開始時から反映されます)。
    </div>
    <div id="settingsParams"></div>
    <button type="button" class="primary" style="width:100%; margin-top:8px;" onclick="saveSettings()">
      保存
    </button>
    <div id="settingsMsg" style="font-size:12px; color:#3fb950; margin-top:6px;"></div>

    <div style="border-top:1px solid #30363d; margin-top:14px; padding-top:10px;">
      <div style="font-size:14px; font-weight:bold; color:#e6edf3; margin-bottom:6px;">学習進捗状況</div>
      <div id="learningInfo" style="font-size:12px; color:#c9d1d9; line-height:1.6;">
        設定を開くと、現在選択中のドライバー・車両・モードの学習状況を表示します。
      </div>
    </div>
  </div>
</div>

<div class="setup" id="setupPanel">
  <div style="display:flex; align-items:center; gap:6px;">
    <select id="driverSel" style="flex:1;"></select>
    <button type="button" style="width:auto; padding:10px 12px;" onclick="openDriverAdd()" title="新規追加">＋</button>
    <button type="button" style="width:auto; padding:10px 12px;" onclick="openDriverEdit()" title="選択中のドライバーを編集">✎</button>
    <button type="button" style="width:auto; padding:10px 12px;" onclick="deleteDriver()" title="選択中のドライバーを削除">🗑</button>
  </div>
  <div class="label" id="driverCount" style="font-size:11px; color:#8b949e; margin:2px 0 8px;"></div>
  <div id="driverForm" class="hidden" style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px; margin-bottom:8px;">
    <div id="driverFormTitle" style="font-size:13px; font-weight:bold; margin-bottom:6px; color:#e6edf3;">ドライバーを追加</div>
    <input type="text" id="newDriverName" placeholder="ドライバー名" style="width:100%; padding:8px; margin-bottom:6px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
    <div style="display:flex; gap:6px;">
      <button type="button" class="primary" style="flex:1;" id="driverSaveBtn" onclick="saveDriver()">ドライバーを追加</button>
      <button type="button" style="width:auto; padding:10px 14px;" onclick="closeDriverForm()">キャンセル</button>
    </div>
    <div id="driverFormMsg" style="font-size:12px; color:#f0883e; margin-top:4px;"></div>
  </div>

  <div style="display:flex; align-items:center; gap:6px;">
    <select id="vehicleSel" style="flex:1;"></select>
    <button type="button" style="width:auto; padding:10px 12px;" onclick="openVehicleAdd()" title="新規追加">＋</button>
    <button type="button" style="width:auto; padding:10px 12px;" onclick="openVehicleEdit()" title="選択中の車両を編集">✎</button>
    <button type="button" style="width:auto; padding:10px 12px;" onclick="deleteVehicle()" title="選択中の車両を削除">🗑</button>
  </div>
  <div class="label" id="vehicleCount" style="font-size:11px; color:#8b949e; margin:2px 0 8px;"></div>
  <div id="vehicleForm" class="hidden" style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px; margin-bottom:8px;">
    <div id="vehicleFormTitle" style="font-size:13px; font-weight:bold; margin-bottom:6px; color:#e6edf3;">車両を追加</div>
    <input type="text" id="newVehicleName" placeholder="車両名 (例: シビック)" style="width:100%; padding:8px; margin-bottom:6px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px;">
      <input type="number" id="newVehicleMass" placeholder="車重 kg (例:1200)" style="padding:8px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
      <input type="number" id="newVehicleWheelbase" placeholder="ホイールベース mm" style="padding:8px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
      <input type="number" id="newVehicleTreadF" placeholder="前トレッド mm" style="padding:8px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
      <input type="number" id="newVehicleTreadR" placeholder="後トレッド mm" style="padding:8px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
      <input type="number" id="newVehicleCg" placeholder="重心高 mm (任意)" style="padding:8px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
      <select id="newVehicleDrive" style="padding:8px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:6px;">
        <option value="FF">FF</option><option value="FR">FR</option><option value="AWD">AWD</option>
      </select>
    </div>
    <div style="display:flex; gap:6px; margin-top:6px;">
      <button type="button" class="primary" style="flex:1;" id="vehicleSaveBtn" onclick="saveVehicle()">車両を追加</button>
      <button type="button" style="width:auto; padding:10px 14px;" onclick="closeVehicleForm()">キャンセル</button>
    </div>
    <div id="vehicleFormMsg" style="font-size:12px; color:#f0883e; margin-top:4px;"></div>
  </div>

  <select id="modeSel" onchange="onModeChange()">
    <option value="STREET">STREET</option>
    <option value="MOUNTAIN">MOUNTAIN</option>
    <option value="CIRCUIT">CIRCUIT</option>
  </select>
  <div id="circuitNote" class="hidden" style="margin:6px 0;padding:8px 10px;background:#0d2b3d;
       border:1px solid #1f6feb;border-radius:6px;color:#9fd0ff;font-size:12px;">
    ℹ CIRCUITモードではグリップ利用率(TUR)の連続監視とタイヤロック/グリップ喪失検出が
    有効になります。制動ロックのジャダー(約10〜20Hz)を捉えるため、Sensor Serverアプリ側の
    <b>加速度センサー配信レートを100Hz以上(SENSOR_DELAY_FASTEST推奨)</b>に設定してください。
    レートが低い間はジャダーに基づく前輪/後輪判定のみ自動的に一時停止し、他の検出は継続します。
    走行データが3セッション・20イベント以上蓄積すると、推定グリップ上限(mu_long_max/
    mu_lat_max)がご自身の実績値に自動的にフィットしていきます。
  </div>
  <div id="sensorNotRunningWarning" class="hidden"
       style="font-size:12px; color:#f0b72f; background:#2d2a1a; border:1px solid #5a4a1a;
              border-radius:6px; padding:10px; margin:6px 0 8px; text-align:left; line-height:1.6;">
    ⚠ <b>Sensor Serverアプリが起動していないか、接続できていません。</b><br>
    <span id="sensorNotRunningReason" style="color:#d9b877; font-size:11px;"></span>
    このままでは実センサではなく<b>シミュレーションデータ</b>で走行が記録されます。<br><br>
    → スマホで「Sensor Server」アプリを起動し、各センサーの配信(Start)をONにしてください。<br>
    (パッケージ名: <code id="sensorServerPackageText">github.umer0586.sensorserver</code>)<br><br>
    まだインストールしていない場合はこちら:
    <a id="sensorServerFdroidLink" href="https://f-droid.org/packages/github.umer0586.sensorserver/"
       target="_blank" rel="noopener" style="color:#58a6ff;">F-Droidでインストール</a><br>
    <span style="font-size:10px; color:#6e7681;">
      (このメッセージは接続状態を数秒おきに自動確認しており、接続できると自動的に消えます)
    </span>
  </div>
  <button class="primary" onclick="startSession()">走行開始 (キャリブレーション)</button>
</div>

<div id="mainPanel" class="hidden">
  <div id="simBanner" class="hidden" style="margin:10px 14px;padding:10px;background:#3d2c00;
       border:1px solid #9e6a03;border-radius:8px;color:#ffdf86;font-size:12px;">
    ⚠ シミュレーションモード動作中 (実センサ未使用)<br>
    <span id="simReason" style="color:#c9b27c;"></span><br>
    静止していてもデモ用の疑似走行データが再生されるため、Gの表示が動きます。
  </div>
  <div id="staleBanner" class="hidden" style="margin:10px 14px;padding:10px;background:#3d1a00;
       border:1px solid #9e4a03;border-radius:8px;color:#ffb686;font-size:12px;">
    ⚠ Sensor Serverには接続できていますが、実データを受信できていません<br>
    <span id="staleDetail" style="color:#d99b6f;"></span><br>
    Sensor Serverアプリ側で該当センサーが正しく開始されているか確認してください。
  </div>
  <div id="tireLockBanner" class="hidden" style="margin:10px 14px;padding:10px;background:#4a0d0d;
       border:1px solid #da3633;border-radius:8px;color:#ffb3b3;font-size:13px;font-weight:bold;">
    ⚠ タイヤロック/グリップ喪失を検出 <span id="tireLockType"></span>
  </div>
  <div class="score-big"><div class="value" id="scoreTotal">--</div><div class="label">TOTAL SCORE</div></div>
  <div style="text-align:center; font-size:11px; color:#8b949e; margin-top:-8px; margin-bottom:6px;" id="scoreReliability"></div>
  <div class="grid">
    <div class="card"><div class="label">Gx (前後)</div><div class="value" id="gx">0.00</div></div>
    <div class="card"><div class="label">Gy (左右)</div><div class="value" id="gy">0.00</div></div>
    <div class="card"><div class="label">Gtotal</div><div class="value" id="gxy">0.00</div></div>
    <div class="card"><div class="label">Jerk</div><div class="value" id="jerk">0.00</div></div>
  </div>
  <canvas id="ggCanvas" width="320" height="320"></canvas>
  <div class="grid">
    <div class="card"><div class="label">平均速度</div><div class="value" id="avgSpeed" style="font-size:16px;">-- km/h</div></div>
    <div class="card"><div class="label">走行距離</div><div class="value" id="distanceKm" style="font-size:16px;">-- km</div></div>
    <div class="card"><div class="label">RMS Gx (前後)</div><div class="value" id="rmsGx" style="font-size:16px;">0.00</div></div>
    <div class="card"><div class="label">RMS Gy (左右)</div><div class="value" id="rmsGy" style="font-size:16px;">0.00</div></div>
  </div>
  <div style="display:flex; align-items:center; justify-content:center; gap:8px; margin:6px 0;">
    <span style="font-size:12px; color:#8b949e;">G-Gボール 前後の向き</span>
    <button type="button" id="ggLongToggle" onclick="toggleGGLong()"
            style="width:auto; padding:6px 12px; font-size:12px;">加速 = 下 ▼</button>
  </div>
  <div id="gripUsageBox" class="habit-list hidden">
    <b>グリップ利用率 (TUR)</b>
    <div style="font-size:11px; color:#8b949e; margin:4px 0 8px;">
      推定グリップ上限に対し、今どれだけタイヤの摩擦力を使っているか(100%=推定限界到達)。
    </div>
    <div style="display:flex; align-items:center; gap:10px;">
      <div style="flex:1; height:16px; background:#21262d; border-radius:8px; overflow:hidden;">
        <div id="turBarFill" style="height:100%; width:0%; background:#3fb950;
             transition:width 0.12s linear, background 0.2s linear;"></div>
      </div>
      <div id="turValue" style="font-size:22px; font-weight:bold; min-width:64px; text-align:right;">0%</div>
    </div>
    <div style="font-size:12px; color:#8b949e; margin-top:6px;">
      セッション最高: <b id="turPeakValue" style="color:#e6edf3;">0%</b>
      <span id="turGateNote" style="color:#f0883e; margin-left:6px;"></span>
    </div>
  </div>
  <div class="habit-list"><b>SESSION MAX G</b>
    <div class="grid" style="margin-top:6px;">
      <div class="card"><div class="label">制動 (Brake)</div><div class="value" id="maxBrake" style="font-size:20px;color:#ff7b72;">0.00</div></div>
      <div class="card"><div class="label">加速 (Accel)</div><div class="value" id="maxAccel" style="font-size:20px;color:#7ee787;">0.00</div></div>
      <div class="card"><div class="label">左コーナー</div><div class="value" id="maxCornerL" style="font-size:20px;color:#58a6ff;">0.00</div></div>
      <div class="card"><div class="label">右コーナー</div><div class="value" id="maxCornerR" style="font-size:20px;color:#58a6ff;">0.00</div></div>
      <div class="card"><div class="label">合成 (Combined)</div><div class="value" id="maxCombined" style="font-size:20px;color:#f0b72f;">0.00</div></div>
    </div>
  </div>
  <div class="grid">
    <div class="card"><div class="label">路面状態</div><div class="value" id="roadState" style="font-size:16px;">--</div></div>
    <div class="card"><div class="label">直近30秒の荒れ率</div><div class="value" id="roadPct" style="font-size:16px;">--</div></div>
    <div class="card"><div class="label">タイヤロック検出</div><div class="value" id="tireLockCount" style="font-size:16px;">0 回</div></div>
    <div class="card"><div class="label">直近ロック種別</div><div class="value" id="tireLockLast" style="font-size:14px;">--</div></div>
  </div>
  <div class="event-box" id="eventBox">
    <div class="type">-- NO EVENT --</div>
  </div>
  <div class="status-bar" id="statusBar"></div>
  <button class="stop" onclick="stopSession()">走行終了</button>
</div>

<div id="reportPanel" class="hidden">
  <div class="score-big"><div class="value" id="reportScore">--</div><div class="label">TOTAL SCORE</div></div>
  <div style="text-align:center; font-size:11px; color:#8b949e; margin-top:-8px; margin-bottom:2px;" id="reportReliability"></div>
  <div style="text-align:center; font-size:11px; color:#6e7681; margin-bottom:6px;" id="reportBonusNote"></div>
  <div class="habit-list" style="font-size:13px; color:#c9d1d9;">
    <div id="reportSummaryLine" style="line-height:1.7;"></div>
  </div>
  <div class="grid">
    <div class="card"><div class="label">平均速度</div><div class="value" id="reportAvgSpeed" style="font-size:16px;">-- km/h</div></div>
    <div class="card"><div class="label">走行距離</div><div class="value" id="reportDistanceKm" style="font-size:16px;">-- km</div></div>
    <div class="card"><div class="label">RMS Gx (前後)</div><div class="value" id="reportRmsGx" style="font-size:16px;">--</div></div>
    <div class="card"><div class="label">RMS Gy (左右)</div><div class="value" id="reportRmsGy" style="font-size:16px;">--</div></div>
  </div>
  <div id="reportEventTypeBox" class="habit-list hidden">
    <b>EVENT BREAKDOWN (種別ごとの件数・平均スコア)</b>
    <ul id="reportEventTypeList" style="font-size:13px;"></ul>
  </div>
  <div id="reportBreakdownBox" class="habit-list hidden">
    <b>スコア内訳 (今回走行の平均)</b>
    <div style="text-align:center; margin:6px 0;">
      <canvas id="radarBreakdown" width="240" height="240"></canvas>
    </div>
    <ul id="reportBreakdownList" style="font-size:13px;"></ul>
  </div>
  <div class="habit-list"><b>SESSION MAX G</b><ul id="reportMaxGList" style="font-size:13px;"></ul></div>
  <div id="reportGripBox" class="habit-list hidden">
    <b>グリップ利用率 (TUR)</b>
    <div id="reportGripSummary" style="font-size:13px;color:#c9d1d9;margin:6px 0;"></div>
  </div>
  <div id="reportTireLockBox" class="habit-list hidden">
    <b>TIRE LOCK / GRIP LOSS</b>
    <div id="reportTireLockSummary" style="font-size:13px;color:#8b949e;margin:6px 0;"></div>
    <ul id="reportTireLockList" style="font-size:12px;"></ul>
  </div>
  <div class="habit-list"><b>DRIVING CHARACTERISTICS</b><ul id="habitList"></ul></div>
  <div id="reportFingerprintBox" class="habit-list hidden">
    <b>運転特性プロファイル (蓄積データ, 8項目)</b>
    <div style="font-size:11px; color:#8b949e; margin:4px 0 8px;">
      過去のセッションからゆるやかに(EMAで)更新される、このドライバーの長期的な傾向です。
    </div>
    <div style="text-align:center; margin:6px 0;">
      <canvas id="radarFingerprint" width="260" height="260"></canvas>
    </div>
  </div>
  <div id="reportAdaptiveBox" class="habit-list hidden">
    <b>AUTO-CALIBRATION (自動補正)</b>
    <div id="reportAdaptiveSummary" style="font-size:13px;color:#8b949e;margin:6px 0;"></div>
    <div id="reportAdaptiveEffect" style="font-size:13px;margin:6px 0;"></div>
    <ul id="reportAdaptiveList" style="font-size:12px;"></ul>
    <div id="reportScoreTrend" style="margin-top:8px;"></div>
  </div>
  <div id="reportDownloadBox" class="hidden" style="margin:10px 0;">
    <a id="reportDownloadLink" href="#" download
      style="display:block; text-align:center; padding:10px; background:#238636; color:#fff;
             border-radius:6px; text-decoration:none; font-size:13px;">
      📄 AI分析用レポート(TXT)をダウンロード — AIに読み込ませて詳細分析できます
    </a>
  </div>
  <div style="text-align:center; font-size:10px; color:#6e7681; margin:4px 0 8px;" id="reportVersionFooter"></div>
  <button onclick="location.reload()">戻る</button>
</div>

<script>
let polling = null;
let vehiclesCache = [];          // 全車両データ(編集プリフィル用)
let editingVehicleId = null;     // null=新規追加モード / 値あり=その車両を編集中
let driversCache = [];           // 全ドライバーデータ(編集プリフィル用)
let editingDriverId = null;      // null=新規追加モード / 値あり=そのドライバーを編集中

async function loadOptions(){
  const d = await (await fetch('/api/drivers')).json();
  const v = await (await fetch('/api/vehicles')).json();
  const lim = await (await fetch('/api/limits')).json();
  driversCache = d;
  vehiclesCache = v;
  const prevDriverSel = document.getElementById('driverSel').value;
  const prevSel = document.getElementById('vehicleSel').value;
  document.getElementById('driverSel').innerHTML = d.map(x=>`<option value="${x.driver_id}">${x.display_name}</option>`).join('');
  document.getElementById('vehicleSel').innerHTML = v.map(x=>`<option value="${x.vehicle_id}">${x.name}</option>`).join('');
  // 直前の選択を可能な限り維持する。
  if(prevDriverSel && d.some(x=>x.driver_id===prevDriverSel)){ document.getElementById('driverSel').value = prevDriverSel; }
  if(prevSel && v.some(x=>x.vehicle_id===prevSel)){ document.getElementById('vehicleSel').value = prevSel; }
  document.getElementById('driverCount').innerText = `ドライバー ${lim.driver_count} / ${lim.driver_max}`;
  document.getElementById('vehicleCount').innerText = `車両 ${lim.vehicle_count} / ${lim.vehicle_max}`;
}
loadOptions();

// --- Ver/作成者表示 + 設定パネル(⚙) ---
let tunableParamsCache = [];

let sensorServerPackage = 'github.umer0586.sensorserver';  // /api/config取得までの初期値(フォールバック)
let sensorServerFdroidUrl = 'https://f-droid.org/packages/github.umer0586.sensorserver/';

async function loadAppInfo(){
  try{
    const cfg = await (await fetch('/api/config')).json();
    document.getElementById('appVersion').innerText = cfg.app_version;
    document.getElementById('appAuthor').innerText = cfg.app_author;
    tunableParamsCache = cfg.params;
    if(cfg.sensor_server_package){
      sensorServerPackage = cfg.sensor_server_package;
      const pkgText = document.getElementById('sensorServerPackageText');
      if(pkgText) pkgText.innerText = sensorServerPackage;
    }
    if(cfg.sensor_server_fdroid_url){
      sensorServerFdroidUrl = cfg.sensor_server_fdroid_url;
      const link = document.getElementById('sensorServerFdroidLink');
      if(link) link.href = sensorServerFdroidUrl;
    }
    if(cfg.sensor_server_check_poll_sec){
      const changed = window.__SENSOR_SERVER_CHECK_POLL_SEC !== cfg.sensor_server_check_poll_sec;
      window.__SENSOR_SERVER_CHECK_POLL_SEC = cfg.sensor_server_check_poll_sec;
      if(changed && typeof startSensorServerCheckPolling === 'function'){
        startSensorServerCheckPolling();  // 取得できた正しい間隔でポーリングを再設定
      }
    }
  }catch(e){ /* ignore */ }
}
loadAppInfo();

// Version 1.5: 起動直後の「Sensor Serverアプリを起動」ボタンは、Chromeの仕様上
// (BROWSABLEカテゴリ非対応アプリはintent経由で起動できない)多くの環境で実質機能しない
// ため廃止した。代わりに、セットアップ画面表示中は数秒おきに接続状況を確認し、
// 未接続(シミュレーションモード)であれば明確なワーニングを表示する。
// Sensor Server起動後、配信がONになり接続が確立されれば自動的に消える。
let sensorServerCheckTimer = null;
async function checkSensorServerStatus(){
  const warn = document.getElementById('sensorNotRunningWarning');
  if(!warn) return;
  try{
    const s = await (await fetch('/api/state')).json();
    if(s.sensor_simulate){
      warn.classList.remove('hidden');
      document.getElementById('sensorNotRunningReason').innerText =
        s.sensor_sim_reason ? `理由: ${s.sensor_sim_reason}` : '';
    } else {
      warn.classList.add('hidden');
    }
  }catch(e){ /* 通信エラー時は前回表示状態を維持 */ }
}
function startSensorServerCheckPolling(){
  checkSensorServerStatus();
  if(sensorServerCheckTimer) clearInterval(sensorServerCheckTimer);
  sensorServerCheckTimer = setInterval(checkSensorServerStatus,
    (window.__SENSOR_SERVER_CHECK_POLL_SEC || 3) * 1000);
}
function stopSensorServerCheckPolling(){
  if(sensorServerCheckTimer){ clearInterval(sensorServerCheckTimer); sensorServerCheckTimer = null; }
}
startSensorServerCheckPolling();

async function openSettings(){
  const box = document.getElementById('settingsParams');
  document.getElementById('settingsMsg').innerText = '';
  document.getElementById('settingsPanel').style.display = 'flex';
  box.innerHTML = '<div style="font-size:12px; color:#8b949e;">読み込み中...</div>';
  // ページ読み込み時のloadAppInfo()がまだ完了していない場合(モバイル回線が遅い等)や
  // 途中で失敗していた場合に、設定を開くたびに確実に最新値を取得し直す。
  await loadAppInfo();
  if(!tunableParamsCache || !tunableParamsCache.length){
    box.innerHTML = '<div style="font-size:12px; color:#f0883e;">設定の取得に失敗しました。'
      + '通信状態を確認して、設定を開き直してください。</div>';
    return;
  }
  box.innerHTML = tunableParamsCache.map(p => `
    <div style="margin-bottom:10px;">
      <label style="font-size:12px; color:#c9d1d9;">${p.label}</label>
      <input type="number" id="cfg_${p.key}" value="${p.value}" min="${p.min}" max="${p.max}" step="${p.step}"
        style="width:100%; padding:6px; margin-top:2px; background:#0d1117; color:#e6edf3;
               border:1px solid #30363d; border-radius:6px;">
      <div style="font-size:10px; color:#6e7681;">${p.desc}</div>
    </div>`).join('');
  refreshLearningInfo();
}

function closeSettings(){
  document.getElementById('settingsPanel').style.display = 'none';
}

async function refreshLearningInfo(){
  const el = document.getElementById('learningInfo');
  try{
    const driverId = document.getElementById('driverSel').value;
    const vehicleId = document.getElementById('vehicleSel').value;
    const mode = document.getElementById('modeSel') ? document.getElementById('modeSel').value : 'STREET';
    if(!driverId || !vehicleId){ el.innerText = 'ドライバー・車両を選択すると表示されます。'; return; }
    const data = await (await fetch(`/api/learning?driver_id=${encodeURIComponent(driverId)}&vehicle_id=${encodeURIComponent(vehicleId)}&mode=${encodeURIComponent(mode)}`)).json();
    if(!data.profile){
      el.innerHTML = `まだ自動補正は適用されていません(走行データ蓄積中)。<br>` +
        `目安: ${data.min_sessions}セッション以上・${data.min_events}イベント以上で自動補正が有効になります。`;
      return;
    }
    const p = data.profile;
    const c = p.corrections || {};
    const muLine = (c.mu_long_max != null || c.mu_lat_max != null)
      ? `推定グリップ上限: 制動方向 ${c.mu_long_max ?? '(既定値)'}G / 旋回方向 ${c.mu_lat_max ?? '(既定値)'}G<br>`
      : `推定グリップ上限: 走行データ蓄積中(既定値を使用中)<br>`;
    el.innerHTML =
      `蓄積セッション数: ${p.n_sessions} / イベント数: ${p.n_events}<br>` +
      `現在の自動補正値: イベント検出G ${c.event_trigger_g}, ジャーク上限 ${c.jerk_limit_g_per_s}, ` +
      `荷重移動変化率上限 ${c.lt_rate_limit}<br>` +
      muLine +
      `最終更新: ${p.updated_at ? new Date(p.updated_at*1000).toLocaleString() : '-'}`;
  }catch(e){ el.innerText = '取得に失敗しました。'; }
}

async function saveSettings(){
  const updates = {};
  for(const p of tunableParamsCache){
    const el = document.getElementById(`cfg_${p.key}`);
    if(el) updates[p.key] = parseFloat(el.value);
  }
  const res = await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(updates)});
  const data = await res.json();
  const msg = document.getElementById('settingsMsg');
  if(data.ok){
    msg.style.color = '#3fb950';
    msg.innerText = '保存しました(次回のセッション開始時から反映されます)。';
    await loadAppInfo();
  } else {
    msg.style.color = '#f0883e';
    msg.innerText = '保存に失敗しました。';
  }
}

function onModeChange(){
  // CIRCUIT選択時のみ、配信レートに関する注意書きを表示する。
  const isCircuit = document.getElementById('modeSel').value === 'CIRCUIT';
  document.getElementById('circuitNote').classList.toggle('hidden', !isCircuit);
}

function toggleForm(id){
  document.getElementById(id).classList.toggle('hidden');
}

function _vehicleFormFields(){
  return {
    name: document.getElementById('newVehicleName'),
    mass: document.getElementById('newVehicleMass'),
    wb: document.getElementById('newVehicleWheelbase'),
    tf: document.getElementById('newVehicleTreadF'),
    tr: document.getElementById('newVehicleTreadR'),
    cg: document.getElementById('newVehicleCg'),
    drive: document.getElementById('newVehicleDrive'),
  };
}

function _clearVehicleForm(){
  const f = _vehicleFormFields();
  f.name.value=''; f.mass.value=''; f.wb.value=''; f.tf.value=''; f.tr.value=''; f.cg.value='';
  f.drive.value='FF';
  document.getElementById('vehicleFormMsg').innerText='';
}

function closeVehicleForm(){
  document.getElementById('vehicleForm').classList.add('hidden');
  editingVehicleId = null;
  _clearVehicleForm();
}

function openVehicleAdd(){
  editingVehicleId = null;
  _clearVehicleForm();
  document.getElementById('vehicleFormTitle').innerText = '車両を追加';
  document.getElementById('vehicleSaveBtn').innerText = '車両を追加';
  document.getElementById('vehicleForm').classList.remove('hidden');
}

function openVehicleEdit(){
  const vid = document.getElementById('vehicleSel').value;
  const veh = vehiclesCache.find(x=>x.vehicle_id===vid);
  if(!veh){ alert('編集する車両を選択してください'); return; }
  editingVehicleId = vid;
  const f = _vehicleFormFields();
  f.name.value  = veh.name ?? '';
  f.mass.value  = veh.mass_kg ?? '';
  f.wb.value    = veh.wheelbase_mm ?? '';
  f.tf.value    = veh.tread_front_mm ?? '';
  f.tr.value    = veh.tread_rear_mm ?? '';
  f.cg.value    = (veh.cg_height_mm ?? '') === null ? '' : (veh.cg_height_mm ?? '');
  f.drive.value = veh.drive_type ?? 'FF';
  document.getElementById('vehicleFormMsg').innerText='';
  document.getElementById('vehicleFormTitle').innerText = `車両を編集: ${veh.name}`;
  document.getElementById('vehicleSaveBtn').innerText = '更新を保存';
  document.getElementById('vehicleForm').classList.remove('hidden');
}

async function deleteVehicle(){
  const vid = document.getElementById('vehicleSel').value;
  const veh = vehiclesCache.find(x=>x.vehicle_id===vid);
  if(!veh){ alert('削除する車両を選択してください'); return; }
  if(!confirm(`車両「${veh.name}」を削除しますか?`)) return;
  const res = await fetch('/api/vehicles/delete', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({vehicle_id: vid})});
  const data = await res.json();
  if(data.ok){ await loadOptions(); }
  else { alert(data.error || '削除に失敗しました'); }
}

function _clearDriverForm(){
  document.getElementById('newDriverName').value = '';
  document.getElementById('driverFormMsg').innerText = '';
}

function closeDriverForm(){
  document.getElementById('driverForm').classList.add('hidden');
  editingDriverId = null;
  _clearDriverForm();
}

function openDriverAdd(){
  editingDriverId = null;
  _clearDriverForm();
  document.getElementById('driverFormTitle').innerText = 'ドライバーを追加';
  document.getElementById('driverSaveBtn').innerText = 'ドライバーを追加';
  document.getElementById('driverForm').classList.remove('hidden');
}

function openDriverEdit(){
  const did = document.getElementById('driverSel').value;
  const drv = driversCache.find(x=>x.driver_id===did);
  if(!drv){ alert('編集するドライバーを選択してください'); return; }
  editingDriverId = did;
  document.getElementById('newDriverName').value = drv.display_name ?? '';
  document.getElementById('driverFormMsg').innerText = '';
  document.getElementById('driverFormTitle').innerText = `ドライバーを編集: ${drv.display_name}`;
  document.getElementById('driverSaveBtn').innerText = '更新を保存';
  document.getElementById('driverForm').classList.remove('hidden');
}

async function saveDriver(){
  const display_name = document.getElementById('newDriverName').value.trim();
  // 編集モードなら update、新規なら add。編集時は対象IDを付与。
  const isEdit = !!editingDriverId;
  const url = isEdit ? '/api/drivers/update' : '/api/drivers/add';
  const body = isEdit ? {driver_id: editingDriverId, display_name} : {display_name};
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)});
  const data = await res.json();
  const msg = document.getElementById('driverFormMsg');
  if(data.ok){
    closeDriverForm();                  // フォームを閉じて必ずクリア(値の残留を防止)
    await loadOptions();
    if(data.driver_id){ document.getElementById('driverSel').value = data.driver_id; }
  } else {
    msg.innerText = data.error || (isEdit ? '更新に失敗しました' : '追加に失敗しました');
  }
}

async function deleteDriver(){
  const did = document.getElementById('driverSel').value;
  const drv = driversCache.find(x=>x.driver_id===did);
  if(!drv){ alert('削除するドライバーを選択してください'); return; }
  if(!confirm(`ドライバー「${drv.display_name}」を削除しますか?`)) return;
  const res = await fetch('/api/drivers/delete', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({driver_id: did})});
  const data = await res.json();
  if(data.ok){ await loadOptions(); }
  else { alert(data.error || '削除に失敗しました'); }
}

async function saveVehicle(){
  const f = _vehicleFormFields();
  const body = {
    name: f.name.value.trim(),
    mass_kg: f.mass.value,
    wheelbase_mm: f.wb.value,
    tread_front_mm: f.tf.value,
    tread_rear_mm: f.tr.value,
    cg_height_mm: f.cg.value,   // 空欄なら重心高をクリア(未入力)扱い
    drive_type: f.drive.value,
  };
  // 編集モードなら update、新規なら add。編集時は対象IDを付与。
  const isEdit = !!editingVehicleId;
  const url = isEdit ? '/api/vehicles/update' : '/api/vehicles/add';
  if(isEdit){ body.vehicle_id = editingVehicleId; }
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)});
  const data = await res.json();
  const msg = document.getElementById('vehicleFormMsg');
  if(data.ok){
    closeVehicleForm();                 // フォームを閉じて必ずクリア(値の残留を防止)
    await loadOptions();
    if(data.vehicle_id){ document.getElementById('vehicleSel').value = data.vehicle_id; }
  } else {
    msg.innerText = data.error || (isEdit ? '更新に失敗しました' : '追加に失敗しました');
  }
}

async function startSession(){
  stopSensorServerCheckPolling();   // Version 1.5: セットアップ画面を離れるのでポーリング停止
  const driver_id = document.getElementById('driverSel').value;
  const vehicle_id = document.getElementById('vehicleSel').value;
  const mode = document.getElementById('modeSel').value;
  await fetch('/api/start', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({driver_id, vehicle_id, mode})});
  document.getElementById('setupPanel').classList.add('hidden');
  document.getElementById('mainPanel').classList.remove('hidden');
  startStream();
}

// Version 1.4: 簡易レポート画面用のレーダーチャート描画(追加ライブラリ不要、Canvas 2Dのみ)。
// labels/values は同じ長さの配列。values は 0〜maxValue のスコア値(通常0-100)。
function drawRadarChart(canvasId, labels, values, maxValue, color){
  const canvas = document.getElementById(canvasId);
  if(!canvas) return;
  const c = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W/2, cy = H/2 - 6;
  const R = Math.min(W, H)/2 - 34;
  const n = labels.length;
  c.clearRect(0,0,W,H);
  if(n < 3){
    c.fillStyle = '#8b949e'; c.font = '12px sans-serif'; c.textAlign = 'center';
    c.fillText('表示には3項目以上が必要です', cx, cy);
    return;
  }
  const angleFor = (i) => (Math.PI*2*i/n) - Math.PI/2;
  // 目盛りの同心グリッド(25/50/75/100%)
  c.strokeStyle = '#30363d'; c.lineWidth = 1;
  for(let ring=1; ring<=4; ring++){
    const rr = R * ring/4;
    c.beginPath();
    for(let i=0;i<=n;i++){
      const a = angleFor(i % n);
      const x = cx + rr*Math.cos(a), y = cy + rr*Math.sin(a);
      if(i===0) c.moveTo(x,y); else c.lineTo(x,y);
    }
    c.stroke();
  }
  // 軸線 + ラベル
  c.fillStyle = '#8b949e'; c.font = '11px sans-serif'; c.textAlign = 'center';
  for(let i=0;i<n;i++){
    const a = angleFor(i);
    const x = cx + R*Math.cos(a), y = cy + R*Math.sin(a);
    c.beginPath(); c.moveTo(cx,cy); c.lineTo(x,y); c.stroke();
    const lx = cx + (R+16)*Math.cos(a), ly = cy + (R+16)*Math.sin(a);
    c.fillText(String(labels[i]), lx, ly + (Math.sin(a)>0.3?8:(Math.sin(a)<-0.3?-2:4)));
  }
  // データポリゴン
  c.beginPath();
  for(let i=0;i<=n;i++){
    const idx = i % n;
    const v = Math.max(0, Math.min(maxValue, values[idx] ?? 0));
    const rr = R * (v/maxValue);
    const a = angleFor(idx);
    const x = cx + rr*Math.cos(a), y = cy + rr*Math.sin(a);
    if(i===0) c.moveTo(x,y); else c.lineTo(x,y);
  }
  c.closePath();
  c.fillStyle = color + '33';   // 半透明塗り
  c.strokeStyle = color; c.lineWidth = 2;
  c.fill(); c.stroke();
  // 頂点マーカー
  c.fillStyle = color;
  for(let i=0;i<n;i++){
    const v = Math.max(0, Math.min(maxValue, values[i] ?? 0));
    const rr = R * (v/maxValue);
    const a = angleFor(i);
    const x = cx + rr*Math.cos(a), y = cy + rr*Math.sin(a);
    c.beginPath(); c.arc(x,y,3,0,Math.PI*2); c.fill();
  }
}

async function stopSession(){
  stopStream();
  const res = await fetch('/api/stop', {method:'POST'});
  const report = await res.json();
  document.getElementById('mainPanel').classList.add('hidden');
  document.getElementById('reportPanel').classList.remove('hidden');
  document.getElementById('reportScore').innerText = report.total_score ?? '--';
  document.getElementById('reportReliability').innerText =
    report.reliability_pct != null ? `信頼度 ${report.reliability_pct}%` : '';

  // Version 1.4: 優良運転ボーナスの内訳(基礎点 + ボーナス = 総合)を明記し、
  // 「なぜこの点数になったか」を透明にする。
  const bonusEl = document.getElementById('reportBonusNote');
  const sb = report.score_bonus;
  if(sb && sb.base != null){
    const b = sb.bonus || 0;
    bonusEl.innerText = (b > 0)
      ? `内訳: 基礎点 ${sb.base} + 優良運転ボーナス +${b} = 総合 ${report.total_score}`
      : `基礎点: ${sb.base}`;
  } else {
    bonusEl.innerText = '';
  }

  // Version 1.4: 簡易レポートの情報量拡充 — ドライバー/車両/モード/走行時間のサマリー行
  document.getElementById('reportSummaryLine').innerHTML =
    `ドライバー: <b>${report.driver_name ?? '--'}</b> &nbsp;|&nbsp; ` +
    `車両: <b>${report.vehicle_name ?? '--'}</b> &nbsp;|&nbsp; モード: <b>${report.mode ?? '--'}</b><br>` +
    `走行時間: <b>${report.duration_min != null ? report.duration_min.toFixed(1) : '--'}分</b> ` +
    `&nbsp;|&nbsp; イベント検出数: <b>${report.event_count ?? 0}</b>`;

  const rds = report.driving_stats || {};
  document.getElementById('reportAvgSpeed').innerText =
    (rds.avg_speed_kmh != null ? rds.avg_speed_kmh.toFixed(1) : '--') + ' km/h';
  document.getElementById('reportDistanceKm').innerText = (rds.distance_km ?? 0).toFixed(2) + ' km';
  document.getElementById('reportRmsGx').innerText = (rds.rms_gx ?? 0).toFixed(2);
  document.getElementById('reportRmsGy').innerText = (rds.rms_gy ?? 0).toFixed(2);
  document.getElementById('habitList').innerHTML =
    (report.habits || []).map(h=>`<li>${h.text} ${h.confidence!=null?('('+h.confidence+'%)'):''}</li>`).join('');

  // Version 1.4: イベント種別ごとの件数・平均スコア
  const ET_LABEL = {BRAKE:'制動', ACCEL:'加速', LEFT_CORNER:'左コーナー',
                    RIGHT_CORNER:'右コーナー', COMBINED:'複合', TRANSITION:'切り返し'};
  const etBox = document.getElementById('reportEventTypeBox');
  const etCounts = report.event_type_counts || {};
  if(Object.keys(etCounts).length){
    etBox.classList.remove('hidden');
    const etAvg = report.event_type_avg_score || {};
    document.getElementById('reportEventTypeList').innerHTML =
      Object.keys(etCounts).map(k=>
        `<li>${ET_LABEL[k]||k}: ${etCounts[k]}件 (平均スコア ${etAvg[k] ?? '--'})</li>`).join('');
  } else {
    etBox.classList.add('hidden');
  }

  // Version 1.4: スコア内訳(今回走行の平均) — 数値リスト + レーダーチャート
  const bdBox = document.getElementById('reportBreakdownBox');
  const bd = report.avg_score_breakdown || {};
  const bdKeys = Object.keys(bd);
  if(bdKeys.length){
    bdBox.classList.remove('hidden');
    document.getElementById('reportBreakdownList').innerHTML =
      bdKeys.map(k=>`<li>${k}: ${bd[k]}</li>`).join('');
    drawRadarChart('radarBreakdown', bdKeys, bdKeys.map(k=>bd[k]), 100, '#58a6ff');
  } else {
    bdBox.classList.add('hidden');
  }

  // Version 1.4: 運転特性プロファイル(蓄積データ, DriverStats.fingerprint) — レーダーチャート
  const fpBox = document.getElementById('reportFingerprintBox');
  const FP_LABEL = {smoothness:'滑らかさ', brake_control:'制動', accel_control:'加速',
                    cornering_control:'旋回', load_transfer_control:'荷重移動',
                    jerk_control:'ジャーク', consistency:'一貫性', lr_symmetry:'左右対称性'};
  const fp = report.driver_fingerprint || {};
  const fpKeys = Object.keys(fp);
  if(fpKeys.length){
    fpBox.classList.remove('hidden');
    drawRadarChart('radarFingerprint', fpKeys.map(k=>FP_LABEL[k]||k), fpKeys.map(k=>fp[k]), 100, '#f0b72f');
  } else {
    fpBox.classList.add('hidden');
  }

  document.getElementById('reportVersionFooter').innerText =
    `Driving Dynamics Analyzer v${report.app_version ?? '-'} by ${report.app_author ?? '-'}`;

  const dlBox = document.getElementById('reportDownloadBox');
  if(report.report_file){
    document.getElementById('reportDownloadLink').href = '/report/' + encodeURIComponent(report.report_file);
    document.getElementById('reportDownloadLink').setAttribute('download', report.report_file);
    dlBox.classList.remove('hidden');
  } else {
    dlBox.classList.add('hidden');
  }

  // セッション最大G サマリ
  const mg = report.max_g || {};
  const MG_ROWS = [['brake','制動'],['accel','加速'],['corner_left','左コーナー'],
                   ['corner_right','右コーナー'],['combined','合成']];
  document.getElementById('reportMaxGList').innerHTML = MG_ROWS.map(([k,label])=>{
    const o = mg[k] || {};
    const g = (o.g != null) ? o.g.toFixed(2) : '0.00';
    const at = (o.rel_t != null) ? ` (t+${o.rel_t}s${o.speed!=null?', '+o.speed+'m/s':''})` : '';
    return `<li>${label}: <b>${g} G</b>${at}</li>`;
  }).join('');

  // グリップ利用率(TUR) サマリ (CIRCUITモード等、対象モードでのみ意味を持つため
  // report.mode で表示要否を判定する)
  const gripBox = document.getElementById('reportGripBox');
  const pk = report.peak_tur || {};
  if(report.mode === 'CIRCUIT' && (pk.value || 0) > 0){
    gripBox.classList.remove('hidden');
    const gm = report.grip_mu_used || {};
    const pct = ((pk.value || 0) * 100).toFixed(0);
    const at = (pk.rel_t != null) ? ` (t+${pk.rel_t}s${pk.speed!=null?', '+pk.speed+'m/s':''})` : '';
    document.getElementById('reportGripSummary').innerHTML =
      `セッション最高: <b style="font-size:18px;">${pct}%</b>${at}<br>` +
      `判定に使用した推定グリップ上限: 制動方向 ${gm.mu_long_max ?? '--'}G / ` +
      `旋回方向 ${gm.mu_lat_max ?? '--'}G` +
      (pct >= 100 ? '<br><span style="color:#ff7b72;">推定上限に到達/超過した区間がありました。</span>' : '');
  } else {
    gripBox.classList.add('hidden');
  }

  // タイヤロック/グリップ喪失 サマリ
  const TL_LABEL_R = {BRAKE_LOCK_FRONT:'前輪ロック(直進)', BRAKE_LOCK_REAR:'後輪ロック(オーバー)',
                      BRAKE_SLIP:'制動スリップ(減速崩壊)', UNDERSTEER:'アンダーステア',
                      OVERSTEER:'オーバーステア', SPIN:'ヨー急変(スピン兆候)',
                      GRIP_PLATEAU:'グリップ頭打ち(滑走疑い/ジャダー無し)'};
  const tlBox = document.getElementById('reportTireLockBox');
  const evs = report.tire_lock_events || [];
  if((report.tire_lock_count ?? 0) > 0){
    tlBox.classList.remove('hidden');
    const byType = report.tire_lock_by_type || {};
    document.getElementById('reportTireLockSummary').innerText =
      `合計 ${report.tire_lock_count} 回  (` +
      Object.keys(byType).map(k=>`${TL_LABEL_R[k]||k}: ${byType[k]}`).join(' / ') + ')';
    document.getElementById('reportTireLockList').innerHTML = evs.map(e=>{
      const gps = (e.lat!=null && e.lon!=null) ? ` @${e.lat.toFixed(5)},${e.lon.toFixed(5)}` : '';
      const spd = (e.speed!=null) ? ` ${e.speed}m/s` : '';
      const tur = (e.tur!=null) ? ` TUR:${(e.tur*100).toFixed(0)}%` : '';
      const cf = (e.confidence!=null) ? ` 信頼度:${(e.confidence*100).toFixed(0)}%` : '';
      return `<li>#${e.index} t+${e.rel_t}s ${TL_LABEL_R[e.type]||e.type}${spd}${tur}${cf}${gps}</li>`;
    }).join('');
  } else {
    tlBox.classList.add('hidden');
  }

  // 自動補正(適応キャリブレーション) サマリ
  const adaptBox = document.getElementById('reportAdaptiveBox');
  const applied = report.adaptive_applied;
  const updated = report.adaptive_updated;
  if(applied || updated){
    adaptBox.classList.remove('hidden');
    document.getElementById('reportAdaptiveSummary').innerText = applied
      ? `今回適用: 検出閾値 ${applied.event_trigger_g}G / Jerk上限 ${applied.jerk_limit_g_per_s}G/s / 荷重変化率上限 ${applied.lt_rate_limit}`
      : '今回は既定値で走行 (学習データ蓄積中)';
    const effEl = document.getElementById('reportAdaptiveEffect');
    if(report.baseline_total_score != null && report.adaptive_delta != null){
      const dlt = report.adaptive_delta, sign = dlt>0?'+':'';
      const col = dlt>0?'#7ee787':(dlt<0?'#ff7b72':'#8b949e');
      effEl.innerHTML = `補正効果: 既定採点 <b>${report.baseline_total_score}</b> → 補正後 <b>${report.total_score}</b> ` +
        `<span style="color:${col};">(${sign}${dlt})</span>`;
    } else { effEl.innerHTML = ''; }
    let items = [];
    if(updated && updated.corrections){
      const c = updated.corrections, d = updated.distribution || {};
      const fmtd = (o) => o && o.n ? `p50=${o.p50} p90=${o.p90} max=${o.max} (n=${o.n})` : 'データ不足';
      items.push(`<li><b>次回反映</b>: 検出閾値 ${c.event_trigger_g}G / Jerk上限 ${c.jerk_limit_g_per_s}G/s (${updated.n_sessions}走行/${updated.n_events}イベントから学習)</li>`);
      items.push(`<li>制動G分布: ${fmtd(d.brake_g)}</li>`);
      items.push(`<li>加速G分布: ${fmtd(d.accel_g)}</li>`);
      items.push(`<li>コーナーG分布: ${fmtd(d.corner_g)}</li>`);
    } else {
      items.push(`<li>あと数走行でデータが集まると自動補正が有効になります (最低3走行・20イベント)</li>`);
    }
    document.getElementById('reportAdaptiveList').innerHTML = items.join('');

    // スコア推移スパークライン
    const trendEl = document.getElementById('reportScoreTrend');
    const hist = report.score_history || [];
    if(hist.length >= 2){
      const vals = hist.map(h=>h.total_score).filter(v=>v!=null);
      const mn=Math.min(...vals), mx=Math.max(...vals), rng=(mx-mn)||1;
      const bars = hist.map(h=>{
        const v=h.total_score??0, ht=8+40*(v-mn)/rng;
        const c=h.adaptive?'#f0b72f':'#30506e';
        return `<div title="${v} ${h.adaptive?'(補正ON)':''}" style="display:inline-block;width:14px;height:${ht.toFixed(0)}px;background:${c};margin:0 2px;vertical-align:bottom;border-radius:2px;"></div>`;
      }).join('');
      trendEl.innerHTML = `<div style="font-size:12px;color:#8b949e;margin-bottom:4px;">スコア推移 (直近${hist.length}走行 / 黄=自動補正ON)</div><div style="height:52px;">${bars}</div>`;
    } else { trendEl.innerHTML = ''; }
  } else {
    adaptBox.classList.add('hidden');
  }
}

const ctx = document.getElementById('ggCanvas').getContext('2d');
const GG = { W:320, H:320, scale:110 };
const GG_TRAIL_MS = 500;      // ボールの軌跡を保持する時間 [ms]
let ggTrail = [];             // {x, y, t} 描画座標(px)で保持
let ggCalibrated = false;     // 未キャリブレーション時は半透明表示

// ボールの表示向き。標準的なG-Gダイアグラムの慣習に合わせる:
//   横(左右): 右コーナー=右 / 左コーナー=左  (ステアを切る方向にボールが動く)
//   縦(前後): 加速=下 / ブレーキ=上          (多くの民生Gメーターと同じ体感基準)
// 内部の gy は「左コーナーで正(+)」なので、右コーナー=右にするには左右を反転する。
// 好みで向きを変えたい場合はこの2定数を +1/-1 で切り替える。
const GG_LAT_SIGN  = -1;   // -1: 右コーナー=右 / +1: 右コーナー=左(体感G)
// 前後の向きはUIトグルで切替可能。+1: 加速=下(体感G) / -1: 加速=上(データロガー流儀)。
// 設定はlocalStorageに保存し、次回起動時も維持する。
let GG_LONG_SIGN = (localStorage.getItem('ggLongSign') === '-1') ? -1 : +1;
function pushGG(gx, gy){
  const cx = GG.W/2, cy = GG.H/2;
  ggTrail.push({ x: cx + GG_LAT_SIGN*gy*GG.scale,
                 y: cy + GG_LONG_SIGN*gx*GG.scale, t: performance.now() });
}
function _updateGGLongLabel(){
  const btn = document.getElementById('ggLongToggle');
  if(btn){ btn.innerText = (GG_LONG_SIGN === +1) ? '加速 = 下 ▼' : '加速 = 上 ▲'; }
}
function toggleGGLong(){
  GG_LONG_SIGN = -GG_LONG_SIGN;
  localStorage.setItem('ggLongSign', String(GG_LONG_SIGN));
  _updateGGLongLabel();
  ggTrail = [];   // 反転直後の残像が逆向きに残らないよう軌跡をクリア
}
_updateGGLongLabel();

// 合成Gの大きさで 青(低G)→黄(中G)→赤(高G) のグラデーション色。
function ggColor(mag){
  const m = Math.max(0, Math.min(1, mag/1.0));
  let r,g,b;
  if(m < 0.5){ const k=m/0.5; r=Math.round(88+(255-88)*k); g=Math.round(166+(210-166)*k); b=Math.round(255+(60-255)*k); }
  else       { const k=(m-0.5)/0.5; r=255; g=Math.round(210+(60-210)*k); b=Math.round(60+(48-60)*k); }
  return {r,g,b};
}
function lerp(a,b,k){ return a+(b-a)*k; }

function renderGG(){
  const {W,H,scale} = GG, cx=W/2, cy=H/2;
  ctx.clearRect(0,0,W,H);
  ctx.strokeStyle='#30363d'; ctx.lineWidth=1;
  for(let r=0.2;r<=1.0;r+=0.2){ ctx.beginPath(); ctx.arc(cx,cy,r*scale,0,Math.PI*2); ctx.stroke(); }
  ctx.beginPath(); ctx.moveTo(0,cy); ctx.lineTo(W,cy); ctx.moveTo(cx,0); ctx.lineTo(cx,H); ctx.stroke();

  const now = performance.now();
  ggTrail = ggTrail.filter(p => now - p.t <= GG_TRAIL_MS);
  const baseAlpha = ggCalibrated ? 1.0 : 0.35;   // 校正中は半透明
  ctx.lineCap='round';
  const STEPS = 6;
  for(let i=1;i<ggTrail.length;i++){
    const p0=ggTrail[i-1], p1=ggTrail[i];
    for(let s=0;s<STEPS;s++){
      const k0=s/STEPS, k1=(s+1)/STEPS;
      const x0=lerp(p0.x,p1.x,k0), y0=lerp(p0.y,p1.y,k0);
      const x1=lerp(p0.x,p1.x,k1), y1=lerp(p0.y,p1.y,k1);
      const tt=lerp(p0.t,p1.t,k1);
      const a=Math.max(0, 1-(now-tt)/GG_TRAIL_MS);
      const mag=Math.hypot((x1-cx)/scale,(y1-cy)/scale);
      const c=ggColor(mag);
      ctx.strokeStyle=`rgba(${c.r},${c.g},${c.b},${(a*a*0.85*baseAlpha).toFixed(3)})`;
      ctx.lineWidth=2+5*a;
      ctx.beginPath(); ctx.moveTo(x0,y0); ctx.lineTo(x1,y1); ctx.stroke();
    }
  }
  if(ggTrail.length){
    const head=ggTrail[ggTrail.length-1];
    const mag=Math.hypot((head.x-cx)/scale,(head.y-cy)/scale);
    const c=ggColor(mag);
    ctx.fillStyle=`rgba(${c.r},${c.g},${c.b},${baseAlpha})`;
    ctx.beginPath(); ctx.arc(head.x, head.y, 6, 0, Math.PI*2); ctx.fill();
  }
  requestAnimationFrame(renderGG);
}
requestAnimationFrame(renderGG);

async function pollState(){
  try{
    const s = await (await fetch('/api/state')).json();
    applyStateUpdate(s);
  }catch(e){ /* ignore transient errors */ }
}

let evtSource = null;

function startStream(){
  if(!('EventSource' in window)){
    // 古い/一部のWebView環境などSSE非対応ならポーリングにフォールバック。
    polling = setInterval(pollState, 150);
    return;
  }
  evtSource = new EventSource('/api/stream');
  evtSource.onmessage = (e) => {
    try{ applyStateUpdate(JSON.parse(e.data)); }catch(err){ /* ignore */ }
  };
  evtSource.onerror = () => {
    // 接続が切れた場合、ブラウザは自動再接続を試みる。ただし完全に閉じてしまった
    // 場合(readyState===CLOSED)は、二重起動しないようポーリングへフォールバック。
    if(evtSource && evtSource.readyState === EventSource.CLOSED && !polling){
      polling = setInterval(pollState, 150);
    }
  };
}

function stopStream(){
  if(evtSource){ evtSource.close(); evtSource = null; }
  if(polling){ clearInterval(polling); polling = null; }
}

function applyStateUpdate(s){
    document.getElementById('gx').innerText = s.gx.toFixed(2);
    document.getElementById('gy').innerText = s.gy.toFixed(2);
    document.getElementById('gxy').innerText = s.gxy.toFixed(2);
    document.getElementById('jerk').innerText = s.jerk.toFixed(2);
    document.getElementById('scoreTotal').innerText = s.total_score ?? '--';
    document.getElementById('scoreReliability').innerText =
      s.reliability_pct != null ? `信頼度 ${s.reliability_pct}%` : '';
    const ds = s.driving_stats || {};
    document.getElementById('avgSpeed').innerText =
      (ds.avg_speed_kmh != null ? ds.avg_speed_kmh.toFixed(1) : '--') + ' km/h';
    document.getElementById('distanceKm').innerText = (ds.distance_km ?? 0).toFixed(2) + ' km';
    document.getElementById('rmsGx').innerText = (ds.rms_gx ?? 0).toFixed(2);
    document.getElementById('rmsGy').innerText = (ds.rms_gy ?? 0).toFixed(2);
    ggCalibrated = !!s.calibrated;
    const adaptTag = (s.adaptive_applied ? ' | 自動補正ON' : '');
    const diag0 = s.sensor_diag || {};
    const staleTag = (diag0.stale ? ' | ⚠STALE' : '');
    const pausedTag = (s.sensor_paused ? ' | ⏸解析一時停止(センサ無応答)' : '');
    const dq = diag0.data_quality_level;
    const dqTag = (dq === 'DEGRADED') ? ' | 受信品質:低下'
                : (dq === 'INVALID') ? ' | 受信品質:不良(ジャダー検出不可)' : '';
    document.getElementById('subline').innerText =
      `Sensor: ${s.sensor_status} | Calib: ${s.calibrated ? 'READY' : 'CALIBRATING'}${adaptTag}${staleTag}${pausedTag}${dqTag}`;
    const banner = document.getElementById('simBanner');
    if(s.sensor_simulate){
      banner.classList.remove('hidden');
      document.getElementById('simReason').innerText = s.sensor_sim_reason || '';
    } else {
      banner.classList.add('hidden');
    }

    const staleBanner = document.getElementById('staleBanner');
    const diag = s.sensor_diag || {};
    if(!s.sensor_simulate && diag.backend === 'sensor-server'){
      const staleThresh = 1.5; // 秒
      const accelStale = diag.accel_age_sec == null || diag.accel_age_sec > staleThresh || !diag.accel_connected;
      const gyroStale = diag.gyro_age_sec == null || diag.gyro_age_sec > staleThresh || !diag.gyro_connected;
      if(accelStale || gyroStale){
        staleBanner.classList.remove('hidden');
        const fmt = (v) => v == null ? '受信なし' : `${v.toFixed(1)}秒前`;
        const streak = diag.stale_streak ? ` [連続STALE ${diag.stale_streak}回]` : '';
        document.getElementById('staleDetail').innerText =
          `加速度センサー: ${diag.accel_connected ? '接続中' : '未接続'} (最終受信 ${fmt(diag.accel_age_sec)}) / ` +
          `ジャイロ: ${diag.gyro_connected ? '接続中' : '未接続'} (最終受信 ${fmt(diag.gyro_age_sec)})${streak}`;
      } else {
        staleBanner.classList.add('hidden');
      }
    } else {
      staleBanner.classList.add('hidden');
    }
    document.getElementById('statusBar').innerText =
      `Session: ${s.session_id || '-'} | Event count: ${s.event_count}`;
    pushGG(s.gx, s.gy);

    // セッション最大G の表示
    const mg = s.max_g || {};
    const fmtG = (o) => (o && o.g != null) ? o.g.toFixed(2) : '0.00';
    document.getElementById('maxBrake').innerText    = fmtG(mg.brake);
    document.getElementById('maxAccel').innerText    = fmtG(mg.accel);
    document.getElementById('maxCornerL').innerText  = fmtG(mg.corner_left);
    document.getElementById('maxCornerR').innerText  = fmtG(mg.corner_right);
    document.getElementById('maxCombined').innerText = fmtG(mg.combined);

    // --- タイヤロック/グリップ喪失 表示 ---
    // --- グリップ利用率 (TUR) 表示 ---
    // TUR: 推定グリップ上限(mu_long_max/mu_lat_max)に対する現在の合成G使用率。
    // CIRCUITモード等(grip_monitoring_active)でのみ意味を持つため、対象外モードでは非表示にする。
    const gripBox = document.getElementById('gripUsageBox');
    if(s.grip_monitoring_active){
      gripBox.classList.remove('hidden');
      const turPct = Math.max(0, Math.min(150, (s.tur || 0) * 100));
      const fill = document.getElementById('turBarFill');
      fill.style.width = Math.min(100, turPct) + '%';
      fill.style.background = turPct >= 100 ? '#da3633' : (turPct >= 85 ? '#f0b72f' : '#3fb950');
      document.getElementById('turValue').innerText = turPct.toFixed(0) + '%';
      document.getElementById('turValue').style.color = turPct >= 100 ? '#ff7b72' : '#e6edf3';
      const pk = s.peak_tur || {};
      document.getElementById('turPeakValue').innerText = ((pk.value || 0) * 100).toFixed(0) + '%';
      const diag1 = s.sensor_diag || {};
      document.getElementById('turGateNote').innerText =
        (diag1.data_quality_level && diag1.data_quality_level !== 'GOOD')
          ? '⚠ 受信品質低下中: ジャダーに基づく前輪/後輪判定は一時停止中' : '';
    } else {
      gripBox.classList.add('hidden');
    }

    const TL_LABEL = {BRAKE_LOCK_FRONT:'前輪ロック(直進)', BRAKE_LOCK_REAR:'後輪ロック(オーバー)',
                      BRAKE_SLIP:'制動スリップ(減速崩壊)', UNDERSTEER:'アンダーステア',
                      OVERSTEER:'オーバーステア', SPIN:'ヨー急変(スピン兆候)',
                      GRIP_PLATEAU:'グリップ頭打ち(滑走疑い/ジャダー無し)'};
    const tlBanner = document.getElementById('tireLockBanner');
    if(s.tire_lock){
      tlBanner.classList.remove('hidden');
      const confPct = (s.tire_lock_confidence != null) ? ` (信頼度${(s.tire_lock_confidence*100).toFixed(0)}%)` : '';
      document.getElementById('tireLockType').innerText =
        '— ' + (TL_LABEL[s.tire_lock_type] || s.tire_lock_type || '') + confPct;
    } else {
      tlBanner.classList.add('hidden');
    }
    document.getElementById('tireLockCount').innerText = (s.tire_lock_count ?? 0) + ' 回';
    const lastTL = s.last_tire_lock;
    document.getElementById('tireLockLast').innerText =
      lastTL ? (TL_LABEL[lastTL.type] || lastTL.type || '--') : '--';

    const roadEl = document.getElementById('roadState');
    roadEl.innerText = s.road_disturbance ? '荒れ検出中' : '良好';
    roadEl.style.color = s.road_disturbance ? '#f0883e' : '#3fb950';
    document.getElementById('roadPct').innerText = (s.road_roughness_pct ?? 0).toFixed(1) + ' %';
    if(s.last_event){
      const ratio = s.last_event.road_disturbance_ratio || 0;
      const note = ratio > 0.15
        ? `<br><span style="color:#f0883e;">路面ノイズの影響あり (${(ratio*100).toFixed(0)}%, 信頼度${(s.last_event.confidence*100).toFixed(0)}%)</span>`
        : '';
      const bd = s.last_event.score_breakdown || {};
      const bdText = Object.keys(bd).length
        ? '<br>' + Object.entries(bd).map(([k,v]) => `${k}:${v}`).join(' / ')
        : '';
      document.getElementById('eventBox').innerHTML =
        `<div class="type">EVENT: ${s.last_event.event_type}</div>
         Peak G: ${s.last_event.peak_g.toFixed(2)} G &nbsp; Peak Jerk: ${s.last_event.peak_jerk.toFixed(2)} G/s<br>
         Score: ${s.last_event.score}${note}
         <span style="font-size:11px; color:#8b949e;">${bdText}</span>`;
    }
}
</script>
</body>
</html>
"""


# =========================================================================
# 18. Main Control
# =========================================================================

class SessionState:
    def __init__(self):
        self.lock = threading.Lock()
        self.session_id: Optional[str] = None
        self.driver: Optional[Driver] = None
        self.vehicle: Optional[Vehicle] = None
        self.mode: str = "STREET"
        self.calibration = Calibration()
        self.orientation: Optional[Orientation] = None
        self.dynamics: Optional[VehicleDynamicsEngine] = None
        self.detector: Optional[EventDetector] = None
        self.scoring: Optional[ScoringEngine] = None
        self.behavior: Optional[DriverBehaviorAnalyzer] = None
        self.periodic = PeriodicAnalyzer()
        self.pretrigger = RingBuffer(Config.PRE_TRIGGER_SEC)
        self.active_waveforms: Dict[str, List[DynamicsSample]] = {}
        self.pending_transitions: List[Dict[str, Any]] = []
        self.event_hold_until: Dict[str, float] = {}
        self.events: List[DrivingEvent] = []
        self.periodic_stats: List[PeriodicStat] = []
        self.events_window: List[DrivingEvent] = []
        self.last_dyn: Optional[DynamicsSample] = None
        self.last_event: Optional[DrivingEvent] = None
        self.last_gps: Optional[SensorSample] = None
        self.first_gps: Optional[SensorSample] = None   # レポート出力用: 走行開始地点/時刻の記録
        # 平均速度・走行距離・RMS G算出用の累積値(一時停止中は加算しない)
        self.distance_m = 0.0
        self.speed_time_s = 0.0     # GPS速度が有効だった積算時間(平均速度の分母)
        self.g_sq_sum_x = 0.0
        self.g_sq_sum_y = 0.0
        self.g_sample_count = 0
        # セッション最大G (制動/加速/左右コーナー/合成)。値はG単位＋発生時刻・GPS。
        self.max_g = self._new_max_g()
        # [1][2] セッション中の最高Traction Utilization Ratio(グリップ利用率)。
        # タイヤロック/グリップ喪失イベントが確定しなくても、"どれだけグリップを
        # 使い切ったか"は常時記録する連続量として重要なため独立して追跡する。
        self.peak_tur = self._new_peak_tur()
        # タイヤロック/グリップ喪失の検出記録 (GPS付き, 立ち上がりエッジで1件)。
        self.tire_lock_count = 0
        self.last_tire_lock: Optional[Dict[str, Any]] = None
        self.tire_lock_events: List[Dict[str, Any]] = []
        self._tire_lock_prev = False
        self.running = False
        self.start_time: Optional[float] = None
        self.start_monotonic: Optional[float] = None   # time.monotonic()側の基準点(レポートの時刻表示用)

    @staticmethod
    def _new_max_g() -> Dict[str, Any]:
        keys = ("brake", "accel", "corner_left", "corner_right", "combined")
        return {k: {"g": 0.0, "rel_t": None, "lat": None, "lon": None, "speed": None} for k in keys}

    @staticmethod
    def _new_peak_tur() -> Dict[str, Any]:
        return {"value": 0.0, "rel_t": None, "lat": None, "lon": None, "speed": None}

    def driving_stats(self) -> Dict[str, Any]:
        """平均速度・走行距離(概算)・RMS G(前後/左右)をまとめて返す。
        呼び出し側がstate.lockを保持している前提(通常のフィールド読み取りのみのため
        ロック無しで呼んでも実害は小さいが、一貫したスナップショットのため推奨)。"""
        avg_speed_kmh = ((self.distance_m / self.speed_time_s) * 3.6
                          if self.speed_time_s > 0.0 else None)
        rms_gx = math.sqrt(self.g_sq_sum_x / self.g_sample_count) if self.g_sample_count else 0.0
        rms_gy = math.sqrt(self.g_sq_sum_y / self.g_sample_count) if self.g_sample_count else 0.0
        return {
            "avg_speed_kmh": round(avg_speed_kmh, 1) if avg_speed_kmh is not None else None,
            "distance_km": round(self.distance_m / 1000.0, 2),
            "rms_gx": round(rms_gx, 3),
            "rms_gy": round(rms_gy, 3),
        }


class MainControl:
    def __init__(self):
        ensure_data_dir()
        load_config_overrides()   # 設定パネルで保存済みの調整値をConfigへ反映
        self.vehicle_db = VehicleDatabase(os.path.join(Config.DATA_DIR, "vehicles.json"))
        self.driver_db = DriverDatabase(os.path.join(Config.DATA_DIR, "drivers.json"))
        self._seed_defaults()
        self.storage = DataStorage(Config.DATA_DIR)
        self.adaptive = AdaptiveProfileStore(os.path.join(Config.DATA_DIR, "adaptive_profiles.json"))
        # 起動時に保持期間切れの古い走行ログを自動削除する。
        removed = self.storage.prune_old_logs()
        if removed:
            print(f" 古い走行ログ {len(removed)} 件を自動削除しました (保持{Config.LOG_RETENTION_DAYS}日)")
        self.sensor = SensorInterface()
        self.state = SessionState()
        self.applied_corrections: Optional[Dict[str, float]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

    def _refresh_adaptive_profile(self, driver_id, vehicle_id, mode):
        """指定条件の走行ログを分析し、自動補正プロファイルを更新する。"""
        if not Config.ADAPTIVE_ENABLED:
            return None
        sessions = self.storage.load_sessions(driver_id, vehicle_id, mode)
        analysis = DrivingProfileAnalyzer.analyze(sessions, mode)
        if analysis is None:
            return None
        return self.adaptive.update(driver_id, vehicle_id, analysis)

    def _score_history(self, driver_id, vehicle_id, mode, limit: int = 10):
        """直近走行のスコア推移を古い→新しい順で返す (自動補正の効き可視化用)。"""
        sessions = self.storage.load_sessions(driver_id, vehicle_id, mode)
        sessions = list(reversed(sessions))[-limit:]
        return [{"session_id": s.get("session_id"), "total_score": s.get("total_score"),
                 "baseline_total_score": s.get("baseline_total_score"),
                 "adaptive": s.get("adaptive_applied") is not None,
                 "events": s.get("event_count", 0)} for s in sessions]

    def _prune_old_reports(self):
        """report/フォルダ内のtxtのうち、保持期間(既定7日)を過ぎたものを削除する。"""
        days = Config.REPORT_RETENTION_DAYS
        if not days or days <= 0:
            return
        cutoff = time.time() - days * 86400.0
        try:
            for fn in os.listdir(Config.REPORT_DIR):
                if not fn.endswith(".txt"):
                    continue
                path = os.path.join(Config.REPORT_DIR, fn)
                try:
                    if os.path.getmtime(path) < cutoff:
                        os.remove(path)
                except OSError:
                    pass
        except OSError:
            pass

    def _write_fallback_report(self, session_record, driver_name, vehicle_name, error) -> str:
        """Version 1.4: 「走行終了後にAIへ渡すレポートを必ず出力する」ことを保証するための
        最終フォールバック。_write_llm_report()が何らかの理由で最後まで完走できなかった
        場合でも、最低限の走行サマリーを含むtxtファイルを必ず1つ残す。"""
        ensure_data_dir()
        now_local = time.localtime(session_record.get("end_time") or time.time())
        fname = time.strftime(f"DDA_Report_v{Config.APP_VERSION}_%Y%m%d_%H%M%S_fallback.txt", now_local)
        path = os.path.join(Config.REPORT_DIR, fname)
        lines = [
            "=" * 70,
            "Driving Dynamics Analyzer (DDA) 走行レポート (簡易版/フォールバック)",
            f"DDAバージョン: {Config.APP_VERSION} / 作成者: {Config.APP_AUTHOR}",
            "=" * 70,
            "",
            "詳細レポートの生成中にエラーが発生したため、最低限のサマリーのみを出力しています。",
            f"エラー内容: {type(error).__name__}: {error}",
            "",
            f"ドライバー: {driver_name}",
            f"車両: {vehicle_name}",
            f"走行モード: {session_record.get('mode')}",
            f"総合スコア: {session_record.get('total_score')}",
            f"データ信頼度: {session_record.get('reliability_pct')}%",
            f"イベント検出数: {session_record.get('event_count')}",
            f"タイヤロック/グリップ喪失 検出数: {session_record.get('tire_lock_count')}",
            "",
            "=" * 70,
            "(このファイルはDDAが自動生成しました。7日後に自動的に削除されます)",
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._prune_old_reports()
        return fname

    def _write_llm_report(self, *, session_record, driver_name, vehicle_name, mode, total,
                           reliability_pct, habits, events, periodic, max_g, tire_lock_count,
                           tire_lock_by_type, first_gps, last_gps, adaptive_applied,
                           baseline_total, start_monotonic, driving_stats,
                           peak_tur=None, grip_mu_used=None, event_type_counts=None,
                           event_type_avg_score=None, avg_score_breakdown=None,
                           score_bonus=None, duration_min=None) -> Optional[str]:
        """走行終了後、外部LLM(Claude/ChatGPT等)にそのまま読み込ませて分析させるための
        txtレポートを report/ フォルダに出力する。プロンプト部分をテンプレート化して
        あるため、ユーザーが追加のコメントを書き足さなくても、読み込ませるだけで
        詳細な分析・具体的な改善アドバイスが得られることを狙っている。
        GPS(緯度経度)と時刻を明記し、読み込んだAI自身がその場所の道路形状や
        当時の天候・気温を調べたうえで分析できるようにする(このスクリプト自体は
        オフラインでも動くようにしたいため、天候・地図情報の取得はここでは行わない)。

        Version 1.4: 「走行終了後に必ず出力する」ことを保証するため、各セクションの
        組み立てを try/except で個別に保護している。どこか1セクションの生成に失敗しても
        (想定外のデータ欠損等)、そこだけスキップして他のセクションは正常に出力し、
        最終的に必ずファイル書き込みまで到達できるようにしてある。"""
        ensure_data_dir()
        now_local = time.localtime(session_record["end_time"])
        fname = time.strftime(f"DDA_Report_v{Config.APP_VERSION}_%Y%m%d_%H%M%S.txt", now_local)
        path = os.path.join(Config.REPORT_DIR, fname)

        def fmt_t(epoch):
            if epoch is None:
                return "不明"
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))

        def fmt_gps(g):
            if g is None or g.lat is None or g.lon is None:
                return "取得なし"
            return f"緯度 {g.lat:.6f}, 経度 {g.lon:.6f} (時刻: {fmt_t(session_record['start_time'])}付近)"

        def event_wall_time(e):
            # e.start_t は time.monotonic() 基準なので、セッション開始時に記録した
            # (wall時刻, monotonic時刻)のペアを使って実時刻に変換する。
            if start_monotonic is None:
                return "不明"
            return fmt_t(session_record["start_time"] + (e.start_t - start_monotonic))

        lines = []

        def _section(builder):
            """Version 1.4: 1セクション分の行を安全に構築する。想定外のデータ欠損等で
            builder()内が例外を送出しても、そのセクションだけ省略した旨を1行残して
            処理を継続する(=1箇所の不具合でレポート全体の生成・出力が止まらないようにする)。"""
            try:
                builder()
            except Exception as sec_e:
                lines.append(f"  (このセクションの生成中にエラーが発生したため一部省略: {sec_e})")

        lines.append("=" * 70)
        lines.append("Driving Dynamics Analyzer (DDA) 走行レポート")
        lines.append(f"DDAバージョン: {Config.APP_VERSION} / 作成者: {Config.APP_AUTHOR}")
        lines.append("=" * 70)
        lines.append("")
        lines.append("# あなた(AI)へのお願い(このレポートを分析してください)")
        lines.append(
            "あなたは自動車運転技術の専門コーチです。以下は、スマートフォンのセンサー"
            "(加速度・ジャイロ・GPS)を用いて記録した実際の1回の走行データです。数値は"
            "全てG(重力加速度単位)・秒・度・m/sなど明記された単位で記録された実測/解析"
            "値です。これを踏まえて、次の観点で具体的に分析してください:")
        lines.append(
            "  1. 総合スコア・信頼度・各イベントの内訳(G制御/ジャーク/荷重移動/整定性/"
            "一貫性)から、特に良かった点を具体的な数値を挙げて指摘してください。平均速度・"
            "RMS G(常時の揺さぶられ具合)も踏まえ、この走行が市街地/峠/高速のどれに近い"
            "性質だったかも考慮してください。")
        lines.append(
            "  2. 特に悪かった点(スコアが低いイベント・タイヤロック・路面外乱の影響が"
            "大きいイベントなど)を具体的に指摘し、「何を」「どう」直せば改善するか、"
            "実際のペダル操作・ステアリング操作・ライン取りのレベルで具体的にアドバイス"
            "してください。")
        lines.append(
            "  3. 下記にGPS座標(緯度・経度)と走行日時を記載しています。可能であれば、"
            "その場所の道路形状(直線/カーブ/勾配/交差点の有無など)、および走行日時"
            "における天候・気温を調べたうえで、路面状況(降雨・低温によるグリップ低下等)"
            "が運転評価に与えた影響についても考察に含めてください。")
        lines.append(
            "  4. 「路面外乱の影響あり」と記録されたイベントは、うねり・段差など"
            "ドライバーの操作とは無関係な外乱の可能性があるため、運転技術の評価からは"
            "切り離して(過度に減点せずに)考慮してください。信頼度(confidence)が低い"
            "データは参考程度に留めてください。")
        lines.append(
            "  5. 下記「グリップ利用率(TUR)」は、タイヤが物理的に出せる摩擦力の推定上限に"
            "対して、実際にどれだけ使い切れていたかを示す指標です(1.0=推定上限到達)。"
            "セッション最高値やイベント毎のpeak_turを踏まえ、まだグリップに余裕を残した"
            "運転だったのか、既に限界に近い/達していたのかを評価してください。"
            "GRIP_PLATEAU種別のタイヤロック記録は、ABS的な脈動(ジャダー)を伴わない"
            "滑らかな滑走(路面の水膜等)の兆候を示すため、通常のロックとは区別して"
            "考察してください。ただしmu_long_max/mu_lat_max(推定グリップ上限)は"
            "走行データが少ないうちは既定値のままであり、精度が限定的である点も"
            "踏まえた上で評価してください。")
        lines.append(
            "  6. 最後に、次回の走行で意識すべき改善ポイントを3つ以内に絞って、"
            "優先順位付きでまとめてください。")
        def _sec_summary():
            lines.append("")
            lines.append("# セッション概要")
            lines.append(f"ドライバー: {driver_name}")
            lines.append(f"車両: {vehicle_name}")
            lines.append(f"走行モード: {mode}")
            lines.append(f"開始時刻: {fmt_t(session_record['start_time'])}")
            lines.append(f"終了時刻: {fmt_t(session_record['end_time'])}")
            dur_min = (duration_min if duration_min is not None
                       else (session_record["end_time"] - session_record["start_time"]) / 60.0)
            lines.append(f"走行時間: 約{dur_min:.1f}分")
            avg_speed = driving_stats.get("avg_speed_kmh")
            lines.append(f"平均速度: {avg_speed if avg_speed is not None else '不明(GPS速度取得なし)'} km/h "
                          f"/ 走行距離(概算): {driving_stats.get('distance_km')} km")
            lines.append(f"RMS G (常時どれだけ揺さぶられていたかの指標): "
                          f"前後 {driving_stats.get('rms_gx')}G / 左右 {driving_stats.get('rms_gy')}G "
                          "(ピークGが小さくても値が大きい場合、乗り心地の粗さや小刻みな操作を示唆します)")
            lines.append(f"総合スコア: {total if total is not None else 'N/A(有効データ不足)'}")
            if score_bonus and score_bonus.get("base") is not None:
                b = score_bonus.get("bonus") or 0.0
                lines.append(
                    f"  内訳: 基礎点(重み付け平均) {score_bonus.get('base')} "
                    f"+ 優良運転ボーナス {'+' if b >= 0 else ''}{b} = 総合 {total}"
                    " (Version 1.4: 高スコアを維持できた割合に応じて加点する仕組み)")
            lines.append(f"データ信頼度: {reliability_pct}% "
                          "(センサ受信品質・路面外乱の影響を加味した信頼度。低いほど参考値扱い)")
            if adaptive_applied:
                lines.append(f"自動補正(このドライバー・車両の走行傾向に基づく採点基準): 適用済み {adaptive_applied}")
                if baseline_total is not None and total is not None:
                    lines.append(f"  (既定基準での採点: {baseline_total} → 自動補正後: {total})")
            else:
                lines.append("自動補正: 未適用(走行データ蓄積中、既定の採点基準を使用)")
            lines.append(f"イベント検出数: {len(events)}")
            lines.append(f"タイヤロック/グリップ喪失 検出数: {tire_lock_count} 内訳: {tire_lock_by_type}")
            if peak_tur:
                gm = grip_mu_used or {}
                lines.append(
                    f"セッション最高グリップ利用率(TUR): {peak_tur.get('value')} "
                    f"(1.0=推定上限到達, t+{peak_tur.get('rel_t')}s"
                    f"{', '+str(peak_tur.get('speed'))+'m/s' if peak_tur.get('speed') is not None else ''}) "
                    f"/ 判定に使用した推定グリップ上限: 制動方向 {gm.get('mu_long_max')}G, "
                    f"旋回方向 {gm.get('mu_lat_max')}G")
        _section(_sec_summary)

        def _sec_event_types():
            if not event_type_counts:
                return
            lines.append("")
            lines.append("# イベント種別ごとの集計 (件数・平均スコア)")
            for et, cnt in event_type_counts.items():
                avg_s = (event_type_avg_score or {}).get(et)
                lines.append(f"  {et}: {cnt}件 / 平均スコア {avg_s if avg_s is not None else 'N/A'}")
        _section(_sec_event_types)

        def _sec_breakdown_avg():
            if not avg_score_breakdown:
                return
            lines.append("")
            lines.append("# スコア内訳 平均(今回走行の全イベント平均, 100点満点)")
            for k, v in avg_score_breakdown.items():
                lines.append(f"  {k}: {v}")
            lines.append("  (この5項目は簡易レポート画面のレーダーチャートにも使用しています)")
        _section(_sec_breakdown_avg)

        def _sec_gps():
            lines.append("")
            lines.append("# 走行位置情報 (GPS) - 道路形状・天候調査の手がかり")
            lines.append(f"走行開始地点: {fmt_gps(first_gps)}")
            lines.append(f"走行終了地点: {fmt_gps(last_gps)}")
        _section(_sec_gps)

        def _sec_habits():
            if habits:
                lines.append("")
                lines.append("# 検出された運転傾向(クセ)")
                for h in habits:
                    lines.append(f"  - {h}")
        _section(_sec_habits)

        def _sec_events():
            lines.append("")
            lines.append("# イベント詳細 (検出順)")
            if not events:
                lines.append("  (このセッションでは有効なイベントは検出されませんでした)")
            for i, e in enumerate(events, 1):
                try:
                    bd = e.score_breakdown or {}
                    bd_text = ", ".join(f"{k}:{v}" for k, v in bd.items())
                    gps_text = (f"緯度{e.lat:.6f},経度{e.lon:.6f}"
                                if (e.lat is not None and e.lon is not None) else "GPS取得なし")
                    note = ""
                    if e.road_disturbance_ratio and e.road_disturbance_ratio > 0.15:
                        note = (f" [路面ノイズの影響あり: {e.road_disturbance_ratio*100:.0f}%, "
                                f"信頼度{e.confidence*100:.0f}%]")
                    lines.append(
                        f"  {i}. [{event_wall_time(e)}] "
                        f"種別:{e.event_type} スコア:{e.score} (内訳: {bd_text}){note}")
                    lines.append(
                        f"      継続時間:{e.duration:.2f}s ピークG:{e.peak_g:.2f}G "
                        f"ピークJerk:{e.peak_jerk:.2f}G/s グリップ利用率(TUR)最大:{e.peak_tur:.2f} "
                        f"整定時間:{(e.settling_time or 0):.2f}s "
                        f"オーバーシュート:{(e.overshoot or 0):.2f} 速度:{e.speed if e.speed is not None else '不明'} "
                        f"位置:{gps_text}")
                except Exception as ev_e:
                    lines.append(f"  {i}. (このイベントの出力中にエラー: {ev_e})")
        _section(_sec_events)

        def _sec_periodic():
            lines.append("")
            lines.append("# 区間統計 (周期集計)")
            if not periodic:
                lines.append("  (区間統計はありません)")
            for i, p in enumerate(periodic, 1):
                try:
                    lines.append(
                        f"  区間{i}: スコア:{p.score} 信頼度:{p.confidence:.2f} "
                        f"平均Gx:{p.mean_gx:.2f} 平均Gy:{p.mean_gy:.2f} ジャークRMS:{p.jerk_rms:.2f} "
                        f"路面荒れ率:{p.road_roughness_pct:.1f}% 一貫性:{p.consistency:.1f} "
                        f"左右バランス:{p.lr_balance:.1f}")
                except Exception as pd_e:
                    lines.append(f"  区間{i}: (出力中にエラー: {pd_e})")
        _section(_sec_periodic)

        def _sec_maxg():
            lines.append("")
            lines.append("# 最大G記録")
            for k, v in max_g.items():
                if v.get("g"):
                    lines.append(f"  {k}: {v['g']:.2f}G "
                                  f"(位置: 緯度{v.get('lat')},経度{v.get('lon')} 速度:{v.get('speed')})")
        _section(_sec_maxg)

        lines.append("")
        lines.append("=" * 70)
        lines.append("(このファイルはDDAが自動生成しました。7日後に自動的に削除されます)")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self._prune_old_reports()
        return fname

    def _seed_defaults(self):
        if not self.driver_db.list():
            self.driver_db.add("Driver 1")
            self.driver_db.add("Driver 2")
        if not self.vehicle_db.list():
            self.vehicle_db.add(name="Vehicle 1", mass_kg=1300, wheelbase_mm=2650,
                                 tread_front_mm=1520, tread_rear_mm=1520, drive_type="FF")

    # --- セッション制御 -------------------------------------------------

    def start_session(self, driver_id: str, vehicle_id: str, mode: str):
        st = self.state
        with st.lock:
            st.session_id = time.strftime("%Y%m%d_%H%M%S")
            st.driver = self.driver_db.get(driver_id) or self.driver_db.list()[0]
            st.vehicle = self.vehicle_db.get(vehicle_id)
            st.mode = mode if mode in Config.EVENT_TRIGGER_G else "STREET"
            # --- 適応キャリブレーション: 蓄積ログから本人の実レンジに閾値を自動補正 ---
            corr = None
            if Config.ADAPTIVE_ENABLED and st.vehicle:
                corr = self.adaptive.get_corrections(st.driver.driver_id, st.vehicle.vehicle_id, st.mode)
            self.applied_corrections = corr
            trigger_g = corr["event_trigger_g"] if corr else None
            jerk_lim = corr["jerk_limit_g_per_s"] if corr else None
            lt_lim = corr["lt_rate_limit"] if corr else None
            # [2]: 適応グリップ包絡線(mu_long_max/mu_lat_max)。蓄積不足で未推定の
            # 場合はcorr内にキー自体が無いため、.get()でNoneフォールバックし
            # TireLockDetector側でConfig既定値が使われるようにする。
            mu_long_max = corr.get("mu_long_max") if corr else None
            mu_lat_max = corr.get("mu_lat_max") if corr else None

            st.calibration = Calibration()
            st.dynamics = VehicleDynamicsEngine(st.vehicle, mu_long_max=mu_long_max, mu_lat_max=mu_lat_max)
            st.dynamics.mode = st.mode   # タイヤロック検出・バンプ処理のモード連動
            st.detector = EventDetector(st.mode, trigger_g=trigger_g)
            st.scoring = ScoringEngine(st.mode, jerk_limit=jerk_lim, lt_rate_limit=lt_lim)
            st.behavior = DriverBehaviorAnalyzer(st.driver)
            st.periodic = PeriodicAnalyzer()
            st.pretrigger = RingBuffer(Config.PRE_TRIGGER_SEC)
            st.active_waveforms = {}
            st.pending_transitions = []
            st.event_hold_until = {}
            st.events = []
            st.periodic_stats = []
            st.events_window = []
            st.last_dyn = None
            st.last_event = None
            st.last_gps = None
            st.first_gps = None
            st.distance_m = 0.0
            st.speed_time_s = 0.0
            st.g_sq_sum_x = 0.0
            st.g_sq_sum_y = 0.0
            st.g_sample_count = 0
            st.max_g = SessionState._new_max_g()
            st.peak_tur = SessionState._new_peak_tur()
            st.tire_lock_count = 0
            st.last_tire_lock = None
            st.tire_lock_events = []
            st._tire_lock_prev = False
            st.orientation = None
            st.running = True
            st.start_time = time.time()
            st.start_monotonic = time.monotonic()

        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._acquisition_loop, daemon=True)
        self._thread.start()

    def stop_session(self) -> Dict[str, Any]:
        st = self.state
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=2.0)

        with st.lock:
            st.running = False
            periodic_pairs = [(p.score, p.confidence) for p in st.periodic_stats]
            event_pairs = [(e.score, e.confidence) for e in st.events]
            total = (st.scoring.total_score(periodic_pairs, event_pairs)
                     if st.scoring else None)
            # Version 1.4: 優良運転ボーナスの内訳(透明性確保のため画面/レポートに表示する)。
            score_bonus = ({"base": st.scoring.last_base_score, "bonus": st.scoring.last_bonus}
                           if (st.scoring and st.scoring.last_base_score is not None) else None)
            # 全体の信頼度(レビュー指摘㉜ DDA Reliability Indexの簡易版):
            # イベント・周期統計それぞれの信頼度を均等重みで平均する。
            all_conf = [c for _, c in periodic_pairs] + [c for _, c in event_pairs]
            reliability_pct = round(100.0 * sum(all_conf) / len(all_conf), 0) if all_conf else 0.0
            habits = st.behavior.detect_habits(st.events) if st.behavior else []

            best = max(st.events, key=lambda e: e.score, default=None)
            worst = min(st.events, key=lambda e: e.score, default=None)

            # --- Version 1.4: 簡易レポート画面の情報量拡充用データ ---
            # イベント種別ごとの件数・平均スコア(簡易レポートの表形式表示用)。
            event_type_counts: Dict[str, int] = {}
            event_type_avg_score: Dict[str, float] = {}
            for et in EVENT_TYPES:
                evs_of_type = [e for e in st.events if e.event_type == et]
                if evs_of_type:
                    event_type_counts[et] = len(evs_of_type)
                    event_type_avg_score[et] = round(
                        sum(e.score for e in evs_of_type) / len(evs_of_type), 1)
            # スコア内訳(G制御/ジャーク/荷重移動/整定性/一貫性)のセッション平均。
            # レーダーチャート(今回走行)の元データとしても使う。
            avg_score_breakdown: Dict[str, float] = {}
            breakdown_keys = ("G制御", "ジャーク", "荷重移動", "整定性", "一貫性")
            for k in breakdown_keys:
                vals = [e.score_breakdown.get(k) for e in st.events
                        if e.score_breakdown and k in e.score_breakdown]
                if vals:
                    avg_score_breakdown[k] = round(sum(vals) / len(vals), 1)
            # 運転特性プロファイル(蓄積EMA, §61)。レーダーチャート(蓄積傾向)の元データ。
            driver_fingerprint = dict(st.driver.stats.fingerprint) if st.driver else {}
            duration_min = (round((time.time() - st.start_time) / 60.0, 1)
                             if st.start_time else None)

            # 自動補正の効果検証: 既定上限で再スコアリングして比較する。
            baseline_total = None
            if self.applied_corrections and st.events and st.scoring:
                base_engine = ScoringEngine(st.mode)
                base_pairs = [(base_engine.score_event(e), e.confidence) for e in st.events]
                baseline_total = base_engine.total_score(periodic_pairs, base_pairs)

            if st.driver:
                st.driver.stats.session_count += 1
                st.driver.stats.event_count += len(st.events)
                self.driver_db.save()

            session_record = {
                "session_id": st.session_id,
                "driver_id": st.driver.driver_id if st.driver else None,
                "vehicle_id": st.vehicle.vehicle_id if st.vehicle else None,
                "mode": st.mode,
                "start_time": st.start_time,
                "end_time": time.time(),
                "total_score": total,
                "reliability_pct": reliability_pct,
                "adaptive_applied": self.applied_corrections,
                "baseline_total_score": baseline_total,
                "event_count": len(st.events),
                "events": [asdict(e) for e in st.events],
                "periodic": [asdict(p) for p in st.periodic_stats],
                "habits": habits,
                "max_g": st.max_g,
                # [1][2] このセッションで実際に使い切ったグリップの最大値(TUR)、および
                # 判定に使用したmu_long_max/mu_lat_max(適応値/既定値のどちらか)。
                "peak_tur": st.peak_tur,
                "grip_mu_used": ({"mu_long_max": st.dynamics.tire_lock.mu_long_max,
                                  "mu_lat_max": st.dynamics.tire_lock.mu_lat_max}
                                 if st.dynamics else None),
                "tire_lock_count": st.tire_lock_count,
                "tire_lock_events": st.tire_lock_events,
                # 荷重移動は常に無次元係数(ΔW/W)で評価・保存する。下記は実測重心高を
                # 使えたか(True)/基準値で代替したか(False)のデータ精度フラグ (単位は同一)。
                "load_transfer_unit": "coefficient_dW_over_W",
                "load_transfer_measured_cg": (st.dynamics.load_transfer_is_estimated_mass()
                                              if st.dynamics else False),
                # Version 1.4: 簡易レポート/AIレポート拡充用データもログへ保存しておく。
                "event_type_counts": event_type_counts,
                "event_type_avg_score": event_type_avg_score,
                "avg_score_breakdown": avg_score_breakdown,
                "score_bonus": score_bonus,
                "duration_min": duration_min,
            }
            self.storage.save_session(session_record)

            driver_id = st.driver.driver_id if st.driver else None
            vehicle_id = st.vehicle.vehicle_id if st.vehicle else None
            driver_name = st.driver.display_name if st.driver else "不明"
            vehicle_name = st.vehicle.name if st.vehicle else "不明"
            mode = st.mode
            max_g = st.max_g
            peak_tur = st.peak_tur
            grip_mu_used = ({"mu_long_max": st.dynamics.tire_lock.mu_long_max,
                             "mu_lat_max": st.dynamics.tire_lock.mu_lat_max}
                            if st.dynamics else None)
            tire_lock_count = st.tire_lock_count
            tire_lock_events = st.tire_lock_events
            first_gps = st.first_gps
            last_gps = st.last_gps
            start_monotonic = st.start_monotonic
            events_snapshot = list(st.events)
            periodic_snapshot = list(st.periodic_stats)
            driving_stats = st.driving_stats()
            # タイヤロック種別別集計 (サーキット復習用)。
            tire_lock_by_type: Dict[str, int] = {}
            for rec in st.tire_lock_events:
                ty = rec.get("type") or "UNKNOWN"
                tire_lock_by_type[ty] = tire_lock_by_type.get(ty, 0) + 1

        # --- ロック外: 保持期間切れログ削除 + 自動補正プロファイル再学習 + スコア推移 ---
        self.storage.prune_old_logs()
        updated_corr = None
        score_history = []
        if driver_id and vehicle_id:
            updated_corr = self._refresh_adaptive_profile(driver_id, vehicle_id, mode)
            score_history = self._score_history(driver_id, vehicle_id, mode)
        adaptive_delta = (round(total - baseline_total, 1)
                           if (baseline_total is not None and total is not None) else None)

        # --- LLM分析用テキストレポートの生成 (report/フォルダ、7日で自動削除) ---
        # Version 1.4: 「走行終了後にAIへ渡すレポートを必ず出力する」ことを保証するため、
        # _write_llm_report() 内部で各セクションを個別に保護したうえで、万一それでも
        # 例外が発生した場合はここで最低限のフォールバックレポートを生成する
        # (=どのような状況でも report/ に最低1つのtxtファイルが必ず残る)。
        report_file = None
        try:
            report_file = self._write_llm_report(
                session_record=session_record, driver_name=driver_name, vehicle_name=vehicle_name,
                mode=mode, total=total, reliability_pct=reliability_pct, habits=habits,
                events=events_snapshot, periodic=periodic_snapshot,
                max_g=max_g, tire_lock_count=tire_lock_count, tire_lock_by_type=tire_lock_by_type,
                first_gps=first_gps, last_gps=last_gps,
                adaptive_applied=self.applied_corrections, baseline_total=baseline_total,
                start_monotonic=start_monotonic, driving_stats=driving_stats,
                peak_tur=peak_tur, grip_mu_used=grip_mu_used,
                event_type_counts=event_type_counts, event_type_avg_score=event_type_avg_score,
                avg_score_breakdown=avg_score_breakdown, score_bonus=score_bonus,
                duration_min=duration_min,
            )
        except Exception as e:
            print(f"[WARN] レポート出力に失敗しました。フォールバックレポートを生成します: {e}")
            try:
                report_file = self._write_fallback_report(session_record, driver_name, vehicle_name, e)
            except Exception as e2:
                print(f"[ERROR] フォールバックレポートの生成にも失敗しました: {e2}")

        return {
            "app_version": Config.APP_VERSION,
            "app_author": Config.APP_AUTHOR,
            "mode": mode,
            "driver_name": driver_name,
            "vehicle_name": vehicle_name,
            "duration_min": duration_min,
            "total_score": total,
            "reliability_pct": reliability_pct,
            "score_bonus": score_bonus,
            "driving_stats": driving_stats,
            "event_count": len(st.events),
            "event_type_counts": event_type_counts,
            "event_type_avg_score": event_type_avg_score,
            "avg_score_breakdown": avg_score_breakdown,
            "driver_fingerprint": driver_fingerprint,
            "habits": habits,
            "adaptive_applied": self.applied_corrections,
            "adaptive_updated": updated_corr,
            "baseline_total_score": baseline_total,
            "adaptive_delta": adaptive_delta,
            "score_history": score_history,
            "max_g": max_g,
            "peak_tur": peak_tur,
            "grip_mu_used": grip_mu_used,
            "tire_lock_count": tire_lock_count,
            "tire_lock_by_type": tire_lock_by_type,
            "tire_lock_events": tire_lock_events,
            "best_event": asdict(best) if best else None,
            "worst_event": asdict(worst) if worst else None,
            "report_file": report_file,
        }

    # --- センサ取得ループ (Sensor Acquisition -> ... -> Score Engine) ---

    def _acquisition_loop(self):
        st = self.state
        target_dt = 1.0 / Config.TARGET_HZ_MAX
        # ドリフト補正スリープ(レビュー指摘③): 単純に time.sleep(target_dt) を
        # 繰り返すと、ループ本体の処理時間ぶんだけ毎回period > target_dtとなり、
        # 実効サンプリングレートが徐々に(そして負荷が重いほど大きく)目標100Hzから
        # 下振れしていく。次回の"目標時刻"を絶対時刻で持ち、それとの差分だけ
        # スリープすることで、処理時間を差し引いた分を自動的に埋め合わせる。
        # (dt自体はs.tの実測差分から計算しているため物理量の誤差は限定的だが、
        #  サンプリング密度が落ちると短時間の高周波イベントを取りこぼしうる。)
        next_time = time.monotonic() + target_dt
        was_paused = False  # 一時停止→再開の遷移検出用 (この変数はループスレッド専有)

        while not self._stop_flag.is_set():
            s = self.sensor.read()

            # --- ロックは状態の読み書きだけを保護し、sleep()の間は必ず解放する ---
            # (ロックを保持したままsleepすると、HTTPハンドラ側のsnapshot()が
            #  ブロックされ続け、ポーリング頻度次第でサーバーが実質フリーズするため)
            with st.lock:
                if self.sensor.is_paused:
                    # レビュー指摘②: センサ無応答が長時間続いている間は、凍結データから
                    # 誤ったイベント/スコアを作らないよう解析を丸ごとスキップする。
                    was_paused = True
                elif not st.calibration.done:
                    if was_paused:
                        self._resume_from_pause(st)
                        was_paused = False
                    st.calibration.feed(s)
                else:
                    if was_paused:
                        # レビュー指摘(コーナーケース): 一時停止中に「進行中」のまま
                        # 固まっていたイベント検出状態や波形バッファを、再開直後に
                        # 数秒単位のギャップを挟んだまま1つのイベントとして誤って
                        # つなげてしまわないよう、ここで確実に破棄してから再開する。
                        self._resume_from_pause(st)
                        was_paused = False
                    if st.orientation is None:
                        st.orientation = Orientation(st.calibration.gravity_vec)

                    if s.gps_ok:
                        st.last_gps = s
                        if st.first_gps is None:
                            st.first_gps = s

                    d = st.dynamics.process(s, st.orientation, st.calibration)
                    if d is not None:
                        st.last_dyn = d
                        st.periodic.add(d)
                        st.pretrigger.append(d)

                        # 平均速度・走行距離・RMS G算出用の累積(レポート/画面表示用)。
                        # GPS速度は取得できている区間だけを積算する(欠測区間は分母に含めない)。
                        if s.speed is not None and (s.gps_age is None or s.gps_age <= Config.GPS_STALE_SEC):
                            st.distance_m += s.speed * d.dt
                            st.speed_time_s += d.dt
                        st.g_sq_sum_x += d.gx * d.gx
                        st.g_sq_sum_y += d.gy * d.gy
                        st.g_sample_count += 1

                        # セッション最大G の更新 (バンプ由来の単発スパイクは
                        # 路面外乱アクティブ中サンプルを除外して拾わない)。
                        if not d.road_disturbance:
                            self._update_max_g(st, d)
                            # [1][2] セッション最高グリップ利用率(TUR)の更新。タイヤロック/
                            # グリップ喪失イベントが確定しなくても「どれだけグリップを
                            # 使い切ったか」は連続量として常時追跡する。
                            self._update_peak_tur(st, d)

                        # タイヤロック/グリップ喪失の立ち上がりエッジで1件記録する
                        # (カウント＋GPS付き完全レコードで「どのコーナーで何が」を復習可能に)。
                        if d.tire_lock and not st._tire_lock_prev:
                            st.tire_lock_count += 1
                            rel_t = (d.t - st.start_monotonic) if st.start_monotonic else d.t
                            rec = {
                                "index": st.tire_lock_count, "t": round(d.t, 2),
                                "rel_t": round(rel_t, 2), "type": d.tire_lock_type,
                                "gx": round(d.gx, 2), "gy": round(d.gy, 2), "gxy": round(d.gxy, 2),
                                "yaw_rate": round(d.yaw_rate, 3), "long_vib_rms": round(d.long_vib_rms, 3),
                                "tur": round(d.tur, 3), "confidence": round(d.tire_lock_confidence, 2),
                                "lat": (round(st.last_gps.lat, 6) if (st.last_gps and st.last_gps.lat is not None) else None),
                                "lon": (round(st.last_gps.lon, 6) if (st.last_gps and st.last_gps.lon is not None) else None),
                                "speed": (round(st.last_gps.speed, 1) if (st.last_gps and st.last_gps.speed is not None) else None),
                            }
                            st.last_tire_lock = rec
                            st.tire_lock_events.append(rec)
                        st._tire_lock_prev = d.tire_lock

                        started = st.detector.update(d)

                        # --- ヒステリシス系イベント (BRAKE/ACCEL/LEFT_CORNER/RIGHT_CORNER/COMBINED) ---
                        # 開始時にプリトリガーバッファ(§41)から過去分を波形に含める。
                        for etype in EVENT_TYPES:
                            if etype == "TRANSITION":
                                continue
                            if etype in started:
                                pre = st.pretrigger.slice_seconds(d.t, Config.PRE_TRIGGER_SEC)
                                st.active_waveforms[etype] = pre + [d]
                            elif etype in st.detector.active_types():
                                st.active_waveforms.setdefault(etype, []).append(d)
                        for etype in list(st.active_waveforms.keys()):
                            if etype not in st.detector.active_types():
                                waveform = st.active_waveforms.pop(etype)
                                if len(waveform) >= 3:
                                    self._finalize_event(etype, waveform, st)

                        # --- TRANSITION (切り返し) ---
                        # 符号反転の瞬間だけを捉えるヒステリシス"active"状態を持たないため、
                        # 固定時間 (pre-trigger + POST_TRIGGER_SEC) のキャプチャとして扱う。
                        # これを実装しないと、_active フラグが立たないまま次フレームで
                        # 波形が即座に破棄され、TRANSITIONイベントが常に保存されなかった。
                        if "TRANSITION" in started:
                            pre = st.pretrigger.slice_seconds(d.t, Config.PRE_TRIGGER_SEC)
                            st.pending_transitions.append({"start_t": d.t, "waveform": list(pre)})

                        still_pending = []
                        for pt in st.pending_transitions:
                            pt["waveform"].append(d)
                            if d.t - pt["start_t"] >= Config.POST_TRIGGER_SEC:
                                if len(pt["waveform"]) >= 3:
                                    self._finalize_event("TRANSITION", pt["waveform"], st)
                            else:
                                still_pending.append(pt)
                        st.pending_transitions = still_pending

                        if st.periodic.ready(d.t):
                            self._finalize_periodic(st)

                        self._trim_history(st)

            now = time.monotonic()
            sleep_time = next_time - now
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # 処理が重く遅延が蓄積した場合、無理に詰めて連続空振りループに
                # ならないよう次の目標時刻を現在時刻基準に再設定する。
                next_time = now
            next_time += target_dt

    def _update_max_g(self, st: SessionState, d: DynamicsSample):
        """セッション最大G(制動/加速/左右コーナー/合成)を更新する。
        符号規約: gx<0=制動, gx>0=加速, gy>0=左コーナー, gy<0=右コーナー。"""
        rel_t = (d.t - st.start_monotonic) if st.start_monotonic else d.t
        gps = st.last_gps

        def put(key, value):
            if value >= Config.MAXG_MIN_G and value > st.max_g[key]["g"]:
                st.max_g[key] = {
                    "g": round(value, 3), "rel_t": round(rel_t, 2),
                    "lat": (round(gps.lat, 6) if (gps and gps.lat is not None) else None),
                    "lon": (round(gps.lon, 6) if (gps and gps.lon is not None) else None),
                    "speed": (round(gps.speed, 1) if (gps and gps.speed is not None) else None),
                }
        if d.gx < 0:
            put("brake", -d.gx)
        else:
            put("accel", d.gx)
        if d.gy > 0:
            put("corner_left", d.gy)
        else:
            put("corner_right", -d.gy)
        put("combined", d.gxy)

    def _update_peak_tur(self, st: SessionState, d: DynamicsSample):
        """[1][2] セッション最高Traction Utilization Ratio(グリップ利用率)を更新する。
        タイヤロック/グリップ喪失イベントとして確定しなかった走行区間でも、
        「このコーナー/この制動でグリップを何%使ったか」を連続量として残す
        ことが、ユーザーの本来の目的(限界を使い切れているかの見極め)に
        直結するため、tire_lockのアクティブ状態とは独立に常時更新する。"""
        if d.tur <= st.peak_tur["value"]:
            return
        rel_t = (d.t - st.start_monotonic) if st.start_monotonic else d.t
        gps = st.last_gps
        st.peak_tur = {
            "value": round(d.tur, 3), "rel_t": round(rel_t, 2),
            "lat": (round(gps.lat, 6) if (gps and gps.lat is not None) else None),
            "lon": (round(gps.lon, 6) if (gps and gps.lon is not None) else None),
            "speed": (round(gps.speed, 1) if (gps and gps.speed is not None) else None),
        }

    @staticmethod
    def _trim_history(st: SessionState):
        """異常な長時間セッションでのメモリ際限なき増大を防ぐ安全弁 (通常は発動しない)。"""
        if len(st.events) > Config.MAX_STORED_EVENTS:
            st.events = st.events[-Config.MAX_STORED_EVENTS:]
        if len(st.periodic_stats) > Config.MAX_STORED_PERIODIC:
            st.periodic_stats = st.periodic_stats[-Config.MAX_STORED_PERIODIC:]

    def _resume_from_pause(self, st: SessionState):
        """センサ無応答による解析一時停止からの復帰処理。呼び出し元は st.lock を
        保持した状態でこれを呼ぶ(このメソッド自体はこのスレッド専有のオブジェクトしか
        触らないため、ロックを保持したままでも軽量で安全)。
        一時停止中は EventDetector.update()/波形バッファへの追加を行っていないため、
        「一時停止直前に進行中だったイベント」の状態が古いサンプルのまま残っている。
        これをそのまま再開すると、再開直後の新しいサンプルが古い波形に継ぎ足され、
        数秒単位のギャップを挟んだまま1つのイベントとして誤って確定してしまう恐れが
        あるため、進行中の検出状態・波形バッファを破棄してから解析を再開する。"""
        st.detector.reset()
        st.active_waveforms = {}
        st.pending_transitions = []
        # slice_seconds()は実時刻ベースで古いサンプルを自動的に除外するため厳密には
        # 不要だが、無意味に古いデータを保持し続けないための明示的なクリア。
        st.pretrigger.buf.clear()
        # タイヤロック検出器も同様に、ギャップを跨いだ古いサンプルがジャダー窓・
        # 傾き窓・速度クロスチェック窓に混入し誤検出につながらないよう破棄する。
        if st.dynamics is not None:
            st.dynamics.tire_lock.reset()

    def _finalize_event(self, etype: str, waveform: List[DynamicsSample], st: SessionState):
        """呼び出し元(_acquisition_loop)は st.lock を保持した状態でこれを呼ぶ。
        EventAnalyzer.analyze()/score_event() はサンプル数に応じて時間のかかる処理
        (波形全体の走査・統計計算)なので、ロックを保持したまま実行すると、同時に
        ポーリングしてくる /api/state (snapshot()) がロック解放待ちでブロックされ
        UIが一瞬固まる(レビュー指摘①)。そのため重い計算の間だけ一時的にロックを
        解放し、計算結果の反映(状態の書き換え)だけを再度ロックした状態で行う。"""
        now = waveform[-1].t
        hold_until = st.event_hold_until.get(etype, 0)
        if now < hold_until:
            return
        st.event_hold_until[etype] = now + Config.MIN_EVENT_HOLD_SEC + Config.EVENT_COOLDOWN_SEC
        last_gps = st.last_gps  # 参照を確保してからロックを離す(単純代入なので競合しても実害は無い)

        st.lock.release()
        try:
            ev = EventAnalyzer.analyze(etype, waveform, last_gps)
            ev.score = st.scoring.score_event(ev)
            ev.score_breakdown = st.scoring.score_event_breakdown(ev)
        finally:
            st.lock.acquire()

        st.events.append(ev)
        st.events_window.append(ev)
        st.last_event = ev
        st.behavior.update_fingerprint(ev, None)

    def _finalize_periodic(self, st: SessionState):
        """_finalize_event と同じ理由でロックを一時解放する。特に driver_db.save()
        はファイルI/Oであり、ロックを保持したまま行うのは避けるべき影響が大きい。"""
        events_window = st.events_window
        last_event = st.last_event

        st.lock.release()
        try:
            stat = st.periodic.flush(events_window)
            stat.score = st.scoring.score_periodic(stat)
            if last_event:
                st.behavior.update_fingerprint(last_event, stat)
            self.driver_db.save()
        finally:
            st.lock.acquire()

        st.periodic_stats.append(stat)
        st.events_window = []

    # --- 状態スナップショット (HTTP API向け) -----------------------------

    def snapshot(self) -> Dict[str, Any]:
        st = self.state
        with st.lock:
            periodic_pairs = [(p.score, p.confidence) for p in st.periodic_stats]
            event_pairs = [(e.score, e.confidence) for e in st.events]
            total = (st.scoring.total_score(periodic_pairs, event_pairs)
                     if (st.scoring and st.running) else None)
            all_conf = [c for _, c in periodic_pairs] + [c for _, c in event_pairs]
            reliability_pct = round(100.0 * sum(all_conf) / len(all_conf), 0) if all_conf else None
            d = st.last_dyn
            recent_roughness = st.periodic_stats[-1].road_roughness_pct if st.periodic_stats else 0.0
            return {
                "session_id": st.session_id,
                "calibrated": st.calibration.done,
                "sensor_status": ", ".join(f"{k}:{v}" for k, v in self.sensor.status.items()),
                "gx": d.gx if d else 0.0, "gy": d.gy if d else 0.0,
                "gxy": d.gxy if d else 0.0, "jerk": d.jxy if d else 0.0,
                "total_score": total,
                "reliability_pct": reliability_pct,
                "driving_stats": st.driving_stats(),
                "event_count": len(st.events),
                "last_event": asdict(st.last_event) if st.last_event else None,
                "road_disturbance": d.road_disturbance if d else False,
                "road_roughness_pct": recent_roughness,
                "max_g": st.max_g,
                # [1][2] 現在のグリップ利用率(TUR)とセッション最高値。CIRCUITモード以外
                # (TIRE_LOCK_MODES対象外)ではdynamics側が常に0.0を返す。
                "tur": d.tur if d else 0.0,
                "peak_tur": st.peak_tur,
                "grip_monitoring_active": st.mode in Config.TIRE_LOCK_MODES,
                "tire_lock": d.tire_lock if d else False,
                "tire_lock_type": d.tire_lock_type if d else None,
                "tire_lock_confidence": d.tire_lock_confidence if d else 1.0,
                "tire_lock_count": st.tire_lock_count,
                "last_tire_lock": st.last_tire_lock,
                "adaptive_applied": self.applied_corrections,
                "sensor_simulate": self.sensor.simulate,
                "sensor_sim_reason": self.sensor.sim_reason,
                "sensor_diag": self.sensor.diagnostics(),
                "sensor_paused": self.sensor.is_paused,
            }


# --- HTTP ハンドラ -------------------------------------------------------

def make_handler(control: MainControl):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html):
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # コンソールを静かに保つ

        def _handle_sse_stream(self):
            """Server-Sent Events配信。ポーリング(fetch連打)の代わりに、サーバー側から
            プッシュ配信することで通信回数を減らしバッテリー消費を抑える。
            ThreadingHTTPServerなので、この接続がブロックしていても他のリクエスト
            (停止操作など)には影響しない。セッションが終了(st.running=False)したら
            ループを抜けて接続を閉じる。"""
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
            try:
                while control.state.running:
                    try:
                        payload = json.dumps(control.snapshot(), ensure_ascii=False)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
                    time.sleep(Config.SSE_INTERVAL_SEC)
            except Exception:
                pass

        def _serve_report_file(self, name: str):
            """report/フォルダ内のtxtレポートをダウンロード提供する。
            パストラバーサル対策として basename のみを許可し、report/配下に
            実在するファイルであることを確認してから返す。"""
            safe_name = os.path.basename(name)
            path = os.path.join(Config.REPORT_DIR, safe_name)
            if (not safe_name.endswith(".txt")) or (not os.path.isfile(path)):
                self._send_json({"error": "not found"}, 404)
                return
            try:
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{quote(safe_name)}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self._send_html(HTML_PAGE)
            elif self.path == "/api/state":
                self._send_json(control.snapshot())
            elif self.path == "/api/stream":
                self._handle_sse_stream()
            elif self.path == "/api/drivers":
                self._send_json([{"driver_id": d.driver_id, "display_name": d.display_name}
                                  for d in control.driver_db.list()])
            elif self.path == "/api/vehicles":
                # 編集フォームのプリフィルに使うため全フィールドを返す。
                self._send_json([asdict(v) for v in control.vehicle_db.list()])
            elif self.path == "/api/limits":
                self._send_json({
                    "driver_count": len(control.driver_db.list()),
                    "driver_max": DriverDatabase.MAX_DRIVERS,
                    "vehicle_count": len(control.vehicle_db.list()),
                    "vehicle_max": VehicleDatabase.MAX_VEHICLES,
                })
            elif self.path == "/api/config":
                self._send_json({
                    "app_version": Config.APP_VERSION,
                    "app_author": Config.APP_AUTHOR,
                    "sensor_server_package": Config.SENSOR_SERVER_PACKAGE_NAME,
                    "sensor_server_fdroid_url": Config.SENSOR_SERVER_FDROID_URL,
                    "sensor_server_check_poll_sec": Config.SENSOR_SERVER_CHECK_POLL_SEC,
                    "params": [dict(p, value=getattr(Config, p["key"])) for p in Config.TUNABLE_PARAMS],
                })
            elif self.path.startswith("/api/learning"):
                q = parse_qs(urlparse(self.path).query)
                driver_id = (q.get("driver_id") or [None])[0]
                vehicle_id = (q.get("vehicle_id") or [None])[0]
                mode = (q.get("mode") or ["STREET"])[0]
                prof = (control.adaptive.get(driver_id, vehicle_id, mode)
                        if (driver_id and vehicle_id) else None)
                self._send_json({"profile": prof, "min_sessions": Config.ADAPTIVE_MIN_SESSIONS,
                                  "min_events": Config.ADAPTIVE_MIN_EVENTS})
            elif self.path.startswith("/report/"):
                self._serve_report_file(self.path[len("/report/"):])
            else:
                self._send_json({"error": "not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except Exception:
                payload = {}

            if self.path == "/api/start":
                control.start_session(payload.get("driver_id"), payload.get("vehicle_id"),
                                       payload.get("mode", "STREET"))
                self._send_json({"ok": True})
            elif self.path == "/api/config":
                applied = save_config_overrides(payload if isinstance(payload, dict) else {})
                self._send_json({"ok": True, "applied": applied})
            elif self.path == "/api/stop":
                report = control.stop_session()
                self._send_json(report)
            elif self.path == "/api/vehicles/add":
                try:
                    def _f(key, default=None):
                        v = payload.get(key)
                        return float(v) if v not in (None, "") else default

                    v = control.vehicle_db.add(
                        name=(payload.get("name") or "").strip() or f"Vehicle {len(control.vehicle_db.list()) + 1}",
                        maker=payload.get("maker", ""),
                        model=payload.get("model", ""),
                        mass_kg=_f("mass_kg", 1200.0),
                        wheelbase_mm=_f("wheelbase_mm", 2600.0),
                        tread_front_mm=_f("tread_front_mm", 1500.0),
                        tread_rear_mm=_f("tread_rear_mm", 1500.0),
                        cg_height_mm=_f("cg_height_mm", None),
                        drive_type=payload.get("drive_type", "FF"),
                    )
                    self._send_json({"ok": True, "vehicle_id": v.vehicle_id})
                except ValueError as e:
                    self._send_json({"ok": False, "error": str(e)}, 400)
            elif self.path == "/api/vehicles/update":
                try:
                    def _f(key, default=None):
                        v = payload.get(key)
                        return float(v) if v not in (None, "") else default

                    vid = payload.get("vehicle_id")
                    if not vid:
                        raise ValueError("vehicle_id が指定されていません")
                    # cg_height_mm は空欄=Noneクリア意図なので、キー存在時は明示的に反映する。
                    cg = _f("cg_height_mm", None) if "cg_height_mm" in payload else None
                    v = control.vehicle_db.update(
                        vid,
                        name=(payload.get("name") or "").strip() or None,
                        mass_kg=_f("mass_kg"),
                        wheelbase_mm=_f("wheelbase_mm"),
                        tread_front_mm=_f("tread_front_mm"),
                        tread_rear_mm=_f("tread_rear_mm"),
                        drive_type=payload.get("drive_type") or None,
                    )
                    # 重心高は「空欄でNoneに戻す」も許可するため個別に代入。
                    if "cg_height_mm" in payload:
                        v.cg_height_mm = cg
                        control.vehicle_db.save()
                    self._send_json({"ok": True, "vehicle_id": v.vehicle_id})
                except ValueError as e:
                    self._send_json({"ok": False, "error": str(e)}, 400)
            elif self.path == "/api/vehicles/delete":
                try:
                    control.vehicle_db.remove(payload.get("vehicle_id"))
                    self._send_json({"ok": True})
                except ValueError as e:
                    self._send_json({"ok": False, "error": str(e)}, 400)
            elif self.path == "/api/drivers/add":
                try:
                    d = control.driver_db.add(
                        display_name=(payload.get("display_name") or "").strip()
                        or f"Driver {len(control.driver_db.list()) + 1}")
                    self._send_json({"ok": True, "driver_id": d.driver_id})
                except ValueError as e:
                    self._send_json({"ok": False, "error": str(e)}, 400)
            elif self.path == "/api/drivers/update":
                try:
                    did = payload.get("driver_id")
                    if not did:
                        raise ValueError("driver_id が指定されていません")
                    name = (payload.get("display_name") or "").strip()
                    if not name:
                        raise ValueError("ドライバー名を入力してください")
                    d = control.driver_db.update(did, display_name=name)
                    self._send_json({"ok": True, "driver_id": d.driver_id})
                except ValueError as e:
                    self._send_json({"ok": False, "error": str(e)}, 400)
            elif self.path == "/api/drivers/delete":
                try:
                    control.driver_db.remove(payload.get("driver_id"))
                    self._send_json({"ok": True})
                except ValueError as e:
                    self._send_json({"ok": False, "error": str(e)}, 400)
            else:
                self._send_json({"error": "not found"}, 404)

    return Handler


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _auto_open_browser(url: str, delay: float = 0.6):
    """サーバー起動後、少し待ってから既定ブラウザでHTMLを自動的に開く。
    (Pydroid3上のAndroidでも webbrowser 経由でブラウザ起動Intentが呼ばれる。
     失敗しても致命的ではないため例外は握りつぶし、URLを表示するのみに留める。)"""
    def _open():
        time.sleep(delay)
        try:
            opened = webbrowser.open(url, new=1)
            if not opened:
                print(f" (自動起動に失敗しました。手動で {url} を開いてください)")
        except Exception as e:
            print(f" (ブラウザ自動起動エラー: {e} — 手動で {url} を開いてください)")
    threading.Thread(target=_open, daemon=True).start()


def safe_open_browser(url: str) -> bool:
    """[Version 1.5.1 追加] main.py(Kivyランチャー)/service.py 双方から呼べる、
    即時実行版のブラウザ起動ヘルパー。_auto_open_browser()と違いスレッドを
    自前で起こさない(呼び出し側で既にKivyのClock等から呼ばれるため)。
    失敗しても例外を外に伝播させない。"""
    try:
        opened = webbrowser.open(url, new=1)
        return bool(opened)
    except Exception as e:
        print(f" (ブラウザ起動エラー: {e} — 手動で {url} を開いてください)")
        return False


def start_app_server(bind_host: str = "0.0.0.0") -> Tuple["MainControl", ThreadingHTTPServer, str]:
    """[Version 1.5.1 追加] APK(main.py/service.py)から呼び出す、非ブロッキング版の
    起動関数。main()と異なりコンソール出力やserve_forever()のブロッキング待機を
    行わず、HTTPサーバーをバックグラウンドスレッドで起動してすぐに戻る。
    戻り値: (MainControl, ThreadingHTTPServer, アクセスURL文字列)
    アプリのロジック(センサー取得・解析・採点等)はMainControl側で従来通り
    別スレッドで動作するため、ここでは変更していない。"""
    control = MainControl()
    server = ThreadingHTTPServer((bind_host, Config.HTTP_PORT), make_handler(control))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{Config.HTTP_PORT}/"
    return control, server, url


def main():
    control = MainControl()
    server = ThreadingHTTPServer(("0.0.0.0", Config.HTTP_PORT), make_handler(control))
    ip = get_local_ip()
    local_url = f"http://127.0.0.1:{Config.HTTP_PORT}/"
    print("=" * 60)
    print(f" Driving Dynamics Analyzer (DDA) - Version {Config.APP_VERSION}")
    print("=" * 60)
    print(f" センサモード: {'シミュレーション' if control.sensor.simulate else '実センサ'}")
    if control.sensor.simulate:
        print(" " + "!" * 56)
        print(" ⚠ シミュレーションモードで動作しています (実センサ未使用)")
        print(f" 理由: {control.sensor.sim_reason}")
        print(" このモードでは実際のセンサ値の代わりに、検証用の疑似走行")
        print(" データ (加速→ブレーキ→右旋回→左旋回を12秒周期で繰り返す)")
        print(" を使用します。端末を静止させていてもG-Gダイアグラムの")
        print(" ボールが動くのは、このデモデータによるものです。")
        print(" ヒント: 実センサ値を使うにはスマホに「Sensor Server」アプリ")
        print(" (F-Droid配布, github.com/UmerCodez/SensorServer) を導入・起動し、")
        print(" 画面に表示されるIP/ポートを このファイル冒頭の")
        print(" Config.SENSOR_SERVER_HOST/PORT に設定してください。")
        print(" " + "!" * 56)
    print(f" ブラウザでアクセス: http://{ip}:{Config.HTTP_PORT}/")
    print(f" (同一端末上のブラウザなら {local_url} )")
    print(f" 走行ログ保存先: {Config.LOG_DIR}")
    print(f"   (プログラムフォルダ配下に自動作成/保持{Config.LOG_RETENTION_DAYS}日で自動削除)")
    print(" 起動後、ブラウザを自動的に開きます...")
    print(" Ctrl+C で終了")
    print("=" * 60)

    _auto_open_browser(local_url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了します。")
        server.shutdown()


if __name__ == "__main__":
    main()
