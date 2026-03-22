# HANMAI-LIVE

喊麦 + livecoding 现场表演系统 — 基于 Faust DSP 的实时电子音乐演出工具。

## 特性

- **Faust DSP 引擎** — 通过 DawDreamer 编译运行，支持 8 种乐器（kick, snare, hihat, clap, tom, bass, lead, pad）
- **热重载** — 编辑 DSP 代码或 YAML 配置后自动重新加载，无需重启
- **OSC 分布式架构** — Master 时钟广播，多乐器独立进程通过 OSC 同步
- **AI Agent 集成** — 内置 AI 辅助（通过 OpenRouter），可用自然语言控制参数和序列
- **终端 UI** — 基于 curses 的彩色界面，实时参数调节和序列器可视化

## 安装

```bash
pip install -r requirements.txt
```

依赖：
- `dawdreamer` — Faust DSP 引擎
- `pyaudio` — 实时音频 I/O
- `python-osc` — OSC 通信
- `pyyaml` — 配置解析
- `watchdog` — 文件监控
- `numpy` — 音频处理

## 运行

### 单乐器模式（新架构）

```bash
python src/cli/main.py
```

### 多乐器模式（tmux）

```bash
./start.sh
# 或手动启动：
python master.py                # 主时钟
python instrument.py -t kick    # 乐器进程
python instrument.py -t bass
```

## 键盘控制

### Master

| 按键 | 功能 |
|------|------|
| `Space` | 播放/停止 |
| `+` / `-` | 调整 BPM |
| `r` | 回到小节开头 |
| `t` | 进入 AI Agent 模式 |
| `q` | 退出 |

### Instrument

| 按键 | 功能 |
|------|------|
| `Space` | 手动触发 |
| `↑` `↓` | 选择参数 |
| `←` `→` | 微调参数 |
| `[` `]` | 快速调参（20x） |
| `x` | 切换当前步的 pattern（鼓组） |
| `+` / `-` | 调整 BPM |
| `t` | 进入 AI Agent 模式 |
| `q` | 退出 |

## 项目结构

```
├── master.py                  # 主时钟进程
├── instrument.py              # 多模板乐器进程
├── start.sh                   # tmux 启动脚本
├── src/
│   ├── cli/main.py            # 新架构入口
│   ├── core/
│   │   ├── audio_engine.py    # 集中式音频混合
│   │   ├── transport.py       # 全局时钟
│   │   └── file_watcher.py    # 热重载监控
│   └── instrument/
│       └── instrument_pane.py # 乐器 UI 面板
├── lib/                       # 共享库
│   ├── instrument.py          # DawDreamer 封装
│   ├── templates.py           # 乐器模板注册
│   ├── horizontal_sequencer.py # 16步序列器
│   ├── audio_player.py        # PyAudio 播放
│   ├── agent.py               # AI Agent
│   ├── ui.py                  # 终端 UI
│   └── param_mapper.py        # 参数选择器
├── dsp/instruments/           # Faust DSP 源码
│   ├── kick.dsp, snare.dsp, hihat.dsp, clap.dsp
│   ├── tom.dsp, bass.dsp, lead.dsp, pad.dsp
└── config/instruments/        # YAML 配置
    └── kick.yaml
```

## 技术参数

- 采样率：48 kHz
- 缓冲区：256 samples（~5.3ms 延迟）
- UI 刷新：30 FPS
- 序列器：16 步循环，4 步/拍（16 分音符精度）
- OSC 端口：9010-9019（每个乐器独占一个端口）

## 开发路线

- [x] Phase 1: 单乐器测试
- [ ] Phase 2: Transport + 多乐器协同
- [ ] Phase 3: Visual pane（彩色 ASCII 可视化）
- [ ] Phase 4: Agent 深度集成
