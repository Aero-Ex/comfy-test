"""Auto-discover nodes from custom node's NODE_CLASS_MAPPINGS."""

import importlib.util
import sys
from pathlib import Path

from ..errors import SetupError


def discover_nodes(node_path: Path) -> list[str]:
    """Import custom node and return NODE_CLASS_MAPPINGS keys.

    Args:
        node_path: Path to the custom node directory containing __init__.py

    Returns:
        List of node names from NODE_CLASS_MAPPINGS

    Raises:
        SetupError: If import fails or NODE_CLASS_MAPPINGS not found
    """
    init_file = node_path / "__init__.py"
    if not init_file.exists():
        raise SetupError(
            f"No __init__.py found in {node_path}",
            "Custom nodes must have an __init__.py that exports NODE_CLASS_MAPPINGS"
        )

    # Generate a unique module name to avoid conflicts
    module_name = f"_comfy_test_node_{node_path.name}"

    # Add node_path to sys.path temporarily
    node_path_str = str(node_path)
    if node_path_str not in sys.path:
        sys.path.insert(0, node_path_str)

    try:
        # Load the module from the __init__.py file
        spec = importlib.util.spec_from_file_location(module_name, init_file)
        if spec is None or spec.loader is None:
            raise SetupError(
                f"Failed to load module spec from {init_file}",
                "The __init__.py file could not be parsed"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise SetupError(
                f"Failed to import {node_path.name}",
                f"Import error: {e}"
            )

        # Get NODE_CLASS_MAPPINGS
        if not hasattr(module, "NODE_CLASS_MAPPINGS"):
            raise SetupError(
                f"NODE_CLASS_MAPPINGS not found in {node_path.name}",
                "Custom nodes must export NODE_CLASS_MAPPINGS in __init__.py"
            )

        node_class_mappings = getattr(module, "NODE_CLASS_MAPPINGS")
        if not isinstance(node_class_mappings, dict):
            raise SetupError(
                f"NODE_CLASS_MAPPINGS is not a dict in {node_path.name}",
                f"Expected dict, got {type(node_class_mappings).__name__}"
            )

        return list(node_class_mappings.keys())

    finally:
        # Clean up: remove from sys.modules and sys.path
        if module_name in sys.modules:
            del sys.modules[module_name]
        if node_path_str in sys.path:
            sys.path.remove(node_path_str)
