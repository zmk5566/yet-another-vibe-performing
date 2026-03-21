#!/usr/bin/env python3
"""
HANMAI-LIVE Master - 全局时钟和控制

通过 OSC 广播时钟信号到所有 instrument
支持全局 play/stop/rewind/BPM 控制
"""

import curses
import time
import sys
import os
import threading
from pythonosc import udp_client

sys.path.insert(0, os.path.dirname(__file__))
from lib.agent import MasterAgent, parse_agent_response


class MasterClock:
    """
    全局时钟

    通过 OSC 广播时钟信号
    """

    def __init__(self, bpm=120, steps_per_beat=4):
        """
        初始化 master clock

        Args:
            bpm: BPM
            steps_per_beat: 每拍的步数（4 = 16分音符）
        """
        self.bpm = bpm
        self.steps_per_beat = steps_per_beat
        self.beat = 0.0
        self.step = 0
        self.is_playing = False

        # OSC 客户端（广播到所有 instrument 端口）
        # 支持最多 10 个 instrument（端口 9010-9019）
        self.osc_clients = []
        for port in range(9010, 9020):
            try:
                client = udp_client.SimpleUDPClient("127.0.0.1", port)
                self.osc_clients.append(client)
            except:
                pass

        # 时序
        self.last_step_time = time.time()

    def play(self):
        """开始播放"""
        self.is_playing = True
        self.last_step_time = time.time()

    def stop(self):
        """停止播放"""
        self.is_playing = False

    def rewind(self):
        """重置到起始位置"""
        self.beat = 0.0
        self.step = 0
        self.last_step_time = time.time()
        # 广播 rewind 消息
        for client in self.osc_clients:
            try:
                client.send_message("/clock/rewind", [])
            except:
                pass

    def set_bpm(self, bpm):
        """设置 BPM"""
        self.bpm = max(40, min(300, bpm))

    def update(self):
        """
        更新时钟状态

        Returns:
            bool: 是否触发了新的 step
        """
        if not self.is_playing:
            return False

        current_time = time.time()

        # 计算步长时长
        beats_per_second = self.bpm / 60.0
        steps_per_second = self.steps_per_beat * beats_per_second
        step_duration = 1.0 / steps_per_second

        # 检查是否到下一步
        if current_time - self.last_step_time >= step_duration:
            self.last_step_time = current_time

            # 更新 beat 和 step
            self.step += 1
            self.beat = self.step / self.steps_per_beat

            # 广播 tick 消息
            for client in self.osc_clients:
                try:
                    client.send_message("/clock/tick", [self.step])
                    client.send_message("/clock/beat", [self.beat])
                    client.send_message("/clock/bpm", [self.bpm])
                except:
                    pass

            return True

        return False


def main(stdscr):
    """主循环"""

    # 初始化 curses
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(10)

    # 初始化颜色
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)

    # 创建 master clock
    clock = MasterClock(bpm=120, steps_per_beat=4)

    # UI 刷新率
    TARGET_FPS = 30
    frame_time = 1.0 / TARGET_FPS
    last_draw_time = time.time()

    # 创建 master agent
    instruments_info = {
        "kick": {
            "params": {"freq": {"value": 60, "min": 20, "max": 200},
                      "decay": {"value": 0.3, "min": 0.1, "max": 2}},
            "pattern": "X...X...X...X...",
            "port": 9010
        }
    }
    agent = MasterAgent(instruments_info)
    agent_message = ""
    chat_input = ""
    chat_mode = False

    # Quantized change 队列
    pending_changes = []
    agent_busy = False
    last_bar_step = -1  # 上一次检测到的小节起始 step

    def apply_pending_changes():
        """应用排队的变化（在小节开始时调用）"""
        nonlocal pending_changes
        for cmd in pending_changes:
            try:
                if cmd.get('action') == 'set_bpm':
                    value = cmd.get('value')
                    if value is not None:
                        clock.set_bpm(int(value))
                elif cmd.get('action') == 'set_param':
                    inst = cmd.get('instrument', 'kick')
                    param = cmd.get('param')
                    value = cmd.get('value')
                    port = instruments_info.get(inst, {}).get('port', 9010)
                    try:
                        c = udp_client.SimpleUDPClient("127.0.0.1", port)
                        c.send_message(f"/param/{param}", [float(value)])
                    except:
                        pass
                elif cmd.get('action') == 'set_pattern':
                    inst = cmd.get('instrument', 'kick')
                    pattern = cmd.get('pattern')
                    port = instruments_info.get(inst, {}).get('port', 9010)
                    try:
                        c = udp_client.SimpleUDPClient("127.0.0.1", port)
                        c.send_message("/pattern", [pattern])
                    except:
                        pass
            except Exception:
                pass
        pending_changes = []

    def agent_worker(user_msg):
        """后台线程运行 agent"""
        nonlocal agent_message, agent_busy, pending_changes
        agent_busy = True
        agent_message = "🤔 thinking..."

        try:
            reply = agent.chat(user_msg)
            agent_message = reply

            commands = parse_agent_response(reply)
            if commands:
                pending_changes.extend(commands)
                agent_message = f"⏳ queued → {reply}"
        except Exception as e:
            agent_message = f"❌ {e}"

        agent_busy = False

    running = True

    try:
        while running:
            current_time = time.time()

            # 更新时钟
            ticked = clock.update()

            # 检测小节开始（每 16 步 = 1 小节）
            if ticked and clock.step % 16 == 0 and clock.step != last_bar_step:
                last_bar_step = clock.step
                if pending_changes:
                    apply_pending_changes()

            # 绘制 UI（限制帧率）
            if current_time - last_draw_time >= frame_time:
                stdscr.erase()

                rows, cols = stdscr.getmaxyx()

                # 标题
                title = "◉ HANMAI-LIVE MASTER ◉"
                try:
                    stdscr.addstr(2, (cols - len(title)) // 2, title,
                                curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass

                # 状态
                status_y = 5
                status = "▶ PLAYING" if clock.is_playing else "■ STOPPED"
                status_color = curses.color_pair(1) if clock.is_playing else curses.color_pair(4)

                try:
                    stdscr.addstr(status_y, 2, f"Status: ", curses.color_pair(3))
                    stdscr.addstr(status_y, 10, status, status_color | curses.A_BOLD)
                except curses.error:
                    pass

                # BPM
                try:
                    stdscr.addstr(status_y + 1, 2, f"BPM: ", curses.color_pair(3))
                    stdscr.addstr(status_y + 1, 10, f"{clock.bpm}", curses.color_pair(2) | curses.A_BOLD)
                except curses.error:
                    pass

                # Beat
                try:
                    stdscr.addstr(status_y + 2, 2, f"Beat: ", curses.color_pair(3))
                    stdscr.addstr(status_y + 2, 10, f"{clock.beat:.2f}", curses.color_pair(2))
                except curses.error:
                    pass

                # Step
                try:
                    stdscr.addstr(status_y + 3, 2, f"Step: ", curses.color_pair(3))
                    stdscr.addstr(status_y + 3, 10, f"{clock.step}", curses.color_pair(2))
                except curses.error:
                    pass

                # Beat 网格（4x4）
                beat_grid_y = status_y + 5
                try:
                    stdscr.addstr(beat_grid_y, 2, "Beat Grid:", curses.color_pair(3))
                except curses.error:
                    pass

                beat_in_bar = clock.beat % 4
                for i in range(4):
                    try:
                        x = 14 + i * 3
                        if i < int(beat_in_bar):
                            stdscr.addstr(beat_grid_y, x, "█", curses.color_pair(1))
                        elif i == int(beat_in_bar):
                            stdscr.addstr(beat_grid_y, x, "█", curses.color_pair(2) | curses.A_BOLD)
                        else:
                            stdscr.addstr(beat_grid_y, x, "░", curses.color_pair(3))
                    except curses.error:
                        pass

                # OSC 信息
                osc_y = beat_grid_y + 2
                try:
                    stdscr.addstr(osc_y, 2, "OSC Broadcasting:", curses.color_pair(3))
                    stdscr.addstr(osc_y + 1, 2, "  127.0.0.1:9010-9019", curses.color_pair(2))
                    stdscr.addstr(osc_y + 2, 2, "  /clock/tick", curses.color_pair(3))
                    stdscr.addstr(osc_y + 3, 2, "  /clock/beat", curses.color_pair(3))
                    stdscr.addstr(osc_y + 4, 2, "  /clock/bpm", curses.color_pair(3))
                except curses.error:
                    pass

                # 帮助文本
                help_y = rows - 2
                help_text = "空格:Play/Stop  +/-:BPM  r:Rewind  t:Agent  q:Quit"
                try:
                    stdscr.addstr(help_y, 2, help_text, curses.color_pair(3))
                except curses.error:
                    pass

                # Agent 消息显示
                if agent_message:
                    max_width = cols - 4
                    msg_lines = agent_message.split('\n')
                    for i, line in enumerate(msg_lines[:3]):
                        display_line = line[:max_width]
                        try:
                            stdscr.addstr(rows - 5 - len(msg_lines[:3]) + i, 2,
                                        display_line, curses.color_pair(2))
                        except curses.error:
                            pass

                # Pending changes 指示器
                if pending_changes:
                    try:
                        stdscr.addstr(osc_y + 6, 2, f"⏳ {len(pending_changes)} change(s) queued → next bar",
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

                stdscr.refresh()
                last_draw_time = current_time

            # 处理键盘输入
            try:
                key = stdscr.getch()

                if chat_mode:
                    if key == 27:  # ESC
                        chat_mode = False
                        chat_input = ""
                    elif key == 10 or key == 13:  # Enter
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

                    # Play/Stop
                    elif key == ord(' '):
                        if clock.is_playing:
                            clock.stop()
                        else:
                            clock.play()

                    # BPM 控制
                    elif key == ord('+') or key == ord('='):
                        clock.set_bpm(clock.bpm + 5)
                    elif key == ord('-') or key == ord('_'):
                        clock.set_bpm(clock.bpm - 5)

                    # Rewind
                    elif key == ord('r'):
                        clock.rewind()

                    # Agent
                    elif key == ord('t'):
                        chat_mode = True
                        chat_input = ""

            except curses.error:
                pass

            # 短暂休眠避免忙等
            time.sleep(0.01)

    finally:
        pass


def run():
    """入口点"""
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\n👋 Master stopped!")


if __name__ == '__main__':
    run()
