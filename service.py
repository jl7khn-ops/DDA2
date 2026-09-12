#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Driving Dynamics Analyzer (DDA) - バックグラウンドサービス本体 (service.py)
================================================================================
buildozer.spec の

    services = DDAServer:service.py:foreground

によりAndroidのフォアグラウンドサービスとして起動されるエントリポイント。
別プロセスとして動作するため、メイン画面(main.py)がバックグラウンドに
回っても(ブラウザ操作中/画面消灯中など)、走行中のセンサー取得・解析・
イベント検出・スコアリングを継続できる。

このファイル自身にDDAの解析ロジックは一切含まれておらず、既存の
dda_core.py (元のDrivingAnalyzer_v1.5.py) が提供する start_app_server() を
呼び出して HTTP サーバー(+内部の取得/解析スレッド群)を起動し、
プロセスを維持するだけの薄いラッパーである。
"""
import time

import dda_core


def _acquire_wakelock():
    """画面消灯・Doze中もCPUが止まらないよう、可能であればパーシャル
    ウェイクロックを取得する(取得できなくても致命的ではないため握りつぶす)。
    走行中に解析ループが間引かれると検出精度が落ちるため、可能な限り
    CPUを維持したい。"""
    try:
        from jnius import autoclass
        PythonService = autoclass("org.kivy.android.PythonService")
        Context = autoclass("android.content.Context")
        service = PythonService.mService
        power_manager = service.getSystemService(Context.POWER_SERVICE)
        PowerManager = autoclass("android.os.PowerManager")
        wake_lock = power_manager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK, "DDA::AcquisitionWakeLock")
        wake_lock.acquire()
        return wake_lock
    except Exception as e:
        print(f"[DDA service] WakeLock取得に失敗しました(継続動作します): {e}")
        return None


def main():
    wake_lock = _acquire_wakelock()
    control, server, url = dda_core.start_app_server()
    print(f"[DDA service] HTTPサーバーを起動しました: {url}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            if wake_lock is not None:
                wake_lock.release()
        except Exception:
            pass


if __name__ == "__main__":
    main()
