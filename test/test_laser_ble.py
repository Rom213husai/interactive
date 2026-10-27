import asyncio
import sys
import threading
import unittest
from unittest.mock import AsyncMock, patch

from laser import ble


class LaserBLETests(unittest.TestCase):
    def test_windows_bluetooth_runs_on_another_thread(self):
        caller = threading.get_ident()

        async def job():
            return threading.get_ident()

        with patch.object(ble.sys, "platform", "win32"):
            self.assertNotEqual(ble._run(job), caller)

    def test_both_bluetooth_operations_connect_and_close_on_worker(self):
        caller = threading.get_ident()
        threads = []

        async def connect():
            threads.append(threading.get_ident())
            return laser

        laser = AsyncMock()
        with patch.object(ble.sys, "platform", "win32"), patch.object(
            ble.Laser, "connect", side_effect=connect
        ), patch.object(ble, "log"):
            ble.dmx_mode()
            ble.beam_off()
        self.assertTrue(all(thread != caller for thread in threads))
        self.assertEqual(len(threads), 2)
        laser.dmx_mode.assert_awaited_once()
        self.assertEqual(laser.close.await_count, 2)

    @unittest.skipUnless(sys.platform == "win32", "Windows COM regression")
    def test_bluetooth_thread_check_passes_after_audio_initialization(self):
        import pygame
        from bleak.backends.winrt.util import assert_mta

        # ダミー出力で実際に mixer を初期化し、音や Bluetooth 通信は発生させない。
        with patch.dict("os.environ", {"SDL_AUDIODRIVER": "dummy"}):
            pygame.mixer.init()
        try:
            ble._run(assert_mta)
        finally:
            pygame.mixer.quit()


if __name__ == "__main__":
    unittest.main()
