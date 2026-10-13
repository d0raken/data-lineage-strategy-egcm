"""Exporters for lineage graphs into JSON, YAML and CSV formats."""

import csv
import json
from pathlib import Path
from typing import Any, Dict
import yaml
from mosaic_lineage.models import LineageGraph


class LineageExporter:
    """Exporta o grafo de linhagem e catálogo de métricas em múltiplos formatos."""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, graph: LineageGraph, format_type: str = "json", prefix: str = "lineage") -> Dict[str, str]:
        """Exporta de acordo com o formato solicitado ('json', 'yaml', 'csv', 'all')."""
        fmt = format_type.lower()
        exported_files: Dict[str, str] = {}

        if fmt in ("json", "all"):
            exported_files.update(self.to_json(graph, prefix))
        if fmt in ("yaml", "yml", "all"):
            exported_files.update(self.to_yaml(graph, prefix))
        if fmt in ("csv", "all"):
            exported_files.update(self.to_csv(graph, prefix))

        return exported_files

    def to_json(self, graph: LineageGraph, prefix: str) -> Dict[str, str]:
        """Exporta para JSON em formato Node-Link e dicionário de métricas."""
        data = graph.to_dict()
        out_file = self.output_dir / f"{prefix}_graph.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return {"json": str(out_file)}

    def to_yaml(self, graph: LineageGraph, prefix: str) -> Dict[str, str]:
        """Exporta para YAML estruturado e legível para GitOps."""
        data = graph.to_dict()
        out_file = self.output_dir / f"{prefix}_catalog.yaml"
        with open(out_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)
        return {"yaml": str(out_file)}

    def to_csv(self, graph: LineageGraph, prefix: str) -> Dict[str, str]:
        """Exporta tabelas relacionais normalizadas (nodes.csv, edges.csv, metrics.csv)."""
        nodes_file = self.output_dir / f"{prefix}_nodes.csv"
        edges_file = self.output_dir / f"{prefix}_edges.csv"
        metrics_file = self.output_dir / f"{prefix}_metrics.csv"

        # 1. Nodes CSV
        with open(nodes_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["node_id", "node_name", "node_type", "properties_json"])
            for n in graph.nodes.values():
                writer.writerow([n.id, n.name, n.type, json.dumps(n.properties, ensure_ascii=False)])

        # 2. Edges CSV
        with open(edges_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source_id", "target_id", "relationship_type", "properties_json"])
            for e in graph.edges:
                writer.writerow([e.source_id, e.target_id, e.relationship_type, json.dumps(e.properties, ensure_ascii=False)])

        # 3. Metrics definitions CSV
        with open(metrics_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "metric_id", "metric_name", "sub_type", "formula",
                "aggregation", "is_compound", "dependencies_count", "dependencies_ids"
            ])
            for m in graph.metrics_catalog.values():
                dep_ids = ";".join([ref.object_id for ref in m.referenced_objects])
                writer.writerow([
                    m.id,
                    m.name,
                    m.sub_type,
                    m.formula_text,
                    m.aggregation or "",
                    m.is_compound,
                    len(m.referenced_objects),
                    dep_ids
                ])

        return {
            "csv_nodes": str(nodes_file),
            "csv_edges": str(edges_file),
            "csv_metrics": str(metrics_file)
        }
