#!/usr/bin/env python3
"""
完整的 OSC 通信诊断工具
"""

from pythonosc import dispatcher, osc_server, udp_client
import threading
import time

print("="*60)
print("OSC 通信诊断")
print("="*60)

# 测试 1: 创建服务器监听 9016
print("\n[测试 1] 创建 OSC 服务器监听端口 9016...")

received = []

def handler(address, *args):
    msg = f"{address} {args}"
    print(f"  ✓ 收到: {msg}")
    received.append(msg)

disp = dispatcher.Dispatcher()
disp.set_default_handler(handler)

try:
    server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 9016), disp)
    print("  ✓ 服务器启动成功")
except Exception as e:
    print(f"  ✗ 服务器启动失败: {e}")
    exit(1)

server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True
server_thread.start()

time.sleep(0.5)

# 测试 2: 发送消息
print("\n[测试 2] 发送 OSC 消息到 9016...")
client = udp_client.SimpleUDPClient("127.0.0.1", 9016)

try:
    client.send_message("/test", [123])
    print("  ✓ 消息发送成功")
except Exception as e:
    print(f"  ✗ 消息发送失败: {e}")

time.sleep(0.5)

# 测试 3: 检查接收
print("\n[测试 3] 检查消息接收...")
if len(received) > 0:
    print(f"  ✓ 收到 {len(received)} 条消息")
else:
    print("  ✗ 没有收到消息")

# 测试 4: 模拟 master 广播
print("\n[测试 4] 模拟 master 广播到多个端口...")
print("  发送到端口 9016...")
client.send_message("/clock/tick", [42])
time.sleep(0.2)

if "/clock/tick" in str(received):
    print("  ✓ 广播测试成功")
else:
    print("  ✗ 广播测试失败")

server.shutdown()

print("\n" + "="*60)
if len(received) >= 2:
    print("✓✓ OSC 通信正常工作")
    print("\n可能的问题：")
    print("1. Master 启动时 kick.py 还没运行")
    print("2. Kick.py 的 OSC 处理函数有问题")
    print("3. 端口号不匹配")
else:
    print("✗✗ OSC 通信有问题")
    print("\n建议：")
    print("1. 检查防火墙设置")
    print("2. 检查端口是否被占用")
print("="*60)
