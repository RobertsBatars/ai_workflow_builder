# AI Workflow Builder

A cross-platform Python application for creating AI agent workflows using a node-based interface. Users can drag-and-drop nodes (LLMs, tools, logic, storage), configure them, and export/share workflows as self-contained JSON files.

## Features

- **Node-Based Visual Editor**: Create workflows by connecting nodes on a canvas
- **Multiple Node Types**:
  - **LLM Node**: Run local/remote models (via LiteLLM), attach tools, validate JSON outputs
  - **Decision Node**: Branch workflows using Python expressions
  - **Composite Node**: Encapsulate sub-workflows into reusable nodes
  - **Storage Node**: Store text/key-value data and vector embeddings
  - **Custom Python Node**: Execute user code in sandboxed environments
  - **Tool Node**: Use prebuilt (web search, file I/O) or user-defined tools
- **Workflow Management**: Export and import workflows as JSON
- **Execution Engine**: Async execution with topological sorting
- **Virtualization**: Optional Docker-based sandboxing
- **State Management**: Autosave progress and resume from checkpoints

## Installation

### Prerequisites

- Python 3.8 or higher
- PIP package manager

### Install from PyPI

```bash
pip install ai-workflow-builder
```

### Install from Source

```bash
git clone https://github.com/yourusername/ai-workflow-builder.git
cd ai-workflow-builder
pip install -e .
```

## Usage

### Starting the Application

```bash
# Start the full application (GUI + API server)
ai-workflow-builder

# Start in headless mode (API server only)
ai-workflow-builder --headless

# Start with custom host and port
ai-workflow-builder --host 0.0.0.0 --port 8888
```

### Command Line Options

- `--headless`: Run in headless mode (API server only)
- `--host HOST`: Host to bind the API server (default: localhost)
- `--port PORT`: Port to bind the API server (default: 8000)
- `--debug`: Run in debug mode
- `--version`: Show version information

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/yourusername/ai-workflow-builder.git
cd ai-workflow-builder
pip install -e ".[dev]"
```

### Project Structure

```
ai_workflow_builder/
├── frontend/                 # PySide6 GUI
│   ├── main_window.py        # Main window setup
│   ├── node_editor/          # NodeGraphQt integration
│   ├── widgets/              # Property panels, toolboxes
│   └── utils/                # Helper functions
├── backend/
│   ├── nodes/                # Node classes (LLM, decision, etc.)
│   ├── tools/                # Web search, file I/O, custom tools
│   ├── storage/              # FAISS/SQLite storage logic
│   ├── workflows.py          # DAG execution engine
│   ├── state_manager.py      # Checkpointing logic
│   └── api.py                # FastAPI endpoints
├── shared/                   # Schemas, constants
└── tests/                    # Unit/integration tests
```

## Examples

### Example Workflow: Research Assistant

1. **Research Phase**:
   - LLM Node generates search queries
   - Web Search Tool fetches information
   - Vector Storage Node stores the results

2. **Report Phase**:
   - LLM Node retrieves relevant information from Vector Storage
   - LLM Node generates a comprehensive report

3. **Export the workflow as JSON** for sharing or reuse

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.