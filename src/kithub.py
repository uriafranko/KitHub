import logging
import re
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPBearer
from langchain_core.tools import BaseTool, StructuredTool, Tool
from langchain_core.utils.function_calling import convert_to_openai_function
from pydantic import BaseModel, Field, ValidationError, create_model
from pydantic.v1.error_wrappers import ValidationError as ValidationErrorV1

from models import AuthenticatedTool

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tool_types = (AuthenticatedTool, StructuredTool, BaseTool, Tool)
tool_types_types = Union[AuthenticatedTool, StructuredTool, BaseTool, Tool]


class FunctionRunRequest(BaseModel):
    function_name: str = Field(title="Function name")
    params: Dict[str, Any]


def get_python_type(openapi_type: str) -> Any:
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": List,
        "object": Dict,
    }
    return type_mapping.get(openapi_type, Any)


def create_kit(
    tools: List[Union[tool_types_types, Callable]], prefix: str = "", **kwargs
) -> APIRouter:
    router = APIRouter(prefix=prefix, **kwargs)
    functions_list = []
    function_dict: Dict[str, tool_types_types] = {}
    operation_ids = set()

    for func in tools:
        if isinstance(func, tool_types):
            func_name = func.name
        elif callable(func):
            func_name = func.__name__
            if not func.__doc__:
                raise ValueError(f"Function {func_name} must have a docstring")
            func = AuthenticatedTool.from_function(
                name=func_name, func=func, description=func.__doc__
            )
        else:
            raise ValueError(f"Invalid function type: {type(func)}")

        auth_dependencies = []
        if isinstance(func, AuthenticatedTool):
            for auth in func.auth_requirements:
                if auth["type"] == "oauth2":
                    bearer_sec = HTTPBearer()
                    auth_dependencies.append(Depends(bearer_sec))
                elif auth["type"] == "apiKey":
                    api_key_scheme = APIKeyHeader(name=auth["name"])
                    auth_dependencies.append(Depends(api_key_scheme))

        parsed_func = convert_to_openai_function(func)

        functions_list.append(parsed_func)
        function_dict[func_name] = func

        # Create a Pydantic model for the function parameters
        param_fields = {}
        for param_name, param_info in (
            parsed_func.get("parameters", {}).get("properties", {}).items()
        ):
            param_type = get_python_type(param_info.get("type", "string"))
            param_description = param_info.get("description", "")
            is_required = param_name in parsed_func.get("parameters", {}).get(
                "required", []
            )

            if is_required:
                param_fields[param_name] = (
                    param_type,
                    Field(..., description=param_description),
                )
            else:
                param_fields[param_name] = (
                    Optional[param_type],
                    Field(None, description=param_description),
                )

        ParamModel = create_model(f"{func_name}Params", **param_fields)

        def create_endpoint_function(func_name: str, func: tool_types_types, ParamModel):
            async def run_specific_function(request: Request, params: ParamModel):
                try:
                    auth_headers = dict(request.headers)
                    auth_params = dict(request.query_params)

                    full_params = {
                        **params.model_dump(),
                        "auth_headers": auth_headers,
                        "auth_params": auth_params,
                    }
                    result = func.invoke(input=full_params)
                    return {"result": result}
                except (ValidationError, ValidationErrorV1) as e:
                    raise e
                except Exception as e:
                    logger.exception(f"Error executing function '{func_name}'")
                    raise HTTPException(status_code=500, detail=str(e))

            return run_specific_function

        # Generate a unique operation ID
        base_operation_id = re.sub(r"[^a-zA-Z0-9_]", "_", func_name.lower())
        operation_id = base_operation_id
        counter = 1
        while operation_id in operation_ids:
            operation_id = f"{base_operation_id}_{counter}"
            counter += 1
        operation_ids.add(operation_id)

        # Create an endpoint for this specific function
        endpoint_function = create_endpoint_function(func_name, func, ParamModel)
        router.add_api_route(
            f"/{func_name}",
            endpoint_function,
            methods=["POST"],
            summary=func.description,
            dependencies=auth_dependencies,
            response_model=Dict[str, Any],
            operation_id=operation_id,
        )

        # Assign the unique operation ID
        endpoint_function.__name__ = operation_id

        # Assign the docstring to the endpoint function for better documentation
        endpoint_function.__doc__ = func.description

    @router.get("", response_model=List[Dict[str, Any]])
    async def get_functions():
        return functions_list

    return router


def create_kithub(
    kits: List[APIRouter],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **kwargs,
) -> FastAPI:
    app = FastAPI(**kwargs)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,  # Modify this in production
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )

    @app.exception_handler(ValidationError)
    @app.exception_handler(ValidationErrorV1)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: Union[ValidationError, ValidationErrorV1, RequestValidationError],
    ):
        errors = defaultdict(list)
        for error in exc.errors():
            locs = error["loc"]
            msg = error["msg"]
            loc_str = ".".join(str(loc) for loc in locs if loc != "body")
            errors[loc_str].append(msg)

        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {"detail": "Validation error", "errors": dict(errors)}
            ),
        )

    for router in kits:
        app.include_router(router)

    return app
