"""
clang-uml large-project analysis and filtering system.

Automatically splits big UML files into smaller diagrams.
"""

__version__ = "0.1.0"

from .parser import ClangUMLParser
from .graph_builder import GraphBuilder
from .analyzer import GraphAnalyzer
from .filter import DiagramFilter
from .generator import PumlGenerator
from .sequence_parser import SequenceDiagramParser, SequenceDiagramGenerator

__all__ = [
    "ClangUMLParser",
    "GraphBuilder", 
    "GraphAnalyzer",
    "DiagramFilter",
    "PumlGenerator",
    "SequenceDiagramParser",
    "SequenceDiagramGenerator",
]

