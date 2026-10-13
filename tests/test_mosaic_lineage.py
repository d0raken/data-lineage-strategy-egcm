"""Unit tests for Mosaic Data Lineage Extractor."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
import yaml

from mosaic_lineage.client import MosaicClient
from mosaic_lineage.config import Config
from mosaic_lineage.exporters import LineageExporter
from mosaic_lineage.graph import GraphBuilder
from mosaic_lineage.metric_parser import MetricParser


class TestMosaicLineage(unittest.TestCase):

    def test_metric_parser_atomic_and_compound(self):
        # 1. Métrica atômica (soma de fato)
        raw_atomic = {
            "id": "M_REV_001",
            "name": "Revenue",
            "expression": {
                "tokens": [
                    {"type": "function", "value": "Sum"},
                    {"type": "left_paren", "value": "("},
                    {"type": "object_reference", "value": "TOT_REV", "target": {"objectId": "F_REV_10", "name": "Fact_Revenue", "subType": "FACT"}},
                    {"type": "right_paren", "value": ")"}
                ]
            }
        }
        metric_def = MetricParser.parse_metric_dict(raw_atomic)
        self.assertEqual(metric_def.id, "M_REV_001")
        self.assertFalse(metric_def.is_compound)
        self.assertEqual(len(metric_def.referenced_objects), 1)
        self.assertEqual(metric_def.referenced_objects[0].object_id, "F_REV_10")
        self.assertIn("[Fact_Revenue]", metric_def.formula_text)

        # 2. Métrica composta (lucro = receita - custo)
        raw_compound = {
            "id": "M_PROFIT_002",
            "name": "Profit",
            "expression": {
                "tokens": [
                    {"type": "object_reference", "target": {"objectId": "M_REV_001", "name": "Revenue", "subType": "METRIC"}},
                    {"type": "operator", "value": "-"},
                    {"type": "object_reference", "target": {"objectId": "M_COST_003", "name": "Cost", "subType": "METRIC"}}
                ]
            }
        }
        comp_def = MetricParser.parse_metric_dict(raw_compound)
        self.assertEqual(comp_def.id, "M_PROFIT_002")
        self.assertTrue(comp_def.is_compound)
        self.assertEqual(len(comp_def.referenced_objects), 2)
        self.assertIn("[Revenue] - [Cost]", comp_def.formula_text)

    def test_graph_builder(self):
        model_meta = {
            "id": "DM_SALES",
            "name": "Sales Model",
            "description": "Enterprise sales semantic model",
            "tables": [{"id": "TBL_ORDERS", "name": "orders_fact", "datasource": "Snowflake"}]
        }
        attrs = [
            {
                "id": "ATTR_CUSTOMER",
                "name": "Customer",
                "forms": [{"id": "F_ID", "tables": [{"id": "TBL_ORDERS"}]}]
            },
            {
                "id": "ATTR_REGION",
                "name": "Region",
                "forms": []
            }
        ]
        relationships = [
            {"parentId": "ATTR_REGION", "childId": "ATTR_CUSTOMER", "type": "1_TO_N"}
        ]
        fact_metrics = [
            {"id": "FM_SALES_AMT", "name": "Sales Amount", "tableId": "TBL_ORDERS", "dataType": "DECIMAL"}
        ]
        metrics = [
            {
                "id": "M_TOTAL_SALES",
                "name": "Total Sales",
                "expression": {
                    "tokens": [
                        {"type": "function", "value": "Sum"},
                        {"type": "left_paren", "value": "("},
                        {"type": "object_reference", "target": {"objectId": "FM_SALES_AMT", "name": "Sales Amount", "subType": "FACT_METRIC"}},
                        {"type": "right_paren", "value": ")"}
                    ]
                }
            }
        ]

        builder = GraphBuilder()
        graph = builder.build_from_model_data(
            model_metadata=model_meta,
            attributes_data=attrs,
            metrics_data=metrics,
            fact_metrics_data=fact_metrics,
            relationships_data=relationships
        )

        # Valida nós
        self.assertIn("DM_SALES", graph.nodes)
        self.assertEqual(graph.nodes["DM_SALES"].type, "data_model")
        self.assertIn("ATTR_CUSTOMER", graph.nodes)
        self.assertIn("ATTR_REGION", graph.nodes)
        self.assertIn("FM_SALES_AMT", graph.nodes)
        self.assertIn("M_TOTAL_SALES", graph.nodes)
        self.assertIn("TBL_ORDERS", graph.nodes)

        # Valida arestas
        edge_types = [e.relationship_type for e in graph.edges]
        self.assertIn("contains", edge_types)
        self.assertIn("maps_to", edge_types)
        self.assertIn("relates_to", edge_types)
        self.assertIn("sources_from", edge_types)
        self.assertIn("calculates_from", edge_types)

        # Valida catálogo de métricas
        self.assertIn("M_TOTAL_SALES", graph.metrics_catalog)

    def test_exporters(self):
        builder = GraphBuilder()
        graph = builder.build_from_model_data(
            model_metadata={"id": "DM_TEST", "name": "Test"},
            attributes_data=[{"id": "A1", "name": "Attr1"}],
            metrics_data=[{"id": "M1", "name": "Met1", "formula": "Sum(1)"}],
            fact_metrics_data=[],
            relationships_data=[]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = LineageExporter(output_dir=tmpdir)
            exported = exporter.export(graph, format_type="all", prefix="test_lineage")

            # Verifica se arquivos foram criados
            self.assertTrue(Path(exported["json"]).is_file())
            self.assertTrue(Path(exported["yaml"]).is_file())
            self.assertTrue(Path(exported["csv_nodes"]).is_file())
            self.assertTrue(Path(exported["csv_edges"]).is_file())
            self.assertTrue(Path(exported["csv_metrics"]).is_file())

            # Valida integridade do JSON
            with open(exported["json"], "r", encoding="utf-8") as f:
                json_data = json.load(f)
                self.assertIn("nodes", json_data)
                self.assertIn("edges", json_data)
                self.assertIn("metrics_catalog", json_data)
                self.assertEqual(len(json_data["nodes"]), 3)

            # Valida integridade do YAML
            with open(exported["yaml"], "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
                self.assertEqual(yaml_data["summary"]["total_nodes"], 3)

    def test_client_mock_endpoints(self):
        mock_conn = MagicMock()
        mock_conn.base_url = "https://strategy.example.com/MicroStrategyLibrary/api"
        mock_conn.project_id = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": "M1", "name": "Metric 1"}]
        mock_conn.get.return_value = mock_response

        client = MosaicClient(config=Config(), connection=mock_conn)
        metrics = client.get_metrics("MODEL_123")

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["name"], "Metric 1")
        mock_conn.get.assert_called_with(endpoint="/model/dataModels/MODEL_123/metrics", params=None)

    def test_end_to_end_five_stage_lineage(self):
        builder = GraphBuilder()
        graph = builder.build_from_model_data(
            model_metadata={"id": "DM_SALES", "name": "Modelo de Vendas"},
            attributes_data=[{"id": "ATTR_PROD", "name": "Produto", "forms": [{"tables": [{"id": "TBL_VENDAS", "name": "vendas"}]}]}],
            metrics_data=[{"id": "M_TOTAL", "name": "Total Vendas"}],
            fact_metrics_data=[{"id": "FM_QTD", "name": "Quantidade", "table": {"id": "TBL_VENDAS", "name": "vendas"}}],
            relationships_data=[],
            datasource_data={"id": "DS_POSTGRES", "name": "Postgres DW", "type": "database_connection"},
            dependents_data=[
                {"id": "DOSS_01", "name": "Painel Executivo", "type": "dossier"},
                {"id": "BOT_01", "name": "Agente Financeiro", "type": "bot_agent"}
            ]
        )

        # Valida nós dos 5 estágios
        self.assertIn("DS_POSTGRES", graph.nodes)
        self.assertEqual(graph.nodes["DS_POSTGRES"].type, "datasource")
        self.assertIn("TBL_VENDAS", graph.nodes)
        self.assertEqual(graph.nodes["TBL_VENDAS"].type, "table")
        self.assertIn("DM_SALES", graph.nodes)
        self.assertEqual(graph.nodes["DM_SALES"].type, "data_model")
        self.assertIn("ATTR_PROD", graph.nodes)
        self.assertEqual(graph.nodes["ATTR_PROD"].type, "attribute")
        self.assertIn("DOSS_01", graph.nodes)
        self.assertEqual(graph.nodes["DOSS_01"].type, "dossier")
        self.assertIn("BOT_01", graph.nodes)
        self.assertEqual(graph.nodes["BOT_01"].type, "bot_agent")

        # Valida arestas da cadeia contínua
        edge_types = [e.relationship_type for e in graph.edges]
        self.assertIn("provides", edge_types)
        self.assertIn("feeds", edge_types)
        self.assertIn("defines", edge_types)
        self.assertIn("used_by", edge_types)

        # Valida DataFrame do Sankey contínuo e desnormalizado
        from mosaic_lineage.cube_publisher import CubePublisher
        publisher = CubePublisher(connection=MagicMock())
        df_sankey = publisher.build_sankey_dataframe(graph)

        self.assertGreater(len(df_sankey), 0)
        expected_cols = {
            "source_name", "table_name", "model_name",
            "object_name", "object_type",
            "formula", "aggregation", "is_compound",
            "dependent_name", "dependent_type", "weight"
        }
        self.assertTrue(expected_cols.issubset(set(df_sankey.columns)))

        # Valida que source_name contém apenas a fonte de dados (Postgres DW)
        self.assertEqual(set(df_sankey["source_name"].unique()), {"Postgres DW"})
        # Valida que table_name contém a tabela vendas
        self.assertEqual(set(df_sankey["table_name"].unique()), {"vendas"})
        # Valida que model_name contém o modelo
        self.assertEqual(set(df_sankey["model_name"].unique()), {"Modelo de Vendas"})
        # Valida objetos semânticos
        objects = set(df_sankey["object_name"].unique())
        self.assertIn("Produto", objects)
        self.assertIn("Total Vendas", objects)
        # Valida dependentes downstream
        dependents = set(df_sankey["dependent_name"].unique())
        self.assertIn("Painel Executivo", dependents)
        self.assertIn("Agente Financeiro", dependents)

    def test_cube_publisher_dataframes(self):
        from mosaic_lineage.cube_publisher import CubePublisher

        builder = GraphBuilder()
        graph = builder.build_from_model_data(
            model_metadata={"id": "DM_1", "name": "Model 1"},
            attributes_data=[{"id": "A1", "name": "Customer"}],
            metrics_data=[{"id": "M1", "name": "Revenue", "expression": {"tokens": [{"type": "object_reference", "target": {"objectId": "A1", "name": "Customer", "subType": "ATTRIBUTE"}}]}}],
            fact_metrics_data=[],
            relationships_data=[]
        )

        mock_conn = MagicMock()
        publisher = CubePublisher(connection=mock_conn)

        df_sankey = publisher.build_sankey_dataframe(graph)
        self.assertIn("source_name", df_sankey.columns)
        self.assertIn("table_name", df_sankey.columns)
        self.assertIn("model_name", df_sankey.columns)
        self.assertIn("object_name", df_sankey.columns)
        self.assertIn("formula", df_sankey.columns)
        self.assertIn("dependent_name", df_sankey.columns)
        self.assertIn("weight", df_sankey.columns)
        self.assertGreater(len(df_sankey), 0)

        df_metrics = publisher.build_metrics_dataframe(graph)
        self.assertIn("model_name", df_metrics.columns)
        self.assertIn("object_name", df_metrics.columns)
        self.assertIn("formula", df_metrics.columns)
        self.assertEqual(df_metrics.iloc[0]["object_name"], "Revenue")
        self.assertEqual(df_metrics.iloc[0]["model_name"], "Model 1")

        df_nodes = publisher.build_nodes_dataframe(graph)
        self.assertEqual(len(df_nodes), len(graph.nodes))

        df_edges = publisher.build_edges_dataframe(graph)
        self.assertEqual(len(df_edges), len(graph.edges))

    def test_bilingual_folder_resolution(self):
        from unittest.mock import patch
        from mosaic_lineage.cube_publisher import CubePublisher

        mock_conn = MagicMock()
        mock_conn.project_name = "INCA"
        mock_conn.project_id = "067BACAAC045EE6F14D1B68684FDCA2F"
        publisher = CubePublisher(connection=mock_conn)

        # Simula pasta encontrada via busca por "Relatórios"
        mock_search_item = MagicMock()
        mock_search_item.id = "FLD_RELATORIOS"
        mock_search_item.name = "Relatórios"
        mock_search_item.path = "/INCA/Objetos Públicos/Relatórios"

        mock_parent_folder = MagicMock()
        mock_parent_folder.id = "FLD_RELATORIOS"
        mock_parent_folder.name = "Relatórios"
        
        mock_subfolder = MagicMock()
        mock_subfolder.id = "FLD_LINEAGE"
        mock_subfolder.name = "Data Lineage"
        mock_parent_folder.get_contents.return_value = [mock_subfolder]

        with patch("mosaic_lineage.cube_publisher.Folder") as mock_folder_cls, \
             patch("mosaic_lineage.cube_publisher.full_search", return_value=[mock_search_item]):
            # Falha nas tentativas por path direto para acionar full_search
            def folder_side_effect(**kwargs):
                if kwargs.get("path"):
                    raise ValueError("Path not found")
                return mock_parent_folder

            mock_folder_cls.side_effect = folder_side_effect

            result = publisher.get_or_create_reports_folder(subfolder_name="Data Lineage")
            self.assertIsNotNone(result)

    def test_calculated_metrics_lineage_and_formula(self):
        """Valida que métricas calculadas aparecem com object_type='metric', herdando tabela dos fatos e com fórmula correta."""
        from mosaic_lineage.cube_publisher import CubePublisher

        model_meta = {
            "id": "DM_FINANCE",
            "name": "Modelo Financeiro",
            "description": "Modelo com métricas calculadas compostas"
        }
        attributes = [
            {"id": "ATTR_CONTA", "name": "Conta Contábil", "forms": [{"id": "F_ID", "tables": [{"id": "TBL_LANCAMENTOS", "name": "tb_lancamentos"}]}]}
        ]
        fact_metrics = [
            {"id": "FM_VALOR_BRUTO", "name": "Valor Bruto", "tableId": "TBL_LANCAMENTOS", "dataType": "DECIMAL", "function": "Sum"}
        ]
        metrics = [
            {
                "id": "M_IMPOSTO",
                "name": "Imposto Calculado",
                "expression": {
                    "text": "[Valor Bruto] * 0.15",
                    "tokens": [
                        {"type": "object_reference", "target": {"objectId": "FM_VALOR_BRUTO", "name": "Valor Bruto", "subType": "FACT_METRIC"}},
                        {"type": "operator", "value": "*"},
                        {"type": "constant", "value": "0.15"}
                    ]
                }
            },
            {
                "id": "M_VALOR_LIQUIDO",
                "name": "Valor Líquido",
                "expression": {
                    "text": "[Valor Bruto] - [Imposto Calculado]",
                    "tokens": [
                        {"type": "object_reference", "target": {"objectId": "FM_VALOR_BRUTO", "name": "Valor Bruto", "subType": "FACT_METRIC"}},
                        {"type": "operator", "value": "-"},
                        {"type": "object_reference", "target": {"objectId": "M_IMPOSTO", "name": "Imposto Calculado", "subType": "METRIC"}}
                    ]
                }
            }
        ]
        datasource = {"id": "DS_ORACLE", "name": "Oracle ERP"}

        builder = GraphBuilder()
        graph = builder.build_from_model_data(
            model_metadata=model_meta,
            attributes_data=attributes,
            metrics_data=metrics,
            fact_metrics_data=fact_metrics,
            relationships_data=[],
            datasource_data=datasource
        )

        publisher = CubePublisher(connection=MagicMock())
        df_sankey = publisher.build_sankey_dataframe(graph)

        # 1. Verifica presença de todos os tipos em object_type
        object_types = set(df_sankey["object_type"].unique())
        self.assertIn("attribute", object_types)
        self.assertIn("fact_metric", object_types)
        self.assertIn("metric", object_types)

        # 2. Verifica correspondência exata de fórmulas para métricas calculadas
        df_imposto = df_sankey[df_sankey["object_name"] == "Imposto Calculado"]
        self.assertFalse(df_imposto.empty)
        self.assertEqual(df_imposto.iloc[0]["formula"], "[Valor Bruto] * 0.15")
        self.assertEqual(df_imposto.iloc[0]["object_type"], "metric")
        # Rastreabilidade upstream resolvida via fato -> tabela
        self.assertEqual(df_imposto.iloc[0]["table_name"], "tb_lancamentos")
        self.assertEqual(df_imposto.iloc[0]["source_name"], "Oracle ERP")

        df_liq = df_sankey[df_sankey["object_name"] == "Valor Líquido"]
        self.assertFalse(df_liq.empty)
        self.assertEqual(df_liq.iloc[0]["formula"], "[Valor Bruto] - [Imposto Calculado]")
        self.assertEqual(df_liq.iloc[0]["object_type"], "metric")
        self.assertEqual(df_liq.iloc[0]["is_compound"], "True")
        self.assertEqual(df_liq.iloc[0]["table_name"], "tb_lancamentos")

        # 3. Verifica Metrics_Catalog
        df_cat = publisher.build_metrics_dataframe(graph)
        metric_names = set(df_cat["object_name"].unique())
        self.assertIn("Imposto Calculado", metric_names)
        self.assertIn("Valor Líquido", metric_names)


if __name__ == "__main__":
    unittest.main()
