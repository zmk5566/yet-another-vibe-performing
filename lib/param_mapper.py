"""
Parameter Mapper - Simple parameter selector (like old TV volume control)
No complex key mapping needed - just select and adjust
"""

class ParameterMapper:
    """
    Single selection mode parameter control
    Select parameter with ↑↓, adjust with ←→
    """

    def __init__(self, params):
        """
        Args:
            params: Dictionary of parameter name -> parameter info
        """
        self.params = params
        self.selected_index = 0

    def select_next(self):
        """Select next parameter (↓)"""
        param_names = list(self.params.keys())
        if len(param_names) > 0:
            self.selected_index = (self.selected_index + 1) % len(param_names)

    def select_prev(self):
        """Select previous parameter (↑)"""
        param_names = list(self.params.keys())
        if len(param_names) > 0:
            self.selected_index = (self.selected_index - 1) % len(param_names)

    def get_selected_param(self):
        """
        Get currently selected parameter name

        Returns:
            str: Parameter name, or None if no parameters
        """
        param_names = list(self.params.keys())
        if len(param_names) == 0:
            return None
        return param_names[self.selected_index]

    def adjust_selected(self, direction):
        """
        Adjust currently selected parameter

        Args:
            direction: -1 for decrease (←), +1 for increase (→)

        Returns:
            tuple: (param_name, new_value) or (None, None) if no params
        """
        param_name = self.get_selected_param()
        if param_name is None:
            return None, None

        param = self.params[param_name]

        # Calculate step (use provided step or auto-calculate)
        step = param.get('step', (param['max'] - param['min']) / 100)

        # Calculate new value
        new_value = param['value'] + (step * direction)
        new_value = max(param['min'], min(param['max'], new_value))

        return param_name, new_value
