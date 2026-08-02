"""Protocol-level checks for the optional MCP Python SDK 2.x adapter."""

from __future__ import annotations

import asyncio
from importlib.metadata import version

import pytest


def test_mcp_server_negotiates_2026_protocol_and_lists_structured_tools() -> None:
    pytest.importorskip("mcp")
    if int(version("mcp").split(".", 1)[0]) < 2:
        pytest.skip("MCP Python SDK 2.x is required")

    from mcp import Client

    from abi.mcp.server import create_server

    async def exercise_server() -> None:
        async with Client(create_server()) as client:
            listed = await client.list_tools()

            assert client.protocol_version == "2026-07-28"
            assert client.server_info is not None
            assert client.server_info.name == "abi"
            assert client.server_info.version == version("abi-agent")

            list_types = next(tool for tool in listed.tools if tool.name == "abi_list_types")
            assert list_types.input_schema["type"] == "object"
            assert list_types.output_schema is not None
            assert list_types.output_schema["type"] == "object"
            assert list_types.annotations is not None
            assert list_types.annotations.read_only_hint is True

            plan = next(tool for tool in listed.tools if tool.name == "abi_plan")
            assert plan.annotations is not None
            assert plan.annotations.read_only_hint is False
            thread_schema = plan.input_schema["properties"]["threads"]["anyOf"][0]
            assert thread_schema["minimum"] == 1
            assert thread_schema["description"]

    asyncio.run(exercise_server())
