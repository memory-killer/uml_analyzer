#!/usr/bin/env python3
"""
UML processor CLI

Analyze clang-uml JSON files and generate multi-view UML diagrams.
"""

import sys
import json
import argparse
import yaml
from pathlib import Path
from typing import Dict, Any

from .parser import ClangUMLParser
from .graph_builder import GraphBuilder
from .analyzer import GraphAnalyzer
from .filter import DiagramFilter, ViewStrategy
from .generator import PumlGenerator
from .sequence_parser import SequenceDiagramParser, SequenceDiagramGenerator


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML configuration file."""
    if not config_path.exists():
        print(f"⚠️ Config file not found: {config_path}")
        return {}
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def generate_analysis_report(
    analyzer: GraphAnalyzer,
    filter_obj: DiagramFilter,
    output_path: Path,
    format: str = "markdown"
):
    """Generate an analysis report."""
    summary = analyzer.get_analysis_summary()
    namespace_coupling = analyzer.analyze_namespace_coupling()
    
    if format == "markdown":
        lines = [
            "# UML Analysis Report",
            "",
            "## Overall statistics",
            f"- Total classes: {summary['total_nodes']}",
            f"- Total relationships: {summary['total_edges']}",
            f"- Communities: {summary['communities_count']}",
            f"- Hotspots: {summary['hotspots_count']}",
            f"- Leaf classes: {summary['leaf_classes_count']}",
            f"- Root classes: {summary['root_classes_count']}",
            "",
            "## Most important classes (PageRank)",
            "",
        ]
        
        for i, node in enumerate(summary['top_important_nodes'], 1):
            lines.append(f"{i}. **{node['name']}** (score: {node['score']:.4f})")
        
        lines.extend([
            "",
            "## Most connected classes",
            "",
        ])
        
        for i, node in enumerate(summary['top_connected_nodes'], 1):
            lines.append(f"{i}. **{node['name']}** (degree: {node['degree']})")
        
        lines.extend([
            "",
            "## Namespace coupling analysis",
            "",
            "| Namespace | Class count | Cohesion | Coupling |",
            "|-----------|------------|----------|----------|",
        ])
        
        for ns, stats in sorted(namespace_coupling.items()):
            if ns:  # skip empty namespaces
                lines.append(
                    f"| {ns} | {stats['node_count']} | "
                    f"{stats['cohesion']:.2f} | {stats['coupling']:.2f} |"
                )
        
        output_path.write_text("\n".join(lines), encoding='utf-8')
    
    elif format == "json":
        import json
        report = {
            "summary": summary,
            "namespace_coupling": namespace_coupling
        }
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


def run_plantuml(puml_files: list, plantuml_jar: str):
    """Run PlantUML to generate SVG files."""
    import subprocess
    import os
    
    # Expand ~
    plantuml_jar = os.path.expanduser(plantuml_jar)
    
    if not Path(plantuml_jar).exists():
        print(f"⚠️ PlantUML jar not found: {plantuml_jar}")
        print("  Skipping SVG generation.")
        return
    
    print("\n📊 Generating SVGs with PlantUML...")
    
    for puml_file in puml_files:
        try:
            cmd = ["java", "-jar", plantuml_jar, "-tsvg", str(puml_file)]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"  ✓ {puml_file.name}")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ {puml_file.name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze large clang-uml projects and generate multi-view diagrams."
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        help="Input JSON file (can also be specified in the config file)."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output directory (can also be specified in the config file)."
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path("uml_processor/config.yaml"),
        help="Path to config file (default: uml_processor/config.yaml)."
    )
    parser.add_argument(
        "--no-svg",
        action="store_true",
        help="Skip SVG generation."
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Run analysis only (do not generate diagrams)."
    )
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config) if args.config.exists() else {}
    
    # Decide input file
    input_file = args.input or Path(config.get("input", {}).get("json_file", ""))
    
    if not input_file or not input_file.exists():
        print("❌ Please specify a valid input JSON file.")
        print("   Example: python -m uml_processor.main -i test_project/output/app_class_diagram.json")
        sys.exit(1)
    
    # Decide output directory
    output_dir = args.output or Path(config.get("output", {}).get("directory", "output/views"))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🔍 Starting analysis: {input_file}")
    print(f"📁 Output directory: {output_dir}")
    print()
    
    # 0. Detect diagram type
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_json = json.load(f)
    
    diagram_type = raw_json.get("diagram_type", "class")
    
    # Sequence diagram path
    if diagram_type == "sequence":
        print("📊 Sequence diagram mode")
        print()
        
        # 1. Parse JSON
        print("1️⃣ Parsing JSON...")
        seq_parser = SequenceDiagramParser()
        seq_data = seq_parser.parse_file(input_file)
        stats = seq_parser.get_statistics()
        print(f"   ✓ {stats['total_participants']} participants, {stats['total_messages']} messages")
        
        # 2. Generate PlantUML
        print("2️⃣ Generating PlantUML file...")
        seq_generator = SequenceDiagramGenerator(seq_data)
        output_file = output_dir / f"{seq_data.name}.puml"
        seq_generator.save_puml(output_file, title=seq_data.name)
        print(f"   ✓ {output_file}")
        
        # 3. Generate SVG (optional)
        if not args.no_svg and config.get("output", {}).get("generate_svg", True):
            plantuml_jar = config.get("output", {}).get("plantuml_jar", "~/bin/plantuml.jar")
            run_plantuml([output_file], plantuml_jar)
        
        print(f"\n✅ Done! Output: {output_dir}")
        return
    
    # Class diagram path (original logic)
    print("📊 Class diagram mode")
    print()
    
    # 1. Parse JSON
    print("1️⃣ Parsing JSON...")
    uml_parser = ClangUMLParser()
    diagram_data = uml_parser.parse_file(input_file)
    stats = uml_parser.get_statistics()
    print(f"   ✓ {stats['total_elements']} classes, {stats['total_relationships']} relationships")
    
    # 2. Build graph
    print("2️⃣ Building graph...")
    builder = GraphBuilder(diagram_data)
    graph_stats = builder.get_statistics()
    print(f"   ✓ Density: {graph_stats['density']:.3f}, DAG: {graph_stats['is_dag']}")
    
    # 3. Analyze graph
    print("3️⃣ Analyzing graph...")
    analyzer = GraphAnalyzer(builder.get_graph())
    analysis_summary = analyzer.get_analysis_summary()
    print(f"   ✓ Communities: {analysis_summary['communities_count']}")
    print(f"   ✓ Hotspots: {analysis_summary['hotspots_count']}")
    
    # Generate analysis report
    if config.get("analysis", {}).get("generate_report", True):
        report_format = config.get("analysis", {}).get("report_format", "markdown")
        report_ext = "md" if report_format == "markdown" else "json"
        report_path = output_dir / f"analysis_report.{report_ext}"
        generate_analysis_report(analyzer, None, report_path, report_format)
        print(f"   ✓ Analysis report: {report_path}")
    
    if args.analysis_only:
        print("\n✅ Analysis completed (diagram generation skipped)")
        return
    
    # 4. Filtering and view creation
    print("4️⃣ Creating views...")
    filter_obj = DiagramFilter(diagram_data, builder, analyzer)
    
    views_config = config.get("views", {})
    all_views = {}
    
    # Namespace views
    if views_config.get("namespace", {}).get("enabled", True):
        min_nodes = views_config.get("namespace", {}).get("min_nodes", 2)
        views = filter_obj.create_namespace_views(min_nodes=min_nodes)
        all_views.update(views)
        print(f"   ✓ Namespace views: {len(views)}")
    
    # Community views
    if views_config.get("community", {}).get("enabled", True):
        min_size = views_config.get("community", {}).get("min_size", 3)
        views = filter_obj.create_community_views(min_community_size=min_size)
        all_views.update(views)
        print(f"   ✓ Community views: {len(views)}")
    
    # Hotspot view
    if views_config.get("hotspot", {}).get("enabled", True):
        nodes = filter_obj.create_hotspot_view(
            min_degree=views_config.get("hotspot", {}).get("min_degree", 5),
            min_complexity=views_config.get("hotspot", {}).get("min_complexity", 10),
            include_neighbors=views_config.get("hotspot", {}).get("include_neighbors", True)
        )
        if nodes:
            all_views["hotspot"] = nodes
            print(f"   ✓ Hotspot view: {len(nodes)} nodes")
    
    # Importance view
    if views_config.get("importance", {}).get("enabled", True):
        nodes = filter_obj.create_importance_view(
            top_n=views_config.get("importance", {}).get("top_n", 15),
            metric=views_config.get("importance", {}).get("metric", "pagerank"),
            include_neighbors=views_config.get("importance", {}).get("include_neighbors", True)
        )
        if nodes:
            all_views["importance"] = nodes
            print(f"   ✓ Importance view: {len(nodes)} nodes")
    
    # Layer views
    if views_config.get("layer", {}).get("enabled", False):
        layers = views_config.get("layer", {}).get("layers", {})
        if layers:
            views = filter_obj.create_layer_views(layers)
            all_views.update(views)
            print(f"   ✓ Layer views: {len(views)}")
    
    print(f"\n   Total {len(all_views)} views created")
    
    # 5. Generate PlantUML
    print("5️⃣ Generating PlantUML files...")
    generator = PumlGenerator(diagram_data, builder)
    
    diagram_config = config.get("diagram", {})
    puml_files = generator.generate_multiple_views(
        all_views,
        output_dir,
        show_members=diagram_config.get("show_members", True),
        show_methods=diagram_config.get("show_methods", True),
        group_by_namespace=diagram_config.get("group_by_namespace", True)
    )
    print(f"   ✓ {len(puml_files)} PUML files generated")
    
    # 6. Generate SVG (before HTML index)
    if not args.no_svg and config.get("output", {}).get("generate_svg", True):
        plantuml_jar = config.get("output", {}).get("plantuml_jar", "~/bin/plantuml.jar")
        run_plantuml(puml_files, plantuml_jar)
    
    # 7. Generate HTML index (after SVG generation)
    if config.get("output", {}).get("generate_index", True):
        index_file = generator.generate_index_html(all_views, output_dir)
        print(f"   ✓ HTML index: {index_file}")
    
    print(f"\n✅ Done! Output: {output_dir}")
    print(f"   Open index.html in your browser: file://{output_dir.absolute()}/index.html")


if __name__ == "__main__":
    main()

