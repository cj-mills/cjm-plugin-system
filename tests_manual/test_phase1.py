import sys
import os
import json
import asyncio
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass

# Ensure we can import cjm_plugin_system
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.interface import FileBackedDTO

# --- 1. Mock Data Object (Zero-Copy) ---
@dataclass
class MockAudioData:
    data: str
    
    def to_temp_file(self) -> str:
        t = tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False)
        t.write(self.data)
        t.close()
        print(f"[Host] Wrote Zero-Copy file to: {t.name}")
        return t.name

# --- 2. Test Logic ---

async def run_tests():
    print("=== STARTING PHASE 1 VERIFICATION ===")
    
    # A. Setup Environment
    # We create a local .cjm/plugins folder for discovery
    local_plugin_dir = Path.cwd() / ".cjm" / "plugins"
    local_plugin_dir.mkdir(parents=True, exist_ok=True)
    
    # B. Create Manifest
    # Pointing to the CURRENT python interpreter and the dummy plugin above
    manifest = {
        "name": "test-dummy",
        "version": "0.1.0",
        "module": "tests_manual.dummy_plugin",
        "class": "DummyPlugin",
        "python_path": sys.executable, # Use same python for simplicity
        "env_vars": {"TEST_VAR": "hello"}
    }
    
    manifest_path = local_plugin_dir / "test-dummy.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f)
    
    print(f"[Setup] Created manifest at {manifest_path}")

    try:
        # C. Initialize Manager
        manager = PluginManager()
        
        # D. Discovery
        print("\n--- Test 1: Discovery ---")
        manager.discover_manifests()
        if "test-dummy" in [m.name for m in manager.discovered]:
            print("✅ Discovery Successful")
        else:
            print("❌ Discovery Failed")
            return

        # E. Loading (Launches Process)
        print("\n--- Test 2: Loading & Process Launch ---")
        success = manager.load_plugin(manager.discovered[0], config={"foo": "bar"})
        if success:
            print("✅ Plugin Loaded & Initialized")
        else:
            print("❌ Load Failed")
            return

        # F. Sync Execution
        print("\n--- Test 3: Sync Execution ---")
        result = manager.execute_plugin("test-dummy", text="Echo", repeat=2)
        print(f"Result: {result}")
        if result['result'] == "EchoEcho":
             print("✅ Sync Exec Passed")
        else:
             print("❌ Sync Exec Failed")

        # G. Async Execution
        print("\n--- Test 4: Async Execution ---")
        result = await manager.execute_plugin_async("test-dummy", text="Async", repeat=1)
        if result['result'] == "Async":
             print("✅ Async Exec Passed")
        else:
             print("❌ Async Exec Failed")

        # H. Zero-Copy Transfer
        print("\n--- Test 5: Zero-Copy Data Transfer ---")
        # We pass a MockAudioData object. 
        # The Proxy should detect .to_temp_file(), write it, pass path to worker.
        # Worker reads file content and returns it.
        heavy_obj = MockAudioData(data="SECRET_PAYLOAD")
        
        # We pass it as 'file_path' argument expected by DummyPlugin
        result = manager.execute_plugin("test-dummy", text="FileTest", file_path=heavy_obj)
        
        print(f"Worker read content: {result.get('file_content_read')}")
        if result.get('file_content_read') == "SECRET_PAYLOAD":
             print("✅ Zero-Copy Transfer Passed")
        else:
             print("❌ Zero-Copy Transfer Failed")

        # I. Streaming
        print("\n--- Test 6: Streaming ---")
        print("Stream output: ", end="")
        count = 0
        async for chunk in manager.execute_plugin_stream("test-dummy", count=3):
            print(f"{chunk['chunk']}...", end="", flush=True)
            count += 1
        print("")
        
        if count == 3:
             print("✅ Streaming Passed")
        else:
             print("❌ Streaming Failed")

        # J. Stats & Config
        print("\n--- Test 7: Telemetry & Schema ---")
        stats = manager.get_plugin_stats("test-dummy")
        print(f"Stats: {stats}")
        
        schema = manager.get_plugin_config_schema("test-dummy")
        print(f"Schema: {schema}")
        
        if stats and schema:
            print("✅ Telemetry Passed")
        else:
            print("❌ Telemetry Failed")

    finally:
        # K. Cleanup
        print("\n--- Test 8: Cleanup ---")
        manager.unload_all()
        
        # Clean up temp files
        if local_plugin_dir.exists():
            shutil.rmtree(local_plugin_dir.parent) # Remove .cjm
        
        print("✅ Cleanup Complete (Check if worker process exits in htop)")

if __name__ == "__main__":
    asyncio.run(run_tests())