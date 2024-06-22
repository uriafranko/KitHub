import pytest
from fastapi.testclient import TestClient
from tests.example_tools import (
    example_function, example_tool, example_tool_with_args, get_app
)

from kithub import create_kit, create_kithub


@pytest.fixture
def client():
    app = get_app()
    return TestClient(app)


def test_get_functions(client):
    response = client.get("/v1")
    assert response.status_code == 200
    functions = response.json()
    assert len(functions) == 3
    function_names = [func["name"] for func in functions]
    assert "example_function" in function_names
    assert "example_tool" in function_names
    assert "example_tool_with_args" in function_names


def test_run_example_function(client):
    response = client.post(
        "/v1", json={"function_name": "example_function", "params": {}}
    )
    assert response.status_code == 200
    assert response.json() == {"result": "This is example function 1"}


def test_run_example_tool(client):
    response = client.post("/v1", json={"function_name": "example_tool", "params": {}})
    assert response.status_code == 200
    assert response.json() == {"result": "This is example tool 1"}


def test_run_example_tool_with_args(client):
    response = client.post(
        "/v1",
        json={"function_name": "example_tool_with_args", "params": {"x": 5, "y": 3}},
    )
    assert response.status_code == 200
    assert response.json() == {"result": "The sum of 5 and 3 is 8"}


def test_run_nonexistent_function(client):
    response = client.post(
        "/v1", json={"function_name": "nonexistent_function", "params": {}}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_run_function_with_invalid_params(client):
    response = client.post(
        "/v1",
        json={
            "function_name": "example_tool_with_args",
            "params": {"x": "not_a_number", "y": 3},
        },
    )
    assert response.status_code == 422
    assert "Validation error" in response.json()["detail"]


def test_run_function_with_missing_params(client):
    response = client.post(
        "/v1", json={"function_name": "example_tool_with_args", "params": {"x": 5}}
    )
    assert response.status_code == 422
    assert "Validation error" in response.json()["detail"]


@pytest.mark.parametrize(
    "tool_func", [example_function, example_tool, example_tool_with_args]
)
def test_tool_registration(tool_func):
    router = create_kit(prefix="/test", tools=[tool_func])
    app = create_kithub([router])
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    functions = response.json()
    print(functions)
    func_name = hasattr(tool_func, "name") and tool_func.name or tool_func.__name__
    assert any(func["name"] == func_name for func in functions)


def test_multiple_kits():
    router1 = create_kit(prefix="/v1", tools=[example_function])
    router2 = create_kit(prefix="/v2", tools=[example_tool])
    app = create_kithub([router1, router2])
    client = TestClient(app)

    response1 = client.get("/v1")
    assert response1.status_code == 200
    assert any(func["name"] == "example_function" for func in response1.json())

    response2 = client.get("/v2")
    assert response2.status_code == 200
    assert any(func["name"] == "example_tool" for func in response2.json())


def test_error_handling():
    def error_tool():
        """Tool that raises an error."""
        raise ValueError("Test error")

    router = create_kit(prefix="/test", tools=[error_tool])
    app = create_kithub([router])
    client = TestClient(app)

    response = client.post("/test", json={"function_name": "error_tool", "params": {}})
    assert response.status_code == 500
    assert "Test error" in response.json()["detail"]
