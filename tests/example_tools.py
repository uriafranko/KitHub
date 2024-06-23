from langchain_core.tools import tool

from kithub import create_kit, create_kithub


def example_function():
    """Example function that does nothing."""
    return "This is example function 1"


@tool
def example_tool():
    """Example tool that does nothing."""
    return "This is example tool 1"


@tool
def example_tool_with_args(x: int, y: int):
    """Add two numbers together."""
    return f"The sum of {x} and {y} is {x + y}"


def get_app():
    # Register endpoints
    kit = create_kit(
        prefix="/example", tools=[example_function, example_tool, example_tool_with_args]
    )

    return create_kithub([kit])


if __name__ == "__main__":
    app = get_app()
