#!/usr/bin/env python3
"""
HANMAI-LIVE - 通用 Instrument 入口

支持 drum 和 synth 两种模式，通过 template 选择 instrument
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

sys.path.insert(0, os.path.dirname(__file__))

from lib.audio_player import RealtimeAudioPlayer
from lib.instrument import Instrument
from lib.ui import TerminalUI
from lib.horizontal_sequencer import HorizontalSequencer
from lib.agent import InstrumentAgent, parse_agent_response
from lib.templates import TEMPLATES, midi_to_freq


class DSPFileHandler(FileSystemEventHandler):
    def __init__(self, instrument, engine, dsp_path):
        self.instrument = instrument
        self.engine = engine
        self.dsp_path = dsp_path
        self.last_modified = 0

    def on_modified(self, event):
        if event.src_path.endswith('.dsp'):
            current_time = time.time()
            if current_time - self.last_modified < 0.5:
                return
            self.last_modified = current_time
            try:
                with open(self.dsp_path, 'r') as f:
                    dsp_code = f.read()
                self.instrument.processor.set_dsp_string(dsp_code)
                self.engine.load_graph([(self.instrument.processor, [])])
            except Exception:
                pass


def find_available_port(start_port=9010, end_port=9019):
    import socket
    for port in range(start_port, end_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return port
        except OSError:
            continue
    return None


def select_template(stdscr):
    """显示 template 选择菜单，返回选择的 template 名"""
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)

    drums = [(k, v) for k, v in TEMPLATES.items() if v['type'] == 'drum']
    synths = [(k, v) for k, v in TEMPLATES.items() if v['type'] == 'synth']

    while True:
        stdscr.erase()
        rows, cols = stdscr.getmaxyx()

        title = "◉ HANMAI-LIVE - Select Instrument ◉"
        try:
            stdscr.addstr(2, (cols - len(title)) // 2, title,
                         curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

        y = 5
        try:
            stdscr.addstr(y, 4, "Drums:", curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass
        y += 1
        for i, (name, _) in enumerate(drums):
            try:
                stdscr.addstr(y, 6, f"[{i + 1}] {name}", curses.color_pair(1))
            except curses.error:
                pass
            y += 1

        y += 1
        try:
            stdscr.addstr(y, 4, "Synths:", curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass
        y += 1
        for i, (name, _) in enumerate(synths):
            try:
                stdscr.addstr(y, 6, f"[{len(drums) + i + 1}] {name}", curses.color_pair(1))
            except curses.error:
                pass
            y += 1

        try:
            stdscr.addstr(rows - 2, 4, "Press number to select, q to quit",
                         curses.color_pair(3))
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('q'):
            return None

        all_templates = drums + synths
        idx = key - ord('1')
        if 0 <= idx < len(all_templates):
            return all_templates[idx][0]


def main(stdscr, template_name, osc_port=None, device_index=None):
    """主循环"""

    template = TEMPLATES[template_name]
    inst_type = template['type']  # "drum" or "synth"
    dsp_path = template['dsp']

    # 自动分配端口
    if osc_port is None:
        osc_port = find_available_port()
        if osc_port is None:
            raise RuntimeError("No available OSC ports in range 9010-9019")

    # 初始化 UI
    ui = TerminalUI(stdscr)

    # DawDreamer 设置
    SAMPLE_RATE = 44100
    BUFFER_SIZE = 2048
    engine = daw.RenderEngine(SAMPLE_RATE, BUFFER_SIZE)

    # 加载 instrument
    inst = Instrument(engine, dsp_path, template_name)
    engine.load_graph([(inst.processor, [])])

    # 启动音频播放器
    audio_player = RealtimeAudioPlayer(SAMPLE_RATE, BUFFER_SIZE, device_index=device_index)
    audio_player.start()

    # 创建 sequencer
    sequencer = HorizontalSequencer(length=16, bpm=120)
    if inst_type == 'drum':
        sequencer.set_pattern(template['pattern'])
    else:
        sequencer.set_notes(template['notes'])

    # 状态
    triggered = False
    running = True
    last_step = -1
    pending_step = False  # OSC 线程标记有新 step
    gate_on = False  # synth 模式的 gate 状态

    # Quantized change
    pending_changes = []
    agent_busy = False

    # 音频渲染
    render_duration = BUFFER_SIZE / SAMPLE_RATE

    # OSC 服务器
    disp = dispatcher.Dispatcher()

    def handle_tick(address, step):
        nonlocal last_step, pending_step

        new_pos = step % sequencer.length
        old_pos = sequencer.position
        sequencer.position = new_pos

        # 小节开始时应用 pending changes
        if new_pos == 0 and old_pos != 0 and pending_changes:
            apply_pending_changes()

        if step != last_step:
            last_step = step
            pending_step = True  # 标记有新的 step 需要处理

    def handle_bpm(address, bpm):
        sequencer.bpm = bpm

    def handle_rewind(address):
        nonlocal last_step, gate_on
        sequencer.reset()
        last_step = -1
        gate_on = False

    def handle_param(address, value):
        param_name = address.split('/')[-1]
        inst.set_parameter(param_name, float(value))

    def handle_pattern(address, pattern):
        sequencer.set_pattern(pattern)

    def handle_notes(address, *args):
        """处理 /notes 消息"""
        notes = [int(n) if n >= 0 else None for n in args]
        sequencer.set_notes(notes)

    disp.map("/clock/tick", handle_tick)
    disp.map("/clock/bpm", handle_bpm)
    disp.map("/clock/rewind", handle_rewind)
    disp.map("/param/*", handle_param)
    disp.map("/pattern", handle_pattern)
    disp.map("/notes", handle_notes)

    def apply_pending_changes():
        nonlocal pending_changes
        for cmd in pending_changes:
            try:
                if cmd.get('action') == 'set_param':
                    param = cmd.get('param')
                    value = cmd.get('value')
                    if param and value is not None:
                        inst.set_parameter(param, float(value))
                elif cmd.get('action') == 'set_pattern':
                    pattern = cmd.get('pattern')
                    if pattern:
                        sequencer.set_pattern(pattern)
                elif cmd.get('action') == 'set_notes':
                    notes = cmd.get('notes')
                    if notes:
                        sequencer.set_notes(notes)
            except Exception:
                pass
        pending_changes = []

    def agent_worker(user_msg):
        nonlocal agent_message, agent_busy, pending_changes
        agent_busy = True
        agent_message = "🤔 thinking..."
        try:
            agent.update_state(inst.params, sequencer.pattern,
                             sequencer.notes if inst_type == 'synth' else None)
            reply = agent.chat(user_msg)
            agent_message = reply
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
        instrument_name=template_name,
        params=inst.params,
        pattern=sequencer.pattern,
        dsp_path=dsp_path,
        inst_type=inst_type,
        notes=sequencer.notes if inst_type == 'synth' else None
    )
    agent_message = ""
    chat_input = ""
    chat_mode = False

    # 启动 watchdog
    observer = Observer()
    dsp_dir = os.path.dirname(dsp_path)
    handler = DSPFileHandler(inst, engine, dsp_path)
    observer.schedule(handler, path=dsp_dir, recursive=False)
    observer.start()

    # UI 刷新率
    TARGET_FPS = 30
    frame_time = 1.0 / TARGET_FPS
    last_draw_time = time.time()

    try:
        stdscr.nodelay(True)
        stdscr.timeout(5)  # 5ms timeout，更频繁地渲染音频

        while running:
            current_time = time.time()

            # 处理每一步的参数变化（从 OSC 线程传来）
            if pending_step:
                pending_step = False

                if inst_type == 'drum':
                    if sequencer.should_trigger():
                        inst.set_parameter('trigger', 1.0)
                        triggered = True
                    else:
                        inst.set_parameter('trigger', 0.0)
                else:
                    note = sequencer.get_note()
                    if note is not None:
                        inst.set_parameter('freq', midi_to_freq(note))
                        inst.set_parameter('trigger', 1.0)
                        triggered = True
                        gate_on = True
                    elif gate_on:
                        inst.set_parameter('trigger', 0.0)
                        gate_on = False

                if inst_type == 'drum':
                    # drum: 渲染一步时长的音频，然后关 trigger
                    beats_per_second = sequencer.bpm / 60.0
                    step_dur = 1.0 / (beats_per_second * 4)
                    engine.render(step_dur)
                    audio = engine.get_audio()
                    audio_player.play_chunk(audio)
                    inst.set_parameter('trigger', 0.0)
                    continue  # 跳过下面的持续渲染

            # 持续渲染音频（synth 模式或空闲时保持 DSP 运行）
            engine.render(render_duration)
            audio = engine.get_audio()
            audio_player.play_chunk(audio)

            # 绘制 UI
            if current_time - last_draw_time >= frame_time:
                ui.clear()
                ui.draw_border()

                rows, cols = stdscr.getmaxyx()
                title = f"◉ HANMAI-LIVE - {template_name.upper()} (:{osc_port}) ◉"
                try:
                    stdscr.addstr(2, (cols - len(title)) // 2, title,
                                curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass

                # 绘制 sequencer
                ui.draw_horizontal_sequencer(sequencer, y_pos=4, mode=inst_type)

                # 信息
                info_text = f"BPM: {sequencer.bpm}  Step: {sequencer.position + 1}/{sequencer.length}  Type: {inst_type}"
                try:
                    stdscr.addstr(7, 2, info_text, curses.color_pair(3))
                except curses.error:
                    pass

                # 触发指示器
                ui.draw_trigger_indicator(triggered)
                triggered = False

                # 参数条
                ui.draw_params_with_bars(inst, "参数")

                # Pending changes
                if pending_changes:
                    try:
                        stdscr.addstr(8, 2, f"⏳ {len(pending_changes)} change(s) queued → next bar",
                                    curses.color_pair(2) | curses.A_BOLD)
                    except curses.error:
                        pass

                # Agent 消息
                if agent_message:
                    max_width = cols - 4
                    msg_lines = agent_message.split('\n')
                    for i, line in enumerate(msg_lines[:3]):
                        try:
                            stdscr.addstr(rows - 5 - len(msg_lines[:3]) + i, 2,
                                        line[:max_width], curses.color_pair(2))
                        except curses.error:
                            pass

                # 帮助文本
                help_text = "空格:触发  ↑↓:参数  ←→:调整  +/-:BPM  x:切换步  t:Agent  q:退出"
                try:
                    stdscr.addstr(rows - 2, 2, help_text, curses.color_pair(3))
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
                    if key == 27:
                        chat_mode = False
                        chat_input = ""
                    elif key == 10 or key == 13:
                        if chat_input.strip() and not agent_busy:
                            msg = chat_input.strip()
                            t = threading.Thread(target=agent_worker, args=(msg,))
                            t.daemon = True
                            t.start()
                        chat_input = ""
                        chat_mode = False
                    elif key == curses.KEY_BACKSPACE or key == 127:
                        chat_input = chat_input[:-1]
                    elif 32 <= key <= 126:
                        chat_input += chr(key)
                else:
                    if key == ord('q'):
                        running = False

                    elif key == ord(' '):
                        inst.set_parameter('trigger', 1.0)
                        triggered = True
                        engine.render(render_duration)
                        audio = engine.get_audio()
                        audio_player.play_chunk(audio)
                        time.sleep(0.01)
                        inst.set_parameter('trigger', 0.0)
                        triggered = False

                    elif key == curses.KEY_UP:
                        inst.select_prev_param()
                    elif key == curses.KEY_DOWN:
                        inst.select_next_param()
                    elif key == curses.KEY_LEFT:
                        inst.adjust_param(-1)
                    elif key == curses.KEY_RIGHT:
                        inst.adjust_param(+1)

                    elif key == ord('+') or key == ord('='):
                        sequencer.bpm = min(sequencer.bpm + 5, 300)
                    elif key == ord('-') or key == ord('_'):
                        sequencer.bpm = max(sequencer.bpm - 5, 40)

                    elif key == ord('x'):
                        if inst_type == 'drum':
                            pattern_list = list(sequencer.pattern)
                            pos = sequencer.position
                            if pos < len(pattern_list):
                                pattern_list[pos] = 'X' if pattern_list[pos] == '.' else '.'
                                sequencer.set_pattern(''.join(pattern_list))

                    elif key == ord('r'):
                        sequencer.reset()

                    elif key == ord('t'):
                        chat_mode = True
                        chat_input = ""

            except curses.error:
                pass

            time.sleep(0.01)

    finally:
        osc_srv.shutdown()
        observer.stop()
        observer.join()
        audio_player.stop()


def list_audio_devices():
    """列出可用的音频输出设备"""
    import pyaudio
    p = pyaudio.PyAudio()
    default_idx = p.get_default_output_device_info()['index']
    print("可用音频输出设备：")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxOutputChannels'] > 0:
            default = ' ← 默认' if i == default_idx else ''
            print(f"  [{i}] {info['name']} ({info['maxOutputChannels']}ch){default}")
    p.terminate()


def run():
    import argparse

    parser = argparse.ArgumentParser(description='HANMAI-LIVE Instrument')
    parser.add_argument('-t', '--template', type=str, default=None,
                       choices=list(TEMPLATES.keys()),
                       help='Instrument template name')
    parser.add_argument('--port', type=int, default=None,
                       help='OSC port (default: auto-assign)')
    parser.add_argument('-d', '--device', type=int, default=None,
                       help='Audio output device index (default: system default)')
    parser.add_argument('--list-devices', action='store_true',
                       help='List available audio devices and exit')
    args = parser.parse_args()

    if args.list_devices:
        list_audio_devices()
        return

    if args.template:
        try:
            curses.wrapper(lambda stdscr: main(stdscr, args.template, args.port, args.device))
        except KeyboardInterrupt:
            print("\n👋 再见!")
        except RuntimeError as e:
            print(f"\n❌ {e}")
    else:
        def wrapper(stdscr):
            template_name = select_template(stdscr)
            if template_name:
                main(stdscr, template_name, args.port, args.device)

        try:
            curses.wrapper(wrapper)
        except KeyboardInterrupt:
            print("\n👋 再见!")
        except RuntimeError as e:
            print(f"\n❌ {e}")


if __name__ == '__main__':
    run()
