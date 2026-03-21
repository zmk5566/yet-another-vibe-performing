#!/usr/bin/env python3
"""
测试 OSC 通信是否正常工作
"""

from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import udp_client
import threading
import time

print("="*60)
print("OSC 通信测试")
print("="*60)

# 测试接收
received_messages = []

def handle_test(address, *args):
    print(f"✓ 收到消息: {address} {args}")
    received_messages.append((address, args))

# 启动 OSC 服务器（监听 9010）
disp = dispatcher.Dispatcher()
disp.map("/test", handle_test)
disp.map("/clock/tick", handle_test)

server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 9010), disp)
print(f"✓ OSC 服务器启动在端口 9010")

server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True
server_thread.start()

# 等待服务器启动
time.sleep(0.5)

# 发送测试消息
client = udp_client.SimpleUDPClient("127.0.0.1", 9010)
print(f"\n发送测试消息...")
client.send_message("/test", [123, "hello"])
client.send_message("/clock/tick", [42])

# 等待接收
time.sleep(0.5)

print(f"\n收到 {len(received_messages)} 条消息")
if len(received_messages) == 2:
    print("✓✓ OSC 通信正常工作！")
else:
    print("✗✗ OSC 通信有问题")

server.shutdown()
