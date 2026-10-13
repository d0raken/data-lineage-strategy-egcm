# Strategy Mosaic Data Lineage Extractor

Ferramenta CLI para extração automatizada de linhagem de dados ponta a ponta (**End-to-End Lineage**) de **Mosaic Data Models** no Strategy e publicação direta de **SuperCube** para visualização em **Sankey Diagram** no Dossier.

---

## 1. Visão Geral do Fluxo End-to-End no Sankey

O extrator mapeia o ciclo de vida analítico completo em uma cadeia contínua de 5 estágios:

```
[1. Fonte de Dados] ──▶ [2. Tabelas] ──▶ [3. Modelo Mosaic] ──▶ [4. Atributos / Métricas] ──▶ [5. Dependentes]
  (source_name)          (table_name)       (model_name)           (object_name)                (dependent_name)
  (DB Instance /         (Tabelas lógicas   (Modelo semântico      (Camada analítica            (Dossiers, Reports,
   Postgres DW)           e físicas)         central)               exposta)                     Bots / Agentes de IA)
```

Na tabela `Lineage_Sankey` do SuperCube, cada registro representa um caminho completo desnormalizado através dos 5 estágios:
- `source_name`: **Apenas o banco de dados / instância de conexão de origem** (DB Instance)
- `table_name`: **Tabela física ou lógica utilizada**
- `model_name`: **Modelo analítico Mosaic**
- `object_name`: **Atributo ou métrica criada** (`object_type`: `attribute`, `fact_metric`, `metric`)
- `dependent_name`: **Artefato consumidor downstream** (`dependent_type`: `dossier`, `report`, `bot_agent` ou `(Nenhum)`)

Isso permite verificar diretamente se múltiplos modelos foram construídos sobre a mesma fonte de dados e se compartilham ou utilizam tabelas diferentes.

---

## 2. Pré-requisitos e Instalação

- Python 3.10+
- Instalar dependências:

```powershell
pip install -r requirements.txt
```

---

## 3. Configuração (`.env`)

Edite o arquivo `.env` na raiz do projeto:

```ini
# Configuração obrigatória do ambiente Strategy
MSTR_BASE_URL="https://studio.strategy.com/MicroStrategyLibrary/api"
MSTR_USERNAME="seu_usuario"
MSTR_PASSWORD="sua_senha"
MSTR_PROJECT_ID="0253E97B74004755A321AF8612DA3271"

# Opcionais
MSTR_DATA_MODEL_ID=""
MSTR_EXPORT_FORMAT="all"
MSTR_OUTPUT_DIR="./output"
MSTR_SSL_VERIFY="true"
```

---

## 4. Como Usar

### 4.1. Listar Data Models Disponíveis no Projeto

```powershell
python extract_lineage.py --list-models
```
*Lista todos os 39+ Mosaic Data Models do projeto com seus respectivos GUIDs.*

---

### 4.2. Extrair Linhagem e Publicar SuperCube End-to-End no Strategy (Recomendado)

Extrai fontes de dados, tabelas, modelo, atributos, métricas e dependentes downstream, publicando o SuperCube pronto para consumo na pasta `Public Objects > Reports > Data Lineage`:

```powershell
python extract_lineage.py --model-id "3B9C79AD848B478BBA3419E39C2CACBF" --publish-cube "Video Games End-to-End Lineage" --cube-folder "Data Lineage" --format all
```

---

### 4.3. Extrair Linhagem Apenas para Arquivos Locais

```powershell
python extract_lineage.py --model-id "3B9C79AD848B478BBA3419E39C2CACBF" --format all
```

**Arquivos gerados em `output/`:**
- `mosaic_<ID>_graph.json`: Grafo completo (nós, arestas e propriedades dos 5 estágios).
- `mosaic_<ID>_catalog.yaml`: Catálogo semântico legível com resumo e dependências.
- `mosaic_<ID>_nodes.csv`: Tabela normalizada de nós (`node_id`, `node_name`, `node_type`, `properties`).
- `mosaic_<ID>_edges.csv`: Tabela normalizada de arestas (`source_id`, `target_id`, `relationship_type`).
- `mosaic_<ID>_metrics.csv`: Catálogo de métricas e fórmulas decompostas.

---

## 5. Estrutura do SuperCube Publicado

O cubo publicado contém 4 tabelas relacionais em memória com relacionamentos nativos harmonizados:

1. **`Lineage_Sankey`** (Pronto para Sankey de 6 níveis e Grades com fórmulas):
   - `source_name`: Nome da conexão/banco (ex: `postgres_emarinho`, `Oracle ERP`)
   - `table_name`: Nome da tabela (ex: `video_game_sales`, `tb_lancamentos`)
   - `model_name`: Nome do modelo analítico (ex: `Video Games`)
   - `object_name`: Nome do atributo ou da fact metric de origem (ex: `Platform`, `Valor Bruto`)
   - `object_type`: Tipo do objeto base (`attribute` ou `fact_metric`)
   - `metric_name`: Nome da métrica calculada associada (ex: `Valor Líquido`) ou `(Direto)` quando o atributo/fato é consumido diretamente sem intermediários
   - `formula`: **Fórmula resolvida da métrica** (expressão matemática para `metric`, agregação para `fact_metric` ou `'N/A'` para atributos)
   - `aggregation`: Tipo de agregação da métrica (ex: `Sum`, `Avg` ou `'None'`)
   - `is_compound`: Indicador de métrica composta (`'True'`, `'False'` ou `'N/A'`)
   - `dependent_name`: Nome do artefato consumidor (ex: `Torre de Controle - Expo`) ou `(Nenhum)`
   - `dependent_type`: Tipo do dependente (`dossier`, `report`, `bot_agent`, `none`)
   - `weight`: Métrica de contagem / peso (numérico = `1`)
2. **`Nodes`**: Catálogo estrutural completo de entidades (`node_id`, `node_name`, `node_type`, `properties`).
3. **`Edges`**: Conexões direcionadas do grafo DAG (`source_id`, `target_id`, `relationship_type`).
4. **`Metrics_Catalog`**: Métricas atômicas e compostas, fórmulas e dependências (contendo `model_name` e `object_name` para cruzamento nativo com `Lineage_Sankey`).

---

## 6. Como Montar a Visualização no Dossier

### 6.1. Sankey Diagram Multinível de 6 Níveis (Fluxo Contínuo)
1. No **Strategy Web** ou **Library Web**, crie um novo **Dossier**.
2. Adicione os dados do cubo publicado em:
   `Public Objects` > `Reports` > `Data Lineage` > selecione o Cubo.
3. Insira uma visualização do tipo **Sankey Diagram**.
4. Arraste os atributos da tabela `Lineage_Sankey` para as zonas de categorias/níveis:
   - **Nível 1**: `source_name` (Banco de Dados)
   - **Nível 2**: `table_name` (Tabela)
   - **Nível 3**: `model_name` (Modelo de Dados)
   - **Nível 4**: `object_name` (Atributos e Fact Metrics)
   - **Nível 5**: `metric_name` (Métricas Calculadas ou `(Direto)`)
   - **Nível 6**: `dependent_name` (Dossiers, Relatórios e Agentes)
   - **Métrica / Peso**: `weight`
5. O visual exibirá o fluxo conectando diretamente:
   `Banco ──▶ Tabela ──▶ Modelo ──▶ Fact Metric ──▶ Métrica Calculada ──▶ Dossier/Bot` (ou `(Direto)` para atributos)!

### 6.2. Comparação de Modelos e Fontes de Dados (Grid / Matriz)
Para descobrir se você possui mais de um modelo criado em cima da mesma fonte de dados e se usam tabelas diferentes:
1. Insira uma visualização do tipo **Grid** (Grade) ou **Bar Chart**.
2. Arraste para as linhas:
   - `source_name` (Banco de Dados)
   - `table_name` (Tabela Utilizada)
   - `model_name` (Modelo Criado)
3. Arraste para as métricas:
   - `weight` ou contagem distinta de `model_name` e `table_name`.
4. Você verá instantaneamente o agrupamento: quais modelos compartilham a mesma conexão de banco e quais tabelas são utilizadas por cada um!

### 6.3. Planilha/Grade de Linhagem com Fórmulas (Sem Quebras de Relacionamento)
Para visualizar a rastreabilidade completa até a fórmula de cálculo sem conflitos de tabelas:
1. Crie uma visualização **Grid** (Planilha).
2. Arraste os seguintes atributos todos da tabela **`Lineage_Sankey`**:
   - `source_name` ──▶ `table_name` ──▶ `model_name` ──▶ `object_name` ──▶ `formula`
3. Como todas essas informações coexistem na mesma tabela do SuperCube, a planilha exibe todas as linhas perfeitamente sem erros de relacionamento!

---

## 7. Execução de Testes Automatizados

```powershell
python -m unittest tests/test_mosaic_lineage.py
```
