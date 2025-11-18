"""
Diagram filtering strategies.

Provides multi-view generation: context-based, per-module, hotspot views, etc.
"""

import networkx as nx
from typing import Set, Dict, List, Optional
from enum import Enum

from .parser import DiagramData
from .graph_builder import GraphBuilder
from .analyzer import GraphAnalyzer


class ViewStrategy(Enum):
    """Strategies for automatically creating diagram views."""
    CONTEXT = "context"              # N-hop view around a specific class
    NAMESPACE = "namespace"          # Per-namespace views
    COMMUNITY = "community"          # Community-based views
    HOTSPOT = "hotspot"              # Hotspot view
    IMPORTANCE = "importance"        # Importance-based view
    LAYER = "layer"                  # Layered architecture view


class DiagramFilter:
    """Filter class for creating various diagram views."""
    
    def __init__(
        self, 
        diagram_data: DiagramData,
        graph_builder: GraphBuilder,
        analyzer: GraphAnalyzer
    ):
        self.data = diagram_data
        self.builder = graph_builder
        self.analyzer = analyzer
        self.views: Dict[str, Set[str]] = {}
    
    def create_context_view(
        self,
        center_class_name: str,
        max_hops: int = 2,
        direction: str = "both",
        view_name: Optional[str] = None
    ) -> Set[str]:
        """
        Context view: nodes within N hops around a given class.
        
        Args:
            center_class_name: Center class name.
            max_hops: Maximum hop count.
            direction: 'in' (dependents), 'out' (dependees), 'both'.
            view_name: Optional explicit view name (auto-generated if None).
        """
        # Find internal ID by class name
        center_id = None
        for node_id, attrs in self.builder.graph.nodes(data=True):
            if attrs.get("name") == center_class_name or attrs.get("full_name") == center_class_name:
                center_id = node_id
                break
        
        if not center_id:
            raise ValueError(f"Class not found: {center_class_name}")
        
        # Find nodes within N hops
        nodes = self.builder.get_nodes_within_hops(center_id, max_hops, direction)
        
        # Save view
        if view_name is None:
            view_name = f"context_{center_class_name}_h{max_hops}"
        self.views[view_name] = nodes
        
        return nodes
    
    def create_namespace_views(
        self,
        namespace_list: Optional[List[str]] = None,
        min_nodes: int = 2
    ) -> Dict[str, Set[str]]:
        """
        Create views per namespace.
        
        Args:
            namespace_list: Specific namespaces (all namespaces if None).
            min_nodes: Minimum node count to keep a view.
        """
        if namespace_list is None:
            namespace_list = self.data.get_namespaces()
        
        namespace_views = {}
        
        for ns in namespace_list:
            nodes = self.builder.get_nodes_by_namespace(ns)
            
            # Respect minimum node count
            if len(nodes) >= min_nodes:
                view_name = f"namespace_{ns.replace('::', '_')}"
                self.views[view_name] = nodes
                namespace_views[view_name] = nodes
        
        return namespace_views
    
    def create_community_views(
        self,
        min_community_size: int = 3,
        resolution: float = 1.0
    ) -> Dict[str, Set[str]]:
        """
        Create views per community.
        
        Args:
            min_community_size: Minimum community size.
            resolution: Resolution parameter for Louvain algorithm.
        """
        communities = self.analyzer.detect_communities(resolution)
        community_members = self.analyzer.get_community_members()
        
        community_views = {}
        
        for comm_id, members in community_members.items():
            if len(members) >= min_community_size:
                view_name = f"community_{comm_id}"
                self.views[view_name] = members
                community_views[view_name] = members
        
        return community_views
    
    def create_hotspot_view(
        self,
        min_degree: int = 5,
        min_complexity: int = 10,
        include_neighbors: bool = True
    ) -> Set[str]:
        """
        Hotspot view: classes that are good refactoring candidates.
        
        Args:
            min_degree: Minimum degree.
            min_complexity: Minimum complexity.
            include_neighbors: Whether to include direct neighbors.
        """
        hotspots = self.analyzer.find_hotspots(min_degree, min_complexity)
        
        if include_neighbors:
            # Also include direct neighbors of hotspots
            extended = set(hotspots)
            for node in hotspots:
                extended.update(self.builder.get_neighbors(node))
            hotspots = extended
        
        view_name = "hotspot"
        self.views[view_name] = hotspots
        
        return hotspots
    
    def create_importance_view(
        self,
        top_n: int = 20,
        metric: str = "pagerank",
        include_neighbors: bool = True
    ) -> Set[str]:
        """
        Importance-based view: top-N most important classes.
        
        Args:
            top_n: Number of top nodes to include.
            metric: 'pagerank', 'betweenness', or 'degree'.
            include_neighbors: Whether to include direct neighbors.
        """
        top_nodes = self.analyzer.get_top_nodes_by_metric(metric, top_n)
        important_nodes = {node_id for node_id, _ in top_nodes}
        
        if include_neighbors:
            # Also include direct neighbors of important nodes
            extended = set(important_nodes)
            for node in important_nodes:
                extended.update(self.builder.get_neighbors(node))
            important_nodes = extended
        
        view_name = f"importance_{metric}_top{top_n}"
        self.views[view_name] = important_nodes
        
        return important_nodes
    
    def create_layer_views(
        self,
        layer_patterns: Dict[str, str]
    ) -> Dict[str, Set[str]]:
        """
        Layered architecture views (e.g. API, Service, Core).
        
        Args:
            layer_patterns: {layer_name: namespace_pattern}
                           e.g. {"api": "app::api", "service": "app::service", "core": "app::core"}
        """
        layer_views = {}
        
        for layer_name, pattern in layer_patterns.items():
            nodes = self.builder.get_nodes_by_namespace(pattern)
            if nodes:
                view_name = f"layer_{layer_name}"
                self.views[view_name] = nodes
                layer_views[view_name] = nodes
        
        return layer_views
    
    def create_dependency_chain_view(
        self,
        start_class: str,
        end_class: str,
        expand_hops: int = 1
    ) -> Optional[Set[str]]:
        """
        Dependency-chain view: path from A to B plus surrounding context.
        
        Args:
            start_class: Start class name.
            end_class: End class name.
            expand_hops: Number of hops to expand around the path.
        """
        # Find node IDs by class name
        start_id = self._find_node_id_by_name(start_class)
        end_id = self._find_node_id_by_name(end_class)
        
        if not start_id or not end_id:
            return None
        
        # Find shortest path
        path = self.builder.find_shortest_path(start_id, end_id)
        if not path:
            return None
        
        # Path nodes + surrounding nodes
        nodes = set(path)
        if expand_hops > 0:
            for node in path:
                nodes.update(self.builder.get_nodes_within_hops(node, expand_hops))
        
        view_name = f"dependency_{start_class}_to_{end_class}"
        self.views[view_name] = nodes
        
        return nodes
    
    def create_god_class_view(
        self,
        threshold_percentile: float = 90,
        include_neighbors: bool = True
    ) -> Set[str]:
        """God-class view: classes with very high complexity."""
        god_classes = self.analyzer.find_god_classes(threshold_percentile)
        
        if include_neighbors:
            extended = set(god_classes)
            for node in god_classes:
                extended.update(self.builder.get_neighbors(node))
            god_classes = extended
        
        view_name = "god_classes"
        self.views[view_name] = god_classes
        
        return god_classes
    
    def _find_node_id_by_name(self, class_name: str) -> Optional[str]:
        """Find an internal node ID by class name."""
        for node_id, attrs in self.builder.graph.nodes(data=True):
            if attrs.get("name") == class_name or attrs.get("full_name") == class_name:
                return node_id
        return None
    
    def get_view(self, view_name: str) -> Optional[Set[str]]:
        """Get a stored view by name."""
        return self.views.get(view_name)
    
    def get_all_views(self) -> Dict[str, Set[str]]:
        """Return a shallow copy of all stored views."""
        return self.views.copy()
    
    def get_view_statistics(self, view_name: str) -> Optional[Dict]:
        """Return statistics for a specific view."""
        nodes = self.views.get(view_name)
        if not nodes:
            return None
        
        subgraph = self.builder.get_subgraph_by_nodes(nodes)
        
        return {
            "view_name": view_name,
            "node_count": len(nodes),
            "edge_count": subgraph.number_of_edges(),
            "density": nx.density(subgraph) if len(nodes) > 1 else 0,
            "nodes": [
                {
                    "id": node_id,
                    "name": self.builder.graph.nodes[node_id].get("name", ""),
                    "full_name": self.builder.graph.nodes[node_id].get("full_name", "")
                }
                for node_id in nodes
            ]
        }
    
    def auto_create_views(
        self,
        strategies: Optional[List[ViewStrategy]] = None
    ) -> Dict[str, Set[str]]:
        """
        Automatically create multiple standard views.
        
        Args:
            strategies: List of strategies to use (all if None).
        """
        if strategies is None:
            strategies = list(ViewStrategy)
        
        created_views = {}
        
        for strategy in strategies:
            try:
                if strategy == ViewStrategy.NAMESPACE:
                    views = self.create_namespace_views()
                    created_views.update(views)
                
                elif strategy == ViewStrategy.COMMUNITY:
                    views = self.create_community_views()
                    created_views.update(views)
                
                elif strategy == ViewStrategy.HOTSPOT:
                    nodes = self.create_hotspot_view()
                    if nodes:
                        created_views["hotspot"] = nodes
                
                elif strategy == ViewStrategy.IMPORTANCE:
                    nodes = self.create_importance_view(top_n=15)
                    if nodes:
                        created_views["importance_top15"] = nodes
                
                # CONTEXT and LAYER require explicit parameters and are not auto-created here.
            
            except Exception as e:
                print(f"⚠️ Failed to create {strategy.value} view: {e}")
        
        return created_views


if __name__ == "__main__":
    # Simple manual test
    from pathlib import Path
    from .parser import ClangUMLParser
    
    parser = ClangUMLParser()
    test_file = Path("test_project/output/app_class_diagram.json")
    
    if test_file.exists():
        data = parser.parse_file(test_file)
        builder = GraphBuilder(data)
        analyzer = GraphAnalyzer(builder.get_graph())
        filter_obj = DiagramFilter(data, builder, analyzer)
        
        print("✅ Filter created")
        
        # Automatically create views
        views = filter_obj.auto_create_views()
        print(f"\nViews created: {len(views)}")
        for view_name, nodes in views.items():
            print(f"  - {view_name}: {len(nodes)} nodes")

