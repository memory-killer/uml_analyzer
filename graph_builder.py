"""
NetworkX graph builder

Converts clang-uml diagram data into a NetworkX graph for analysis.
"""

import networkx as nx
from typing import Dict, List, Set, Optional
from .parser import DiagramData, ClassElement, Relationship


class GraphBuilder:
    """Convert DiagramData into a NetworkX directed graph."""
    
    def __init__(self, diagram_data: DiagramData):
        self.data = diagram_data
        self.graph = nx.DiGraph()
        self._build_graph()
    
    def _build_graph(self):
        """Build the graph nodes and edges."""
        # Add nodes (classes/interfaces)
        for elem_id, elem in self.data.elements.items():
            self.graph.add_node(
                elem_id,
                name=elem.name,
                full_name=elem.full_name,
                display_name=elem.display_name,
                namespace=elem.namespace,
                type=elem.type,
                is_abstract=elem.is_abstract,
                is_template=elem.is_template,
                member_count=elem.member_count,
                method_count=elem.method_count,
                complexity=elem.complexity_score,
                element=elem  # store full element object
            )
        
        # Add edges (relationships)
        for rel in self.data.relationships:
            if rel.source in self.graph and rel.destination in self.graph:
                # Apply weights depending on relationship type
                weight = self._get_relationship_weight(rel.type)
                
                self.graph.add_edge(
                    rel.source,
                    rel.destination,
                    type=rel.type,
                    label=rel.label,
                    access=rel.access,
                    weight=weight,
                    relationship=rel  # store full relationship object
                )
    
    def _get_relationship_weight(self, rel_type: str) -> float:
        """Return weight per relationship type (stronger coupling = higher weight)."""
        weights = {
            "extension": 2.0,      # inheritance (strong coupling)
            "composition": 1.8,    # composition
            "aggregation": 1.5,    # aggregation
            "association": 1.2,    # association
            "dependency": 0.8,     # dependency (weaker coupling)
        }
        return weights.get(rel_type, 1.0)
    
    def get_neighbors(self, node_id: str, direction: str = "both") -> Set[str]:
        """
        Get neighbors of a node.

        direction: 'in', 'out', 'both'
        """
        if node_id not in self.graph:
            return set()
        
        if direction == "in":
            return set(self.graph.predecessors(node_id))
        elif direction == "out":
            return set(self.graph.successors(node_id))
        else:  # both
            return set(self.graph.predecessors(node_id)) | set(self.graph.successors(node_id))
    
    def get_subgraph_by_nodes(self, node_ids: Set[str]) -> nx.DiGraph:
        """Return a subgraph induced by a set of node IDs."""
        # Filter only existing nodes
        valid_nodes = [nid for nid in node_ids if nid in self.graph]
        return self.graph.subgraph(valid_nodes).copy()
    
    def get_nodes_within_hops(
        self, 
        center_node: str, 
        max_hops: int = 2,
        direction: str = "both"
    ) -> Set[str]:
        """
        Find all nodes within N hops from a given node.

        direction: 'in' (dependents), 'out' (dependees), 'both' (bidirectional)
        """
        if center_node not in self.graph:
            return set()
        
        visited = {center_node}
        current_layer = {center_node}
        
        for _ in range(max_hops):
            next_layer = set()
            for node in current_layer:
                neighbors = self.get_neighbors(node, direction)
                next_layer.update(neighbors - visited)
            
            if not next_layer:
                break
            
            visited.update(next_layer)
            current_layer = next_layer
        
        return visited
    
    def get_nodes_by_namespace(self, namespace_pattern: str) -> Set[str]:
        """Return nodes whose namespace starts with the given pattern."""
        matching_nodes = set()
        
        for node_id, attrs in self.graph.nodes(data=True):
            namespace = attrs.get("namespace", "")
            if namespace.startswith(namespace_pattern):
                matching_nodes.add(node_id)
        
        return matching_nodes
    
    def find_strongly_connected_components(self) -> List[Set[str]]:
        """Find strongly connected components (cycle dependencies)."""
        return list(nx.strongly_connected_components(self.graph))
    
    def find_shortest_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find shortest path between two nodes."""
        try:
            return nx.shortest_path(self.graph, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def get_in_degree(self, node_id: str) -> int:
        """Number of incoming edges (number of dependents)."""
        return self.graph.in_degree(node_id) if node_id in self.graph else 0
    
    def get_out_degree(self, node_id: str) -> int:
        """Number of outgoing edges (number of dependees)."""
        return self.graph.out_degree(node_id) if node_id in self.graph else 0
    
    def get_node_attributes(self, node_id: str) -> Dict:
        """Return all attributes of a node."""
        if node_id not in self.graph:
            return {}
        return dict(self.graph.nodes[node_id])
    
    def get_statistics(self) -> Dict:
        """Return basic statistics of the graph."""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "density": nx.density(self.graph),
            "is_dag": nx.is_directed_acyclic_graph(self.graph),
            "scc_count": len(list(nx.strongly_connected_components(self.graph))),
            "avg_in_degree": sum(d for _, d in self.graph.in_degree()) / self.graph.number_of_nodes() if self.graph.number_of_nodes() > 0 else 0,
            "avg_out_degree": sum(d for _, d in self.graph.out_degree()) / self.graph.number_of_nodes() if self.graph.number_of_nodes() > 0 else 0,
        }
    
    def export_to_graphml(self, filepath: str):
        """Export the graph into GraphML format (e.g. for yEd)."""
        nx.write_graphml(self.graph, filepath)
    
    def get_graph(self) -> nx.DiGraph:
        """Return the internal NetworkX graph object."""
        return self.graph


if __name__ == "__main__":
    # Simple manual test
    from pathlib import Path
    from .parser import ClangUMLParser
    
    parser = ClangUMLParser()
    test_file = Path("test_project/output/app_class_diagram.json")
    
    if test_file.exists():
        data = parser.parse_file(test_file)
        builder = GraphBuilder(data)
        
        print("✅ Graph built successfully")
        stats = builder.get_statistics()
        print("\nGraph statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Print neighbors of the first element
        if data.elements:
            first_id = list(data.elements.keys())[0]
            first_elem = data.elements[first_id]
            neighbors = builder.get_neighbors(first_id)
            print(f"\nNeighbors of {first_elem.name}: {len(neighbors)}")

