"""
Graph analyzer.

Graph analysis utilities on top of NetworkX (importance metrics, community detection, etc.).
"""

import networkx as nx
import community as community_louvain  # python-louvain
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class GraphAnalyzer:
    """Graph analysis helper built on top of NetworkX."""
    
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        self._pagerank_cache = None
        self._betweenness_cache = None
        self._communities_cache = None
    
    def calculate_pagerank(self, alpha: float = 0.85) -> Dict[str, float]:
        """
        Compute PageRank (web-page importance algorithm).
        Higher scores indicate classes that many other classes depend on.
        """
        if self._pagerank_cache is None:
            self._pagerank_cache = nx.pagerank(self.graph, alpha=alpha)
        return self._pagerank_cache
    
    def calculate_betweenness_centrality(self) -> Dict[str, float]:
        """
        Compute betweenness centrality.
        Higher scores indicate bridge-like classes lying on many shortest paths.
        """
        if self._betweenness_cache is None:
            self._betweenness_cache = nx.betweenness_centrality(self.graph)
        return self._betweenness_cache
    
    def calculate_degree_centrality(self) -> Dict[str, float]:
        """
        Compute degree centrality.
        Higher scores indicate hub-like classes with many direct connections.
        """
        return nx.degree_centrality(self.graph)
    
    def get_top_nodes_by_metric(
        self, 
        metric: str = "pagerank", 
        top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Return top-N nodes according to a metric.
        
        metric: 'pagerank', 'betweenness', 'degree', 'in_degree', 'out_degree'
        """
        if metric == "pagerank":
            scores = self.calculate_pagerank()
        elif metric == "betweenness":
            scores = self.calculate_betweenness_centrality()
        elif metric == "degree":
            scores = self.calculate_degree_centrality()
        elif metric == "in_degree":
            scores = dict(self.graph.in_degree())
        elif metric == "out_degree":
            scores = dict(self.graph.out_degree())
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        # Sort and return top-N nodes
        sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_nodes[:top_n]
    
    def detect_communities(self, resolution: float = 1.0) -> Dict[str, int]:
        """
        Detect communities using the Louvain algorithm.
        Returns: {node_id: community_id}
        """
        if self._communities_cache is None:
            # Convert the DiGraph into an undirected graph for community detection
            undirected = self.graph.to_undirected()
            self._communities_cache = community_louvain.best_partition(
                undirected, 
                resolution=resolution
            )
        return self._communities_cache
    
    def get_community_members(self, community_id: int = None) -> Dict[int, Set[str]]:
        """
        Return member nodes per community.
        If community_id is None, return all communities.
        """
        communities = self.detect_communities()
        
        # Group nodes by community
        community_map = defaultdict(set)
        for node_id, comm_id in communities.items():
            community_map[comm_id].add(node_id)
        
        if community_id is not None:
            return {community_id: community_map.get(community_id, set())}
        
        return dict(community_map)
    
    def find_hotspots(
        self, 
        min_degree: int = 5,
        min_complexity: int = 10
    ) -> Set[str]:
        """
        Detect hotspots: highly coupled and complex classes (refactoring candidates).
        """
        hotspots = set()
        
        for node_id, attrs in self.graph.nodes(data=True):
            degree = self.graph.degree(node_id)
            complexity = attrs.get("complexity", 0)
            
            if degree >= min_degree and complexity >= min_complexity:
                hotspots.add(node_id)
        
        return hotspots
    
    def find_god_classes(self, threshold_percentile: float = 90) -> Set[str]:
        """
        Detect potential God classes: very high complexity classes.
        """
        complexities = [
            attrs.get("complexity", 0) 
            for _, attrs in self.graph.nodes(data=True)
        ]
        
        if not complexities:
            return set()
        
        # Compute percentile threshold
        import numpy as np
        threshold = np.percentile(complexities, threshold_percentile)
        
        god_classes = set()
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("complexity", 0) >= threshold:
                god_classes.add(node_id)
        
        return god_classes
    
    def find_leaf_classes(self) -> Set[str]:
        """Leaf classes: classes no other classes depend on (out_degree = 0)."""
        return {node for node, degree in self.graph.out_degree() if degree == 0}
    
    def find_root_classes(self) -> Set[str]:
        """Root classes: classes that do not depend on others (in_degree = 0)."""
        return {node for node, degree in self.graph.in_degree() if degree == 0}
    
    def analyze_namespace_coupling(self) -> Dict[str, Dict]:
        """Analyze coupling per namespace."""
        namespace_stats = defaultdict(lambda: {
            "nodes": set(),
            "internal_edges": 0,
            "external_edges_out": 0,
            "external_edges_in": 0
        })
        
        # Collect nodes per namespace
        for node_id, attrs in self.graph.nodes(data=True):
            namespace = attrs.get("namespace", "")
            namespace_stats[namespace]["nodes"].add(node_id)
        
        # Analyze edges
        for source, target in self.graph.edges():
            source_ns = self.graph.nodes[source].get("namespace", "")
            target_ns = self.graph.nodes[target].get("namespace", "")
            
            if source_ns == target_ns:
                namespace_stats[source_ns]["internal_edges"] += 1
            else:
                namespace_stats[source_ns]["external_edges_out"] += 1
                namespace_stats[target_ns]["external_edges_in"] += 1
        
        # Aggregate results
        result = {}
        for ns, stats in namespace_stats.items():
            node_count = len(stats["nodes"])
            internal = stats["internal_edges"]
            external = stats["external_edges_out"] + stats["external_edges_in"]
            total = internal + external
            
            result[ns] = {
                "node_count": node_count,
                "internal_edges": internal,
                "external_edges": external,
                "cohesion": internal / total if total > 0 else 0,  # internal ratio
                "coupling": external / node_count if node_count > 0 else 0  # edges per node to other namespaces
            }
        
        return result
    
    def get_analysis_summary(self) -> Dict:
        """Return a high-level summary of graph analysis."""
        pagerank = self.calculate_pagerank()
        communities = self.detect_communities()
        hotspots = self.find_hotspots()
        
        top_important = self.get_top_nodes_by_metric("pagerank", 5)
        top_connected = self.get_top_nodes_by_metric("degree", 5)
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "communities_count": len(set(communities.values())),
            "hotspots_count": len(hotspots),
            "leaf_classes_count": len(self.find_leaf_classes()),
            "root_classes_count": len(self.find_root_classes()),
            "top_important_nodes": [
                {
                    "id": node_id,
                    "name": self.graph.nodes[node_id].get("name", ""),
                    "score": score
                }
                for node_id, score in top_important
            ],
            "top_connected_nodes": [
                {
                    "id": node_id,
                    "name": self.graph.nodes[node_id].get("name", ""),
                    "degree": score
                }
                for node_id, score in top_connected
            ],
        }


if __name__ == "__main__":
    # Simple manual test
    from pathlib import Path
    from .parser import ClangUMLParser
    from .graph_builder import GraphBuilder
    
    parser = ClangUMLParser()
    test_file = Path("test_project/output/app_class_diagram.json")
    
    if test_file.exists():
        data = parser.parse_file(test_file)
        builder = GraphBuilder(data)
        analyzer = GraphAnalyzer(builder.get_graph())
        
        print("✅ Analysis completed")
        summary = analyzer.get_analysis_summary()
        print("\nAnalysis summary:")
        print(f"  Total nodes: {summary['total_nodes']}")
        print(f"  Total edges: {summary['total_edges']}")
        print(f"  Communities: {summary['communities_count']}")
        print(f"  Hotspots: {summary['hotspots_count']}")
        
        print("\nMost important classes (PageRank):")
        for node in summary["top_important_nodes"][:3]:
            print(f"  - {node['name']}: {node['score']:.4f}")

