import time
import os
import json
from dataclasses import dataclass
from typing import Dict, Any, Generator

# Mocking the Interface (since we are inside the worker env)
class DummyPlugin:
    def __init__(self):
        self.config = {}
        self.name = "dummy-plugin"
        self.version = "0.0.1"

    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        print(f"[DummyPlugin] Initialized with: {self.config}")
        with open("./tests_manual/initialize.txt", mode="w") as write_file:
            write_file.write(f"[DummyPlugin] Initialized with: {self.config}")

    def execute(self, text: str, repeat: int = 1, file_path: str = None) -> Dict[str, Any]:
        """
        Simulates work. 
        If 'file_path' is provided, it simulates reading a Zero-Copy file.
        """
        print(f"[DummyPlugin] Executing: {text} x {repeat}")
        
        file_content = None
        if file_path:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    file_content = f.read()
            else:
                file_content = "FILE_NOT_FOUND"

        return {
            "result": text * repeat,
            "processed_by_pid": os.getpid(),
            "file_content_read": file_content,
            "config_used": self.config
        }

    def execute_stream(self, count: int) -> Generator[Dict[str, int], None, None]:
        """Simulates streaming response."""
        for i in range(count):
            time.sleep(0.1)
            yield {"chunk": i, "status": "streaming"}
    
    def get_config_schema(self):
        return {"type": "object", "properties": {"foo": {"type": "string"}}}

    def get_current_config(self):
        return self.config

    def cleanup(self):
        print("[DummyPlugin] Cleaning up...")
        with open("./tests_manual/cleanup.txt", mode="w") as write_file:
            write_file.write("[DummyPlugin] Cleaning up...")