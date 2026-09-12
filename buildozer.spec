[app]

# --- 基本情報 -----------------------------------------------------------
title = Driving Dynamics Analyzer
package.name = drivinganalyzer
package.domain = org.jl7khn
version = 1.5

# --- ソース ---------------------------------------------------------------
source.dir = .
source.include_exts = py,json,txt,md
# ビルド成果物や不要ファイルを取り込まない(ビルドエラー/APK肥大化防止)
source.exclude_dirs = .git,.github,bin,.buildozer,__pycache__,dda_data,report

# --- 画面 -------------------------------------------------------------------
orientation = portrait
fullscreen = 0

# --- Python requirements ---------------------------------------------------
# 標準ライブラリのみで動作するdda_core.pyに対し、Android用の最小限のUI殻として
# Kivyのみを追加する(この構成が最も実績が多く、buildozer/python-for-androidの
# ビルドで問題が起きにくい)。pyjniusはAndroid通知・WakeLock・アプリ起動連携で
# 明示的に使用しているため明記する(kivyのAndroidビルドでは内部的にも必須)。
requirements = python3,kivy,pyjnius

# --- アイコン/スプラッシュ (未設定。必要であれば data/ 以下に配置し指定する) ---
#icon.filename = %(source.dir)s/data/icon.png
#presplash.filename = %(source.dir)s/data/presplash.png

# --- バックグラウンドサービス ------------------------------------------------
# service.py をフォアグラウンドサービスとして登録する。走行中にブラウザへ
# 切り替えて画面をバックグラウンドにしても、HTTPサーバー/センサー取得・解析
# ループは通知バー常駐のサービスプロセス内で継続動作する。
services = DDAServer:service.py:foreground

# --- Android権限 ------------------------------------------------------------
# INTERNET             : HTTPサーバー / Sensor ServerアプリへのWebSocket接続
# ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE : 端末IP取得(get_local_ip)の補助
# FOREGROUND_SERVICE   : services= で登録したフォアグラウンドサービスの実行に必須
# WAKE_LOCK            : 画面消灯中も解析ループを継続させるためのパーシャルロック
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,FOREGROUND_SERVICE,WAKE_LOCK

# --- API/アーキテクチャ ------------------------------------------------------
# 個人利用のAPK(Play Store配信を想定しない)であり、最新APIレベル必須化に伴う
# フォアグラウンドサービス種別宣言(android.foreground_service_type)等の追加対応を
# 避け、実績豊富な組み合わせでビルドエラーを抑える。
android.api = 33
android.minapi = 21
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True

# NDK/p4aのバージョンはbuildozer公式Dockerイメージが検証済みの既定値に委ねる
# (固定するとイメージ内のバージョンと不一致になりビルド失敗の原因になりやすいため
#  意図的に未指定のままにしている)。
#android.ndk = 25b
#p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
