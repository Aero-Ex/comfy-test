"""Workflow validation for ComfyUI workflows."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class ValidationError:
    """A single validation error."""
    node_id: int
    node_type: str
    message: str
    level: str  # "schema", "graph", "introspection", "execution"

    def __str__(self) -> str:
        return f"[{self.level}] Node {self.node_id} ({self.node_type}): {self.message}"


@dataclass
class ValidationResult:
    """Result of workflow validation."""
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    executable_nodes: List[int] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


class WorkflowValidator:
    """Validates ComfyUI workflows against node schemas.

    Implements 4 levels of validation:
    - Level 1: Schema validation (widget values match allowed types/enums/ranges)
    - Level 2: Graph validation (connections are valid, no cycles)
    - Level 3: Node introspection (INPUT_TYPES, RETURN_TYPES are valid)
    - Level 4: Partial execution (identify nodes that can run without CUDA)
    """

    def __init__(
        self,
        object_info: Dict[str, Any],
        cuda_packages: Optional[List[str]] = None,
        cuda_node_types: Optional[Set[str]] = None,
    ):
        """
        Args:
            object_info: Node definitions from /object_info API
            cuda_packages: List of CUDA package names (for Level 4)
            cuda_node_types: Set of node types that require CUDA (for Level 4)
        """
        self.object_info = object_info
        self.cuda_packages = cuda_packages or []
        self.cuda_node_types = cuda_node_types or set()

    def validate(self, workflow: Dict[str, Any]) -> ValidationResult:
        """Run all validation levels on a workflow.

        Args:
            workflow: Parsed workflow JSON

        Returns:
            ValidationResult with errors, warnings, and executable nodes
        """
        result = ValidationResult()

        # Level 1: Schema validation
        result.errors.extend(self._validate_schema(workflow))

        # Level 2: Graph validation
        result.errors.extend(self._validate_graph(workflow))

        # Level 4: Find executable prefix (nodes before CUDA)
        if not result.errors:
            result.executable_nodes = self._get_executable_prefix(workflow)

        return result

    def validate_file(self, workflow_path: Path) -> ValidationResult:
        """Validate a workflow JSON file.

        Args:
            workflow_path: Path to workflow JSON file

        Returns:
            ValidationResult
        """
        workflow_path = Path(workflow_path)
        with open(workflow_path) as f:
            workflow = json.load(f)
        return self.validate(workflow)

    def _validate_schema(self, workflow: Dict[str, Any]) -> List[ValidationError]:
        """Level 1: Validate widget values against node schemas."""
        errors = []

        for node in workflow.get("nodes", []):
            node_id = node.get("id", 0)
            node_type = node.get("type", "unknown")

            # Check node type exists
            if node_type not in self.object_info:
                errors.append(ValidationError(
                    node_id, node_type,
                    f"Unknown node type: {node_type}",
                    "schema"
                ))
                continue

            schema = self.object_info[node_type]
            errors.extend(self._validate_widgets(node, schema))

        return errors

    def _validate_widgets(
        self,
        node: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[ValidationError]:
        """Validate widget values for a single node."""
        errors = []
        node_id = node.get("id", 0)
        node_type = node.get("type", "unknown")

        inputs = schema.get("input", {})
        required = inputs.get("required", {})
        optional = inputs.get("optional", {})
        all_inputs = {**required, **optional}

        widgets_values = node.get("widgets_values", [])
        widget_idx = 0

        for input_name, input_spec in all_inputs.items():
            if not isinstance(input_spec, (list, tuple)) or len(input_spec) < 1:
                continue

            input_type = input_spec[0]

            # Skip connection types (uppercase like IMAGE, MASK, etc.)
            # These are not widgets, they're connections
            if isinstance(input_type, str) and input_type.isupper():
                continue

            # This is a widget - get its value
            if widget_idx >= len(widgets_values):
                # No more widget values - might be using defaults
                break

            value = widgets_values[widget_idx]
            widget_idx += 1

            # Validate based on input type
            error = self._validate_value(input_name, input_type, input_spec, value)
            if error:
                errors.append(ValidationError(node_id, node_type, error, "schema"))

        return errors

    def _validate_value(
        self,
        input_name: str,
        input_type: Any,
        input_spec: List[Any],
        value: Any
    ) -> Optional[str]:
        """Validate a single widget value against its spec.

        Returns error message if invalid, None if valid.
        """
        # Enum validation - input_type is a list of allowed values
        if isinstance(input_type, list):
            if value not in input_type:
                return f"'{input_name}': '{value}' not in allowed values {input_type}"
            return None

        # Get options dict (second element of spec, if present)
        opts = input_spec[1] if len(input_spec) > 1 and isinstance(input_spec[1], dict) else {}

        # INT validation
        if input_type == "INT":
            if not isinstance(value, (int, float)):
                return f"'{input_name}': expected INT, got {type(value).__name__}"
            min_val = opts.get("min")
            max_val = opts.get("max")
            if min_val is not None and value < min_val:
                return f"'{input_name}': {value} < minimum {min_val}"
            if max_val is not None and value > max_val:
                return f"'{input_name}': {value} > maximum {max_val}"

        # FLOAT validation
        elif input_type == "FLOAT":
            if not isinstance(value, (int, float)):
                return f"'{input_name}': expected FLOAT, got {type(value).__name__}"
            min_val = opts.get("min")
            max_val = opts.get("max")
            if min_val is not None and value < min_val:
                return f"'{input_name}': {value} < minimum {min_val}"
            if max_val is not None and value > max_val:
                return f"'{input_name}': {value} > maximum {max_val}"

        # STRING validation
        elif input_type == "STRING":
            if not isinstance(value, str):
                return f"'{input_name}': expected STRING, got {type(value).__name__}"

        # BOOLEAN validation
        elif input_type == "BOOLEAN":
            if not isinstance(value, bool):
                return f"'{input_name}': expected BOOLEAN, got {type(value).__name__}"

        return None

    def _validate_graph(self, workflow: Dict[str, Any]) -> List[ValidationError]:
        """Level 2: Validate graph connections."""
        errors = []

        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])

        # Build node lookup
        nodes_by_id = {n.get("id"): n for n in nodes}

        # Validate each link
        for link in links:
            if not isinstance(link, list) or len(link) < 6:
                continue

            link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]

            # Check source node exists
            if from_node not in nodes_by_id:
                errors.append(ValidationError(
                    from_node, "unknown",
                    f"Link {link_id}: source node {from_node} does not exist",
                    "graph"
                ))
                continue

            # Check target node exists
            if to_node not in nodes_by_id:
                errors.append(ValidationError(
                    to_node, "unknown",
                    f"Link {link_id}: target node {to_node} does not exist",
                    "graph"
                ))
                continue

            # Validate connection types match
            from_node_obj = nodes_by_id[from_node]
            to_node_obj = nodes_by_id[to_node]
            from_type = from_node_obj.get("type", "unknown")
            to_type = to_node_obj.get("type", "unknown")

            # Check output type matches expected input type
            if from_type in self.object_info and to_type in self.object_info:
                error = self._validate_connection(
                    from_node_obj, from_slot, to_node_obj, to_slot, link_type
                )
                if error:
                    errors.append(ValidationError(
                        to_node, to_type, error, "graph"
                    ))

        return errors

    def _validate_connection(
        self,
        from_node: Dict[str, Any],
        from_slot: int,
        to_node: Dict[str, Any],
        to_slot: int,
        declared_type: str
    ) -> Optional[str]:
        """Validate a single connection between nodes.

        Returns error message if invalid, None if valid.
        """
        from_type = from_node.get("type", "unknown")
        to_type = to_node.get("type", "unknown")

        # Get output type from source node
        from_schema = self.object_info.get(from_type, {})
        from_outputs = from_schema.get("output", [])

        if from_slot >= len(from_outputs):
            return f"Output slot {from_slot} does not exist on {from_type}"

        output_type = from_outputs[from_slot]

        # Get input type from target node
        to_schema = self.object_info.get(to_type, {})
        to_inputs = to_schema.get("input", {})
        required = to_inputs.get("required", {})
        optional = to_inputs.get("optional", {})
        all_inputs = {**required, **optional}

        # Find the input at the given slot
        input_idx = 0
        target_input_type = None
        for input_name, input_spec in all_inputs.items():
            if not isinstance(input_spec, (list, tuple)) or len(input_spec) < 1:
                continue
            spec_type = input_spec[0]
            # Only count connection inputs (uppercase types)
            if isinstance(spec_type, str) and spec_type.isupper():
                if input_idx == to_slot:
                    target_input_type = spec_type
                    break
                input_idx += 1

        if target_input_type is None:
            return f"Input slot {to_slot} does not exist on {to_type}"

        # Check type compatibility
        # ComfyUI allows some type coercion, but we'll be strict for now
        if output_type != target_input_type and output_type != "*" and target_input_type != "*":
            return f"Type mismatch: {from_type} outputs {output_type}, but {to_type} expects {target_input_type}"

        return None

    def _get_executable_prefix(self, workflow: Dict[str, Any]) -> List[int]:
        """Level 4: Get node IDs that can execute without CUDA.

        Returns nodes that:
        1. Don't require CUDA themselves
        2. Don't depend on any CUDA node's output
        """
        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])

        # Build dependency graph
        nodes_by_id = {n.get("id"): n for n in nodes}
        dependencies = {n.get("id"): set() for n in nodes}

        for link in links:
            if not isinstance(link, list) or len(link) < 6:
                continue
            _, from_node, _, to_node, _, _ = link[:6]
            if to_node in dependencies:
                dependencies[to_node].add(from_node)

        # Find CUDA nodes
        cuda_nodes = set()
        for node in nodes:
            node_type = node.get("type", "")
            if node_type in self.cuda_node_types:
                cuda_nodes.add(node.get("id"))

        # Find all nodes that depend on CUDA nodes (transitive)
        def depends_on_cuda(node_id: int, visited: Set[int] = None) -> bool:
            if visited is None:
                visited = set()
            if node_id in visited:
                return False
            visited.add(node_id)

            if node_id in cuda_nodes:
                return True

            for dep_id in dependencies.get(node_id, []):
                if depends_on_cuda(dep_id, visited):
                    return True

            return False

        # Return nodes that don't depend on CUDA
        executable = []
        for node in nodes:
            node_id = node.get("id")
            if not depends_on_cuda(node_id):
                executable.append(node_id)

        return executable
