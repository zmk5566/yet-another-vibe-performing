#!/bin/bash
# HANMAI-LIVE 启动脚本
# 在 tmux 中启动 master 和多个 instrument

SESSION="hanmai"

# 检查 tmux session 是否已存在
tmux has-session -t $SESSION 2>/dev/null

if [ $? == 0 ]; then
    echo "Session $SESSION already exists. Attaching..."
    tmux attach -t $SESSION
    exit 0
fi

# 创建新的 tmux session
tmux new-session -d -s $SESSION -n master

# 启动 master clock
tmux send-keys -t $SESSION:master "python3 master.py" C-m

# 创建 instrument 窗口
tmux new-window -t $SESSION -n kick
tmux send-keys -t $SESSION:kick "python3 instrument.py -t kick" C-m

tmux new-window -t $SESSION -n hihat
tmux send-keys -t $SESSION:hihat "python3 instrument.py -t hihat" C-m

tmux new-window -t $SESSION -n bass
tmux send-keys -t $SESSION:bass "python3 instrument.py -t bass" C-m

# 可选：更多 instrument
# tmux new-window -t $SESSION -n snare
# tmux send-keys -t $SESSION:snare "python3 instrument.py -t snare" C-m
# tmux new-window -t $SESSION -n lead
# tmux send-keys -t $SESSION:lead "python3 instrument.py -t lead" C-m

# 选择 master 窗口
tmux select-window -t $SESSION:master

# Attach 到 session
tmux attach -t $SESSION
