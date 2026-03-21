"""
HANMAI-LIVE 主程序入口

Phase 1: 单个 kick instrument 测试
"""

import os
import sys
import threading
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../..'))

from src.core.audio_engine import AudioEngine
from src.core.transport import Transport
from src.instrument.instrument_pane import InstrumentPane


def main():
    """Phase 1: 单个 kick instrument 测试"""
    print("="*60)
    print("  HANMAI-LIVE - Phase 1: Single Instrument Test")
    print("="*60)
    print()

    # 创建 AudioEngine
    print("[Main] Creating AudioEngine...")
    audio_engine = AudioEngine(sample_rate=48000, buffer_size=256)

    # 创建 Transport
    print("[Main] Creating Transport...")
    transport = Transport(bpm=120.0)
    audio_engine.set_transport(transport)

    # 启动 transport
    transport.start()

    # 创建 kick instrument pane
    print("[Main] Creating kick instrument...")
    kick_pane = InstrumentPane(
        instrument_id="kick",
        config_path="config/instruments/kick.yaml",
        audio_engine=audio_engine,
        transport=transport
    )

    # 启动音频引擎
    print("[Main] Starting audio engine...")
    audio_engine.start()

    print()
    print("="*60)
    print("  System running!")
    print("  Press Space to trigger kick")
    print("  Press q/a to adjust decay")
    print("  Press w/s to adjust drive")
    print("  Press 'q' to quit")
    print("="*60)
    print()

    # 运行 instrument pane（主线程）
    try:
        kick_pane.run()
    except KeyboardInterrupt:
        print("\n[Main] Interrupted")
    finally:
        # 清理
        print("[Main] Shutting down...")
        transport.stop()
        audio_engine.stop()
        print("[Main] Goodbye!")


if __name__ == "__main__":
    main()
