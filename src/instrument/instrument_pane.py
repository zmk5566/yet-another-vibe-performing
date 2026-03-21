"""
Instrument pane 主程序

每个 instrument 在独立线程中运行，管理自己的 DSP 和 UI
"""

import os
import sys
import time
import threading
import yaml
import dawdreamer as daw
import numpy as np
import termios
import tty
import select
from typing import Dict, Any, Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.core.file_watcher import FileWatcher


class InstrumentPane:
    """
    单个 instrument 的 pane 程序

    职责：
    1. 加载和管理自己的 DawDreamer RenderEngine
    2. 监听配置文件和 DSP 文件变化，hot reload
    3. 渲染终端 UI（参数显示、波形可视化）
    4. 处理键盘输入（参数调整、触发）
    5. 向全局 AudioEngine 注册自己的 render engine
    """

    def __init__(
        self,
        instrument_id: str,
        config_path: str,
        audio_engine,
        transport=None,
        sample_rate: int = 48000,
        buffer_size: int = 256
    ):
        """
        初始化 instrument pane

        Args:
            instrument_id: instrument 唯一标识
            config_path: 配置文件路径
            audio_engine: AudioEngine 实例
            transport: Transport 实例（可选）
            sample_rate: 采样率
            buffer_size: 缓冲区大小
        """
        self.instrument_id = instrument_id
        self.config_path = config_path
        self.audio_engine = audio_engine
        self.transport = transport
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

        # 加载配置
        self.config = self.load_config()

        # 获取 DSP 文件路径
        self.dsp_path = self.config['dsp']['path']

        # 创建 DawDreamer render engine
        self.engine = daw.RenderEngine(sample_rate, buffer_size)

        # 创建 Faust processor
        self.processor = self.engine.make_faust_processor(instrument_id)

        # 初始化参数字典（在 load_dsp 之前）
        self.parameters: Dict[str, float] = {}
        self.parameter_ranges: Dict[str, tuple] = {}

        self.load_dsp()

        # 构建 graph
        self.engine.load_graph([(self.processor, [])])

        # 文件监听器
        watch_paths = [config_path, self.dsp_path]
        self.file_watcher = FileWatcher(watch_paths, self.on_file_changed)

        # UI 状态
        self.current_beat = 0.0
        self.is_playing = False
        self.quick_controls: Dict[str, str] = {}

        # 从 Faust processor 获取参数信息
        self.update_parameters_from_processor()

        # 向全局 AudioEngine 注册
        self.audio_engine.register_instrument(instrument_id, self.engine)

        # 运行标志
        self.running = True

        # Gate 状态（用于触发后自动释放）
        self.gate_active = False
        self.gate_release_time = 0

        print(f"[{instrument_id}] Initialized")

    def load_config(self) -> Dict[str, Any]:
        """加载 YAML 配置"""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        return config

    def load_dsp(self):
        """加载 Faust DSP 代码"""
        try:
            with open(self.dsp_path) as f:
                dsp_code = f.read()

            self.processor.set_dsp_string(dsp_code)

            # 从配置文件应用初始参数
            if 'parameters' in self.config:
                for param, value in self.config['parameters'].items():
                    self.set_parameter(param, value)

            print(f"[{self.instrument_id}] DSP loaded from {self.dsp_path}")

        except Exception as e:
            print(f"[{self.instrument_id}] Error loading DSP: {e}")

    def update_parameters_from_processor(self):
        """从 Faust processor 获取参数信��"""
        try:
            params_desc = self.processor.get_parameters_description()

            for param_info in params_desc:
                param_name = param_info['label']
                self.parameters[param_name] = param_info['value']
                self.parameter_ranges[param_name] = (param_info['min'], param_info['max'])

            # 加载 quick controls
            if 'quick_control' in self.config:
                self.quick_controls = self.config['quick_control']

        except Exception as e:
            print(f"[{self.instrument_id}] Error getting parameters: {e}")

    def set_parameter(self, param_name: str, value: float):
        """
        设置参数值

        Args:
            param_name: 参数名
            value: 参数值
        """
        try:
            # 查找完整的参数路径
            params_desc = self.processor.get_parameters_description()
            param_path = None

            for param_info in params_desc:
                if param_info['label'] == param_name:
                    param_path = param_info['name']
                    break

            if param_path:
                self.processor.set_parameter(param_path, value)
                self.parameters[param_name] = value
            else:
                print(f"[{self.instrument_id}] Parameter not found: {param_name}")

        except Exception as e:
            print(f"[{self.instrument_id}] Error setting parameter {param_name}: {e}")

    def trigger(self):
        """触发 instrument（按下 gate）"""
        try:
            # 查找 gate 参数
            params_desc = self.processor.get_parameters_description()
            for param_info in params_desc:
                if 'gate' in param_info['label'].lower():
                    gate_path = param_info['name']
                    # 触发：设置为 1
                    self.processor.set_parameter(gate_path, 1.0)
                    self.gate_active = True
                    # 50ms 后释放
                    self.gate_release_time = time.time() + 0.05
                    print(f"[{self.instrument_id}] Triggered!")
                    break

        except Exception as e:
            print(f"[{self.instrument_id}] Error triggering: {e}")

    def update_gate(self):
        """更新 gate 状态（自动释放）"""
        if self.gate_active and time.time() >= self.gate_release_time:
            try:
                params_desc = self.processor.get_parameters_description()
                for param_info in params_desc:
                    if 'gate' in param_info['label'].lower():
                        gate_path = param_info['name']
                        self.processor.set_parameter(gate_path, 0.0)
                        self.gate_active = False
                        break
            except Exception as e:
                print(f"[{self.instrument_id}] Error releasing gate: {e}")

    def on_file_changed(self, filepath: str):
        """
        文件变化回调 - hot reload

        Args:
            filepath: 变化的文件路径
        """
        if filepath == self.config_path:
            print(f"[{self.instrument_id}] Config changed, reloading...")
            self.config = self.load_config()
            # 重新应用参数
            if 'parameters' in self.config:
                for param, value in self.config['parameters'].items():
                    self.set_parameter(param, value)

        elif filepath == self.dsp_path:
            print(f"[{self.instrument_id}] DSP changed, reloading...")
            self.load_dsp()
            self.update_parameters_from_processor()

    def render_ui(self):
        """渲染彩色 ASCII 终端 UI"""
        # 清屏
        print("\033[2J\033[H", end="")

        # 标题（彩色）
        icon = self.config.get('meta', {}).get('icon', '♪')
        print(f"\033[1;36m{'='*60}\033[0m")
        print(f"\033[1;33m  {icon} {self.instrument_id.upper()}\033[0m")
        print(f"\033[1;36m{'='*60}\033[0m\n")

        # Transport 状态
        if self.transport:
            self.current_beat = self.transport.get_current_beat()
            self.is_playing = self.transport.is_playing()

        status = "\033[1;32mPLAYING\033[0m" if self.is_playing else "\033[1;31mSTOPPED\033[0m"
        print(f"Status: {status}")
        print(f"Beat: \033[1;37m{self.current_beat:.2f}\033[0m\n")

        # 参数列表
        print("\033[1;35mParameters:\033[0m")
        for param, value in sorted(self.parameters.items()):
            # 获取参数范围
            param_range = self.parameter_ranges.get(param, (0.0, 1.0))
            min_val, max_val = param_range

            # 归一化到 0-1
            normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5

            # 参数值用进度条表示
            bar_length = 30
            filled = int(normalized * bar_length)
            bar = "\033[1;32m" + "█" * filled + "\033[0;37m" + "░" * (bar_length - filled) + "\033[0m"
            print(f"  {param:20s} {bar} {value:.3f}")

        print()

        # 快捷键提示
        if self.quick_controls:
            print("\033[1;34mQuick Controls:\033[0m")
            for key, action in sorted(self.quick_controls.items())[:6]:  # 显示前 6 个
                print(f"  [{key}] {action}")
            print()

        print("\033[0;37m[q] quit\033[0m")

    def handle_keyboard_input(self, key: str):
        """
        处理键盘输入

        Args:
            key: 按键字符
        """
        if key == 'q':
            self.running = False
            return

        # 处理快捷键
        if key in self.quick_controls:
            action = self.quick_controls[key]

            if action == "trigger":
                self.trigger()
            elif action.endswith('+'):
                # 增加参数
                param_name = action[:-1]
                if param_name in self.parameters:
                    param_range = self.parameter_ranges.get(param_name, (0.0, 1.0))
                    min_val, max_val = param_range
                    step = (max_val - min_val) * 0.05  # 5% 步进
                    new_value = min(self.parameters[param_name] + step, max_val)
                    self.set_parameter(param_name, new_value)
            elif action.endswith('-'):
                # 减少参数
                param_name = action[:-1]
                if param_name in self.parameters:
                    param_range = self.parameter_ranges.get(param_name, (0.0, 1.0))
                    min_val, max_val = param_range
                    step = (max_val - min_val) * 0.05  # 5% 步进
                    new_value = max(self.parameters[param_name] - step, min_val)
                    self.set_parameter(param_name, new_value)

    def read_key_nonblocking(self):
        """非阻塞读取键盘输入"""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

    def run(self):
        """主循环"""
        # 启动文件监听器
        self.file_watcher.start()

        # 保存终端设置
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            # 设置为 raw mode
            tty.setraw(fd)

            # 立即渲染第一帧 UI
            self.render_ui()
            last_render = time.time()

            while self.running:
                # 更新 gate 状态
                self.update_gate()

                # 非阻塞读取键盘输入
                key = self.read_key_nonblocking()
                if key:
                    self.handle_keyboard_input(key)

                # 定时渲染 UI（10 FPS）
                current_time = time.time()
                if current_time - last_render >= 0.1:
                    self.render_ui()
                    last_render = current_time

                # 短暂休眠避免 CPU 占用过高
                time.sleep(0.01)

        except KeyboardInterrupt:
            print(f"\n[{self.instrument_id}] Interrupted")

        finally:
            # 恢复终端设置
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            # 清理
            self.file_watcher.stop()
            self.audio_engine.unregister_instrument(self.instrument_id)
            print(f"[{self.instrument_id}] Stopped")
