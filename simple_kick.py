#!/usr/bin/env python3
"""
HANMAI-LIVE - Simple kick drum with curses UI
Based on working reference implementation
"""

import curses
import time
import dawdreamer as daw
import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from lib.audio_player import RealtimeAudioPlayer
from lib.instrument import Instrument
from lib.ui import TerminalUI


def main(stdscr):
    """Main application loop"""

    # Initialize UI
    ui = TerminalUI(stdscr)

    # DawDreamer setup
    SAMPLE_RATE = 44100
    BUFFER_SIZE = 512
    engine = daw.RenderEngine(SAMPLE_RATE, BUFFER_SIZE)

    # Load kick instrument
    kick = Instrument(engine, "dsp/instruments/kick.dsp", "kick")

    # Load graph
    engine.load_graph([(kick.processor, [])])

    # Start real-time audio player
    audio_player = RealtimeAudioPlayer(SAMPLE_RATE, BUFFER_SIZE)
    audio_player.start()

    # State
    triggered = False
    running = True

    # UI refresh rate
    TARGET_FPS = 30
    frame_time = 1.0 / TARGET_FPS
    last_draw_time = time.time()

    # Audio rendering
    render_duration = BUFFER_SIZE / SAMPLE_RATE

    try:
        # Set up curses
        stdscr.nodelay(True)
        stdscr.timeout(10)

        while running:
            current_time = time.time()

            # Draw UI (rate-limited)
            if current_time - last_draw_time >= frame_time:
                ui.clear()
                ui.draw_border()

                # Draw title
                rows, cols = stdscr.getmaxyx()
                title = "HANMAI-LIVE - Kick Drum"
                try:
                    stdscr.addstr(2, (cols - len(title)) // 2, title,
                                curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass

                # Draw trigger indicator
                ui.draw_trigger_indicator(triggered)

                # Draw parameters with bars
                ui.draw_params_with_bars(kick, "Kick Parameters")

                # Draw help
                help_text = "Space:Trigger  ↑↓:Select  ←→:Adjust  q:Quit"
                try:
                    stdscr.addstr(rows - 2, 2, help_text, curses.color_pair(3))
                except curses.error:
                    pass

                ui.refresh()
                last_draw_time = current_time

            # Handle keyboard input
            try:
                key = stdscr.getch()

                if key == ord('q'):
                    running = False

                # Trigger with space
                elif key == ord(' '):
                    kick.set_parameter('trigger', 1.0)
                    triggered = True

                    # Render and play audio
                    engine.render(render_duration)
                    audio = engine.get_audio()
                    audio_player.play_chunk(audio)

                    # Reset trigger after short delay
                    time.sleep(0.01)
                    kick.set_parameter('trigger', 0.0)
                    triggered = False

                # Parameter selection
                elif key == curses.KEY_UP:
                    kick.select_prev_param()
                elif key == curses.KEY_DOWN:
                    kick.select_next_param()

                # Parameter adjustment
                elif key == curses.KEY_LEFT:
                    kick.adjust_param(-1)
                elif key == curses.KEY_RIGHT:
                    kick.adjust_param(+1)

            except curses.error:
                pass

            # Small sleep to prevent busy loop
            time.sleep(0.01)

    finally:
        # Stop audio player
        audio_player.stop()


def run():
    """Entry point"""
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == '__main__':
    run()
