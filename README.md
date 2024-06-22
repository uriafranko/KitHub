<h1 align="center"> 🛠️ KitHub 🛠️ </h1>

<p align="center">
  <img src="public/logo.png" alt="KitHub Logo" width="250"/>
</p>

<p align="center">
  <!-- <a href="https://github.com/uriafranko/kithub/actions"><img src="https://github.com/uriafranko/kithub/workflows/tests/badge.svg" alt="Build Status"></a> -->
  <a href="https://pypi.org/project/kithub/"><img src="https://img.shields.io/pypi/v/kithub.svg" alt="PyPI version"></a>
  <a href="https://github.com/uriafranko/kithub/blob/main/LICENSE"><img src="https://img.shields.io/github/license/uriafranko/kithub.svg" alt="License"></a>
</p>

KitHub is a powerful framework for creating and managing tool-based APIs. It integrates seamlessly with LangChain tools and provides a simple interface for exposing these tools as API endpoints.

## ✨ Features

- 🔧 Easy integration with LangChain tools
- 🚀 Rapid API development with FastAPI
- 🔒 Built-in input validation and error handling
- 📚 Automatic OpenAPI (Swagger) documentation
- 🌐 CORS support out of the box
- 🧰 Modular design with support for multiple tool kits

## 🚀 Quick Start

### Installation

```bash
pip install kithub
```

### Basic Usage

```python
from kithub import create_kit, create_kithub
from langchain_core.tools import tool

@tool
def example_tool(x: int, y: int):
    """Add two numbers together."""
    return x + y

# Create a kit with your tools
kit = create_kit(tools=[example_tool], prefix="/v1")

# Create the KitHub app
app = create_kithub([kit])

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 📖 Documentation

For full documentation, visit [kithub.readthedocs.io](https://kithub.readthedocs.io).

## 🧪 Running Tests

```bash
pytest tests/
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/) for the awesome web framework
- [LangChain](https://python.langchain.com/) for the powerful tool abstractions

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/uriafranko">Uria Franko</a>
</p>
