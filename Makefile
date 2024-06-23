run-tests:
	# @echo "Running tests..."
	poetry run pytest tests/test_kithub.py

run-local:
	@echo "Running local server..."
	poetry run python tests/run_dev.py
