"""ComfyUI REST API client."""

import json
from typing import Any, Dict, List, Optional

import requests

from ..errors import ServerError, VerificationError


class ComfyUIAPI:
    """Client for ComfyUI REST API.

    Provides methods to interact with a running ComfyUI server.

    Args:
        base_url: Base URL of the ComfyUI server (e.g., "http://127.0.0.1:8188")
        timeout: Request timeout in seconds

    Example:
        >>> api = ComfyUIAPI("http://127.0.0.1:8188")
        >>> nodes = api.get_object_info()
        >>> print(list(nodes.keys())[:5])
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def health_check(self) -> bool:
        """Check if the server is responsive.

        Returns:
            True if server responds, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/system_stats",
                timeout=self.timeout,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_object_info(self) -> Dict[str, Any]:
        """Get information about all registered nodes.

        Returns:
            Dictionary mapping node names to their info

        Raises:
            ServerError: If request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/object_info",
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ServerError(
                "Failed to get object_info from ComfyUI",
                str(e)
            )

    def verify_nodes(self, expected_nodes: List[str]) -> None:
        """Verify that expected nodes are registered.

        Args:
            expected_nodes: List of node names that must exist

        Raises:
            VerificationError: If any expected nodes are missing
        """
        nodes = self.get_object_info()
        missing = [name for name in expected_nodes if name not in nodes]

        if missing:
            raise VerificationError(
                f"Expected nodes not found: {', '.join(missing)}",
                missing_nodes=missing,
            )

    def queue_prompt(self, workflow: Dict[str, Any]) -> str:
        """Queue a workflow for execution.

        Args:
            workflow: Workflow definition (the "prompt" part of a workflow JSON)

        Returns:
            Prompt ID for tracking execution

        Raises:
            ServerError: If request fails
        """
        try:
            response = self.session.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["prompt_id"]
        except requests.RequestException as e:
            raise ServerError(
                "Failed to queue prompt",
                str(e)
            )
        except KeyError:
            raise ServerError(
                "Invalid response from /prompt endpoint",
                "Missing prompt_id in response"
            )

    def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get execution history for a prompt.

        Args:
            prompt_id: ID from queue_prompt

        Returns:
            History data if available, None if prompt hasn't started

        Raises:
            ServerError: If request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get(prompt_id)
        except requests.RequestException as e:
            raise ServerError(
                f"Failed to get history for prompt {prompt_id}",
                str(e)
            )

    def get_queue(self) -> Dict[str, Any]:
        """Get current queue status.

        Returns:
            Queue data with 'queue_running' and 'queue_pending'

        Raises:
            ServerError: If request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/queue",
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ServerError(
                "Failed to get queue status",
                str(e)
            )

    def interrupt(self) -> None:
        """Interrupt currently running workflow."""
        try:
            self.session.post(
                f"{self.base_url}/interrupt",
                timeout=self.timeout,
            )
        except requests.RequestException:
            pass  # Best effort

    def free_memory(self, unload_models: bool = True) -> None:
        """Free memory and optionally unload models.

        Calls ComfyUI's /free endpoint to release cached data.
        This helps prevent memory accumulation when running multiple workflows.

        Args:
            unload_models: If True, also unload any loaded models
        """
        try:
            self.session.post(
                f"{self.base_url}/free",
                json={"unload_models": unload_models, "free_memory": True},
                timeout=self.timeout,
            )
        except requests.RequestException:
            pass  # Best effort - don't fail if cleanup fails

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self) -> "ComfyUIAPI":
        return self

    def __exit__(self, *args) -> None:
        self.close()
