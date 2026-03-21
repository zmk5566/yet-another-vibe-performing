"""
HANMAI-LIVE Agent - 嵌入式 AI 助手

支持单 instrument agent 和全局 master agent
使用 OpenRouter API (Gemini Flash)
"""

import openai
import os

# 代理设置
os.environ.setdefault('http_proxy', 'http://127.0.0.1:10808')
os.environ.setdefault('https_proxy', 'http://127.0.0.1:10808')

OPENROUTER_API_KEY = "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"
MODEL = "google/gemini-3-flash-preview"


def create_client():
    """创建 OpenRouter 客户端"""
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY
    )


class InstrumentAgent:
    """
    单 instrument 的 AI agent

    可以修改参数、pattern、DSP 代码
    """

    def __init__(self, instrument_name, params, pattern, dsp_path, inst_type="drum", notes=None):
        """
        Args:
            instrument_name: instrument 名称
            params: 当前参数字典 {name: {value, min, max}}
            pattern: 当前 pattern 字符串
            dsp_path: DSP 文件路径
            inst_type: "drum" 或 "synth"
            notes: synth 模式的音符列表
        """
        self.instrument_name = instrument_name
        self.params = params
        self.pattern = pattern
        self.dsp_path = dsp_path
        self.inst_type = inst_type
        self.notes = notes or [None] * 16
        self.client = create_client()
        self.history = []

    def _build_system_prompt(self):
        """构建系统提示"""
        params_desc = "\n".join(
            f"  - {name}: {info['value']:.2f} (range: {info['min']}-{info['max']})"
            for name, info in self.params.items()
        )

        if self.inst_type == "drum":
            seq_desc = f"- Pattern (16步, X=触发, .=静音): {self.pattern}"
            seq_actions = f"""2. 修改 pattern（必须恰好 16 个字符，X=触发，.=静音）：
{{"action": "set_pattern", "pattern": "X...X...X...X..."}}"""
        else:
            # synth 模式：显示音符
            from lib.templates import midi_to_name
            notes_display = []
            for n in self.notes:
                if n is not None:
                    notes_display.append(f"{midi_to_name(n)}({n})")
                else:
                    notes_display.append("_")
            notes_str = ", ".join(notes_display)
            seq_desc = f"- Notes (16步序列): [{notes_str}]"
            seq_actions = f"""2. 修改音符序列（必须恰好 16 个元素，MIDI note number 或 null 表示静音）：
{{"action": "set_notes", "notes": [60, null, 64, null, 67, null, 64, null, 60, null, 67, null, 72, null, null, null]}}

常用 MIDI 音符参考：
C2=36, D2=38, E2=40, F2=41, G2=43, A2=45, B2=47
C3=48, D3=50, E3=52, F3=53, G3=55, A3=57, B3=59
C4=60, D4=62, E4=64, F4=65, G4=67, A4=69, B4=71
C5=72, D5=74, E5=76"""

        return f"""你是 HANMAI-LIVE 系统中 {self.instrument_name} 的 AI 助手。

当前状态：
- Instrument: {self.instrument_name} (类型: {self.inst_type})
{seq_desc}
- 参数:
{params_desc}

你可以执行以下操作（用 JSON 格式回复）：

1. 修改参数：
{{"action": "set_param", "param": "参数名", "value": 数值}}

{seq_actions}

3. 同时修改多个：
{{"actions": [...]}}

回复时先简短说明你要做什么，然后给出 JSON 命令。用中文回复。"""

    def update_state(self, params, pattern, notes=None):
        """更新当前状态"""
        self.params = params
        self.pattern = pattern
        if notes is not None:
            self.notes = notes

    def chat(self, user_message):
        """
        与 agent 对话

        Args:
            user_message: 用户消息

        Returns:
            str: agent 回复
        """
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    *self.history[-6:]  # 保留最近 6 条历史
                ]
            )

            reply = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            return f"Agent error: {e}"


class MasterAgent:
    """
    全局 master agent

    可以控制所有 instrument
    """

    def __init__(self, instruments_info):
        """
        Args:
            instruments_info: {name: {params, pattern, port}} 字典
        """
        self.instruments_info = instruments_info
        self.client = create_client()
        self.history = []

    def _build_system_prompt(self):
        """构建系统提示"""
        instruments_desc = ""
        for name, info in self.instruments_info.items():
            params_desc = ", ".join(
                f"{p}: {v['value']:.2f}" for p, v in info.get('params', {}).items()
            )
            instruments_desc += f"\n- {name} (port {info.get('port', '?')}): pattern={info.get('pattern', '?')}, params=[{params_desc}]"

        return f"""你是 HANMAI-LIVE 系统的全局 AI 助手（MC/DJ 助手）。

当前 instruments:{instruments_desc}

你可以执行以下操作（用 JSON 格式回复）：

1. 修改某个 instrument 的参数：
{{"action": "set_param", "instrument": "kick", "param": "decay", "value": 0.5}}

2. 修改某个 instrument 的 pattern：
{{"action": "set_pattern", "instrument": "kick", "pattern": "X...X...X...X..."}}

3. 修改全局 BPM：
{{"action": "set_bpm", "value": 140}}

4. 同时修改多个：
{{"actions": [...]}}

回复时先简短说明你要做什么，然后给出 JSON 命令。用中文回复。"""

    def update_instruments(self, instruments_info):
        """更新 instruments 状态"""
        self.instruments_info = instruments_info

    def chat(self, user_message):
        """与 agent 对话"""
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    *self.history[-6:]
                ]
            )

            reply = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            return f"Agent error: {e}"


def parse_agent_response(response_text):
    """
    从 agent 回复中解析 JSON 命令

    Args:
        response_text: agent 回复文本

    Returns:
        list: 命令列表 [{action, ...}, ...]
    """
    import json
    import re

    commands = []

    # 方法 1: 找 ```json ... ``` 代码块
    code_blocks = re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text)
    for block in code_blocks:
        try:
            cmd = json.loads(block)
            if 'action' in cmd:
                commands.append(cmd)
            elif 'actions' in cmd:
                commands.extend(cmd['actions'])
        except json.JSONDecodeError:
            pass

    if commands:
        return commands

    # 方法 2: 找独立的 JSON 对象（支持嵌套数组）
    # 通过追踪花括号深度来匹配
    i = 0
    while i < len(response_text):
        if response_text[i] == '{':
            depth = 0
            start = i
            for j in range(i, len(response_text)):
                if response_text[j] == '{':
                    depth += 1
                elif response_text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = response_text[start:j+1]
                        try:
                            cmd = json.loads(candidate)
                            if 'action' in cmd:
                                commands.append(cmd)
                            elif 'actions' in cmd:
                                commands.extend(cmd['actions'])
                        except json.JSONDecodeError:
                            pass
                        i = j + 1
                        break
            else:
                i += 1
        else:
            i += 1

    return commands
