from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import Field


class AuthenticatedTool(StructuredTool):
    auth_requirements: List[Dict[str, Any]] = Field(default=[])

    @classmethod
    def from_function(
        cls,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        return_direct: bool = False,
        args_schema: Optional[Any] = None,
        infer_schema: bool = True,
        auth_requirements: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> "AuthenticatedTool":
        tool = super().from_function(
            func=func,
            name=name,
            description=description,
            return_direct=return_direct,
            args_schema=args_schema,
            infer_schema=infer_schema,
            **kwargs,
        )
        return cls(
            func=tool.func,
            name=tool.name,
            description=tool.description,
            return_direct=tool.return_direct,
            args_schema=tool.args_schema,
            auth_requirements=auth_requirements or [],
            **kwargs,
        )
