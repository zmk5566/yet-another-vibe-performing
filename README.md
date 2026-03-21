# HANMAI-LIVE

喊麦 + livecoding 现场表演系统

## Phase 1: 单个 kick instrument 测试

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
cd /Users/k/Documents/hanmai
python src/cli/main.py
```

### 控制

- `Space`: 触发 kick
- `q/a`: 调整 decay 参数
- `w/s`: 调整 drive 参数
- `e/d`: 调整 tone 参数
- `r/f`: 调整 level 参数
- `q`: 退出

### Hot Reload

编辑以下文件会自动重新加载：
- `config/instruments/kick.yaml` - 参数配置
- `dsp/instruments/kick.dsp` - Faust DSP 代码

## 架构

- **AudioEngine**: 集中式音频混合，单一 PyAudio 流
- **Transport**: 全局时钟和 BPM
- **InstrumentPane**: 每个 instrument 的 UI 和控制
- **DawDreamer**: Headless Faust DSP 引擎

## 下一步

- Phase 2: Transport + 多 instrument
- Phase 3: Visual pane（彩色 ASCII）
- Phase 4: Agent 集成
