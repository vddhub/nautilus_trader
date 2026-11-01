# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------
"""
Integration tests for runtime execution client add/remove on a live node.
"""

import asyncio

import pytest

from nautilus_trader.adapters.sandbox import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox import SandboxExecutionClientFactory
from nautilus_trader.live import LiveNode
from nautilus_trader.model.identifiers import Venue


@pytest.mark.asyncio
async def test_add_and_remove_exec_client_on_running_node() -> None:
    """
    Test adding and removing an execution client on a running live node.

    - Builds and runs a live node
    - Adds an execution client for a venue at runtime
    - Verifies removal works
    - Tests that duplicate-venue add raises RuntimeError
    """
    # Build the node before running
    node = LiveNode.build(
        name="TestNode",
        config=None,
        data_factories=None,
        exec_factories=None,
    )

    # Capture handle before starting the run
    handle = node.handle()

    # Track test outcomes
    test_completed = False
    duplicate_venue_raised = False

    # Start a concurrent task to run the node and test the add/remove
    async def run_node_with_client_lifecycle():
        nonlocal test_completed, duplicate_venue_raised
        try:
            await asyncio.sleep(0.1)  # Give the node a moment to start

            # Add a client at runtime
            factory = SandboxExecutionClientFactory()
            config = SandboxExecutionClientConfig(venue=Venue("SIM"))

            # Call py_add_exec_client_live on the node
            node.py_add_exec_client_live(factory, config, routing=None)

            # Wait for the command to process
            await asyncio.sleep(0.2)

            # Test: attempt to add another client for the same venue should raise
            try:
                factory2 = SandboxExecutionClientFactory()
                config2 = SandboxExecutionClientConfig(venue=Venue("SIM"))
                node.py_add_exec_client_live(factory2, config2, routing=None)
                # Should not reach here
                assert False, "Expected RuntimeError for duplicate-venue add"
            except RuntimeError as e:
                if "already has a registered execution client" in str(e):
                    duplicate_venue_raised = True
                else:
                    raise

            # Remove the client
            client_id = "SIM"
            node.py_remove_exec_client(client_id)

            # Wait for the removal to process
            await asyncio.sleep(0.2)

            test_completed = True

        finally:
            # Stop the node
            handle.stop()

    # Run both the node and the test task concurrently
    run_task = asyncio.create_task(run_node_with_client_lifecycle())
    try:
        await node.run_async()
    finally:
        # Make sure the test task completes
        try:
            await asyncio.wait_for(run_task, timeout=6.0)
        except asyncio.TimeoutError:
            pass

    assert test_completed, "Test did not complete"
    assert duplicate_venue_raised, "Duplicate-venue add did not raise RuntimeError"


def test_add_exec_client_node_not_running() -> None:
    """
    Test that py_add_exec_client_live raises when node is not running.
    """
    # Build a node but do NOT run it
    node = LiveNode.build(
        name="TestNode",
        config=None,
        data_factories=None,
        exec_factories=None,
    )

    # Attempt to add a client should raise
    factory = SandboxExecutionClientFactory()
    config = SandboxExecutionClientConfig(venue=Venue("SIM"))

    with pytest.raises(RuntimeError) as exc_info:
        node.py_add_exec_client_live(factory, config, routing=None)

    assert "not running" in str(exc_info.value)


def test_remove_exec_client_node_not_running() -> None:
    """
    Test that py_remove_exec_client raises when node is not running.
    """
    # Build a node but do NOT run it
    node = LiveNode.build(
        name="TestNode",
        config=None,
        data_factories=None,
        exec_factories=None,
    )

    # Attempt to remove a client should raise
    with pytest.raises(RuntimeError) as exc_info:
        node.py_remove_exec_client("SIM")

    assert "not running" in str(exc_info.value)
