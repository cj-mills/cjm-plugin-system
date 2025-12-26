import subprocess
import sys
import time
import os
import psutil
import signal

# The code for the "Victim" process that will be killed
VICTIM_SCRIPT = """
import time
import sys
import os
# Add path to find local libs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager

def run_victim():
    manager = PluginManager()
    manager.discover_manifests()
    
    # Load a lightweight plugin (System Monitor)
    # We assume 'cjm-system-monitor-nvidia' is installed from previous steps
    plugin_name = 'cjm-system-monitor-nvidia'
    target_plugin = next((item for item in manager.discovered if item.name == plugin_name), None)

    if not target_plugin:
        print("ERROR: Plugin not found")
        return

    # Load the plugin (Starts the Worker Subprocess)
    manager.load_plugin(target_plugin)
    
    # Get the Worker PID
    proxy = manager.get_plugin(plugin_name)
    stats = proxy.get_stats()
    worker_pid = stats['pid']
    
    # Print PID so the Test Runner knows it
    print(f"WORKER_PID:{worker_pid}", flush=True)
    
    # Sleep forever until killed (Simulating a running app)
    while True:
        time.sleep(1)

if __name__ == "__main__":
    run_victim()
"""

def test_zombie_pact():
    print("=== ZOMBIE PACT VERIFICATION ===")
    
    # 1. Write the Victim Script to disk
    victim_path = "tests_manual/temp_victim.py"
    with open(victim_path, "w") as f:
        f.write(VICTIM_SCRIPT)

    victim_proc = None
    worker_pid = None

    try:
        # 2. Launch the Victim Host
        print("[Test] Launching Victim Host...")
        victim_proc = subprocess.Popen(
            [sys.executable, victim_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 3. Wait for Victim to report the Worker PID
        start_time = time.time()
        while time.time() - start_time < 15:
            line = victim_proc.stdout.readline()
            if "WORKER_PID:" in line:
                worker_pid = int(line.split(":")[1].strip())
                print(f"[Test] Victim started Worker at PID: {worker_pid}")
                break
            if "ERROR" in line:
                print(f"❌ Setup Failed: {line}")
                return
        
        if not worker_pid:
            print("❌ Timeout waiting for worker startup.")
            print(victim_proc.stderr.read())
            return

        # 4. Verify Worker exists
        if not psutil.pid_exists(worker_pid):
            print("❌ Sanity Check Failed: Worker PID not found.")
            return

        # 5. KILL THE HOST (Simulate Crash)
        print(f"[Test] 🔪 Killing Victim Host (PID {victim_proc.pid})...")
        victim_proc.kill() # SIGKILL (Hard kill, no cleanup handlers run)
        victim_proc.wait()

        # 6. Wait for Watchdog Trigger
        # The watchdog in worker.py sleeps for 1s loops. Give it 3s to notice.
        print("[Test] Waiting for Worker to detect orphan status...")
        time.sleep(3)

        # 7. Check if Worker is dead
        if psutil.pid_exists(worker_pid):
            # Check if it's a zombie process (defunct) vs actually running
            try:
                p = psutil.Process(worker_pid)
                if p.status() == psutil.STATUS_ZOMBIE:
                    print("✅ SUCCESS: Worker is dead (Zombie status is expected until reparented init cleans it).")
                else:
                    print(f"❌ FAILURE: Worker (PID {worker_pid}) is still alive and running!")
                    # Cleanup
                    p.kill()
            except psutil.NoSuchProcess:
                print("✅ SUCCESS: Worker process is completely gone.")
        else:
            print("✅ SUCCESS: Worker process is completely gone.")

    finally:
        # Cleanup temp file
        if os.path.exists(victim_path):
            os.remove(victim_path)
        # Ensure victim is dead
        if victim_proc and victim_proc.poll() is None:
            victim_proc.kill()

if __name__ == "__main__":
    test_zombie_pact()