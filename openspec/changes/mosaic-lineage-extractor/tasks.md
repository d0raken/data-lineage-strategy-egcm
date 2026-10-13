## 1. Setup e Estrutura do Pacote

- [x] 1.1 Criar estrutura do pacote `mosaic_lineage` e arquivo `requirements.txt`
- [x] 1.2 Implementar módulo de configuração `mosaic_lineage/config.py` com suporte a variáveis de ambiente (`.env`) e argumentos CLI priorizando `MSTR_PROJECT_ID`

## 2. Cliente REST e Extração de Modelos

- [x] 2.1 Implementar `MosaicClient` em `mosaic_lineage/client.py` integrando autenticação via `mstrio.connection.Connection` e requisições REST autenticadas
- [x] 2.2 Implementar extração de metadados do modelo e listagem via `/api/model/dataModels`
- [x] 2.3 Implementar extração de métricas e métricas de fato via `/api/model/dataModels/{dataModelId}/metrics` e `/factMetrics`
- [x] 2.4 Implementar extração de atributos e relacionamentos via `/api/model/dataModels/{dataModelId}/attributes` e `/relationships`

## 3. Resolução de Métricas e Modelagem de Dados

- [x] 3.1 Definir schemas e dataclasses para entidades do modelo (`Metric`, `Attribute`, `Relationship`, `Node`, `Edge`) em `mosaic_lineage/models.py`
- [x] 3.2 Implementar `MetricParser` em `mosaic_lineage/metric_parser.py` para interpretar fórmulas textuais, tokens de expressão e dependências

## 4. Construção do Grafo e Exportadores

- [x] 4.1 Implementar `GraphBuilder` em `mosaic_lineage/graph.py` para conectar modelos, atributos, métricas e tabelas em um DAG
- [x] 4.2 Implementar exportador para JSON (Graph Node-Link), YAML (catálogo hierárquico) e CSV (tabelas normalizadas `nodes`, `edges`, `metrics`) em `mosaic_lineage/exporters.py`
- [x] 4.3 Implementar CLI executável em `mosaic_lineage/cli.py` e script de entrada na raiz `extract_lineage.py`

## 5. Validação e Testes Iniciais

- [x] 5.1 Criar testes unitários com mocks das respostas dos endpoints REST da Strategy
- [x] 5.2 Validar geração de arquivos de saída JSON, YAML e CSV a partir de fixtures de modelo Mosaic

## 6. Publicação Inicial de Cubo no Strategy (Sankey)

- [x] 6.1 Implementar `CubePublisher` em `mosaic_lineage/cube_publisher.py` com resolução de pasta em `Public Objects > Reports`
- [x] 6.2 Integrar flags `--publish-cube` e `--cube-folder` na CLI `mosaic_lineage/cli.py`
- [x] 6.3 Adicionar testes unitários para geração de DataFrames do cubo e fluxo Sankey

## 7. Linhagem End-to-End (Data Sources e Dependentes Downstream)

- [x] 7.1 Implementar `get_datasource_info(model_id)` em `mosaic_lineage/client.py` usando `export_sql_view()` e `/api/datasources`
- [x] 7.2 Implementar `get_dependents(model_id)` em `mosaic_lineage/client.py` usando `SuperCube.list_dependents()` e mapeamento de tipos (Dossier, Report, Bot/Agent)
- [x] 7.3 Atualizar `GraphBuilder` em `mosaic_lineage/graph.py` para sintetizar a cadeia contínua de 5 estágios (`datasource` -> `table` -> `data_model` -> `attribute`/`metric` -> `dependent_object`)
- [x] 7.4 Atualizar `CubePublisher` em `mosaic_lineage/cube_publisher.py` para alimentar `Lineage_Sankey` com o fluxo contínuo
- [x] 7.5 Atualizar testes unitários em `tests/test_mosaic_lineage.py` para validar a cadeia de 5 estágios
- [x] 7.6 Validar execução real no Strategy e atualizar documentação [README.md](file:///c:/Users/erik.marinho/OneDrive/C%C3%B3digos/Data%20Lineage Strategy EGCM/README.md)

## 8. Desnormalização de Estágios em Lineage_Sankey (DB, Tabela, Modelo, Objetos, Dependentes)

- [x] 8.1 Atualizar `CubePublisher.build_sankey_dataframe` para gerar caminhos desnormalizados com `source_name` (apenas DB), `table_name`, `model_name`, `object_name`, `object_type`, `dependent_name`, `dependent_type`, `weight`
- [x] 8.2 Atualizar testes unitários em `tests/test_mosaic_lineage.py` para validar schema e linhas desnormalizadas de `Lineage_Sankey`
- [x] 8.3 Atualizar documentação em [README.md](file:///c:/Users/erik.marinho/OneDrive/C%C3%B3digos/Data%20Lineage Strategy EGCM/README.md) demonstrando configuração no Dossier (Sankey multinível e comparação de modelos por fonte/tabela)
- [x] 8.4 Re-publicar cubos de teste no Strategy e validar schema no Dossier

## 9. Inclusão de Fórmulas em Lineage_Sankey e Harmonização de Relacionamentos

- [x] 9.1 Atualizar `CubePublisher.build_sankey_dataframe` para incluir colunas `formula`, `aggregation`, `is_compound` recuperando definições do catálogo de métricas
- [x] 9.2 Atualizar `CubePublisher.build_metrics_dataframe` para incluir `object_name` e `model_name` harmonizando relacionamentos nativos do Strategy
- [x] 9.3 Atualizar testes unitários em `tests/test_mosaic_lineage.py` para validar `formula` em `Lineage_Sankey` e chaves compartilhadas em `Metrics_Catalog`
- [x] 9.4 Atualizar documentação em [README.md](file:///c:/Users/erik.marinho/OneDrive/C%C3%B3digos/Data%20Lineage Strategy EGCM/README.md) demonstrando grid sem quebras (`source_name --> table_name --> model_name --> object_name --> formula`)
- [x] 9.5 Re-publicar cubos no Strategy e validar exibição de fórmulas no Dossier

## 10. Resolução Bilíngue de Pastas de Destino (Inglês e Português)

- [x] 10.1 Atualizar `CubePublisher.get_or_create_reports_folder` para resolver caminhos e buscas tanto em inglês (`Public Objects > Reports`) quanto em português (`Objetos Públicos > Relatórios`)
- [x] 10.2 Adicionar testes unitários para resolução bilíngue de pastas em `tests/test_mosaic_lineage.py`
- [x] 10.3 Re-executar publicação no projeto INCA (`067BACAAC045EE6F14D1B68684FDCA2F`) e validar criação bem-sucedida do cubo
