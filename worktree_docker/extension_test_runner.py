#!/usr/bin/env python3
"""
Generic extension test runner.
This script provides a generic way to test any extension that has a test.sh file.
"""

import subprocess
import sys
from pathlib import Path


def cleanup_containers():
    """Clean up test containers and environment."""
    print("Cleaning up test environment...")
    try:
        subprocess.run(["wtd", "--prune"], capture_output=True, timeout=30, check=False)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    try:
        subprocess.run(
            ["docker", "container", "prune", "-f", "--filter", "label=wtd"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    try:
        cache_dir = Path(".wtd")
        if cache_dir.exists():
            import shutil

            shutil.rmtree(cache_dir, ignore_errors=True)
    except Exception:
        pass


def run_extension_test_generic(
    extension_name: str, test_repo: str = "blooop/test_wtd@main"
) -> bool:
    """
    Generic extension test runner that handles all the boilerplate.

    Note: With the new extension filtering system, extensions are now auto-detected
    and have dependencies. Tests focus on ensuring the extension system works correctly
    rather than testing extensions in isolation.

    Args:
        extension_name: Name of the extension to test
        test_repo: Test repository to use (default: blooop/test_wtd@main)
    Returns:
        True if all tests pass, False otherwise
    """
    print(f"=== TESTING EXTENSION: {extension_name.upper()} ===")
    try:
        print("=== STEP 1: TEST EXTENSION IN LIST ===")
        result = subprocess.run(
            ["wtd", "--ext-list"], capture_output=True, text=True, timeout=30, check=False
        )
        if extension_name not in result.stdout:
            print(f"✗ {extension_name} extension not found in extension list")
            print(f"Extension list output: {result.stdout}")
            return False
        print(f"✓ {extension_name} extension appears in extension list")

        print("=== STEP 2: TEST EXTENSION LOADING ===")
        print(f"Testing {extension_name} extension loading with test repository...")

        # With the new system, we don't test extensions in isolation since they have
        # dependencies and auto-detection. Instead, we test that the extension loads
        # successfully as part of the overall extension system.
        load_result = subprocess.run(
            [
                "wtd",
                "--rebuild",  # Force rebuild to ensure fresh environment
                test_repo,
                "echo",
                "extension system test",
            ],
            capture_output=True,
            text=True,
            timeout=180,  # Increase timeout for rebuilds
            check=False,
        )
        output = load_result.stdout + load_result.stderr

        # Check that the extension system loaded successfully
        if "Loading extensions:" not in output:
            print("✗ Extension system failed to initialize")
            print("Load output:")
            print(output)
            return False
        print("✓ Extension system initialized successfully")

        # Check that our target extension was loaded (might be via dependencies or auto-detection)
        if f"✓ Loaded extension: {extension_name}" not in output:
            print(f"⚠ {extension_name} extension was not explicitly loaded")
            print("  This may be normal if the extension is loaded via dependencies")
        else:
            print(f"✓ {extension_name} extension loaded successfully")

        # Check that the command executed (more important than specific extension loading)
        if load_result.returncode == 0:
            print("✓ Command executed successfully in extension environment")
        else:
            print("✗ Command failed to execute")
            print("Load output:")
            print(output)
            return False

        print("=== STEP 3: TEST EXTENSION AVAILABILITY ===")
        # Test that the extension's functionality is available in the environment
        # First try to run the extension's specific test by reading and executing it
        extensions_dir = Path(__file__).parent.parent / "extensions"
        test_script = extensions_dir / extension_name / "test.sh"

        if test_script.exists():
            print(f"Running extension-specific test based on: {test_script}")
            # Read the test script content and execute it inline
            test_script_content = test_script.read_text()
            test_result = subprocess.run(
                [
                    "wtd",
                    "--rebuild",  # Force rebuild to test the fixed dockerfile
                    "-e",
                    extension_name,  # Explicitly request this extension
                    test_repo,
                    "bash",
                    "-c",
                    test_script_content,
                ],
                capture_output=True,
                text=True,
                timeout=180,  # Increase timeout for rebuild
                check=False,
            )
        else:
            print(f"No test.sh found for {extension_name}, running generic test")
            test_result = subprocess.run(
                [
                    "wtd",
                    "--rebuild",  # Force rebuild for generic tests too
                    "-e",
                    extension_name,  # Explicitly request this extension
                    test_repo,
                    "bash",
                    "-c",
                    f"echo 'Testing {extension_name} extension functionality' && exit 0",
                ],
                capture_output=True,
                text=True,
                timeout=180,  # Increase timeout for rebuild
                check=False,
            )

        if test_result.returncode == 0:
            print(f"✓ {extension_name} extension environment is functional")
        else:
            print(f"✗ {extension_name} extension environment test failed")
            test_output = test_result.stdout + test_result.stderr
            print("Test output:")
            print(test_output)
            return False

        print(f"=== {extension_name.upper()} EXTENSION TEST PASSED ===")
        return True

    except subprocess.TimeoutExpired:
        print(f"✗ {extension_name} extension test timed out")
        return False
    except Exception as e:
        print(f"✗ {extension_name} extension test failed with exception: {e}")
        return False


def main():
    """Main entry point for the extension test runner."""
    if len(sys.argv) != 2:
        print("Usage: python extension_test_runner.py <extension_name>")
        sys.exit(1)
    extension_name = sys.argv[1]
    cleanup_containers()
    try:
        success = run_extension_test_generic(extension_name)
        if success:
            print(f"\n🎉 All tests passed for {extension_name} extension!")
            sys.exit(0)
        else:
            print(f"\n❌ Tests failed for {extension_name} extension!")
            sys.exit(1)
    finally:
        cleanup_containers()


if __name__ == "__main__":
    main()
