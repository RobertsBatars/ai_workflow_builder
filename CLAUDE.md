# AI Workflow Builder Guidelines

## Commands
- Install: `pip install -e .`
- Run app: `python -m ai_workflow_builder`
- Run headless: `python -m ai_workflow_builder --headless`
- Run with custom port: `python -m ai_workflow_builder --port 8888`
- Install dev dependencies: `pip install -r ai_workflow_builder/requirements.txt`

## Features & Usage
- **Main Window**: Provides menu options, toolbar, and central canvas
- **Toolbox**: Left sidebar with draggable node types
- **Property Panel**: Right sidebar for configuring selected nodes
- **Log Console**: Bottom panel showing application messages
- **Workflow Execution**: Use Run/Stop commands from the Workflow menu
- **History**: Undo/Redo support for all operations
- **Theme Settings**: Light/dark mode via Preferences dialog
- **Workflow Generation**: Generate workflows from natural language descriptions
- **Drag and Drop**: Drag nodes from toolbox to canvas
- **Saving/Loading**: Save workflows as checkpoints, import/export as JSON
- **Docker Integration**: Secure code execution with configurable isolation

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

## Debugging
- Check logs in the Log Console
- Look for errors in the terminal when running
- Use refresh_ui to reload UI if theme issues occur
- Make sure the API server is running (check /health endpoint)
- Verify file permissions in the checkpoints directory

## Recent Improvements
- Fixed drag and drop functionality
- Added proper theme handling for dark mode
- Implemented start/stop workflow controls
- Added undo/redo functionality with history tracking
- Added preferences dialog for theme and other settings
- Fixed checkpoint loading and management
- Added comprehensive workflow status monitoring