"""
Graph Federation Demo: The "Ingestion" Workflow (Art of War Edition)

This test demonstrates the full lifecycle:
1.  JOB: Transcribe Audio (Voxtral) -> Generates a Job ID
2.  LOGIC: Create Graph Nodes using Type-Safe Domain Library
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

# Tier 2 Core DTOs
from cjm_graph_plugin_system.core import SourceRef

# Tier 2 Domain Library (The new addition)
from cjm_graph_domains.domains.knowledge import Person, Work, Concept, Topic, Quote
from cjm_graph_domains.domains.relations import KnowledgeRelations


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
    shared_job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    # Path to audio file
    audio_file = "/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-voxtral-hf/test_files/02 - 1. Laying Plans.mp3"

    print(f"\n--- Phase 1: Transcribing Audio ---")
    print(f"Job ID: {shared_job_id}")
    print(f"File:   {os.path.basename(audio_file)}")

    if not os.path.exists(audio_file):
        print(f"WARNING: Audio file not found at {audio_file}. Skipping transcription logic (mocking job_id).")
    else:
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

    # 6. EXECUTION PHASE 2: EXTRACTING ENTITIES (USING DOMAIN LIBRARY)
    print(f"\n--- Phase 2: Extracting Entities (Using cjm-graph-domains) ---")
    
    # Define the Source Reference
    ref = SourceRef(
        plugin_name=transcriber_name,
        table_name="transcriptions",
        row_id=shared_job_id,
        segment_slice="full_text"
    )
    
    # --- A. Instantiate Domain Objects (Type-Safe Pydantic Models) ---
    
    # 1. The Author
    p_sun_tzu = Person(
        name="Sun Tzu", 
        role="General/Strategist", 
        era="Ancient China"
    )

    # 2. The Work
    w_art_of_war = Work(
        title="The Art of War",
        author_name="Sun Tzu",
        year=-500
    )

    # 3. Concepts
    c_five_factors = Concept(
        name="The Five Constant Factors",
        definition="The governing parameters of warfare: Moral Law, Heaven, Earth, Commander, Method."
    )
    
    c_commander = Concept(
        name="The Commander",
        domain="Leadership"
    )
    
    c_wisdom = Concept(
        name="Wisdom",
        domain="Virtue"
    )
    
    c_deception = Concept(
        name="Deception",
        definition="The basis of all warfare."
    )

    # 4. Quote
    q_quote = Quote(
        text="All warfare is based on deception.",
        speaker="Sun Tzu"
    )

    # --- B. Convert to GraphNodes (With SourceRefs) ---
    # We call .to_graph_node(sources=[ref]) then .to_dict() for JSON serialization
    
    nodes_objs = [
        p_sun_tzu.to_graph_node(sources=[ref]),
        w_art_of_war.to_graph_node(sources=[ref]),
        c_five_factors.to_graph_node(sources=[ref]),
        c_commander.to_graph_node(sources=[ref]),
        c_wisdom.to_graph_node(sources=[ref]),
        c_deception.to_graph_node(sources=[ref]),
        q_quote.to_graph_node(sources=[ref])
    ]
    
    # Prepare JSON-ready list
    nodes_data = [n.to_dict() for n in nodes_objs]
    
    # Map IDs for Edge Creation
    id_map = {
        "Sun Tzu": nodes_objs[0].id,
        "Art of War": nodes_objs[1].id,
        "Five Factors": nodes_objs[2].id,
        "Commander": nodes_objs[3].id,
        "Wisdom": nodes_objs[4].id,
        "Deception": nodes_objs[5].id,
        "Quote": nodes_objs[6].id
    }

    # --- C. Create Edges (Using Standard Relations) ---
    rels = KnowledgeRelations
    edges_data = []

    def make_edge(src_key, tgt_key, rel_type):
        return {
            "id": str(uuid.uuid4()),
            "source_id": id_map[src_key],
            "target_id": id_map[tgt_key],
            "relation_type": rel_type,
            "properties": {}
        }

    edges_data.append(make_edge("Sun Tzu", "Art of War", rels.AUTHORED))
    edges_data.append(make_edge("Art of War", "Five Factors", rels.DEFINES))
    edges_data.append(make_edge("Commander", "Five Factors", rels.RELATED_TO)) # Part of
    edges_data.append(make_edge("Commander", "Wisdom", "REQUIRES")) # Custom relation allowed too
    edges_data.append(make_edge("Art of War", "Deception", "BASED_ON"))
    edges_data.append(make_edge("Art of War", "Quote", rels.QUOTES))

    print(f"  Generated {len(nodes_data)} Nodes and {len(edges_data)} Edges using Domain Library.")

    # 7. EXECUTION PHASE 3: GRAPH INGESTION
    print(f"\n--- Phase 3: Writing to Context Graph ---")

    print("  -> Adding Nodes...")
    result = await manager.execute_plugin_async(
        graph_name,
        action="add_nodes",
        nodes=nodes_data
    )
    print(f"     Result: {result}")

    print("  -> Adding Edges...")
    result = await manager.execute_plugin_async(
        graph_name,
        action="add_edges",
        edges=edges_data
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

    # Query
    query = f"""
    SELECT
        t.job_id,
        n.label as type,
        -- Note: We rely on the Domain Library's 'name' normalization here!
        json_extract_string(n.properties, '$.name') as name,
        e.relation_type as relation,
        (SELECT json_extract_string(properties, '$.name') 
         FROM db_graph.nodes target 
         WHERE target.id = e.target_id) as target_concept
    FROM db_graph.nodes n
    LEFT JOIN db_graph.edges e ON n.id = e.source_id
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
            display_cols = ['type', 'name', 'relation', 'target_concept']
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