"""
Instrument - Encapsulates Faust DSP processor with automatic parameter parsing
"""

from lib.param_mapper import ParameterMapper


class Instrument:
    """
    Instrument wraps a DawDreamer Faust processor
    Automatically parses parameters from DSP and provides simple control interface
    """

    def __init__(self, engine, dsp_path, name="synth"):
        """
        Args:
            engine: DawDreamer RenderEngine instance
            dsp_path: Path to Faust .dsp file
            name: Processor name
        """
        self.name = name
        self.processor = engine.make_faust_processor(name)

        # Load DSP code
        with open(dsp_path, 'r') as f:
            dsp_code = f.read()
        self.processor.set_dsp_string(dsp_code)

        # Parse parameters from DawDreamer
        self.params = self._parse_parameters()

        # Get parameter name mapping (DawDreamer adds prefixes)
        param_info = self.processor.get_parameters_description()
        self.param_paths = {p['label']: p['name'] for p in param_info}

        # Create parameter selector
        self.mapper = ParameterMapper(self.params)

    def _parse_parameters(self):
        """
        Automatically parse parameters from DawDreamer

        Returns:
            dict: Parameter name -> {path, value, min, max, step}
        """
        param_info = self.processor.get_parameters_description()
        params = {}

        for p in param_info:
            label = p['label']

            # Skip buttons (trigger), only include sliders
            if 'button' in str(p).lower() or label == 'trigger':
                continue

            params[label] = {
                'path': p['name'],
                'value': p.get('init', p.get('default', 0)),
                'min': p.get('min', 0),
                'max': p.get('max', 1),
                'step': p.get('step', 0.01)
            }

        return params

    def select_next_param(self):
        """Select next parameter"""
        self.mapper.select_next()

    def select_prev_param(self):
        """Select previous parameter"""
        self.mapper.select_prev()

    def adjust_param(self, direction):
        """
        Adjust currently selected parameter

        Args:
            direction: -1 for decrease, +1 for increase
        """
        param_name, new_value = self.mapper.adjust_selected(direction)

        if param_name is None:
            return

        # Update local value
        self.params[param_name]['value'] = new_value

        # Update DawDreamer processor
        self.processor.set_parameter(
            self.params[param_name]['path'],
            new_value
        )

    def get_selected_param(self):
        """
        Get name of currently selected parameter

        Returns:
            str: Parameter name
        """
        return self.mapper.get_selected_param()

    def set_parameter(self, param_label, value):
        """
        Set parameter by label

        Args:
            param_label: Parameter label (e.g., 'freq', 'decay')
            value: New value
        """
        if param_label in self.param_paths:
            self.processor.set_parameter(self.param_paths[param_label], value)

            # Update local cache if it's a slider param
            if param_label in self.params:
                self.params[param_label]['value'] = value

    def __repr__(self):
        return f"Instrument(name={self.name}, params={list(self.params.keys())})"
