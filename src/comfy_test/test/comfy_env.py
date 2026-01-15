"""Utilities for reading comfy-env.toml configuration."""

import sys
from pathlib import Path
from typing import List

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def get_cuda_packages(node_dir: Path) -> List[str]:
    """
    Read comfy-env.toml and return list of CUDA package names.

    Args:
        node_dir: Path to the custom node directory

    Returns:
        List of CUDA package names (e.g., ['nvdiffrast', 'flash_attn'])
    """
    config_path = Path(node_dir) / "comfy-env.toml"
    if not config_path.exists():
        return []

    try:
        config = tomllib.loads(config_path.read_text())
    except Exception:
        return []

    cuda_packages = []
    for env_name, env_config in config.items():
        if isinstance(env_config, dict) and "cuda" in env_config:
            # Package names in config use hyphens, but Python imports use underscores
            for pkg_name in env_config["cuda"].keys():
                # Normalize: flash-attn -> flash_attn
                cuda_packages.append(pkg_name.replace("-", "_"))

    return cuda_packages
