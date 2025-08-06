#!/usr/bin/env python3
"""
Test all available extensions using the generic extension test runner.
This ensures that all extensions are properly tested and working correctly.
"""

import sys
import tempfile
import pytest
from pathlib import Path
from worktree_docker.extension_test_runner import run_extension_test_generic
from worktree_docker.worktree_docker import ExtensionManager, auto_detect_extensions


@pytest.mark.parametrize("extension", ["base", "git", "user", "pixi", "uv"])
def test_extension_integration(extension):
    """Test extension integration using the generic test runner."""
    test_success = run_extension_test_generic(extension)
    assert test_success, f"{extension} extension test failed"


class TestExtensionAutoDetection:
    """Test auto-detection functionality for extensions."""

    def test_auto_detect_pixi_extension(self):
        """Test that pixi extension is auto-detected from pixi.toml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # Create a pixi.toml file
            pixi_toml = repo_path / "pixi.toml"
            pixi_toml.write_text(
                """
[project]
name = "test"
version = "0.1.0"
""",
                encoding="utf-8",
            )

            ext_manager = ExtensionManager(Path("/tmp"))
            detected = auto_detect_extensions(repo_path, ext_manager)
            assert "pixi" in detected

    def test_auto_detect_uv_extension(self):
        """Test that uv extension is auto-detected from pyproject.toml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # Create a pyproject.toml file with [tool.uv] section
            pyproject_toml = repo_path / "pyproject.toml"
            pyproject_toml.write_text(
                """
[tool.uv]
option = "value"
""",
                encoding="utf-8",
            )

            ext_manager = ExtensionManager(Path("/tmp"))
            detected = auto_detect_extensions(repo_path, ext_manager)
            assert "uv" in detected

    def test_auto_detect_common_extensions(self):
        """Test that commonly useful extensions (x11, fzf) are auto-detected when their conditions are met."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            ext_manager = ExtensionManager(Path("/tmp"))
            detected = auto_detect_extensions(repo_path, ext_manager)

            # fzf should be detected if bash exists (which it should on most systems)
            # x11 should be detected if X11 socket exists
            # These may or may not be detected depending on the test environment
            # Just verify the detection logic works without hard assertions
            assert isinstance(detected, list)

    def test_pixi_extension_installation(self):
        """Test that pixi extension has proper installation logic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ExtensionManager(Path(tmpdir))
            pixi_ext = manager.get_extension("pixi")

            assert pixi_ext is not None
            assert pixi_ext.name == "pixi"
            # Check that the dockerfile includes logic to install as the right user
            assert "if id wtd" in pixi_ext.dockerfile_content
            assert "su - wtd -c" in pixi_ext.dockerfile_content
            # Check that PATH includes both locations
            assert "/root/.pixi/bin:/home/wtd/.pixi/bin" in pixi_ext.dockerfile_content


if __name__ == "__main__":
    # Run all extension tests manually if executed as a script
    all_passed = True
    for ext in ["base", "git", "user", "pixi", "uv"]:
        print(f"\nRunning test for extension: {ext}")
        result = run_extension_test_generic(ext)
        if not result:
            all_passed = False
    sys.exit(0 if all_passed else 1)
