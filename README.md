# Driving Dynamics Analyzer (DDA) — Android APK ビルド一式

DrivingAnalyzer_v1.5.py (作成者: JL7KHN) を、GitHub Actions 上で
`buildozer` + `python-for-android` を用いてAndroid APKにビルドするための
プロジェクト一式です。

## フォルダ構成

```
DrivingAnalyzer_APK/
├── .github/
│   └── workflows/
│       └── build-apk.yml     # GitHub Actions ワークフロー(pushまたは手動実行でAPKをビルド)
├── main.py                    # Kivy製の起動ランチャー(HTTPサーバー起動 + ブラウザ自動起動)
├── service.py                 # フォアグラウンドサービス本体(バックグラウンドでも継続動作)
├── dda_core.py                # 元の DrivingAnalyzer_v1.5.py 本体(解析ロジックは無改変)
├── buildozer.spec             # ビルド設定
└── README.md                  # このファイル
```

## アーキテクチャ (なぜこの3ファイル構成か)

DDAは元々「標準ライブラリのみで動くHTTPサーバー + スマホのブラウザで操作する
HTML/JS UI」という構成のアプリです。これはAndroidアプリ化においても実は
相性が良く、以下のように役割分担しています。

| ファイル | 役割 | 動作プロセス |
|---|---|---|
| `dda_core.py` | センサー取得・解析・スコアリング・HTTPサーバー本体(**無改変**) | - |
| `service.py` | `dda_core.py` の `start_app_server()` を呼び出し、Androidの**フォアグラウンドサービス**として常駐 | 別プロセス(通知バー常駐) |
| `main.py` | 起動画面(Kivy)。サービスを起動し、ブラウザで `http://127.0.0.1:8080/` を自動的に開く | メインActivity |

**フォアグラウンドサービスにしている理由**: 走行中にブラウザ側の画面(実際の
操作UI)を前面にすると、`main.py` のActivityはバックグラウンドになります。
これが通常のActivityだけの構成だと、AndroidのバックグラウンドプロセスKill/
Doze制御によりセンサー取得ループが停止しうるため、`service.py` を
`foreground` サービスとして独立させ、走行中は継続動作するようにしています。

`dda_core.py` に加えた変更は次の3点のみで、**スコアリング/センサー融合/
イベント検出などの解析ロジックには一切手を加えていません**。

1. データ保存先 (`Config.APP_DIR`) を、Android実機では書き込み可能な
   アプリ専用領域に自動判定するようにした(Windows/Raspberry Pi/Pydroid3では
   従来通り `__file__` の場所を使用)。
2. 「Sensor Serverアプリを開く」処理を、Android実機では `pyjnius` 経由の
   確実なアプリ起動 (`getLaunchIntentForPackage`) に変更した
   (旧来のChrome専用Intent URIはネイティブアプリのプロセスからでは機能しないため)。
3. HTTPサーバーを非ブロッキングでバックグラウンド起動する
   `start_app_server()` と、`safe_open_browser()` を追加した
   (`main()` 自体は元のまま残してあり、Windows/Pydroid3では従来通り
   `python dda_core.py` で単体実行できます)。

## ビルド方法 (GitHub Actions)

1. このフォルダの中身をそのままGitHubリポジトリの直下にpushしてください
   (`buildozer.spec` がリポジトリのルートに来るようにする)。
2. GitHubの「Actions」タブ → 「Build Android APK」→「Run workflow」で
   手動実行するか、`main`/`master` ブランチへのpushで自動実行されます。
3. ビルド完了後、ワークフロー実行結果の「Artifacts」から
   `DrivingAnalyzer-debug-apk` をダウンロードしてください
   (中に `.apk` ファイルが入っています)。
4. スマートフォンに転送し、「提供元不明のアプリ」を許可してインストールします。

初回ビルドはAndroid SDK/NDKのダウンロードが走るため、**20〜40分程度**
かかることがあります(2回目以降はDockerイメージ内キャッシュにより高速化)。

## 使い方 (インストール後)

1. アプリを起動 → 「走行を開始 (サーバー起動)」をタップ。
2. 数秒後、自動的にブラウザが開き、DDAの操作画面(ドライバー/車両/モード選択)
   が表示されます。自動で開かない場合は「ブラウザを開く」をタップしてください。
3. センサー実測値を使うには、別途スマートフォンに
   [Sensor Server](https://f-droid.org/packages/github.umer0586.sensorserver/)
   アプリ (F-Droid配布) をインストールし、加速度/ジャイロ/GPSの配信を
   開始しておいてください。未起動の場合はDDA側がシミュレーションモードで
   動作し、その旨が画面上に警告表示されます。
4. 走行終了後は「走行終了」でレポートを確認し、アプリ側の
   「サーバーを停止して終了」で終了できます。

## ビルドエラーが出た場合のチェックポイント

buildozer/python-for-androidは環境差異で失敗しやすいツールのため、
エラーが出た場合はまず以下を確認してください。

| 症状 | 主な原因 / 対処 |
|---|---|
| `Command failed: ... gradlew` 系のエラー | 一時的なパッケージダウンロード失敗が多い。ワークフローの再実行(Re-run jobs)で解決することが多い |
| `Aidl not found` / SDKコンポーネント不足 | `buildozer android clean` 相当のキャッシュクリアが必要。Actionsの場合はキャッシュを使っていなければ通常発生しない |
| Cython関連のビルド失敗 | `buildozer.spec` の `requirements` に `cython==<公式Dockerイメージ対応バージョン>` を明示的に追加して固定する |
| `android.permissions` のスペルミスで権限が反映されない | カンマ区切り・スペース無しで記述されているか確認 (`buildozer.spec` 参照) |
| フォアグラウンドサービスがAndroid 12+で起動直後に落ちる | `android.api` を33のまま据え置く(34以降はforeground service type宣言が必須になり追加設定が必要) |
| APKインストール後、即クラッシュ (`main.py`のimportエラー) | `dda_core.py`/`service.py` がリポジトリ直下(`buildozer.spec`と同階層)に置かれているか確認 |

## 既知の制約

- このAPKは**HTTPサーバーとして動作しブラウザ経由で操作する**設計です
  (元のDDAの設計をそのまま踏襲)。ネイティブなAndroid UIではありません。
- センサー実測値の取得は本APK単体では行わず、別アプリ「Sensor Server」
  経由です(元の仕様通り)。
- `android.api = 33` としているため、Google Play Storeへ配信する場合は
  最新のターゲットAPI要件に合わせて追加対応(フォアグラウンドサービス種別の
  宣言等)が必要です。個人利用(サイドロード)であれば現状のままで問題ありません。
