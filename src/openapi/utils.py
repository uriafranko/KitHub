from typing import List, Optional
from urllib.parse import urljoin

import requests


def create_api_operation(method, path, RequestModel, auth_requirements, base_url):
    def api_operation(**kwargs):
        nonlocal path  # This allows us to modify the path if needed
        validated_data = RequestModel(**kwargs)
        headers = {}
        params = {}
        data = None
        json_data = None
        auth = None

        # Process authentication
        for auth_req in auth_requirements:
            if auth_req["type"] == "apiKey":
                if auth_req["in"] == "header":
                    headers[auth_req["name"]] = kwargs.get("auth_headers", {}).get(
                        auth_req["name"]
                    )
                elif auth_req["in"] == "query":
                    params[auth_req["name"]] = kwargs.get("auth_params", {}).get(
                        auth_req["name"]
                    )
            elif auth_req["type"] == "oauth2":
                token = kwargs.get("auth_headers", {}).get("Authorization")
                if token:
                    headers["Authorization"] = token
            elif auth_req["type"] == "http" and auth_req["scheme"] == "bearer":
                token = kwargs.get("auth_headers", {}).get("Authorization")
                if token:
                    headers["Authorization"] = f"Bearer {token}"

        # Process parameters
        for param_name, param_value in validated_data.dict(exclude_unset=True).items():
            param_info = RequestModel.__fields__[param_name]
            param_location = param_info.field_info.extra.get("in", "body")

            if param_location == "query":
                params[param_name] = param_value
            elif param_location == "header":
                headers[param_name] = str(param_value)
            elif param_location == "path":
                path = path.replace(f"{{{param_name}}}", str(param_value))
            else:  # Assume body parameter if not specified
                if data is None:
                    data = {}
                data[param_name] = param_value

        if data and method.lower() in ["post", "put", "patch"]:
            json_data = data
            data = None

        url = urljoin(base_url, path)

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                params=params,
                headers=headers,
                data=data,
                json=json_data,
                auth=auth,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {
                "error": str(e),
                "status_code": e.response.status_code if e.response else None,
                "response_text": e.response.text if e.response else None,
            }

    return api_operation


def get_bearer_token(
    client_id: str,
    client_secret: str,
    token_url: str,
    grant_type: str,
    scopes: Optional[List[str]] = None,
) -> str:
    import requests

    data = {
        "grant_type": grant_type,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    if scopes:
        data["scope"] = " ".join(scopes)

    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]

    raise Exception(f"Failed to retrieve token: {response.text}")
