
if __name__ == "__main__":
    import uvicorn

    # Run the app
    uvicorn.run("example_tools:get_app", host="0.0.0.0", port=8000, reload=True)
