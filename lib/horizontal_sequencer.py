"""
简单的横向循环 sequencer

用于 HANMAI-LIVE 系统的节奏控制
"""


class HorizontalSequencer:
    """
    横向循环 sequencer

    显示格式：[X][.][.][.][X][.][.][.][X][.][.][.][X][.][.][.]
              ^
    当前位置用 ^ 标记
    """

    def __init__(self, length=16, bpm=120):
        """
        初始化 sequencer

        Args:
            length: 步数（默认 16 步）
            bpm: BPM（每分钟节拍数）
        """
        self.length = length
        self.position = 0
        self.bpm = bpm
        self.pattern = "X...X...X...X..."  # 默认 4/4 pattern

        # 音高支持（用于 melodic instruments）
        self.notes = [None] * length  # MIDI note numbers 或 None

    def move(self):
        """移动到下一步"""
        self.position = (self.position + 1) % self.length

    def should_trigger(self):
        """
        检查当前位置是否应该触发

        Returns:
            bool: 如果 pattern[position] == 'X' 返回 True
        """
        if self.position >= len(self.pattern):
            return False
        return self.pattern[self.position] == 'X'

    def set_pattern(self, pattern):
        """
        设置新的 pattern

        Args:
            pattern: Pattern 字符串（如 "X...X...X...X..."）
        """
        self.pattern = pattern
        # 确保 pattern 不超过 length
        if len(pattern) > self.length:
            self.pattern = pattern[:self.length]
        # 如果 pattern 太短，用 '.' 填充
        elif len(pattern) < self.length:
            self.pattern = pattern + '.' * (self.length - len(pattern))

    def reset(self):
        """重置到起始位置"""
        self.position = 0

    def get_pattern_char(self):
        """
        获取当前位置的 pattern 字符

        Returns:
            str: 当前位置的字符（'X' 或 '.'）
        """
        if self.position >= len(self.pattern):
            return '.'
        return self.pattern[self.position]

    # 音高支持方法（用于 bass/synth 等 melodic instruments）

    def set_notes(self, notes):
        """
        设置音符列表（用于 melodic instruments）

        Args:
            notes: MIDI note numbers 列表，None 表示不触发
                  例如：[60, None, None, None, 64, None, None, None, ...]
        """
        self.notes = notes[:]
        # 确保长度匹配
        while len(self.notes) < self.length:
            self.notes.append(None)
        if len(self.notes) > self.length:
            self.notes = self.notes[:self.length]

    def get_note(self):
        """
        获取当前位置的音符

        Returns:
            int or None: MIDI note number 或 None
        """
        if self.position >= len(self.notes):
            return None
        return self.notes[self.position]

    def set_note_at(self, position, note):
        """
        设置指定位置的音符

        Args:
            position: 位置索引
            note: MIDI note number 或 None
        """
        if 0 <= position < len(self.notes):
            self.notes[position] = note

    def should_trigger_synth(self):
        """
        Synth 模式：检查当前位置是否有音符

        Returns:
            bool: 如果当前位置有音符返回 True
        """
        return self.get_note() is not None

    def should_release(self):
        """
        Synth 模式：检查当前位置是否应该释放 gate

        当前位置无音符，说明应该 release

        Returns:
            bool: 如果当前位置无音符返回 True
        """
        return self.get_note() is None

    def __repr__(self):
        return f"HorizontalSequencer(pos={self.position}/{self.length}, bpm={self.bpm})"
