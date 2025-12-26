import asyncio
import json
from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.scheduling import SafetyScheduler

async def main():
    print("=== FULL SYSTEM INTEGRATION TEST ===")
    
    # 1. Initialize Manager with Safety Policy
    manager = PluginManager(scheduler=SafetyScheduler())
    
    # 2. Discover Plugins (Should find Whisper and SysMon)
    manager.discover_manifests()
    print(f"Discovered: {[p.name for p in manager.discovered]}")
    
    # 3. Load & Register System Monitor
    whisper_plugin_name = 'cjm-transcription-plugin-whisper'
    whisper_plugin_meta = next((item for item in manager.discovered if item.name == whisper_plugin_name), None)
    manager.load_plugin(whisper_plugin_meta, {"model": "large-v3", "device": "cuda"})

    # This spins up the lightweight 'test-sys-mon' environment
    print("\n--- Starting System Monitor ---")
    sysmon_plugin_name = 'cjm-system-monitor-nvidia'
    sysmon_plugin_meta = next((item for item in manager.discovered if item.name == sysmon_plugin_name), None)
    if not manager.load_plugin(sysmon_plugin_meta):
        print("❌ Failed to load monitor")
        return
        
    manager.register_system_monitor(sysmon_plugin_name)
    
    # 4. Verify we can see Real Hardware Stats
    stats = await manager._get_global_stats_async()
    print(f"✅ Real-Time System Stats: {json.dumps(stats, indent=2)}")
    
    # 5. Load Whisper
    # This spins up the heavy 'test-whisper-auto' environment
    print("\n--- Starting Whisper ---")
    whisper_meta = manager.plugins[whisper_plugin_name]
    print(whisper_meta)
    
    # 6. Execute with Safety Check
    # The Scheduler will compare 'stats' (from step 4) against 'whisper_meta.resources'
    print(f"Requesting execution for {whisper_meta.name}...")
    try:
        # Note: Ensure you have a valid audio file path here
        # If execution starts, it means the Scheduler approved the resources
        result = await manager.execute_plugin_async(
            "cjm-transcription-plugin-whisper", 
            audio="/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-fasthtml-workflow-transcription-single-file/test_files/01 - Chapter 1.mp3"
        )
        print(f"✅ Execution Successful! Transcription: {result['text'][:50]}...")
        
    except RuntimeError as e:
        print(f"⚠️ Execution Blocked by Scheduler: {e}")
        print("(This is GOOD if your GPU is full/small, BAD if you have >4GB free)")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

    # 7. Cleanup
    manager.unload_all()
    print("\n✅ System Shutdown Complete")

if __name__ == "__main__":
    asyncio.run(main())