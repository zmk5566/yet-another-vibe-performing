"""
测试音频输出 - 验证 DawDreamer + PyAudio 链路
"""

import sys
sys.path.insert(0, '.')

import dawdreamer as daw
import pyaudio
import numpy as np
import time

print("="*60)
print("  Audio Output Test")
print("="*60)

# 创建 DawDreamer engine
sample_rate = 48000
buffer_size = 256
engine = daw.RenderEngine(sample_rate, buffer_size)

# 创建简单的正弦波测试音
processor = engine.make_faust_processor("test")
processor.set_dsp_string("""
import("stdfaust.lib");
freq = 440;
process = os.osc(freq) * 0.3;
""")

engine.load_graph([(processor, [])])

print("\n✓ DawDreamer engine created")

# 测试渲染
engine.render(0.1)
audio = engine.get_audio()
print(f"✓ Rendered audio shape: {audio.shape}")
print(f"✓ Audio range: [{audio.min():.3f}, {audio.max():.3f}]")

# 创建 PyAudio 实例
p = pyaudio.PyAudio()

print(f"\n✓ PyAudio initialized")
print(f"  Available devices: {p.get_device_count()}")

# 获取默认输出设备
default_output = p.get_default_output_device_info()
print(f"  Default output: {default_output['name']}")

# 创建音频回调
callback_count = 0

def audio_callback(in_data, frame_count, time_info, status):
    global callback_count
    callback_count += 1

    # 渲染音频
    engine.render(frame_count / sample_rate)
    audio = engine.get_audio()

    # 转换为立体声
    if len(audio.shape) == 1:
        stereo = np.stack([audio, audio], axis=1)
    else:
        stereo = np.stack([audio[0], audio[0]], axis=1)

    return (stereo.astype(np.float32).tobytes(), pyaudio.paContinue)

# 打开音频流
stream = p.open(
    format=pyaudio.paFloat32,
    channels=2,
    rate=sample_rate,
    output=True,
    frames_per_buffer=buffer_size,
    stream_callback=audio_callback
)

print("\n✓ Audio stream opened")
print("\n播放 440Hz 正弦波 3 秒...")
print("如果听到声音，说明音频输出正常工作！\n")

stream.start_stream()
time.sleep(3)
stream.stop_stream()
stream.close()
p.terminate()

print(f"\n✓ 完成 ({callback_count} callbacks)")
print("\n如果你听到了声音，音频系统工作正常。")
print("如果没有声音，可能是：")
print("  1. 音量设置太低")
print("  2. 选择了错误的音频设备")
print("  3. PyAudio 配置问题")
