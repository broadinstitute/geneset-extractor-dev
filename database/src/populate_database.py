#!/usr/bin/env python3
"""
Populate GenSeCoDB database from GMT gene set files.

Usage:
    python populate_database.py --db-path database.db --schema-file schema.sql --data-root /path/to/data
"""

import argparse
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GeneSeCoDatabasePopulator:
    """Populate GenSeCoDB database from GMT files."""

    def __init__(self, db_path: str):
        """Initialize database connection."""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.next_available_node_id = 1  # Track next available node ID for spacing gene sets

    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        # Enable foreign keys
        self.cursor.execute('PRAGMA foreign_keys = ON')
        logger.info(f"Connected to database: {self.db_path}")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            logger.info("Database connection closed")

    def initialize_schema(self, schema_file: str):
        """Create database tables and indexes from schema file."""
        try:
            schema_path = Path(schema_file)
            if not schema_path.exists():
                raise FileNotFoundError(f"Schema file not found: {schema_file}")
            
            logger.info(f"Initializing database schema from {schema_file}...")
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            self.cursor.executescript(schema_sql)
            self.conn.commit()
            logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing schema: {e}")
            raise

    def find_gmt_files(self, root_path: str) -> List[Path]:
        """Find all .gmt files in root directory and subdirectories."""
        root = Path(root_path)
        if not root.exists():
            raise ValueError(f"Data root path does not exist: {root_path}")
        
        gmt_files = list(root.rglob('*.gmt'))
        logger.info(f"Found {len(gmt_files)} .gmt files")
        return gmt_files

    def parse_gmt_file(self, gmt_path: Path) -> List[Tuple[str, List[str]]]:
        """
        Parse GMT file.
        
        Format: <gene_set_name>TAB<gene_1> <gene_2> ... <gene_n>
        
        Returns:
            List of (gene_set_name, gene_list) tuples
        """
        gene_sets = []
        try:
            with open(gmt_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) < 2:
                        logger.warning(f"{gmt_path}:{line_num} - Invalid line format (missing tab)")
                        continue
                    
                    gene_set_name = parts[0]
                    # Second column is typically description (optional in some GMT files)
                    # Genes are space-separated, starting from the second column
                    genes_str = '\t'.join(parts[1:])
                    genes = genes_str.split()
                    
                    if not genes:
                        logger.warning(f"{gmt_path}:{line_num} - No genes found for {gene_set_name}")
                        continue
                    
                    gene_sets.append((gene_set_name, genes))
            
            logger.info(f"Parsed {len(gene_sets)} gene sets from {gmt_path}")
            return gene_sets
        except Exception as e:
            logger.error(f"Error parsing {gmt_path}: {e}")
            return []

    def insert_species(self, species_code: str, species_name: str) -> int:
        """Insert or get species ID."""
        try:
            self.cursor.execute(
                'SELECT species_id FROM species WHERE species_code = ?',
                (species_code,)
            )
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            self.cursor.execute(
                'INSERT INTO species (species_code, species_name) VALUES (?, ?)',
                (species_code, species_name)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"Species insert error: {e}")
            # Try to get existing ID
            self.cursor.execute(
                'SELECT species_id FROM species WHERE species_code = ?',
                (species_code,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None

    def insert_namespace(self, label: str, species_code: str) -> int:
        """Insert or get namespace ID."""
        try:
            self.cursor.execute(
                'SELECT namespace_id FROM namespace WHERE label = ? AND species_code = ?',
                (label, species_code)
            )
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            self.cursor.execute(
                'INSERT INTO namespace (label, species_code) VALUES (?, ?)',
                (label, species_code)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"Namespace insert error: {e}")
            self.cursor.execute(
                'SELECT namespace_id FROM namespace WHERE label = ? AND species_code = ?',
                (label, species_code)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None

    def insert_gene_symbol(self, symbol: str, namespace_id: int, ncbi_id: str = None) -> int:
        """Insert or get gene symbol ID."""
        try:
            self.cursor.execute(
                'SELECT gene_symbol_id FROM gene_symbol WHERE symbol = ? AND namespace_id = ?',
                (symbol, namespace_id)
            )
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            self.cursor.execute(
                'INSERT INTO gene_symbol (symbol, namespace_id, NCBI_id) VALUES (?, ?, ?)',
                (symbol, namespace_id, ncbi_id)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"Gene symbol insert error: {e}")
            self.cursor.execute(
                'SELECT gene_symbol_id FROM gene_symbol WHERE symbol = ? AND namespace_id = ?',
                (symbol, namespace_id)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None

    def insert_collection(self, collection_name: str, full_name: str = None, description: str = None) -> int:
        """Insert or get collection ID."""
        try:
            self.cursor.execute(
                'SELECT collection_id FROM collection WHERE collection_name = ?',
                (collection_name,)
            )
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            self.cursor.execute(
                'INSERT INTO collection (collection_name, full_name, description) VALUES (?, ?, ?)',
                (collection_name, full_name or collection_name, description or '')
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"Collection insert error: {e}")
            self.cursor.execute(
                'SELECT collection_id FROM collection WHERE collection_name = ?',
                (collection_name,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None

    def insert_gene_set_license(self, license_code: str, license_name: str = None) -> int:
        """Insert or get gene set license ID."""
        try:
            self.cursor.execute(
                'SELECT gene_set_license_id FROM gene_set_license WHERE license_code = ?',
                (license_code,)
            )
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            self.cursor.execute(
                'INSERT INTO gene_set_license (license_code, license_name) VALUES (?, ?)',
                (license_code, license_name or license_code)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"License insert error: {e}")
            self.cursor.execute(
                'SELECT gene_set_license_id FROM gene_set_license WHERE license_code = ?',
                (license_code,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None

    def insert_gene_set(
        self,
        standard_name: str,
        collection_name: str,
        license_code: str,
        tags: str = None,
        gene_set_id: int = None
    ) -> int:
        """Insert gene set with optional explicit ID."""
        try:
            if gene_set_id is not None:
                # Insert with explicit ID
                self.cursor.execute(
                    'INSERT INTO gene_set (gene_set_id, standard_name, collection_name, license_code, tags) VALUES (?, ?, ?, ?, ?)',
                    (gene_set_id, standard_name, collection_name, license_code, tags)
                )
                return gene_set_id
            else:
                # Auto-increment ID
                self.cursor.execute(
                    'INSERT INTO gene_set (standard_name, collection_name, license_code, tags) VALUES (?, ?, ?, ?)',
                    (standard_name, collection_name, license_code, tags)
                )
                self.conn.commit()
                return self.cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"Gene set insert error for {standard_name}: {e}")
            # Try to get existing ID
            self.cursor.execute(
                'SELECT gene_set_id FROM gene_set WHERE standard_name = ?',
                (standard_name,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None

    def insert_gene_set_gene_symbol(self, gene_set_id: int, gene_symbol_id: int):
        """Insert gene set gene symbol association."""
        try:
            self.cursor.execute(
                'INSERT INTO gene_set_gene_symbol (gene_set_id, gene_symbol_id) VALUES (?, ?)',
                (gene_set_id, gene_symbol_id)
            )
        except sqlite3.IntegrityError:
            pass  # Duplicate entry

    def load_provenance_and_metadata(
        self, 
        gene_set_name: str, 
        root_path: Path
    ) -> Optional[Tuple[str, str, Optional[str]]]:
        """
        Load provenance_graph, geneset_metadata, and run_summary for a gene set.
        
        Looks for:
        - geneset.provenance.json
        - geneset.meta.json
        - run_summary.json (optional)
        
        Returns:
            Tuple of (provenance_graph, geneset_metadata, run_summary) if required files exist.
            run_summary is optional. None returned if required files are missing.
        """
        try:
            provenance_file = root_path / "geneset.provenance.json"
            metadata_file = root_path / "geneset.meta.json"
            run_summary_file = root_path / "run_summary.json"
            
            # Required files must exist
            if not provenance_file.exists() or not metadata_file.exists():
                return None
            
            # Load provenance
            with open(provenance_file, 'r', encoding='utf-8') as f:
                provenance_data = json.load(f)
            provenance_graph = json.dumps(provenance_data)
            
            # Load metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_data = json.load(f)
            geneset_metadata = json.dumps(metadata_data)
            
            # Load run_summary (optional)
            run_summary = None
            if run_summary_file.exists():
                with open(run_summary_file, 'r', encoding='utf-8') as f:
                    run_summary_data = json.load(f)
                run_summary = json.dumps(run_summary_data)
            
            return (provenance_graph, geneset_metadata, run_summary)
        
        except Exception as e:
            logger.debug(f"Error loading provenance/metadata for {gene_set_name}: {e}")
            return None

    def insert_gene_set_details(
        self,
        gene_set_id: int,
        gene_set_name: str,
        metadata_json_str: str,
        species_code: str,
        primary_namespace_id: int,
        contrib_organization: str = None
    ):
        """
        Insert gene_set_details record from parsed metadata JSON.
        
        Maps fields from geneset.meta.json into the gene_set_details table:
        - systematic_name: gene_set_name (unique, e.g. AC10__blood__pos)
        - description_brief / description_full: from gene_set.description
        - exact_source: signature_name + variant + geneset_id
        - external_details_URL: converter.code.repo_url (or notebook_url)
        - source_species_code, primary_namespace_id, num_namespaces: provided
        """
        try:
            try:
                metadata = json.loads(metadata_json_str) if metadata_json_str else {}
            except json.JSONDecodeError:
                metadata = {}
            
            gene_set_meta = metadata.get('gene_set', {}) if isinstance(metadata, dict) else {}
            converter = metadata.get('converter', {}) if isinstance(metadata, dict) else {}
            code = converter.get('code', {}) if isinstance(converter, dict) else {}
            params = converter.get('parameters', {}) if isinstance(converter, dict) else {}
            
            description_full = gene_set_meta.get('description') or ''
            # Brief description: first sentence or first 250 chars
            description_brief = description_full.split('. ')[0].strip()
            if description_brief and not description_brief.endswith('.'):
                description_brief += '.'
            if len(description_brief) > 250:
                description_brief = description_brief[:247] + '...'
            
            # exact_source: identifier from upstream (signature + emitted variant)
            signature_name = params.get('signature_name') if isinstance(params, dict) else None
            geneset_uid = metadata.get('geneset_id') if isinstance(metadata, dict) else None
            exact_source_parts = []
            if signature_name:
                exact_source_parts.append(signature_name)
            # Derive variant suffix from gene_set_name (e.g. AC10__blood__pos -> pos)
            if signature_name and gene_set_name.startswith(signature_name):
                suffix = gene_set_name[len(signature_name):].lstrip('_')
                if suffix:
                    exact_source_parts.append(suffix)
            if geneset_uid:
                exact_source_parts.append(f"geneset:{geneset_uid}")
            exact_source = ' | '.join(exact_source_parts) if exact_source_parts else None
            
            # external URL: prefer notebook_url, fall back to repo_url
            external_url = (code.get('notebook_url')
                            or code.get('script_url')
                            or code.get('repo_url')) if isinstance(code, dict) else None
            
            self.cursor.execute(
                '''INSERT OR REPLACE INTO gene_set_details
                   (gene_set_id, description_brief, description_full, systematic_name,
                    exact_source, external_details_URL, source_species_code,
                    primary_namespace_id, num_namespaces, contrib_organization)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    gene_set_id,
                    description_brief or None,
                    description_full or None,
                    gene_set_name,
                    exact_source,
                    external_url,
                    species_code,
                    primary_namespace_id,
                    1,
                    contrib_organization,
                )
            )
        except sqlite3.IntegrityError as e:
            logger.warning(f"gene_set_details insert error for {gene_set_name} (id={gene_set_id}): {e}")
        except Exception as e:
            logger.error(f"Error inserting gene_set_details for {gene_set_name}: {e}")

    def insert_provenance(
        self,
        gene_set_id: int,
        provenance_graph: str,
        geneset_metadata: str,
        run_summary: str = None
    ):
        """Insert provenance record."""
        try:
            self.cursor.execute(
                'INSERT INTO provenance (gene_set_id, provenance_graph, geneset_metadata, run_summary) VALUES (?, ?, ?, ?)',
                (gene_set_id, provenance_graph, geneset_metadata, run_summary)
            )
        except sqlite3.IntegrityError as e:
            logger.warning(f"Provenance insert error for gene_set_id {gene_set_id}: {e}")

    def insert_provenance_nodes_and_edges(
        self,
        gene_set_id: int,
        provenance_json_str: str,
        geneset_node_name: str = None,
        geneset_node_name_match: str = None
    ) -> int:
        """
        Insert provenance nodes and edges from provenance JSON string.
        
        The GeneSet node gets provenance_node_id = gene_set_id.
        Other nodes get sequential auto-assigned IDs.
        
        Args:
            gene_set_id: ID of the gene set (also used for the GeneSet node)
            provenance_json_str: Full provenance JSON as string (parsed from geneset.provenance.json)
            geneset_node_name: If provided, override the GeneSet node's `name` field with this value
                (used to keep gene_set.standard_name and provenance_node.name in sync).
            geneset_node_name_match: Reserved for future variant-disambiguation; currently unused.
        
        Returns:
            The maximum provenance_node_id used, or 0 if no nodes/edges were inserted.
        """
        max_node_id_used = 0
        
        try:
            provenance_data = json.loads(provenance_json_str)
            logger.debug(f"Provenance JSON type: {type(provenance_data).__name__}")
            
            # Handle different JSON structures
            nodes_to_process = []
            edges_to_process = []
            
            if isinstance(provenance_data, dict):
                # Check if nodes/edges are at top level
                if 'nodes' in provenance_data and 'edges' in provenance_data:
                    nodes_to_process = provenance_data.get('nodes', [])
                    edges_to_process = provenance_data.get('edges', [])
                    logger.debug(f"Found nodes/edges at top level: {len(nodes_to_process)} nodes, {len(edges_to_process)} edges")
                else:
                    # Otherwise iterate through top-level keys looking for nodes/edges
                    for gs_key, gs_data in provenance_data.items():
                        if isinstance(gs_data, dict):
                            if 'nodes' in gs_data or 'edges' in gs_data:
                                nodes_to_process.extend(gs_data.get('nodes', []))
                                edges_to_process.extend(gs_data.get('edges', []))
                    logger.debug(f"Found nodes/edges in nested structure: {len(nodes_to_process)} nodes, {len(edges_to_process)} edges")
            elif isinstance(provenance_data, list):
                logger.debug("Provenance JSON is a list - may need different handling")
                return max_node_id_used
            
            if not nodes_to_process and not edges_to_process:
                logger.debug(f"No nodes or edges found in provenance JSON for gene_set_id {gene_set_id}")
                return max_node_id_used
            
            # Reorder: insert GeneSet nodes FIRST so their reserved provenance_node_id
            # (= gene_set_id) is taken before any non-GeneSet node gets auto-assigned.
            # Otherwise, a non-GeneSet node processed first would receive id=gene_set_id
            # and then be overwritten by the GeneSet node's INSERT OR REPLACE.
            nodes_to_process = sorted(
                nodes_to_process,
                key=lambda n: 0 if n.get('type') == 'GeneSet' else 1
            )
            
            # Mapping from original JSON node ID to new provenance_node_id
            node_id_mapping = {}
            
            # Insert nodes
            nodes_inserted = 0
            for node in nodes_to_process:
                original_id = node.get('id')
                node_type = node.get('type', '')
                name = node.get('name', '')
                # Override GeneSet node name to keep it in sync with gene_set.standard_name
                if node_type == 'GeneSet' and geneset_node_name:
                    name = geneset_node_name
                description = node.get('description', '')
                dcc_url = node.get('dcc_url')
                drc_url = node.get('drc_url')
                
                # Collect all properties except the main ones we extracted
                additional_props = {
                    'original_id': original_id
                }
                
                # Store all other fields (c2m2_properties, analysis, etc.)
                for key, value in node.items():
                    if key not in ['id', 'type', 'name', 'description', 'dcc_url', 'drc_url']:
                        additional_props[key] = value
                
                additional_properties = json.dumps(additional_props)
                
                try:
                    # For GeneSet nodes, use gene_set_id as the provenance_node_id (use INSERT OR REPLACE to handle re-runs)
                    if node_type == 'GeneSet':
                        self.cursor.execute(
                            '''INSERT OR REPLACE INTO provenance_node 
                               (provenance_node_id, gene_set_id, node_type, name, description, dcc_url, drc_url, additional_properties)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (gene_set_id, gene_set_id, node_type, name, description, dcc_url, drc_url, additional_properties)
                        )
                        new_node_id = gene_set_id
                    else:
                        self.cursor.execute(
                            '''INSERT INTO provenance_node 
                               (gene_set_id, node_type, name, description, dcc_url, drc_url, additional_properties)
                               VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (gene_set_id, node_type, name, description, dcc_url, drc_url, additional_properties)
                        )
                        new_node_id = self.cursor.lastrowid
                    
                    node_id_mapping[original_id] = new_node_id
                    max_node_id_used = max(max_node_id_used, new_node_id)
                    nodes_inserted += 1
                except sqlite3.IntegrityError as e:
                    logger.warning(f"Error inserting node {original_id} for gene_set_id {gene_set_id}: {e}")
                    continue
            
            logger.debug(f"Inserted {nodes_inserted} nodes for gene_set_id {gene_set_id}, max node ID used: {max_node_id_used}")
            
            # Insert edges
            edges_inserted = 0
            for edge in edges_to_process:
                source_original_id = edge.get('source')
                target_original_id = edge.get('target')
                label = edge.get('label', '')
                description = edge.get('description', '')
                
                # Look up new node IDs
                source_node_id = node_id_mapping.get(source_original_id)
                target_node_id = node_id_mapping.get(target_original_id)
                
                if not source_node_id or not target_node_id:
                    logger.debug(
                        f"Skipping edge: source={source_original_id}, target={target_original_id} - "
                        f"nodes not found in mapping"
                    )
                    continue
                
                # Collect all properties except the main ones
                additional_props = {
                    'original_id': edge.get('id')
                }
                
                for key, value in edge.items():
                    if key not in ['id', 'source', 'target', 'label', 'description']:
                        additional_props[key] = value
                
                additional_properties = json.dumps(additional_props) if additional_props else None
                
                try:
                    self.cursor.execute(
                        '''INSERT INTO provenance_edge
                           (gene_set_id, source_node_id, target_node_id, label, description, additional_properties)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (gene_set_id, source_node_id, target_node_id, label, description, additional_properties)
                    )
                    edges_inserted += 1
                except sqlite3.IntegrityError as e:
                    logger.warning(f"Error inserting edge {edge.get('id')}: {e}")
                    continue
            
            logger.debug(f"Inserted {edges_inserted} edges for gene_set_id {gene_set_id}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding provenance JSON for gene_set_id {gene_set_id}: {e}")
            logger.debug(f"JSON string (first 500 chars): {provenance_json_str[:500]}")
        except Exception as e:
            logger.error(f"Error inserting provenance nodes/edges for gene_set_id {gene_set_id}: {e}", exc_info=True)
        
        return max_node_id_used

    def populate_from_gmt_files(
        self,
        root_path: str,
        collection_name: str = 'GTEx',
        species_code: str = 'Homo_sapiens',
        species_name: str = 'Homo sapiens',
        namespace_label: str = 'HGNC',
        license_code: str = 'CC-BY-4.0',
        require_provenance: bool = True,
        contrib_organization: str = None
    ):
        """Populate database from GMT files."""
        try:
            root = Path(root_path)
            
            # Find all GMT files
            gmt_files = self.find_gmt_files(root_path)
            if not gmt_files:
                logger.warning("No .gmt files found")
                return
            
            # Initialize reference data
            logger.info("Initializing reference data...")
            species_id = self.insert_species(species_code, species_name)
            namespace_id = self.insert_namespace(namespace_label, species_code)
            collection_id = self.insert_collection(collection_name)
            license_id = self.insert_gene_set_license(license_code)
            
            # Process each GMT file
            total_gene_sets = 0
            total_genes = 0
            skipped_gene_sets = 0
            
            for gmt_file in gmt_files:
                logger.info(f"Processing GMT file: {gmt_file}")
                gene_sets = self.parse_gmt_file(gmt_file)
                
                for gene_set_name, genes in gene_sets:
                    try:
                        # Derive tissue from path: .../genesets/{tissue}/models/{model_id}/tissue_extractor/genesets.gmt
                        tissue = None
                        for ancestor in gmt_file.parents:
                            if ancestor.name == 'models' and ancestor.parent is not None:
                                tissue = ancestor.parent.name
                                break
                        
                        # Build unified standard name: {collection}__{tissue}__{gene_set_name}
                        if tissue:
                            standard_name = f"{collection_name}__{tissue}__{gene_set_name}"
                        else:
                            standard_name = f"{collection_name}__{gene_set_name}"
                        
                        # Load provenance and metadata if required
                        provenance_data = None
                        if require_provenance:
                            provenance_data = self.load_provenance_and_metadata(gene_set_name, gmt_file.parent)
                            if not provenance_data:
                                logger.debug(f"Skipping {gene_set_name} - provenance/metadata files not found")
                                skipped_gene_sets += 1
                                continue
                        
                        # Assign gene_set_id = next_available_node_id (for ID spacing)
                        gene_set_id = self.next_available_node_id
                        
                        # Insert gene set with explicit ID
                        gene_set_id = self.insert_gene_set(
                            standard_name=standard_name,
                            collection_name=collection_name,
                            license_code=license_code,
                            gene_set_id=gene_set_id
                        )
                        
                        if not gene_set_id:
                            logger.warning(f"Failed to insert gene set: {standard_name}")
                            continue
                        
                        # Insert genes and create associations
                        for gene_symbol in genes:
                            gene_symbol_id = self.insert_gene_symbol(
                                symbol=gene_symbol,
                                namespace_id=namespace_id
                            )
                            
                            if gene_symbol_id:
                                self.insert_gene_set_gene_symbol(gene_set_id, gene_symbol_id)
                                total_genes += 1
                        
                        # Insert provenance if available
                        max_node_id = 0
                        if provenance_data:
                            provenance_graph, geneset_metadata, run_summary = provenance_data
                            self.insert_provenance(gene_set_id, provenance_graph, geneset_metadata, run_summary)
                            # Populate gene_set_details from metadata JSON
                            self.insert_gene_set_details(
                                gene_set_id=gene_set_id,
                                gene_set_name=standard_name,
                                metadata_json_str=geneset_metadata,
                                species_code=species_code,
                                primary_namespace_id=namespace_id,
                                contrib_organization=contrib_organization,
                            )
                            if provenance_graph:
                                max_node_id = self.insert_provenance_nodes_and_edges(
                                    gene_set_id, provenance_graph,
                                    geneset_node_name=standard_name,
                                    geneset_node_name_match=gene_set_name
                                )
                        
                        # Always advance next_available_node_id past this gene set's used IDs,
                        # so the next gene set never collides (even if provenance was missing/empty).
                        self.next_available_node_id = max(gene_set_id, max_node_id) + 1
                        
                        total_gene_sets += 1
                        logger.info(
                            f"Loaded gene set '{standard_name}' (id={gene_set_id}, "
                            f"{len(genes)} genes) from {gmt_file}"
                        )
                        
                        if total_gene_sets % 100 == 0:
                            logger.info(f"Progress: {total_gene_sets} gene sets, {total_genes} gene associations so far")
                            self.conn.commit()
                    
                    except Exception as e:
                        logger.error(f"Error processing gene set {gene_set_name}: {e}")
                        continue
            
            # Final commit
            self.conn.commit()
            logger.info(f"Population complete: {total_gene_sets} gene sets, {total_genes} gene associations")
            if skipped_gene_sets > 0:
                logger.info(f"Skipped {skipped_gene_sets} gene sets (missing provenance/metadata)")
        
        except Exception as e:
            logger.error(f"Error during population: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description='Populate GenSeCoDB database from GMT gene set files'
    )
    parser.add_argument(
        '--db-path',
        required=True,
        help='Path to SQLite database file'
    )
    parser.add_argument(
        '--schema-file',
        required=True,
        help='Path to database schema SQL file'
    )
    parser.add_argument(
        '--data-root',
        required=True,
        help='Root directory containing GMT files'
    )
    parser.add_argument(
        '--collection-name',
        default='GTEx',
        help='Collection name (default: GTEx)'
    )
    parser.add_argument(
        '--species-code',
        default='Homo_sapiens',
        help='Species code (default: Homo_sapiens)'
    )
    parser.add_argument(
        '--species-name',
        default='Homo sapiens',
        help='Species full name (default: Homo sapiens)'
    )
    parser.add_argument(
        '--namespace-label',
        default='HGNC',
        help='Gene namespace label (default: HGNC)'
    )
    parser.add_argument(
        '--license-code',
        default='CC-BY-4.0',
        help='License code (default: CC-BY-4.0)'
    )
    parser.add_argument(
        '--contrib-organization',
        default='GTEx Consortium',
        help='Contributing organization for gene_set_details (default: GTEx Consortium)'
    )
    parser.add_argument(
        '--require-provenance',
        action='store_true',
        default=True,
        help='Only include gene sets with provenance/metadata files (default: True)'
    )
    parser.add_argument(
        '--skip-provenance-check',
        action='store_true',
        help='Include all gene sets regardless of provenance/metadata availability'
    )
    
    args = parser.parse_args()
    
    # Determine whether to require provenance
    require_provenance = not args.skip_provenance_check
    
    # Populate database
    populator = GeneSeCoDatabasePopulator(args.db_path)
    populator.connect()
    
    try:
        # Initialize schema
        populator.initialize_schema(args.schema_file)
        
        # Populate data
        populator.populate_from_gmt_files(
            root_path=args.data_root,
            collection_name=args.collection_name,
            species_code=args.species_code,
            species_name=args.species_name,
            namespace_label=args.namespace_label,
            license_code=args.license_code,
            require_provenance=require_provenance,
            contrib_organization=args.contrib_organization,
        )
    finally:
        populator.disconnect()


if __name__ == '__main__':
    main()
