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
    manager.load_plugin(manager.discovered[0], {"model": "large-v3", "device": "cuda"})

    # This spins up the lightweight 'test-sys-mon' environment
    print("\n--- Starting System Monitor ---")
    if not manager.load_plugin(manager.discovered[1]):
        print("❌ Failed to load monitor")
        return
        
    manager.register_system_monitor("cjm-system-monitor-nvidia")
    
    # 4. Verify we can see Real Hardware Stats
    stats = await manager._get_global_stats_async()
    print(f"✅ Real-Time System Stats: {json.dumps(stats, indent=2)}")
    
    # 5. Load Whisper
    # This spins up the heavy 'test-whisper-auto' environment
    print("\n--- Starting Whisper ---")
    whisper_meta = manager.plugins['cjm-transcription-plugin-whisper']
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