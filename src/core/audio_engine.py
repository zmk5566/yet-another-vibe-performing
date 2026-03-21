"""
实时音频引擎 - 使用 DawDreamer + PyAudio

集中式音频混合架构：
- 单一 PyAudio 输出流
- 管理所有 instrument 的 DawDreamer RenderEngine
- 在 callback 中实时混合所有 instrument 的输出
"""

import threading
import numpy as np
import pyaudio
import dawdreamer as daw
from typing import Dict, Optional


class AudioEngine:
    """
    集中式音频引擎

    职责：
    1. 管理单一 PyAudio 输出流
    2. 维护所有 instrument 的 DawDreamer RenderEngine
    3. 在 PyAudio callback 中实时混合所有 instrument 的输出
    4. 提供线程安全的 instrument 注册/注销接口
    """

    def __init__(self, sample_rate: int = 48000, buffer_size: int = 256):
        """
        初始化音频引擎

        Args:
            sample_rate: 采样率（Hz）
            buffer_size: 缓冲区大小（samples）
        """
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.render_duration = buffer_size / sample_rate

        # PyAudio 实例和流
        self.pyaudio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None

        # 所有 instrument 的 render engines（线程安全字典）
        self.instruments: Dict[str, daw.RenderEngine] = {}
        self.instruments_lock = threading.Lock()

        # Transport 引用（由外部注入）
        self.transport = None

        # 性能统计
        self.callback_count = 0
        self.error_count = 0

    def register_instrument(self, instrument_id: str, render_engine: daw.RenderEngine):
        """
        注册一个 instrument 的 render engine（线程安全）

        Args:
            instrument_id: instrument 唯一标识
            render_engine: DawDreamer RenderEngine 实例
        """
        with self.instruments_lock:
            self.instruments[instrument_id] = render_engine
            print(f"[AudioEngine] Registered instrument: {instrument_id}")

    def unregister_instrument(self, instrument_id: str):
        """
        注销一个 instrument

        Args:
            instrument_id: instrument 唯一标识
        """
        with self.instruments_lock:
            if instrument_id in self.instruments:
                del self.instruments[instrument_id]
                print(f"[AudioEngine] Unregistered instrument: {instrument_id}")

    def audio_callback(self, in_data, frame_count, time_info, status):
        """
        PyAudio 实时回调函数

        关键性能考虑：
        1. 必须在 ~5ms 内完成（256 samples @ 48kHz）
        2. 不能有任何阻塞操作
        3. 异常处理必须优雅，不能中断音频流

        Args:
            in_data: 输入音频数据（未使用）
            frame_count: 请求的帧数
            time_info: 时间信息
            status: 状态标志

        Returns:
            (audio_data, continue_flag): 音频数据和继续标志
        """
        self.callback_count += 1

        try:
            # 检查 transport 状态
            is_playing = self.transport.is_playing() if self.transport else True

            if not is_playing:
                # 静音输出
                silence = np.zeros((frame_count, 2), dtype=np.float32)
                return (silence.tobytes(), pyaudio.paContinue)

            # 混合所有 instrument 的输出
            mixed_audio = np.zeros((frame_count, 2), dtype=np.float32)

            with self.instruments_lock:
                for instrument_id, engine in self.instruments.items():
                    try:
                        # 渲染这个 instrument 的音频
                        engine.render(self.render_duration)
                        audio = engine.get_audio()  # shape: (channels, frame_count)

                        # 转置并累加到混合缓冲区
                        if len(audio.shape) == 1:
                            # 单声道：复制到两个声道
                            mixed_audio[:, 0] += audio
                            mixed_audio[:, 1] += audio
                        else:
                            # 立体声或多声道
                            if audio.shape[0] == 1:
                                # 单声道输出
                                mixed_audio[:, 0] += audio[0]
                                mixed_audio[:, 1] += audio[0]
                            else:
                                # 立体声输出
                                mixed_audio[:, 0] += audio[0]
                                mixed_audio[:, 1] += audio[1] if audio.shape[0] > 1 else audio[0]

                    except Exception as e:
                        # 单个 instrument 出错不应影响整体
                        self.error_count += 1
                        if self.error_count % 100 == 1:  # 避免日志刷屏
                            print(f"[AudioEngine] Error rendering {instrument_id}: {e}")
                        continue

            # 软限幅防止削波
            mixed_audio = np.clip(mixed_audio, -1.0, 1.0)

            return (mixed_audio.astype(np.float32).tobytes(), pyaudio.paContinue)

        except Exception as e:
            self.error_count += 1
            print(f"[AudioEngine] Critical error in audio callback: {e}")
            # 返回静音而不是崩溃
            silence = np.zeros((frame_count, 2), dtype=np.float32)
            return (silence.tobytes(), pyaudio.paContinue)

    def start(self):
        """启动音频流"""
        if self.stream is not None:
            print("[AudioEngine] Audio stream already running")
            return

        print(f"[AudioEngine] Starting audio stream ({self.sample_rate}Hz, {self.buffer_size} samples)")

        self.stream = self.pyaudio.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.buffer_size,
            stream_callback=self.audio_callback
        )
        self.stream.start_stream()
        print("[AudioEngine] Audio stream started")

    def stop(self):
        """停止音频流"""
        if self.stream:
            print("[AudioEngine] Stopping audio stream")
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        self.pyaudio.terminate()
        print(f"[AudioEngine] Audio stream stopped (callbacks: {self.callback_count}, errors: {self.error_count})")

    def set_transport(self, transport):
        """
        设置 transport 引用

        Args:
            transport: Transport 实例
        """
        self.transport = transport
