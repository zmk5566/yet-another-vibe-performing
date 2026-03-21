"""
全局 transport 和时钟

维护全局 BPM 和 beat 计数，广播到所有 instrument
"""

import time
import threading
from typing import Optional


class Transport:
    """
    全局 transport 和时钟

    职责：
    1. 维护全局 BPM 和 beat 计数
    2. 处理 play/stop/tempo 变化
    3. 提供当前 beat 查询接口
    """

    def __init__(self, bpm: float = 120.0):
        """
        初始化 transport

        Args:
            bpm: 初始 BPM
        """
        self.bpm = bpm
        self._is_playing = False
        self.current_beat = 0.0
        self.start_time: Optional[float] = None

        # 线程锁
        self.lock = threading.Lock()

        print(f"[Transport] Initialized (BPM: {bpm})")

    def start(self):
        """开始播放"""
        with self.lock:
            if self._is_playing:
                return

            self._is_playing = True
            self.start_time = time.time()

        print("[Transport] Started")

    def stop(self):
        """停止播放"""
        with self.lock:
            if not self._is_playing:
                return

            # 保存当前 beat
            if self.start_time is not None:
                elapsed = time.time() - self.start_time
                beats_per_second = self.bpm / 60.0
                self.current_beat += elapsed * beats_per_second

            self._is_playing = False
            self.start_time = None

        print(f"[Transport] Stopped (beat: {self.current_beat:.2f})")

    def set_bpm(self, bpm: float):
        """
        改变 BPM

        Args:
            bpm: 新的 BPM 值
        """
        with self.lock:
            # 如果正在播放，先更新当前 beat
            if self._is_playing and self.start_time is not None:
                elapsed = time.time() - self.start_time
                beats_per_second = self.bpm / 60.0
                self.current_beat += elapsed * beats_per_second
                self.start_time = time.time()

            self.bpm = bpm

        print(f"[Transport] BPM changed to {bpm}")

    def get_current_beat(self) -> float:
        """
        获取当前 beat（线程安全）

        Returns:
            当前 beat 值
        """
        with self.lock:
            if not self._is_playing or self.start_time is None:
                return self.current_beat

            elapsed = time.time() - self.start_time
            beats_per_second = self.bpm / 60.0
            return self.current_beat + (elapsed * beats_per_second)

    def is_playing(self) -> bool:
        """
        检查是否正在播放

        Returns:
            是否正在播放
        """
        with self.lock:
            return self._is_playing

    def reset(self):
        """重置 beat 计数"""
        with self.lock:
            self.current_beat = 0.0
            if self._is_playing:
                self.start_time = time.time()

        print("[Transport] Reset to beat 0")
