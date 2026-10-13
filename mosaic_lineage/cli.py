"""CLI interface for Mosaic Data Lineage Extractor."""

import argparse
import logging
import sys
from typing import Optional
from mosaic_lineage.client import MosaicClient
from mosaic_lineage.config import Config, load_dotenv
from mosaic_lineage.cube_publisher import CubePublisher
from mosaic_lineage.exporters import LineageExporter
from mosaic_lineage.graph import GraphBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mosaic_lineage.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mosaic-lineage",
        description="Extrai Data Lineage e catálogo de métricas de modelos Mosaic no Strategy."
    )
    parser.add_argument("--base-url", dest="base_url", help="URL base da Library (ex: https://server/MicroStrategyLibrary/api)")
    parser.add_argument("--username", "-u", dest="username", help="Usuário Strategy")
    parser.add_argument("--password", "-p", dest="password", help="Senha Strategy")
    parser.add_argument("--project-id", dest="project_id", help="ID do projeto")
    parser.add_argument("--project-name", dest="project_name", help="Nome do projeto")
    parser.add_argument("--model-id", dest="model_id", help="ID do Data Model Mosaic")
    parser.add_argument("--format", "-f", dest="format", default="all", choices=["json", "yaml", "csv", "all"], help="Formato de exportação (padrão: all)")
    parser.add_argument("--output-dir", "-o", dest="output_dir", default="./output", help="Diretório de saída (padrão: ./output)")
    parser.add_argument("--env-file", dest="env_file", help="Caminho para arquivo .env")
    parser.add_argument("--list-models", action="store_true", help="Lista todos os modelos Mosaic disponíveis no projeto")
    parser.add_argument("--publish-cube", dest="publish_cube", nargs="?", const="Mosaic Lineage Cube", help="Publica o grafo diretamente em um Cubo no Strategy para criação de Sankey no Dossier")
    parser.add_argument("--cube-folder", dest="cube_folder", default="Data Lineage", help="Nome da subpasta dentro de 'Public Objects > Reports' (padrão: Data Lineage)")
    parser.add_argument("--insecure", action="store_true", help="Desabilita verificação SSL")
    return parser


def main(args: Optional[list] = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)

    load_dotenv(parsed.env_file)

    cfg = Config()
    if parsed.base_url:
        cfg.base_url = parsed.base_url
    if parsed.username:
        cfg.username = parsed.username
    if parsed.password:
        cfg.password = parsed.password
    if parsed.project_id:
        cfg.project_id = parsed.project_id
    if parsed.project_name:
        cfg.project_name = parsed.project_name
    if parsed.model_id:
        cfg.data_model_id = parsed.model_id
    if parsed.format:
        cfg.export_format = parsed.format
    if parsed.output_dir:
        cfg.output_dir = parsed.output_dir
    if parsed.insecure:
        cfg.ssl_verify = False

    try:
        cfg.validate(require_model_id=not parsed.list_models)
    except ValueError as e:
        logger.error("Erro de configuração: %s", e)
        if "data_model_id" in str(e):
            print("\nDica: Para listar modelos disponíveis use: python extract_lineage.py --list-models")
            print("Ou informe o ID do modelo: python extract_lineage.py --model-id <GUID>\n")
        return 1

    client = MosaicClient(config=cfg)

    # 1. Modo de listagem de modelos
    if parsed.list_models:
        logger.info("Consultando Data Models disponíveis...")
        models = client.list_data_models()
        print(f"\nModelos encontrados ({len(models)}):")
        for m in models:
            m_id = m.get("id") or m.get("modelId")
            m_name = m.get("name") or m.get("modelName")
            print(f"  - [{m_id}] {m_name}")
        return 0

    # 2. Modo de extração de lineage
    model_id = cfg.data_model_id
    logger.info("Extraindo metadados do modelo %s...", model_id)
    try:
        model_meta = client.get_data_model(model_id)
    except Exception as e:
        logger.warning("Falha ao obter metadados raiz do modelo (%s), prosseguindo com ID básico.", e)
        model_meta = {"id": model_id, "name": model_id}

    logger.info("Consultando atributos...")
    attributes = client.get_attributes(model_id)

    logger.info("Consultando métricas...")
    metrics = client.get_metrics(model_id)
    if not metrics and isinstance(model_meta, dict):
        metrics = model_meta.get("metrics") or model_meta.get("calculatedMetrics") or []
    if metrics:
        logger.info("Métricas calculadas encontradas: %d", len(metrics))

    logger.info("Consultando fact metrics...")
    fact_metrics = client.get_fact_metrics(model_id)

    logger.info("Consultando relacionamentos...")
    relationships = client.get_relationships(model_id, attributes=attributes)

    logger.info("Consultando fonte de dados upstream...")
    datasource_info = client.get_datasource_info(model_id)
    if datasource_info:
        logger.info("Fonte de dados identificada: %s (id: %s)", datasource_info.get("name"), datasource_info.get("id"))

    logger.info("Consultando objetos dependentes downstream...")
    dependents = client.get_dependents(model_id)
    if dependents:
        logger.info("Objetos dependentes encontrados (%d): %s", len(dependents), ", ".join([d["name"] for d in dependents[:3]]))

    logger.info("Construindo grafo de linhagem...")
    builder = GraphBuilder()
    graph = builder.build_from_model_data(
        model_metadata=model_meta,
        attributes_data=attributes,
        metrics_data=metrics,
        fact_metrics_data=fact_metrics,
        relationships_data=relationships,
        datasource_data=datasource_info,
        dependents_data=dependents
    )

    logger.info(
        "Grafo construído: %d nós, %d arestas, %d métricas catalogadas.",
        len(graph.nodes), len(graph.edges), len(graph.metrics_catalog)
    )

    exporter = LineageExporter(output_dir=cfg.output_dir)
    exported = exporter.export(graph, format_type=cfg.export_format, prefix=f"mosaic_{model_id[:8]}")

    print("\nArquivos exportados:")
    for k, path in exported.items():
        print(f"  - [{k}]: {path}")

    # 3. Publicação em Cubo no Strategy
    if parsed.publish_cube:
        cube_name = parsed.publish_cube
        subfolder_name = parsed.cube_folder
        logger.info("Iniciando publicação no Cubo '%s' em 'Public Objects > Reports > %s'...", cube_name, subfolder_name)
        publisher = CubePublisher(connection=client.connection)
        cube = publisher.publish(graph=graph, cube_name=cube_name, subfolder_name=subfolder_name)
        print(f"\nCubo publicado no Strategy: '{cube.name}' (ID: {cube.id}) na pasta 'Public Objects > Reports > {subfolder_name}'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
