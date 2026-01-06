"""
Graph Federation Demo: The "Ingestion" Workflow (Art of War Edition)

This test demonstrates the full lifecycle:
1.  JOB: Transcribe Audio (Voxtral) -> Generates a Job ID
2.  LOGIC: Create Graph Nodes linked to that Job ID (Simulating LLM extraction of Sun Tzu's concepts)
3.  ACTION: Push Nodes to Context Graph via execute(action=...)
4.  QUERY: Use DuckDB to JOIN the Transcript DB with the Graph DB
"""

import asyncio
import json
import duckdb
import uuid
import sys
import os
import time
from pathlib import Path

# Add path to find local libs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.queue import JobQueue, JobStatus
from cjm_plugin_system.core.scheduling import QueueScheduler


async def run_graph_federation():
    print("=== GRAPH FEDERATION DEMO: TRANSCRIPT TO KNOWLEDGE GRAPH (SUN TZU) ===")

    # 1. Setup Manager
    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    # 2. Identify Plugins
    transcriber_name = "cjm-transcription-plugin-voxtral-hf"
    graph_name = "cjm-graph-plugin-sqlite"

    transcriber_meta = next((item for item in manager.discovered if item.name == transcriber_name), None)
    graph_meta = next((item for item in manager.discovered if item.name == graph_name), None)

    if not transcriber_meta:
        print(f"Plugin {transcriber_name} not found. Check manifests in ~/.cjm/plugins/")
        return

    if not graph_meta:
        print(f"Plugin {graph_name} not found. Check manifests in ~/.cjm/plugins/")
        return

    # 3. Load Plugins
    print(f"\n--- Loading Plugins ---")

    # Load Voxtral (CUDA)
    if not manager.load_plugin(transcriber_meta, {"device": "cuda", "model_id": "mistralai/Voxtral-Mini-3B-2507"}):
        print(f"Failed to load {transcriber_name}")
        return
    print(f"  Loaded: {transcriber_name}")

    # Load Graph (CPU/IO)
    if not manager.load_plugin(graph_meta, {"test":"test"}):
        print(f"Failed to load {graph_name}")
        manager.unload_all()
        return
    print(f"  Loaded: {graph_name}")

    # 4. Start Job Queue
    queue = JobQueue(manager)
    await queue.start()

    # 5. EXECUTION PHASE 1: TRANSCRIPTION
    # We define a shared ID that will link the Audio world to the Graph world
    shared_job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    # Update to the specific Art of War file
    # Note: Ensure this file exists in your test_files directory, or update path accordingly
    audio_file = "/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-voxtral-hf/test_files/02 - 1. Laying Plans.mp3"

    print(f"\n--- Phase 1: Transcribing Audio ---")
    print(f"Job ID: {shared_job_id}")
    print(f"File:   {os.path.basename(audio_file)}")

    if not os.path.exists(audio_file):
        print(f"WARNING: Audio file not found at {audio_file}. Please check path.")
        await queue.stop()
        manager.unload_all()
        return

    # Submit to Queue
    queue_job_id = await queue.submit(
        transcriber_name,
        audio=audio_file,
        job_id=shared_job_id,
        priority=10
    )

    # Wait for result
    print("Waiting for transcription...")
    job = await queue.wait_for_job(queue_job_id, timeout=300)

    if job.status != JobStatus.completed:
        print(f"Transcription failed: {job.error}")
        await queue.stop()
        manager.unload_all()
        return

    # Handle result extraction
    transcript_result = job.result
    if isinstance(transcript_result, dict):
        transcript_text = transcript_result.get("text", "")
    else:
        transcript_text = transcript_result.text if hasattr(transcript_result, "text") else str(transcript_result)

    print(f"  -> Transcript Start: {transcript_text[:100]}...")

    # 6. EXECUTION PHASE 2: "REALISTIC" LLM EXTRACTION
    print(f"\n--- Phase 2: Extracting Entities (Simulated LLM) ---")
    
    # We simulate the LLM analyzing "Laying Plans" and extracting the core ontology.
    # All nodes point back to the transcription job.

    source_ref_data = {
        "plugin_name": transcriber_name,
        "table_name": "transcriptions",
        "row_id": shared_job_id,
        "segment_slice": "full_text" # In a real app, this would be specific timestamp ranges
    }

    # -- Define Nodes --
    nodes = []
    edges = []

    # 1. The Author
    node_sun_tzu = {
        "id": str(uuid.uuid4()),
        "label": "Person",
        "properties": {"name": "Sun Tzu", "role": "General/Strategist"},
        "sources": [source_ref_data]
    }
    nodes.append(node_sun_tzu)

    # 2. The Work
    node_art_of_war = {
        "id": str(uuid.uuid4()),
        "label": "Work",
        "properties": {"title": "The Art of War", "importance": "Vital to the State"},
        "sources": [source_ref_data]
    }
    nodes.append(node_art_of_war)

    # 3. The Core Concept (Five Factors)
    node_five_factors = {
        "id": str(uuid.uuid4()),
        "label": "Framework",
        "properties": {"name": "The Five Constant Factors"},
        "sources": [source_ref_data]
    }
    nodes.append(node_five_factors)

    # 4. Specific Factor: The Commander
    node_commander = {
        "id": str(uuid.uuid4()),
        "label": "Factor",
        "properties": {"name": "The Commander"},
        "sources": [source_ref_data]
    }
    nodes.append(node_commander)

    # 5. Required Virtue: Wisdom
    node_wisdom = {
        "id": str(uuid.uuid4()),
        "label": "Virtue",
        "properties": {"name": "Wisdom"},
        "sources": [source_ref_data]
    }
    nodes.append(node_wisdom)

    # 6. Strategic Maxim
    node_deception = {
        "id": str(uuid.uuid4()),
        "label": "Strategy",
        "properties": {"name": "Deception", "quote": "All warfare is based on deception"},
        "sources": [source_ref_data]
    }
    nodes.append(node_deception)

    # -- Define Edges --
    
    # Sun Tzu --[AUTHORED]--> Art of War
    edges.append({
        "id": str(uuid.uuid4()),
        "source_id": node_sun_tzu["id"],
        "target_id": node_art_of_war["id"],
        "relation_type": "AUTHORED",
        "properties": {}
    })

    # Art of War --[GOVERNED_BY]--> Five Factors
    edges.append({
        "id": str(uuid.uuid4()),
        "source_id": node_art_of_war["id"],
        "target_id": node_five_factors["id"],
        "relation_type": "GOVERNED_BY",
        "properties": {}
    })

    # The Commander --[IS_PART_OF]--> Five Factors
    edges.append({
        "id": str(uuid.uuid4()),
        "source_id": node_commander["id"],
        "target_id": node_five_factors["id"],
        "relation_type": "IS_PART_OF",
        "properties": {}
    })

    # The Commander --[REQUIRES]--> Wisdom
    edges.append({
        "id": str(uuid.uuid4()),
        "source_id": node_commander["id"],
        "target_id": node_wisdom["id"],
        "relation_type": "REQUIRES",
        "properties": {}
    })
    
    # Art of War --[BASED_ON]--> Deception
    edges.append({
        "id": str(uuid.uuid4()),
        "source_id": node_art_of_war["id"],
        "target_id": node_deception["id"],
        "relation_type": "BASED_ON",
        "properties": {}
    })

    print(f"  Generated {len(nodes)} Nodes and {len(edges)} Edges based on 'Laying Plans'.")

    # 7. EXECUTION PHASE 3: GRAPH INGESTION
    print(f"\n--- Phase 3: Writing to Context Graph ---")

    print("  -> Adding Nodes...")
    result = await manager.execute_plugin_async(
        graph_name,
        action="add_nodes",
        nodes=nodes
    )
    print(f"     Result: {result}")

    print("  -> Adding Edges...")
    result = await manager.execute_plugin_async(
        graph_name,
        action="add_edges",
        edges=edges
    )
    print(f"     Result: {result}")

    # Verify with get_schema
    print("  -> Verifying Graph Ontology...")
    schema = await manager.execute_plugin_async(
        graph_name,
        action="get_schema"
    )
    print(f"     Labels found: {schema['node_labels']}")

    # 8. EXECUTION PHASE 4: FEDERATED QUERY
    print(f"\n--- Phase 4: Data Federation (DuckDB) ---")

    db_path_vox = manager.plugins[transcriber_name].manifest['db_path']
    db_path_graph = manager.plugins[graph_name].manifest['db_path']

    # Connect DuckDB
    con = duckdb.connect()

    con.execute(f"ATTACH '{db_path_vox}' AS db_vox (TYPE SQLITE, READ_ONLY TRUE);")
    con.execute(f"ATTACH '{db_path_graph}' AS db_graph (TYPE SQLITE, READ_ONLY TRUE);")

    # Query: Show me the breakdown of concepts derived from this specific audio file
    query = f"""
    SELECT
        t.job_id,
        n.label as type,
        json_extract_string(n.properties, '$.name') as name,
        json_extract_string(n.properties, '$.title') as title,
        e.relation_type as relation,
        -- Find the target node name if available (simple self-join simulation)
        (SELECT json_extract_string(properties, '$.name') 
         FROM db_graph.nodes target 
         WHERE target.id = e.target_id) as target_concept
    FROM db_graph.nodes n
    -- Left join edges to show structure
    LEFT JOIN db_graph.edges e ON n.id = e.source_id
    -- Join to transcript to prove linkage
    JOIN db_vox.transcriptions t
      ON json_extract_string(n.sources, '$[0].row_id') = t.job_id
    WHERE t.job_id = '{shared_job_id}'
    ORDER BY n.label, e.relation_type
    """

    try:
        df = con.execute(query).df()

        print("\n=== FEDERATION RESULT: KNOWLEDGE EXTRACTED ===")
        import pandas as pd
        pd.set_option('display.max_colwidth', None)
        pd.set_option('display.width', 1000)

        if not df.empty:
            # Clean up display by coalescing name/title
            df['entity'] = df['name'].fillna(df['title'])
            display_cols = ['type', 'entity', 'relation', 'target_concept']
            print(df[display_cols].to_string(index=False))
        else:
            print("No linked records found.")

    except Exception as e:
        print(f"DuckDB Query Error: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    await queue.stop()
    manager.unload_all()
    print("\n--- Demo Complete ---")


if __name__ == "__main__":
    asyncio.run(run_graph_federation())