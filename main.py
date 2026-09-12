#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Driving Dynamics Analyzer (DDA) - Android ランチャー (main.py)
================================================================
このファイルは dda_core.py (元の DrivingAnalyzer_v1.5.py) 本体には一切手を
加えず、Android実機でAPKとして動作させるための「入口(ランチャー画面)」だけを
提供する薄いKivyアプリです。

役割:
  1. 画面上のボタン操作で、buildozer.spec の `services=` に登録した
     バックグラウンドサービス (service.py, foreground) を起動する。
     このサービス内で dda_core.py の HTTP サーバー本体が動作し続けるため、
     ユーザーがブラウザ操作でこの画面をバックグラウンドに回しても、
     Androidのフォアグラウンドサービスとして走行ログの収集が継続する。
  2. サービスが起動しHTTPサーバーが応答可能になったのを確認したら、
     端末の既定ブラウザ(Chrome等)で http://127.0.0.1:8080/ を開く。
     実際の操作画面(ドライバー/車両選択、走行中表示、レポート等)は
     すべて dda_core.py が提供する既存のHTML/JS UIがそのまま使われる。
  3. Android実機以外(Windows/Linux上でのローカル動作確認)でも
     このファイルをそのまま実行でき、その場合はサービスを使わず
     このプロセス内で直接HTTPサーバーを起動する。

注意:
  センサー実測値の取得には、別途スマートフォンにインストールした
  「Sensor Server」アプリ (F-Droid配布, github.com/UmerCodez/SensorServer)
  側で加速度/ジャイロ/GPSの配信を開始しておく必要があります
  (このAPK自体はセンサーへ直接アクセスしません。dda_core.py内の
  SensorServerSource がWebSocket経由でSensor Serverアプリへ接続します)。
"""
import os
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

import dda_core

APP_URL = f"http://127.0.0.1:{dda_core.Config.HTTP_PORT}/"


def _is_android() -> bool:
    try:
        import android  # noqa: F401
        return True
    except Exception:
        return "ANDROID_ARGUMENT" in os.environ


class DDALauncherApp(App):
    title = "Driving Dynamics Analyzer"

    def build(self):
        self._service = None          # Android側 AndroidService オブジェクト
        self._control = None          # デスクトップ実行時の MainControl (テスト用)
        self._server = None
        self._server_started = False

        root = BoxLayout(orientation="vertical", padding=24, spacing=14)

        self.title_label = Label(
            text="Driving Dynamics Analyzer\n(Version 1.5)",
            font_size="20sp", halign="center", valign="middle", size_hint=(1, 0.25),
        )
        self.title_label.bind(size=self.title_label.setter("text_size"))

        self.status_label = Label(
            text="「走行を開始」を押してください。",
            font_size="15sp", halign="center", valign="middle", size_hint=(1, 0.35),
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))

        self.start_btn = Button(text="走行を開始 (サーバー起動)", size_hint=(1, 0.15),
                                 on_release=self.on_start)
        self.open_btn = Button(text="ブラウザを開く", size_hint=(1, 0.15),
                                on_release=self.on_open_browser)
        self.stop_btn = Button(text="サーバーを停止して終了", size_hint=(1, 0.15),
                                on_release=self.on_stop)

        root.add_widget(self.title_label)
        root.add_widget(self.status_label)
        root.add_widget(self.start_btn)
        root.add_widget(self.open_btn)
        root.add_widget(self.stop_btn)
        return root

    # --- サーバー/サービス起動 -------------------------------------------------
    def on_start(self, *args):
        self.status_label.text = "起動中です。しばらくお待ちください..."
        self.start_btn.disabled = True
        threading.Thread(target=self._start_backend, daemon=True).start()

    def _start_backend(self):
        try:
            if _is_android():
                self._start_android_service()
            else:
                # Windows/Linux等でのローカル動作確認用: このプロセス内で直接起動する。
                self._control, self._server, _ = dda_core.start_app_server()
            self._server_started = True
            self._wait_for_server_ready()
            Clock.schedule_once(lambda dt: self._on_started())
        except Exception as e:
            Clock.schedule_once(lambda dt, err=e: self._on_error(err))

    def _start_android_service(self):
        """buildozer.spec の services= に登録した service.py (foreground) を起動する。
        AndroidServiceはpython-for-androidが提供するヘルパー(android.AndroidService)で、
        通知バー常駐のフォアグラウンドサービスとして別プロセスで実行される。"""
        from android import AndroidService  # python-for-android 同梱
        service = AndroidService("Driving Dynamics Analyzer", "走行データを記録しています")
        service.start("DDA server running")
        self._service = service

    def _wait_for_server_ready(self, timeout_sec: float = 12.0):
        """service.py側でHTTPサーバーがbindされ応答可能になるまで、
        軽量なTCP接続確認でポーリングする(重いHTTPリクエストは投げない)。"""
        import socket as _socket
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                with _socket.create_connection(("127.0.0.1", dda_core.Config.HTTP_PORT), timeout=1.0):
                    return True
            except OSError:
                time.sleep(0.5)
        return False

    def _on_started(self):
        self.status_label.text = (
            f"サーバー起動完了。\n{APP_URL}\n"
            "ブラウザが自動的に開かない場合は\n下のボタンを押してください。"
        )
        self.open_btn.disabled = False
        dda_core.safe_open_browser(APP_URL)

    def _on_error(self, err):
        self.start_btn.disabled = False
        self.status_label.text = f"起動エラー:\n{err}"

    # --- ブラウザ操作 -----------------------------------------------------------
    def on_open_browser(self, *args):
        dda_core.safe_open_browser(APP_URL)

    # --- 終了処理 ---------------------------------------------------------------
    def on_stop(self, *args):
        try:
            if self._service is not None:
                self._service.stop()
        except Exception:
            pass
        try:
            if self._server is not None:
                self._server.shutdown()
        except Exception:
            pass
        self.stop()


if __name__ == "__main__":
    DDALauncherApp().run()
