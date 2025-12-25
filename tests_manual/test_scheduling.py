import asyncio
import time
import sys
import os
from typing import Dict, Any

# Ensure path is set to import local cjm_plugin_system
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.scheduling import SafetyScheduler, QueueScheduler
from cjm_plugin_system.core.metadata import PluginMeta

# --- Mocks ---

class MockMonitorPlugin:
    def __init__(self, vram_mb=10000):
        self.vram_mb = vram_mb
        self.name = "mock-monitor"

    def execute(self, *args, **kwargs):
        # Return what NvidiaMonitorPlugin returns
        return {
            "gpu_free_memory_mb": self.vram_mb,
            "memory_available_mb": 16000
        }
    
    async def execute_async(self, *args, **kwargs):
        return self.execute()

# --- Tests ---

async def test_safety_scheduler():
    print("\n--- Test 1: Safety Scheduler ---")
    
    # 1. Setup Manager with SafetyScheduler
    manager = PluginManager(scheduler=SafetyScheduler())
    
    # 2. Inject Mock Monitor directly into the manager
    # (Bypassing load_plugin for pure logic test)
    manager.system_monitor = MockMonitorPlugin(vram_mb=2000) # Only 2GB free
    
    # 3. Create a fake plugin that needs 4GB
    heavy_plugin = PluginMeta(name="heavy-ai", version="1.0")
    heavy_plugin.manifest = {
        "resources": {"requires_gpu": True, "min_gpu_vram_mb": 4096}
    }
    # Mock instance so execute works
    heavy_plugin.instance = type("MockInstance", (), {"execute": lambda *a: "Ran", "execute_async": lambda *a: "Ran"})()
    manager.plugins["heavy-ai"] = heavy_plugin
    
    # 4. Try to run (Should Fail)
    print(f"Attempting to run Heavy AI (Needs 4GB) on 2GB system...")
    try:
        manager.execute_plugin("heavy-ai")
        print("❌ FAILED: Scheduler should have blocked this!")
    except RuntimeError as e:
        print(f"✅ PASSED: Scheduler blocked execution: {e}")

async def test_queue_scheduler():
    print("\n--- Test 2: Queue Scheduler (Async) ---")
    
    # 1. Setup QueueScheduler (Short timeout for test)
    scheduler = QueueScheduler(timeout=5.0, poll_interval=1.0)
    manager = PluginManager(scheduler=scheduler)
    
    # 2. Inject Mock Monitor
    mock_monitor = MockMonitorPlugin(vram_mb=2000) # Starts with 2GB (Insufficient)
    manager.system_monitor = mock_monitor
    
    # 3. Create fake plugin
    heavy_plugin = PluginMeta(name="heavy-ai", version="1.0")
    heavy_plugin.manifest = {"resources": {"requires_gpu": True, "min_gpu_vram_mb": 4096}}
    heavy_plugin.instance = type("MockInstance", (), {"execute": lambda *a: "Ran"})()
    # Add async execute mock
    async def async_exec(*args, **kwargs): return "Ran Async"
    heavy_plugin.instance.execute_async = async_exec
    
    manager.plugins["heavy-ai"] = heavy_plugin

    # 4. Simulate Resources freeing up in background
    async def liberate_gpu():
        print("   [Background] Hogging GPU...")
        await asyncio.sleep(2.5)
        print("   [Background] Releasing GPU! (VRAM -> 8GB)")
        mock_monitor.vram_mb = 8192

    # 5. Run concurrently
    print("   [Main] Requesting execution (Queued)...")
    
    start = time.time()
    task_resource = asyncio.create_task(liberate_gpu())
    
    # This should block (await) until liberate_gpu updates the monitor
    result = await manager.execute_plugin_async("heavy-ai")
    
    duration = time.time() - start
    
    if result == "Ran Async" and duration > 2.0:
        print(f"✅ PASSED: Execution waited {duration:.2f}s and succeeded.")
    else:
        print(f"❌ FAILED: Result={result}, Duration={duration}")

    await task_resource

if __name__ == "__main__":
    asyncio.run(test_safety_scheduler())
    asyncio.run(test_queue_scheduler())