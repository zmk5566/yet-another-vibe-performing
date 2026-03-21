#!/usr/bin/env python3
"""
OSC 监听器 - 监听所有端口看是否收到 master 的消息
"""

from pythonosc import dispatcher
from pythonosc import osc_server
import threading

print("="*60)
print("OSC 监听器 - 监听端口 9015")
print("="*60)

def handle_any(address, *args):
    print(f"✓ 收到: {address} {args}")

disp = dispatcher.Dispatcher()
disp.set_default_handler(handle_any)

try:
    server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 9015), disp)
    print("✓ 监听端口 9015")
    print("等待 master 的消息...")
    print("(在 master 中按空格开始播放)")
    print()
    server.serve_forever()
except KeyboardInterrupt:
    print("\n停止监听")
