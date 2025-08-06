import subprocess
import os
import pytest
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).parent / "workflows"


def run_workflow_script(script_name, allowed_returncodes=(0, 1)):
    script = os.path.join(WORKFLOWS_DIR, script_name)
    os.chmod(script, 0o755)
    result = subprocess.run([script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    output = result.stdout.decode() + result.stderr.decode()
    assert result.returncode in allowed_returncodes, f"{script_name} failed: {output}"
    return output


def test_5_environment_recreation():
    """Test wtd environment recreation and recovery"""
    output = run_workflow_script("test_workflow_7_wtd_recreation.sh", allowed_returncodes=(0,))

    # Verify all test steps
    steps = [
        "=== STEP 1: Normal wtd operation ===",
        "=== STEP 2: Deleting .wtd folder ===",
        "=== STEP 3: Testing wtd recreation ===",
        "=== STEP 4: Testing subsequent operations ===",
        "=== ALL TESTS PASSED ===",
    ]
    for step in steps:
        assert step in output, f"{step} not found"

    # Ensure no critical errors occurred
    critical_errors = ["container breakout detected", "OCI runtime exec failed"]
    for error in critical_errors:
        assert error not in output, f"{error} error detected"


@pytest.mark.parametrize(
    "prune_workflow,expected_checks",
    [
        (
            "test_workflow_8_prune.sh",
            {
                "test_sections": [
                    "=== TEST 1: SETUP TEST ENVIRONMENT ===",
                    "=== TEST 2: SELECTIVE PRUNE TEST ===",
                    "=== TEST 3: SETUP MULTIPLE ENVIRONMENTS ===",
                    "=== TEST 4: FULL PRUNE TEST ===",
                ],
                "success_messages": [
                    "=== ALL PRUNE TESTS PASSED ===",
                    "✓ Selective prune completed",
                    "✓ Full prune completed",
                    "✓ Container correctly removed by selective prune",
                    "✓ Worktree correctly removed by selective prune",
                    "✓ All wtd containers correctly removed by full prune",
                    "✓ .wtd directory correctly removed by full prune",
                ],
            },
        ),
        (
            "test_workflow_10_new_branch.sh",
            {
                "test_sections": [
                    "=== TEST: NEW BRANCH WORKFLOW WITH PRUNE ===",
                    "=== STEP 1: INITIAL CLEANUP ===",
                    "=== STEP 2: CREATE NEW BRANCH ENVIRONMENT ===",
                    "=== STEP 3: VERIFY NEW BRANCH ENVIRONMENT ===",
                    "=== STEP 4: VERIFY CONTAINER EXISTS ===",
                    "=== STEP 5: TEST SELECTIVE PRUNE ===",
                    "=== STEP 6: RECREATE ENVIRONMENT FOR FULL PRUNE TEST ===",
                    "=== STEP 7: TEST FULL PRUNE ===",
                    "=== STEP 8: VERIFY WORKFLOW WORKS AFTER FULL PRUNE ===",
                ],
                "success_messages": [
                    "=== NEW BRANCH WORKFLOW WITH PRUNE TEST PASSED ===",
                    "✓ Successfully created worktree for new branch and ran git status",
                    "✓ Confirmed on new branch 'new_branch'",
                    "✓ Workspace is clean as expected",
                    "✓ Container for new branch environment is running",
                    "✓ Container correctly removed by selective prune",
                    "✓ Worktree correctly removed by selective prune",
                    "✓ Selective prune completed",
                    "✓ Full prune completed",
                    "✓ All wtd containers correctly removed by full prune",
                    "✓ .wtd directory correctly removed by full prune",
                    "✓ New branch workflow still works after full prune",
                ],
                "git_status_checks": [
                    "On branch new_branch",
                    "nothing to commit, working tree clean",
                ],
            },
        ),
    ],
)
def test_3_comprehensive_prune_operations(prune_workflow, expected_checks):
    """Combined test for prune operations with comprehensive environment validation"""
    output = run_workflow_script(prune_workflow, allowed_returncodes=(0,))

    # Verify all test sections are present
    for section in expected_checks.get("test_sections", []):
        assert section in output, f"{section} not found in {prune_workflow}"

    # Verify all success messages
    for message in expected_checks.get("success_messages", []):
        assert message in output, f"{message} not found in {prune_workflow}"

    # Verify git status checks (for new branch workflow)
    for git_check in expected_checks.get("git_status_checks", []):
        assert git_check in output, f"Git status '{git_check}' not found in {prune_workflow}"


@pytest.mark.parametrize(
    "cache_workflow,expected_checks",
    [
        (
            "test_workflow_5_force_rebuild_cache.sh",
            {
                "sections": [
                    "=== INITIAL BUILD ===",
                    "=== FORCE REBUILD TEST ===",
                    "=== CONTAINER REUSE TEST ===",
                    "=== NO-CACHE REBUILD TEST ===",
                    "=== TIMING SUMMARY ===",
                ],
                "timing_checks": True,
                "date_output": "UTC 202",
                "container_recreation": True,
            },
        ),
        (
            "test_workflow_12_nocache.sh",
            {
                "sections": [
                    "=== TEST: NOCACHE FEATURE ===",
                    "=== NOCACHE FEATURE TEST PASSED ===",
                ],
                "nocache_checks": True,
                "help_check": "✓ --nocache option appears in help",
                "buildx_check": "✓ --no-cache flag passed to buildx bake command",
                "env_check": "✓ Environment works correctly with --nocache",
                "clean_workspace": "✓ Git status shows clean workspace",
                "global_flag": "✓ Global --nocache flag works",
            },
        ),
    ],
)
def test_1_comprehensive_cache_operations(cache_workflow, expected_checks):
    """Combined test for cache-breaking operations with comprehensive validation"""
    import re

    output = run_workflow_script(cache_workflow, allowed_returncodes=(0,))

    # Verify all expected sections are present
    for section in expected_checks.get("sections", []):
        assert section in output, f"{section} section not found in {cache_workflow}"

    # Test workflow 5 specific checks (timing and performance)
    if expected_checks.get("timing_checks"):
        # Check date output
        assert (
            expected_checks["date_output"] in output
        ), f"Expected date output not found in {cache_workflow}"

        # Parse and validate timing data
        initial_match = re.search(r"Initial build:\s+(\d+)s", output)
        force_match = re.search(r"Force rebuild:\s+(\d+)s", output)
        reuse_match = re.search(r"Container reuse:\s+(\d+)s", output)
        nocache_match = re.search(r"No-cache rebuild:\s+(\d+)s", output)

        assert initial_match, "Could not find initial build timing"
        assert force_match, "Could not find force rebuild timing"
        assert nocache_match, "Could not find no-cache rebuild timing"
        assert reuse_match, "Could not find container reuse timing"

        initial_time = int(initial_match.group(1))
        force_time = int(force_match.group(1))
        reuse_time = int(reuse_match.group(1))
        nocache_time = int(nocache_match.group(1))

        # Validate performance expectations
        assert (
            reuse_time <= force_time
        ), f"Container reuse ({reuse_time}s) should be faster than force rebuild ({force_time}s)"
        if nocache_time > 5:
            assert (
                force_time <= nocache_time + 2
            ), f"Force rebuild with cache ({force_time}s) should be close to or faster than no-cache ({nocache_time}s)"

        # Validate container recreation behavior
        if expected_checks.get("container_recreation"):
            if "Force rebuild: removing existing container" in output:
                assert (
                    "Creating new persistent container" in output
                ), "Should create new container after force removal"

        print(
            f"Cache test performance: initial={initial_time}s, force={force_time}s, "
            f"nocache={nocache_time}s, reuse={reuse_time}s"
        )

    # Test workflow 12 specific checks (nocache functionality)
    if expected_checks.get("nocache_checks"):
        for check_key in [
            "help_check",
            "buildx_check",
            "env_check",
            "clean_workspace",
            "global_flag",
        ]:
            if check_key in expected_checks:
                assert (
                    expected_checks[check_key] in output
                ), f"{expected_checks[check_key]} not found in {cache_workflow}"


# Combined into test_1_comprehensive_cache_operations above


@pytest.mark.parametrize(
    "workflow,expected_checks",
    [
        (
            "test_workflow_3_cmd.sh",
            {"git_status": "On branch", "working_dir": ["test_wtd", "/tmp/test_wtd"]},
        ),
        ("test_workflow_4_persistent.sh", {"persistent_file": "persistent.txt"}),
        ("test_workflow_6_clean_git.sh", {"clean_execution": True}),
    ],
)
def test_2_basic_functionality(workflow, expected_checks):
    """Combined test for basic workflow functionality"""
    allowed_codes = (0, 1) if workflow != "test_workflow_6_clean_git.sh" else (0,)
    output = run_workflow_script(workflow, allowed_returncodes=allowed_codes)

    # Git status check
    if "git_status" in expected_checks:
        assert (
            expected_checks["git_status"] in output
        ), f"Expected git status '{expected_checks['git_status']}' not found in {workflow} output"

    # Working directory check
    if "working_dir" in expected_checks:
        found_dir = any(dir_path in output for dir_path in expected_checks["working_dir"])
        assert found_dir, f"Expected working directory paths {expected_checks['working_dir']} not found in {workflow} output"

    # Persistent file check
    if "persistent_file" in expected_checks:
        assert (
            expected_checks["persistent_file"] in output
        ), f"Expected persistent file '{expected_checks['persistent_file']}' not found in {workflow} output"


def test_4_container_lifecycle_management():
    """Test container reuse, recreation, and lifecycle management"""
    output = run_workflow_script("test_workflow_9_container_reuse.sh", allowed_returncodes=(0,))

    # Verify test sections
    test_sections = [
        "=== TEST 1: CREATE INITIAL ENVIRONMENT ===",
        "=== TEST 2: TEST CONTAINER REUSE ===",
        "=== TEST 3: TEST CONTAINER RECREATION AFTER STOP ===",
        "=== TEST 4: TEST REUSE OF RECREATED CONTAINER ===",
        "=== ALL CONTAINER REUSE TESTS PASSED ===",
    ]
    for section in test_sections:
        assert section in output, f"{section} not found"

    # Verify container behavior
    reuse_checks = [
        "✓ Container was reused (same ID:",
        "✓ Container was correctly recreated after being stopped",
        "✓ Recreated container was reused (same ID:",
    ]
    for check in reuse_checks:
        assert check in output, f"{check} not found"

    # Verify no stale container removal during reuse
    lines = output.split("\n")
    container_reuse_found = False
    stale_removal_after_reuse = False
    for i, line in enumerate(lines):
        if "✓ Container was reused (same ID:" in line:
            container_reuse_found = True
            for j in range(max(0, i - 10), min(len(lines), i + 10)):
                if "Removing stale container" in lines[j]:
                    stale_removal_after_reuse = True
                    break

    assert container_reuse_found, "Container reuse confirmation not found"
    assert (
        not stale_removal_after_reuse
    ), "Stale container removal should not happen when reusing existing container"


# Combined into test_3_comprehensive_prune_operations above


def test_6_shell_completion_installation():
    """Test shell completion installation and validation"""
    output = run_workflow_script("test_workflow_11_install_completion.sh", allowed_returncodes=(0,))

    # Test sections
    assert "=== TEST: SHELL COMPLETION INSTALLATION ===" in output, "Test start not found"
    assert (
        "=== SHELL COMPLETION INSTALLATION TEST PASSED ===" in output
    ), "Test completion not found"

    # Completion functionality checks
    completion_checks = [
        "✓ Bash completion file created successfully",
        "✓ Bash completion contains expected function",
        "✓ Bash completion contains correct commands (no destroy)",
        "✓ Bash completion script syntax is valid",
        "✓ Help shows --install option",
        "✓ Handles unsupported shell gracefully",
    ]
    for check in completion_checks:
        assert check in output, f"{check} not confirmed"


def test_0_basic_container_lifecycle():
    """Test basic container lifecycle and state transitions"""
    output = run_workflow_script("test_workflow_0_basic_lifecycle.sh", allowed_returncodes=(0,))

    # Verify test sections
    lifecycle_sections = [
        "=== BASIC CONTAINER LIFECYCLE TEST ===",
        "=== INITIAL CLEANUP ===",
        "=== TEST 1: FRESH START ===",
    ]
    for section in lifecycle_sections:
        assert section in output, f"{section} not found"

    # Verify successful operations
    assert "✓ Fresh container test completed" in output, "Fresh container test not completed"

    # Check for git status output (basic functionality)
    assert "On branch" in output, "Expected git status output not found"
