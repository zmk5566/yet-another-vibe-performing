#!/usr/bin/env python3
"""
HANMAI-LIVE - 简化版 kick drum
直接基于参考实现，确保声音和界面正常工作
"""

import curses
import time
import dawdreamer as daw
import sys
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pythonosc import dispatcher
from pythonosc import osc_server
import threading

# 添加 lib 到路径
sys.path.insert(0, os.path.dirname(__file__))

from lib.audio_player import RealtimeAudioPlayer
from lib.instrument import Instrument
from lib.ui import TerminalUI
from lib.horizontal_sequencer import HorizontalSequencer
from lib.agent import InstrumentAgent, parse_agent_response


class DSPFileHandler(FileSystemEventHandler):
    """DSP 文件变化处理器"""

    def __init__(self, instrument, engine, dsp_path):
        self.instrument = instrument
        self.engine = engine
        self.dsp_path = dsp_path
        self.last_modified = 0

    def on_modified(self, event):
        if event.src_path.endswith('.dsp'):
            # 防抖
            current_time = time.time()
            if current_time - self.last_modified < 0.5:
                return
            self.last_modified = current_time

            # 重新加载 DSP
            try:
                with open(self.dsp_path, 'r') as f:
                    dsp_code = f.read()
                self.instrument.processor.set_dsp_string(dsp_code)
                # 重新加载 graph
                self.engine.load_graph([(self.instrument.processor, [])])
            except Exception as e:
                pass  # 静默失败，避免中断音频


def find_available_port(start_port=9010, end_port=9019):
    """
    查找可用的 OSC 端口

    Args:
        start_port: 起始端口
        end_port: 结束端口

    Returns:
        int: 可用端口号，如果没有可用端口返回 None
    """
    import socket
    for port in range(start_port, end_port + 1):
        try:
            # 尝试绑定端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return port
        except OSError:
            continue
    return None


def main(stdscr, osc_port=None):
    """主循环"""

    # 如果没有指定端口，自动查找可用端口
    if osc_port is None:
        osc_port = find_available_port()
        if osc_port is None:
            raise RuntimeError("No available OSC ports in range 9010-9019")

    # 初始化 UI
    ui = TerminalUI(stdscr)

    # DawDreamer 设置
    SAMPLE_RATE = 44100
    BUFFER_SIZE = 512
    engine = daw.RenderEngine(SAMPLE_RATE, BUFFER_SIZE)

    # 加载 kick instrument
    kick = Instrument(engine, "dsp/instruments/kick.dsp", "kick")

    # 加载 graph
    engine.load_graph([(kick.processor, [])])

    # 启动实时音频播放器
    audio_player = RealtimeAudioPlayer(SAMPLE_RATE, BUFFER_SIZE)
    audio_player.start()

    # 创建 sequencer
    sequencer = HorizontalSequencer(length=16, bpm=120)
    sequencer.set_pattern("X...X...X...X...")  # 4/4 kick pattern

    # 状态
    triggered = False
    running = True
    last_step = -1  # 上一次处理的 step
    pending_trigger = False  # OSC 线程设置，主线程消费

    # Quantized change 队列（下一个小节开始时应用）
    pending_changes = []  # [{action, ...}, ...]
    agent_busy = False  # agent 是否正在处理

    # UI 刷新率
    TARGET_FPS = 30
    frame_time = 1.0 / TARGET_FPS
    last_draw_time = time.time()

    # 音频渲染时长
    render_duration = BUFFER_SIZE / SAMPLE_RATE

    # OSC 服务器（监听 master 时钟）
    disp = dispatcher.Dispatcher()

    def handle_tick(address, step):
        """处理 /clock/tick 消息（在 OSC 线程中运行）"""
        nonlocal last_step, pending_trigger

        # 更新 sequencer 位置
        new_pos = step % sequencer.length
        old_pos = sequencer.position
        sequencer.position = new_pos

        # 小节开始时（position 回到 0）应用 pending changes
        if new_pos == 0 and old_pos != 0 and pending_changes:
            apply_pending_changes()

        # 避免重复触发同一步
        if step != last_step:
            last_step = step

            # 只设置标志，不在这里渲染音频
            if sequencer.should_trigger():
                pending_trigger = True

    def handle_bpm(address, bpm):
        """处理 /clock/bpm 消息"""
        sequencer.bpm = bpm

    def handle_rewind(address):
        """处理 /clock/rewind 消息"""
        nonlocal last_step
        sequencer.reset()
        last_step = -1

    def handle_param(address, value):
        """处理 /param/<name> 消息（来自 master agent）"""
        # 从地址中提取参数名，如 /param/decay -> decay
        param_name = address.split('/')[-1]
        kick.set_parameter(param_name, float(value))
        # 更新本地缓存
        if param_name in kick.params:
            kick.params[param_name]['value'] = float(value)

    def handle_pattern(address, pattern):
        """处理 /pattern 消息（来自 master agent）"""
        sequencer.set_pattern(pattern)

    disp.map("/clock/tick", handle_tick)
    disp.map("/clock/bpm", handle_bpm)
    disp.map("/clock/rewind", handle_rewind)
    disp.map("/param/*", handle_param)
    disp.map("/pattern", handle_pattern)

    def apply_pending_changes():
        """应用排队的变化（在小节开始时调用）"""
        nonlocal pending_changes
        for cmd in pending_changes:
            try:
                if cmd.get('action') == 'set_param':
                    param = cmd.get('param')
                    value = cmd.get('value')
                    if param and value is not None:
                        kick.set_parameter(param, float(value))
                elif cmd.get('action') == 'set_pattern':
                    pattern = cmd.get('pattern')
                    if pattern:
                        sequencer.set_pattern(pattern)
            except Exception:
                pass
        pending_changes = []

    def agent_worker(user_msg):
        """后台线程运行 agent"""
        nonlocal agent_message, agent_busy, pending_changes
        agent_busy = True
        agent_message = "🤔 thinking..."

        try:
            agent.update_state(kick.params, sequencer.pattern)
            reply = agent.chat(user_msg)
            agent_message = reply

            # 解析命令，放入 pending 队列
            commands = parse_agent_response(reply)
            if commands:
                pending_changes.extend(commands)
                agent_message = f"⏳ queued → {reply}"
        except Exception as e:
            agent_message = f"❌ {e}"

        agent_busy = False

    osc_srv = osc_server.ThreadingOSCUDPServer(("127.0.0.1", osc_port), disp)
    osc_thread = threading.Thread(target=osc_srv.serve_forever)
    osc_thread.daemon = True
    osc_thread.start()

    # 创建 agent
    agent = InstrumentAgent(
        instrument_name="kick",
        params=kick.params,
        pattern=sequencer.pattern,
        dsp_path="dsp/instruments/kick.dsp"
    )
    agent_message = ""  # 最近的 agent 回复
    chat_input = ""     # 当前输入的文字
    chat_mode = False   # 是否在聊天模式

    # 启动 watchdog 监听 DSP 文件变化
    observer = Observer()
    handler = DSPFileHandler(kick, engine, "dsp/instruments/kick.dsp")
    observer.schedule(handler, path="dsp/instruments", recursive=False)
    observer.start()

    try:
        # 设置 curses
        stdscr.nodelay(True)
        stdscr.timeout(10)

        while running:
            current_time = time.time()

            # 处理 pending trigger（从 OSC 线程传来）
            if pending_trigger:
                pending_trigger = False
                kick.set_parameter('trigger', 1.0)
                triggered = True

                # 渲染并播放音频
                engine.render(render_duration)
                audio = engine.get_audio()
                audio_player.play_chunk(audio)

                kick.set_parameter('trigger', 0.0)

            # 绘制 UI（限制帧率）
            if current_time - last_draw_time >= frame_time:
                ui.clear()
                ui.draw_border()

                # 标题
                rows, cols = stdscr.getmaxyx()
                title = f"◉ HANMAI-LIVE - KICK DRUM (:{osc_port}) ◉"
                try:
                    stdscr.addstr(2, (cols - len(title)) // 2, title,
                                curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass

                # 绘制 sequencer
                ui.draw_horizontal_sequencer(sequencer, y_pos=4)

                # 显示 BPM 和位置信息
                info_text = f"BPM: {sequencer.bpm}  Step: {sequencer.position + 1}/{sequencer.length}"
                try:
                    stdscr.addstr(7, 2, info_text, curses.color_pair(3))
                except curses.error:
                    pass

                # 触发指示器
                ui.draw_trigger_indicator(triggered)

                # 参数条
                ui.draw_params_with_bars(kick, "参数")

                # 帮助文本
                help_text = "空格:触发  ↑↓:参数  ←→:调整  +/-:BPM  x:切换步  t:Agent  q:退出"
                try:
                    stdscr.addstr(rows - 2, 2, help_text, curses.color_pair(3))
                except curses.error:
                    pass

                # Agent 消息显示
                if agent_message:
                    # 截断显示
                    max_width = cols - 4
                    msg_lines = agent_message.split('\n')
                    for i, line in enumerate(msg_lines[:3]):  # 最多显示 3 行
                        display_line = line[:max_width]
                        try:
                            stdscr.addstr(rows - 5 - len(msg_lines[:3]) + i, 2,
                                        display_line, curses.color_pair(2))
                        except curses.error:
                            pass

                # Pending changes 指示器
                if pending_changes:
                    try:
                        stdscr.addstr(8, 2, f"⏳ {len(pending_changes)} change(s) queued → next bar",
                                    curses.color_pair(2) | curses.A_BOLD)
                    except curses.error:
                        pass

                # 聊天输入框
                if chat_mode:
                    try:
                        stdscr.addstr(rows - 3, 2, f"Agent> {chat_input}_",
                                    curses.color_pair(2) | curses.A_BOLD)
                    except curses.error:
                        pass

                ui.refresh()
                last_draw_time = current_time

            # 处理键盘输入
            try:
                key = stdscr.getch()

                if chat_mode:
                    # 聊天模式下的键盘处理
                    if key == 27:  # ESC 退出聊天模式
                        chat_mode = False
                        chat_input = ""
                    elif key == 10 or key == 13:  # Enter 发送
                        if chat_input.strip() and not agent_busy:
                            # 异步发送到 agent（不阻塞 UI）
                            msg = chat_input.strip()
                            t = threading.Thread(target=agent_worker, args=(msg,))
                            t.daemon = True
                            t.start()

                        chat_input = ""
                        chat_mode = False
                    elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace
                        chat_input = chat_input[:-1]
                    elif 32 <= key <= 126:  # 可打印字符
                        chat_input += chr(key)
                else:
                    # 正常模式
                    if key == ord('q'):
                        running = False

                    # 空格触发
                    elif key == ord(' '):
                        kick.set_parameter('trigger', 1.0)
                        triggered = True

                        # 渲染并播放音频
                        engine.render(render_duration)
                        audio = engine.get_audio()
                        audio_player.play_chunk(audio)

                        # 短暂延迟后重置触发
                        time.sleep(0.01)
                        kick.set_parameter('trigger', 0.0)
                        triggered = False

                    # 参数选择
                    elif key == curses.KEY_UP:
                        kick.select_prev_param()
                    elif key == curses.KEY_DOWN:
                        kick.select_next_param()

                    # 参数调整
                    elif key == curses.KEY_LEFT:
                        kick.adjust_param(-1)
                    elif key == curses.KEY_RIGHT:
                        kick.adjust_param(+1)

                    # BPM 控制
                    elif key == ord('+') or key == ord('='):
                        sequencer.bpm = min(sequencer.bpm + 5, 300)
                    elif key == ord('-') or key == ord('_'):
                        sequencer.bpm = max(sequencer.bpm - 5, 40)

                    # Pattern 编辑
                    elif key == ord('x'):
                        # 切换当前位置的 X/.
                        pattern_list = list(sequencer.pattern)
                        pos = sequencer.position
                        if pos < len(pattern_list):
                            pattern_list[pos] = 'X' if pattern_list[pos] == '.' else '.'
                            sequencer.set_pattern(''.join(pattern_list))

                    # 重置
                    elif key == ord('r'):
                        sequencer.reset()

                    # 进入聊天模式
                    elif key == ord('t'):
                        chat_mode = True
                        chat_input = ""

            except curses.error:
                pass

            # 短暂休眠避免忙等
            time.sleep(0.01)

    finally:
        # 停止 OSC 服务器
        osc_srv.shutdown()
        # 停止 watchdog
        observer.stop()
        observer.join()
        # 停止音频播放器
        audio_player.stop()


def run():
    """入口点"""
    import argparse

    parser = argparse.ArgumentParser(description='HANMAI-LIVE Kick Drum')
    parser.add_argument('--port', type=int, default=None,
                       help='OSC port to listen on (default: auto-assign from 9010-9019)')
    args = parser.parse_args()

    try:
        curses.wrapper(lambda stdscr: main(stdscr, args.port))
    except KeyboardInterrupt:
        print("\n👋 再见!")
    except RuntimeError as e:
        print(f"\n❌ Error: {e}")


if __name__ == '__main__':
    run()
