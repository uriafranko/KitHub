import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Union

from fastapi import APIRouter, Body, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.tools import BaseTool, StructuredTool, Tool
from langchain_core.utils.function_calling import convert_to_openai_function
from pydantic import BaseModel, Field, ValidationError
from pydantic.v1.error_wrappers import ValidationError as ValidationErrorV1
from typing_extensions import Annotated

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tool_types = Union[StructuredTool, BaseTool, Tool]


class FunctionRunRequest(BaseModel):
    function_name: str = Field(title="Function name")
    params: Dict[str, Any]


def create_kit(
    tools: List[Union[tool_types, Callable]], prefix: str = "", **kwargs
) -> APIRouter:
    router = APIRouter(prefix=prefix, **kwargs)
    functions_list = []
    function_dict: Dict[str, tool_types] = {}

    for func in tools:
        if isinstance(func, (StructuredTool, BaseTool, Tool)):
            func_name = func.name
        elif callable(func):
            func_name = func.__name__
            if not func.__doc__:
                raise ValueError(f"Function {func_name} must have a docstring")
            func = StructuredTool.from_function(
                name=func_name, func=func, description=func.__doc__
            )
        else:
            raise ValueError(f"Invalid function type: {type(func)}")

        parsed_func = convert_to_openai_function(func)
        functions_list.append(parsed_func)
        function_dict[func_name] = func

    @router.get("", response_model=List[Dict[str, Any]])
    async def get_functions():
        return functions_list

    @router.post("")
    async def run_function(req: Annotated[FunctionRunRequest, Body] = Body(...)):
        func_name = req.function_name
        if func_name not in function_dict:
            raise HTTPException(
                status_code=404, detail=f"Function '{func_name}' not found"
            )

        func = function_dict[func_name]
        try:
            result = func.invoke(input=req.params)
            return {"result": result}
        except (ValidationError, ValidationErrorV1) as e:
            raise e
        except Exception as e:
            logger.exception(f"Error executing function '{func_name}'")
            raise HTTPException(status_code=500, detail=str(e))

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
