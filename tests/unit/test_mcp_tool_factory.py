"""Tests for safe MCP tool function generation."""

from __future__ import annotations

import inspect
import json
from typing import Annotated, Literal, get_args, get_origin

import pytest

from abi.mcp._tool_factory import ToolDescriptor, make_tool_func


def test_tool_descriptor_builds_keyword_only_signature() -> None:
    desc = ToolDescriptor(
        "run_tool",
        {
            "description": "Run a tool",
            "properties": {
                "input_path": {"type": "string"},
                "threads": {"type": "integer"},
            },
            "required": ["input_path"],
        },
    )

    sig = desc.make_function_signature()
    params = sig.parameters

    assert list(params) == ["input_path", "threads"]
    assert params["input_path"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["input_path"].default is inspect.Parameter.empty
    assert params["input_path"].annotation is str
    assert params["threads"].default is None
    assert sig.return_annotation == dict[str, object] or get_origin(sig.return_annotation) is dict


def test_tool_descriptor_rejects_unsafe_names() -> None:
    with pytest.raises(ValueError, match="Invalid tool name"):
        ToolDescriptor("bad-name", {"properties": {}})
    with pytest.raises(ValueError, match="Invalid parameter name"):
        ToolDescriptor("good_name", {"properties": {"bad-name": {"type": "string"}}})


def test_tool_descriptor_tolerates_malformed_property_metadata() -> None:
    no_properties = ToolDescriptor("no_properties", {"properties": ["not", "a", "mapping"]})
    fallback_type = ToolDescriptor(
        "fallback_type",
        {"properties": {"value": "not a schema"}, "required": ["value"]},
    )

    assert list(no_properties.make_function_signature().parameters) == []
    assert fallback_type.properties == {"value": {"type": "string"}}
    assert fallback_type.make_function_signature().parameters["value"].annotation is str


def test_make_tool_func_rejects_unknown_kwargs_and_calls_agent_method() -> None:
    calls: list[dict] = []

    def agent_method(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return json.dumps({"status": "success", "result": "ok"})

    desc = ToolDescriptor(
        "dispatch",
        {
            "description": "Dispatch",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    func = make_tool_func(desc, agent_method)

    assert func(query="abc") == {"status": "success", "result": "ok"}
    assert calls == [{"query": "abc"}]
    assert func.__name__ == "dispatch"
    assert inspect.signature(func).parameters["query"].annotation is str

    with pytest.raises(ValueError, match="Unknown parameters"):
        func(query="abc", extra=True)


def test_tool_descriptor_preserves_schema_descriptions_constraints_and_enum() -> None:
    desc = ToolDescriptor(
        "constrained_tool",
        {
            "properties": {
                "threads": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Worker count.",
                },
                "engine": {
                    "type": "string",
                    "enum": ["local", "hpc"],
                    "description": "Execution engine.",
                },
            },
            "required": ["threads", "engine"],
        },
    )

    params = desc.make_function_signature().parameters
    threads_annotation = params["threads"].annotation
    engine_annotation = params["engine"].annotation

    assert get_origin(threads_annotation) is Annotated
    assert get_args(threads_annotation)[0] is int
    assert get_origin(engine_annotation) is Annotated
    assert get_origin(get_args(engine_annotation)[0]) is Literal
