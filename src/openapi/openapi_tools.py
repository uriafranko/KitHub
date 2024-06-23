from typing import Any, Dict, List, Optional, Type

import yaml
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field, create_model

from models import AuthenticatedTool
from openapi.utils import create_api_operation


def string_to_bool(obj):
    if isinstance(obj, dict):
        return {k: string_to_bool(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [string_to_bool(elem) for elem in obj]
    if isinstance(obj, str):
        if obj.lower() == "true":
            return True
        if obj.lower() == "false":
            return False
    return obj


def get_type_annotation(param_schema: Dict[str, Any]) -> Any:
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": List[Any],
        "object": Dict[str, Any],
    }
    return type_mapping.get(param_schema.get("type", "string"), Any)


def resolve_schema_ref(spec: Dict[str, Any], ref: str) -> Dict[str, Any]:
    parts = ref.split("/")
    current = spec
    for part in parts[1:]:  # Skip the first '#' part
        if part in current:
            current = current[part]
        else:
            raise ValueError(f"Unable to resolve reference: {ref}")
    return current


def extract_authentication(spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    parsed_schemes = {}

    for scheme_name, scheme in security_schemes.items():
        parsed_scheme = {
            "type": scheme.get("type"),
            "description": scheme.get("description"),
        }

        if scheme["type"] == "oauth2":
            parsed_scheme["flows"] = {}
            for flow_name, flow in scheme.get("flows", {}).items():
                parsed_scheme["flows"][flow_name] = {
                    "authorizationUrl": flow.get("authorizationUrl"),
                    "tokenUrl": flow.get("tokenUrl"),
                    "refreshUrl": flow.get("refreshUrl"),
                    "scopes": flow.get("scopes", {}),
                }
        elif scheme["type"] == "apiKey":
            parsed_scheme["in"] = scheme.get("in")
            parsed_scheme["name"] = scheme.get("name")
        elif scheme["type"] == "http":
            parsed_scheme["scheme"] = scheme.get("scheme")

        parsed_schemes[scheme_name] = parsed_scheme

    return parsed_schemes


def extract_parameters(operation: Dict, spec: Dict[str, Any]) -> List[Dict]:
    all_params = []

    def process_param(param):
        if "$ref" in param:
            param = resolve_schema_ref(spec, param["$ref"])
        param_schema = param.get("schema", {})
        if "$ref" in param_schema:
            param_schema = resolve_schema_ref(spec, param_schema["$ref"])
        description = param.get("description", param_schema.get("description", ""))
        return {
            "name": param.get("name"),
            "description": description,
            "required": param.get("required", False),
            "schema": param_schema,
            "in": param.get("in"),
        }

    # Extract path, query, and header parameters
    all_params.extend(process_param(param) for param in operation.get("parameters", []))

    # Extract body parameters
    request_body = operation.get("requestBody", {})
    if request_body:
        if "$ref" in request_body:
            request_body = resolve_schema_ref(spec, request_body["$ref"])
        content = request_body.get("content", {})
        for content_schema in content.values():
            schema = content_schema.get("schema", {})
            if "$ref" in schema:
                schema = resolve_schema_ref(spec, schema["$ref"])
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    if "$ref" in prop_schema:
                        prop_schema = resolve_schema_ref(spec, prop_schema["$ref"])
                    all_params.append(
                        {
                            "name": prop_name,
                            "description": prop_schema.get(
                                "description", "No description"
                            ),
                            "required": prop_name in schema.get("required", []),
                            "schema": prop_schema,
                            "in": "body",
                        }
                    )

    return all_params


def create_pydantic_model(
    params: List[Dict[str, Any]], model_name: str
) -> Type[BaseModel]:
    fields = {}
    for i, param in enumerate(params):
        field_type = get_type_annotation(param["schema"])
        default = ... if param["required"] else None
        name = param["name"] or f"param_{i}"  # Use a generic name if missing
        fields[name] = (
            Optional[field_type],
            Field(default=default, description=param["description"]),
        )

    return create_model(model_name, **fields)


def create_llm_tools_from_openapi(openapi_file: str) -> List[StructuredTool]:
    with open(openapi_file, "r") as file:
        spec_dict = yaml.safe_load(file)

    spec_dict = string_to_bool(spec_dict)

    try:
        validate(instance=spec_dict, schema={"type": "object"})
    except ValidationError as e:
        raise ValueError(f"Invalid OpenAPI spec: {e}")

    if isinstance(spec_dict, dict):
        auth_schemes = extract_authentication(spec_dict)
        base_url = spec_dict.get("servers", [{}])[0].get("url", "")
    else:
        raise ValueError("Invalid OpenAPI spec")

    tools = []

    for path, path_item in spec_dict.get("paths", {}).items():  # type: ignore
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue

            all_params = extract_parameters(operation, spec_dict)  # type: ignore
            model_name = f"{method.capitalize()}{path.replace('/', '_')}Model"
            RequestModel = create_pydantic_model(all_params, model_name)

            description = operation.get("summary") or operation.get("description", "")
            func_name = f"{path.replace('/', '_').replace('{', '').replace('}', '')}"
            if func_name.startswith("_"):
                func_name = func_name[1:]

            operation_auth = operation.get("security", [])
            auth_requirements = []
            for auth in operation_auth:
                for scheme, scopes in auth.items():
                    if scheme in auth_schemes:
                        auth_req = {
                            "scheme": scheme,
                            "type": auth_schemes[scheme]["type"],
                            "scopes": scopes,
                        }
                        if auth_schemes[scheme]["type"] == "oauth2":
                            auth_req["flows"] = auth_schemes[scheme]["flows"]
                        elif auth_schemes[scheme]["type"] == "apiKey":
                            auth_req["in"] = auth_schemes[scheme]["in"]
                            auth_req["name"] = auth_schemes[scheme]["name"]
                        elif auth_schemes[scheme]["type"] == "http":
                            auth_req["scheme"] = auth_schemes[scheme]["scheme"]
                        auth_requirements.append(auth_req)

            tool = AuthenticatedTool.from_function(
                func=create_api_operation(
                    method, path, RequestModel, auth_requirements, base_url
                ),
                name=func_name,
                description=description.strip(),
                args_schema=RequestModel,
                auth_requirements=auth_requirements,
            )
            tools.append(tool)
    return tools
