"""
Terminal UI using curses
"""

import curses

class TerminalUI:
    """Terminal UI for snake sequencer visualization"""

    def __init__(self, stdscr):
        """
        Args:
            stdscr: curses screen object
        """
        self.stdscr = stdscr
        curses.curs_set(0)  # Hide cursor

        # Initialize colors if available
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Snake
            curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Trigger
            curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Info
            curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)     # Alert

    def clear(self):
        """Clear screen - use erase() instead of clear() to reduce flicker"""
        self.stdscr.erase()  # erase() is faster than clear() in tmux

    def refresh(self):
        """Refresh screen"""
        self.stdscr.refresh()

    def draw_border(self):
        """Draw terminal border - safe version avoiding last position"""
        rows, cols = self.stdscr.getmaxyx()

        # Use a safe area: leave 1 row and 1 col margin
        safe_rows = rows - 1
        safe_cols = cols - 1

        # Top
        try:
            self.stdscr.addstr(0, 0, '┌' + '─' * (safe_cols - 2) + '┐')
        except curses.error:
            pass

        # Sides (avoid last row)
        for r in range(1, safe_rows - 1):
            try:
                self.stdscr.addstr(r, 0, '│')
                if safe_cols > 0:
                    self.stdscr.addstr(r, safe_cols - 1, '│')
            except curses.error:
                pass

        # Bottom (completely avoid last row to prevent flicker)
        # Use safe_rows - 1 instead of rows - 1
        if safe_rows > 1:
            try:
                bottom_str = '└' + '─' * (safe_cols - 2) + '┘'
                self.stdscr.addstr(safe_rows - 1, 0, bottom_str[:safe_cols])
            except curses.error:
                pass

    def draw_snake(self, edge, offset, triggered=False, trail_length=5):
        """
        Draw snake at current position with trail

        Args:
            edge: 'top', 'right', 'bottom', 'left'
            offset: position along edge
            triggered: whether currently triggering
            trail_length: length of snake trail
        """
        rows, cols = self.stdscr.getmaxyx()

        # Safe boundaries
        safe_rows = rows - 1
        safe_cols = cols - 1

        # Calculate screen position for head
        if edge == 'top':
            y, x = 0, offset + 1
        elif edge == 'right':
            y, x = offset + 1, safe_cols - 1
        elif edge == 'bottom':
            y, x = safe_rows - 1, offset + 1
        elif edge == 'left':
            y, x = offset + 1, 0
        else:
            return

        # Safety check - don't draw at last position
        if y >= safe_rows or x >= safe_cols:
            return

        # Choose color for head
        color = curses.color_pair(2) if triggered else curses.color_pair(1)

        # Draw snake head (larger, like a cursor)
        try:
            self.stdscr.addstr(y, x, '█', color | curses.A_BOLD)
        except curses.error:
            pass  # Ignore if out of bounds

    def draw_info(self, info_dict):
        """
        Draw info in center of screen

        Args:
            info_dict: Dictionary with keys:
                - position: current position
                - bpm: beats per minute
                - pattern: pattern string
                - step: step display (e.g., "4/16")
                - current: current pattern character
                - triggered: whether currently triggering
        """
        rows, cols = self.stdscr.getmaxyx()
        center_y = rows // 2
        center_x = cols // 2

        lines = [
            f"Position: {info_dict.get('position', 0)}",
            f"BPM: {info_dict.get('bpm', 120)}",
            f"Pattern: {info_dict.get('pattern', '')}",
            f"Step: {info_dict.get('step', '0/0')}",
            f"Current: [{info_dict.get('current', '.')}]",
        ]

        # Draw each line
        for i, line in enumerate(lines):
            y = center_y - len(lines)//2 + i
            x = center_x - len(line)//2

            if 0 < y < rows - 1 and x > 0:
                try:
                    self.stdscr.addstr(y, x, line, curses.color_pair(3))
                except curses.error:
                    pass

    def draw_trigger_indicator(self, triggered=False):
        """
        Draw a fixed trigger indicator area

        Args:
            triggered: whether currently triggering
        """
        rows, cols = self.stdscr.getmaxyx()
        center_y = rows // 2
        center_x = cols // 2

        # Fixed position for trigger indicator
        y = center_y + 3
        x = center_x - 10

        if 0 < y < rows - 1 and x > 0:
            try:
                if triggered:
                    # Show filled block when triggered
                    indicator = "  TRIGGER  "
                    color = curses.color_pair(2) | curses.A_REVERSE | curses.A_BOLD
                else:
                    # Show empty placeholder
                    indicator = "           "
                    color = curses.color_pair(3)

                self.stdscr.addstr(y, x, indicator, color)
            except curses.error:
                pass

    def draw_params(self, params, title="Parameters"):
        """
        Draw parameter values (old method, kept for compatibility)

        Args:
            params: Dictionary of parameter name -> value
            title: Section title
        """
        rows, cols = self.stdscr.getmaxyx()
        y = rows - len(params) - 3
        x = 2

        if y < 1:
            return

        try:
            self.stdscr.addstr(y, x, title + ":", curses.A_BOLD)
            for i, (name, value) in enumerate(params.items()):
                self.stdscr.addstr(y + 1 + i, x, f"  {name}: {value:.2f}")
        except curses.error:
            pass

    def draw_params_with_bars(self, instrument, title="Parameters"):
        """
        Draw parameters with progress bars (like old TV volume control)

        Args:
            instrument: Instrument instance with params and get_selected_param()
            title: Section title
        """
        rows, cols = self.stdscr.getmaxyx()
        y = rows - len(instrument.params) - 3
        x = 2

        if y < 1:
            return

        try:
            self.stdscr.addstr(y, x, title + ":", curses.A_BOLD)

            selected_param = instrument.get_selected_param()

            for i, (name, param) in enumerate(instrument.params.items()):
                # Calculate progress bar
                value_range = param['max'] - param['min']
                if value_range > 0:
                    normalized = (param['value'] - param['min']) / value_range
                else:
                    normalized = 0

                bar_width = 10
                filled = int(normalized * bar_width)
                bar = '█' * filled + '░' * (bar_width - filled)

                # Check if selected
                is_selected = (name == selected_param)
                prefix = '► ' if is_selected else '  '
                color = curses.color_pair(2) if is_selected else 0

                # Format line
                line = f"{prefix}{name}: [{bar}] {param['value']:.1f}"

                self.stdscr.addstr(y + 1 + i, x, line, color)

        except curses.error:
            pass

    def draw_help(self):
        """Draw help text near bottom but above border"""
        rows, cols = self.stdscr.getmaxyx()
        # Move up more to avoid snake cursor on bottom edge
        y = rows - 4
        x = 2

        help_text = "q:Quit  ↑↓:Param  ←→:Adjust  +/-:BPM  r:Reset"

        if y > 0 and x + len(help_text) < cols:
            try:
                self.stdscr.addstr(y, x, help_text, curses.color_pair(3))
            except curses.error:
                pass

    def draw_horizontal_sequencer(self, sequencer, y_pos=5, mode="drum"):
        """
        绘制横向 sequencer

        Args:
            sequencer: HorizontalSequencer 实例
            y_pos: Y 坐标位置
            mode: "drum" 或 "synth"
        """
        if mode == "synth":
            self._draw_synth_sequencer(sequencer, y_pos)
        else:
            self._draw_drum_sequencer(sequencer, y_pos)

    def _draw_drum_sequencer(self, sequencer, y_pos):
        """绘制 drum 模式 sequencer: [X][.][.][.][X][.][.]"""
        rows, cols = self.stdscr.getmaxyx()
        x_start = 2

        for i in range(min(sequencer.length, len(sequencer.pattern))):
            x = x_start + i * 3
            if x >= cols - 4:
                break

            char = sequencer.pattern[i] if i < len(sequencer.pattern) else '.'

            if i == sequencer.position:
                if char == 'X':
                    color = curses.color_pair(2) | curses.A_BOLD
                else:
                    color = curses.color_pair(1) | curses.A_BOLD
            elif char == 'X':
                color = curses.color_pair(3)
            else:
                color = 0

            try:
                self.stdscr.addstr(y_pos, x, f"[{char}]", color)
            except curses.error:
                pass

        indicator_x = x_start + sequencer.position * 3 + 1
        if indicator_x < cols - 2:
            try:
                self.stdscr.addstr(y_pos + 1, indicator_x, "^",
                                 curses.color_pair(2) | curses.A_BOLD)
            except curses.error:
                pass

    def _draw_synth_sequencer(self, sequencer, y_pos):
        """绘制 synth 模式 sequencer - 动态宽度确保 16 步都能显示"""
        from lib.templates import midi_to_name
        rows, cols = self.stdscr.getmaxyx()
        x_start = 2

        # 动态计算 cell 宽度，确保 16 步都能显示
        available = cols - x_start - 2
        cell_width = max(3, available // sequencer.length)
        cell_width = min(cell_width, 5)  # 最大 5

        for i in range(sequencer.length):
            x = x_start + i * cell_width
            if x >= cols - cell_width:
                break

            note = sequencer.notes[i] if i < len(sequencer.notes) else None

            if note is not None:
                name = midi_to_name(note)
                if cell_width >= 5:
                    display = f"[{name:>2s}]"
                elif cell_width >= 4:
                    display = f" {name[:2]} "[:cell_width]
                else:
                    display = name[0] + " "
            else:
                if cell_width >= 5:
                    display = "[..]"
                elif cell_width >= 4:
                    display = " .. "[:cell_width]
                else:
                    display = ". "

            if i == sequencer.position:
                if note is not None:
                    color = curses.color_pair(2) | curses.A_BOLD
                else:
                    color = curses.color_pair(1) | curses.A_BOLD
            elif note is not None:
                color = curses.color_pair(3)
            else:
                color = 0

            try:
                self.stdscr.addstr(y_pos, x, display[:cell_width], color)
            except curses.error:
                pass

        # 位置指示器
        indicator_x = x_start + sequencer.position * cell_width + cell_width // 2
        if indicator_x < cols - 2:
            try:
                self.stdscr.addstr(y_pos + 1, indicator_x, "^",
                                 curses.color_pair(2) | curses.A_BOLD)
            except curses.error:
                pass
