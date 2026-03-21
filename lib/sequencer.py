"""
Snake Sequencer - moves clockwise around terminal border
"""

class SnakeSequencer:
    """
    Sequencer that moves along terminal border like a snake
    Position represents progress through the pattern
    """

    def __init__(self, rows, cols, bpm=120):
        """
        Args:
            rows: Terminal height
            cols: Terminal width
            bpm: Beats per minute
        """
        self.rows = rows
        self.cols = cols
        self.bpm = bpm

        # Calculate perimeter (border length)
        # Top: cols-1, Right: rows-1, Bottom: cols-1, Left: rows-1
        self.perimeter = (cols - 1) * 2 + (rows - 1) * 2

        # Current position (0 to perimeter-1)
        self.position = 0

        # Pattern (can be set externally)
        self.pattern = "X...X...X...X..."

    def get_edge_and_offset(self):
        """
        Get current edge and offset along that edge

        Returns:
            tuple: (edge_name, offset)
                edge_name: 'top', 'right', 'bottom', 'left'
                offset: position along that edge (0-indexed)
        """
        pos = self.position

        # Top edge (left to right)
        if pos < self.cols - 1:
            return ('top', pos)
        pos -= (self.cols - 1)

        # Right edge (top to bottom)
        if pos < self.rows - 1:
            return ('right', pos)
        pos -= (self.rows - 1)

        # Bottom edge (right to left) - reverse direction
        if pos < self.cols - 1:
            return ('bottom', self.cols - 2 - pos)
        pos -= (self.cols - 1)

        # Left edge (bottom to top) - reverse direction
        return ('left', self.rows - 2 - pos)

    def move(self):
        """Move snake one step clockwise"""
        self.position = (self.position + 1) % self.perimeter

    def should_trigger(self):
        """
        Check if current position should trigger

        Returns:
            bool: True if pattern has 'X' at current position
        """
        if not self.pattern:
            return False

        pattern_pos = self.position % len(self.pattern)
        return self.pattern[pattern_pos] == 'X'

    def is_at_corner(self):
        """
        Check if snake is at a corner

        Returns:
            bool: True if at corner position
        """
        edge, offset = self.get_edge_and_offset()

        # Corners are at offset 0 or max for each edge
        if edge == 'top' and offset == 0:
            return True  # Top-left corner
        elif edge == 'top' and offset == self.cols - 2:
            return True  # Top-right corner
        elif edge == 'bottom' and offset == 0:
            return True  # Bottom-right corner
        elif edge == 'bottom' and offset == self.cols - 2:
            return True  # Bottom-left corner

        return False

    def get_pattern_char(self):
        """
        Get pattern character at current position

        Returns:
            str: Character at current position
        """
        if not self.pattern:
            return '.'

        pattern_pos = self.position % len(self.pattern)
        return self.pattern[pattern_pos]

    def get_pattern_position(self):
        """
        Get position within pattern

        Returns:
            int: Position in pattern (0 to len(pattern)-1)
        """
        if not self.pattern:
            return 0

        return self.position % len(self.pattern)

    def reset(self):
        """Reset position to start"""
        self.position = 0

    def set_pattern(self, pattern):
        """
        Set new pattern

        Args:
            pattern: String pattern (e.g., "X...X...X...")
        """
        self.pattern = pattern

    def __repr__(self):
        return f"SnakeSequencer(pos={self.position}/{self.perimeter}, bpm={self.bpm})"
