## UML Multiview Analyzer

A small companion tool on top of [`clang-uml`](https://github.com/bkryza/clang-uml) that turns huge C++ UML outputs into **small, meaningful diagrams**.

Instead of staring at a giant `*.puml` hairball, you get:
- Focused **namespace / module views**
- Automatically detected **communities** of related classes
- **Layer views** (API / Service / Core, etc.)
- **Importance-based views** (PageRank)
- **Sequence diagrams** generated from clang-uml JSON
- A lightweight **HTML dashboard** and analysis report with SVG/PUML links

---

### Features

- **Multi‑view UML generation (class diagrams)**
  - Namespace-based diagrams (`namespace_*`)
  - Community-based diagrams (`community_*`) via Louvain clustering
  - Layer diagrams (`layer_api`, `layer_service`, `layer_core`, …)
  - Importance view (`importance`) using PageRank
  - Optional hotspot/god‑class views for refactoring targets

- **Sequence diagram support**
  - Parses clang-uml sequence diagram JSON (schema v3)
  - Generates focused PlantUML sequence diagrams
  - Can be run independently from class-diagram mode

- **Graph‑based analysis**
  - Builds a directed graph from `clang-uml` JSON (classes + relationships)
  - PageRank, degree and betweenness centrality
  - Louvain community detection
  - Namespace‑level cohesion/coupling metrics

- **Developer‑friendly output**
  - Multiple small `*.puml` files instead of one unreadable giant
  - Automatic SVG rendering via PlantUML
  - Smart `index.html`:
    - If SVG exists → “View Diagram (SVG)” link
    - Always offers a PUML fallback if the file exists
  - `analysis_report.md` with high‑level metrics

---

### How it fits into your toolchain

This project assumes you already use [`clang-uml`](https://github.com/bkryza/clang-uml) to extract UML information from your C++ codebase.

Typical flow:

1. Build your C++ project and generate `compile_commands.json`
2. Run `clang-uml` to produce **JSON + PlantUML** outputs (class / sequence)
3. Point this tool at the JSON file
4. Open the generated `index.html` and navigate through small, focused diagrams

---

### Installation

#### Python environment

```bash
# Create and activate a virtual environment
uv venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

Required Python libraries:
- `networkx`
- `python-louvain`
- `pyyaml`
- `numpy`
- `scipy`
- (optional) `matplotlib`

#### clang-uml

Follow the official installation guide here:
- [`clang-uml` GitHub repo](https://github.com/bkryza/clang-uml)
- Documentation: [`https://clang-uml.github.io`](https://clang-uml.github.io)

On macOS, for example:

```bash
brew install clang-uml
```

---

### Quick start

#### 1. Class diagrams (multiview)

```bash
cd your_cpp_project
mkdir build && cd build
cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON ..

# Run clang-uml to generate JSON
clang-uml -g json -g plantuml
```

Then run the analyzer:

```bash
cd /path/to/uml_analyzer_repo
source .venv/bin/activate

python -m uml_analyzer.main \
  -i /absolute/path/to/your/class_diagram.json \
  -o /absolute/path/to/output/views

open /absolute/path/to/output/views/index.html
```

#### 2. Sequence diagrams

```bash
python -m uml_analyzer.main \
  -i /absolute/path/to/your/sequence_diagram.json \
  -o /absolute/path/to/output/sequence_views
```

This automatically detects `diagram_type: "sequence"` and generates a PlantUML sequence diagram (and SVG if enabled).

---

### Configuration

All behavior is driven by `config.yaml`. Example:

```yaml
input:
  json_file: "path/to/diagram.json"

output:
  directory: "output/views"
  generate_svg: true
  plantuml_jar: "~/bin/plantuml.jar"
  generate_index: true

views:
  namespace:
    enabled: true
    min_nodes: 2

  community:
    enabled: true
    min_size: 3

  hotspot:
    enabled: true
    min_degree: 5
    min_complexity: 10
    include_neighbors: true

  importance:
    enabled: true
    top_n: 15
    metric: "pagerank"
    include_neighbors: true

  layer:
    enabled: true
    layers:
      api: "your::namespace::api"
      service: "your::namespace::service"
      core: "your::namespace::core"

diagram:
  show_members: true
  show_methods: true
  group_by_namespace: true
```

You can tune thresholds (e.g. what counts as a hotspot) based on your project size.

---

### Programmatic usage

If you want to script your own workflows on top of the graph:

```python
from pathlib import Path
from uml_analyzer import (
    ClangUMLParser,
    GraphBuilder,
    GraphAnalyzer,
    DiagramFilter,
    PumlGenerator,
)

parser = ClangUMLParser()
data = parser.parse_file(Path("path/to/class_diagram.json"))

builder = GraphBuilder(data)
analyzer = GraphAnalyzer(builder.get_graph())
filter_ = DiagramFilter(data, builder, analyzer)

# Example: context view around a core service
nodes = filter_.create_context_view(
    center_class_name="UserService",
    max_hops=2,
    direction="both",
)

generator = PumlGenerator(data, builder)
generator.save_puml(
    node_ids=nodes,
    output_path=Path("output/UserService_context.puml"),
    title="UserService Context View",
)
```

For sequence diagrams:

```python
from pathlib import Path
from uml_analyzer import SequenceDiagramParser, SequenceDiagramGenerator

parser = SequenceDiagramParser()
data = parser.parse_file(Path("path/to/sequence_diagram.json"))

generator = SequenceDiagramGenerator(data)
generator.save_puml(
    output_path=Path("output/login_sequence.puml"),
    title="User Login Flow",
)
```

---

### License

The code in this repository (the multiview analyzer itself) is licensed under the **MIT License**.
