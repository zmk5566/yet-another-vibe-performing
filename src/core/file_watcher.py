"""
文件监听器 - 支持 hot reload

使用 watchdog 库监听文件变化，支持防抖
"""

import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, List


class FileWatcher:
    """
    文件监听器，支持 hot reload

    使用 watchdog 库监听文件变化
    """

    def __init__(self, paths: List[str], callback: Callable[[str], None]):
        """
        初始化文件监听器

        Args:
            paths: 要监听的文件路径列表
            callback: 文件变化时的回调函数 callback(filepath)
        """
        self.paths = paths
        self.callback = callback

        self.observer = Observer()

        # 为每个文件设置监听
        for path in paths:
            if not os.path.exists(path):
                print(f"[FileWatcher] Warning: {path} does not exist, skipping")
                continue

            directory = os.path.dirname(path) or "."
            handler = FileChangeHandler(path, callback)
            self.observer.schedule(handler, directory, recursive=False)

        print(f"[FileWatcher] Watching {len(paths)} files")

    def start(self):
        """启动监听"""
        self.observer.start()
        print("[FileWatcher] Started")

    def stop(self):
        """停止监听"""
        self.observer.stop()
        self.observer.join()
        print("[FileWatcher] Stopped")


class FileChangeHandler(FileSystemEventHandler):
    """文件变化处理器"""

    def __init__(self, filepath: str, callback: Callable[[str], None]):
        """
        初始化处理器

        Args:
            filepath: 要监听的文件路径
            callback: 文件变化时的回调函数
        """
        self.filepath = os.path.abspath(filepath)
        self.callback = callback
        self.last_modified = 0

    def on_modified(self, event):
        """
        文件修改事件

        Args:
            event: 文件系统事件
        """
        if event.is_directory:
            return

        event_path = os.path.abspath(event.src_path)

        if event_path == self.filepath:
            # 防抖：避免重复触发
            current_time = time.time()
            if current_time - self.last_modified > 0.5:
                self.last_modified = current_time
                print(f"[FileWatcher] File changed: {self.filepath}")
                self.callback(self.filepath)
