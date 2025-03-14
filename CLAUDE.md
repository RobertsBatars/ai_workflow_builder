# AI Workflow Builder Guidelines

## Commands
- Install: `pip install -e .`
- Run app: `python -m ai_workflow_builder`
- Run headless: `python -m ai_workflow_builder --headless`
- Run with custom port: `python -m ai_workflow_builder --port 8888`
- Install dev dependencies: `pip install -r ai_workflow_builder/requirements.txt`

## Code Style
- **Imports**: Group standard lib, third-party, then local imports
- **Formatting**: Use 4 spaces for indentation
- **Types**: Use type hints for function parameters and return values
- **Naming**: 
  - snake_case for variables, functions, methods
  - CamelCase for classes
  - ALL_CAPS for constants
- **Documentation**: Docstrings for all classes and functions using """triple quotes"""
- **Error handling**: Use try/except with specific exceptions; log errors
- **Architecture**: Follow the existing frontend/backend/shared structure
- **Extensions**: Add new node types in backend/nodes/ and register in NodeRegistry