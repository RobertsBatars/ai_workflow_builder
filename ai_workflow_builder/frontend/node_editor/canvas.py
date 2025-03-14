"""
Canvas widget for the node editor.
Uses NodeGraphQt for node graph visualization and editing.
"""
import uuid
import json
from typing import Dict, Any, List, Tuple, Optional, Set

from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt, Signal, Slot, QPointF
from PySide6.QtGui import QColor

# NodeGraphQt imports with fallbacks
try:
    # Try standard imports first
    from NodeGraphQt import NodeGraph
    from NodeGraphQt.qgraphics.node_backdrop import BackdropNode
    from NodeGraphQt.qgraphics.node_base import NodeItem as NodeBaseWidget
    from NodeGraphQt.qgraphics.port_item import PortItem as Port
except ImportError as e:
    # Try alternate structure for different versions
    try:
        from NodeGraphQt import NodeGraph, NodeItem as NodeBaseWidget, PortItem as Port
        from NodeGraphQt.nodes.backdrop_node import BackdropNode
    except ImportError:
        # If all else fails, just import what we can
        from NodeGraphQt import NodeGraph
        # Create stub classes for compatibility
        class NodeBaseWidget:
            def __init__(self, name=None):
                self.name = name
        class BackdropNode:
            pass
        class Port:
            pass


# Define node classes for the different node types
class LLMNode(NodeBaseWidget):
    """LLM node for running language models."""
    
    # Unique identifier
    __identifier__ = 'ai_workflow_builder'
    
    # Node type name
    NODE_NAME = 'LLM Node'
    
    def __init__(self):
        super(LLMNode, self).__init__(name=self.NODE_NAME)
        
        # Set node color
        self.set_color(20, 120, 180)
        
        # Create input and output ports
        self.add_input('prompt', color=(180, 80, 0))
        self.add_input('system_prompt', color=(180, 80, 0))
        self.add_input('temperature', color=(180, 80, 0))
        self.add_input('tools', color=(180, 80, 0))
        
        self.add_output('response', color=(0, 180, 80))
        self.add_output('tool_calls', color=(0, 180, 80))
        self.add_output('error', color=(180, 0, 0))
        
        # Node properties
        self.create_property('model', 'gpt-4', widget_type='line_edit')
        self.create_property('system_prompt', 'You are a helpful assistant.', widget_type='text_edit')
        self.create_property('temperature', 0.7, widget_type='float', range=(0.0, 2.0))


class DecisionNode(NodeBaseWidget):
    """Decision node for conditional branching."""
    
    # Unique identifier
    __identifier__ = 'ai_workflow_builder'
    
    # Node type name
    NODE_NAME = 'Decision Node'
    
    def __init__(self):
        super(DecisionNode, self).__init__(name=self.NODE_NAME)
        
        # Set node color
        self.set_color(180, 120, 20)
        
        # Create input and output ports
        self.add_input('value', color=(180, 80, 0))
        self.add_input('condition', color=(180, 80, 0))
        
        self.add_output('true', color=(0, 180, 80))
        self.add_output('false', color=(180, 0, 0))
        self.add_output('error', color=(180, 0, 0))
        
        # Node properties
        self.create_property('condition', 'input > 0', widget_type='line_edit')
        self.create_property('true_port', 'true', widget_type='line_edit')
        self.create_property('false_port', 'false', widget_type='line_edit')


class StorageNode(NodeBaseWidget):
    """Storage node for static and vector storage."""
    
    # Unique identifier
    __identifier__ = 'ai_workflow_builder'
    
    # Node type name
    NODE_NAME = 'Storage Node'
    
    def __init__(self):
        super(StorageNode, self).__init__(name=self.NODE_NAME)
        
        # Set node color
        self.set_color(120, 20, 180)
        
        # Create input and output ports
        self.add_input('key', color=(180, 80, 0))
        self.add_input('value', color=(180, 80, 0))
        self.add_input('operation', color=(180, 80, 0))
        
        self.add_output('result', color=(0, 180, 80))
        self.add_output('success', color=(0, 180, 80))
        self.add_output('error', color=(180, 0, 0))
        
        # Node properties
        self.create_property('storage_type', 'static', widget_type='combo', items=['static', 'vector'])
        self.create_property('dimension', 768, widget_type='int', range=(1, 4096))
        self.create_property('persist', False, widget_type='bool')


class PythonNode(NodeBaseWidget):
    """Python node for custom code execution."""
    
    # Unique identifier
    __identifier__ = 'ai_workflow_builder'
    
    # Node type name
    NODE_NAME = 'Python Node'
    
    def __init__(self):
        super(PythonNode, self).__init__(name=self.NODE_NAME)
        
        # Set node color
        self.set_color(20, 180, 120)
        
        # Create input and output ports
        self.add_input('input', color=(180, 80, 0))
        self.add_input('code', color=(180, 80, 0))
        self.add_input('timeout', color=(180, 80, 0))
        
        self.add_output('output', color=(0, 180, 80))
        self.add_output('error', color=(180, 0, 0))
        
        # Node properties
        self.create_property('code', 'def run(input_data):\n    # Your code here\n    return input_data', widget_type='text_edit')
        self.create_property('requirements', [], widget_type='list')


class ToolNode(NodeBaseWidget):
    """Tool node for using built-in or custom tools."""
    
    # Unique identifier
    __identifier__ = 'ai_workflow_builder'
    
    # Node type name
    NODE_NAME = 'Tool Node'
    
    def __init__(self):
        super(ToolNode, self).__init__(name=self.NODE_NAME)
        
        # Set node color
        self.set_color(180, 20, 120)
        
        # Create input and output ports
        self.add_input('input', color=(180, 80, 0))
        self.add_input('parameters', color=(180, 80, 0))
        
        self.add_output('output', color=(0, 180, 80))
        self.add_output('error', color=(180, 0, 0))
        
        # Node properties
        self.create_property('tool_name', '', widget_type='line_edit')
        self.create_property('tool_parameters', {}, widget_type='dict')


class CompositeNode(NodeBaseWidget):
    """Composite node for encapsulating sub-workflows."""
    
    # Unique identifier
    __identifier__ = 'ai_workflow_builder'
    
    # Node type name
    NODE_NAME = 'Composite Node'
    
    def __init__(self):
        super(CompositeNode, self).__init__(name=self.NODE_NAME)
        
        # Set node color
        self.set_color(100, 100, 100)
        
        # Create input and output ports
        self.add_input('input', color=(180, 80, 0))
        
        self.add_output('output', color=(0, 180, 80))
        self.add_output('error', color=(180, 0, 0))
        
        # Node properties
        self.create_property('workflow_json', {}, widget_type='dict')


class NodeEditorCanvas(QWidget):
    """
    Canvas widget for the node editor.
    Uses NodeGraphQt for node graph visualization and editing.
    """
    # Signals
    node_selected = Signal(object)  # Node ID
    workflow_modified = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Parent window reference
        self.main_window = parent
        
        # Node graph
        self.graph = NodeGraph()
        self.graph.register_node(LLMNode)
        self.graph.register_node(DecisionNode)
        self.graph.register_node(StorageNode)
        self.graph.register_node(PythonNode)
        self.graph.register_node(ToolNode)
        self.graph.register_node(CompositeNode)
        
        # Connect signals
        self.graph.node_selected.connect(self._on_node_selected)
        self.graph.node_created.connect(self._on_node_created)
        self.graph.node_deleted.connect(self._on_node_deleted)
        self.graph.port_connected.connect(self._on_port_connected)
        self.graph.port_disconnected.connect(self._on_port_disconnected)
        self.graph.property_changed.connect(self._on_property_changed)
        
        # Set up UI
        self.setup_ui()
        
        # Node map: Maps node IDs to NodeGraphQt nodes
        self.node_map = {}
    
    def setup_ui(self):
        """Set up the UI components."""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Add the node graph widget to the layout
        self.graph_widget = self.graph.widget
        self.graph_widget.setMinimumSize(800, 600)
        self.layout.addWidget(self.graph_widget)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        # Make sure the graph widget also accepts drops
        self.graph_widget.setAcceptDrops(True)
        
        # Connect graph widget drop events to our handlers
        self.installEventFilter(self)
        self.graph_widget.installEventFilter(self)
    
    def clear(self):
        """Clear the canvas."""
        self.graph.clear_all()
        self.node_map = {}
    
    def load_workflow(self, workflow: Dict[str, Any]):
        """
        Load a workflow onto the canvas.
        
        Args:
            workflow: The workflow configuration to load
        """
        try:
            # Clear the canvas
            self.clear()
            
            # Create nodes
            for node_config in workflow.get("nodes", []):
                self._create_node_from_config(node_config)
            
            # Create connections
            for conn in workflow.get("connections", []):
                self._create_connection_from_config(conn)
            
            # Center the view
            self.graph.fit_to_selection()
            
            # Log success
            if hasattr(self.main_window, "log_console"):
                self.main_window.log_console.log("Workflow loaded successfully")
        
        except Exception as e:
            # Log error
            if hasattr(self.main_window, "log_console"):
                self.main_window.log_console.log(f"Error loading workflow: {str(e)}", "ERROR")
            
            # Show error message
            QMessageBox.critical(
                self, "Error Loading Workflow",
                f"An error occurred while loading the workflow: {str(e)}"
            )
    
    def get_workflow_data(self) -> Dict[str, Any]:
        """
        Get the current workflow data from the canvas.
        
        Returns:
            Dictionary containing the workflow configuration.
        """
        # Get nodes
        nodes = []
        for node_id, graph_node in self.node_map.items():
            node_data = self._get_node_data(graph_node)
            nodes.append(node_data)
        
        # Get connections
        connections = []
        for pipe in self.graph.all_pipes():
            conn_data = {
                "source_node": pipe.output_port.node.id,
                "source_port": pipe.output_port.name(),
                "target_node": pipe.input_port.node.id,
                "target_port": pipe.input_port.name()
            }
            connections.append(conn_data)
        
        # Build workflow data
        workflow_data = {
            "nodes": nodes,
            "connections": connections
        }
        
        return workflow_data
    
    def get_node_data(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get data for a specific node by ID.
        
        Args:
            node_id: The ID of the node
            
        Returns:
            Node data dictionary, or None if not found
        """
        if node_id in self.node_map:
            graph_node = self.node_map[node_id]
            return self._get_node_data(graph_node)
        
        return None
    
    def _create_node_from_config(self, config: Dict[str, Any]):
        """
        Create a node from a configuration dictionary.
        
        Args:
            config: The node configuration
        """
        node_id = config.get("id", "")
        node_type = config.get("type", "")
        node_name = config.get("name", "")
        position = config.get("position", {"x": 0, "y": 0})
        
        # Map node type to NodeGraphQt node type
        type_mapping = {
            "llm": LLMNode.NODE_NAME,
            "decision": DecisionNode.NODE_NAME,
            "storage": StorageNode.NODE_NAME,
            "python": PythonNode.NODE_NAME,
            "tool": ToolNode.NODE_NAME,
            "composite": CompositeNode.NODE_NAME
        }
        
        # Create node
        graph_node_type = type_mapping.get(node_type)
        if not graph_node_type:
            raise ValueError(f"Unknown node type: {node_type}")
        
        # Create the node
        graph_node = self.graph.create_node(graph_node_type, name=node_name, pos=[position.get("x", 0), position.get("y", 0)])
        
        # Set the node ID
        graph_node.set_property("id", node_id)
        
        # Set node properties
        parameters = config.get("parameters", {})
        for prop_name, prop_value in parameters.items():
            if hasattr(graph_node, prop_name) or graph_node.has_property(prop_name):
                graph_node.set_property(prop_name, prop_value)
        
        # Store in node map
        self.node_map[node_id] = graph_node
        
        # Log node creation
        if hasattr(self.main_window, "log_console"):
            self.main_window.log_console.log(
                f"Created {node_type} node: {node_name} at ({position.get('x', 0)}, {position.get('y', 0)})"
            )
        
        return graph_node
    
    def _create_connection_from_config(self, config: Dict[str, Any]):
        """
        Create a connection from a configuration dictionary.
        
        Args:
            config: The connection configuration
        """
        source_node_id = config.get("source_node", "")
        source_port = config.get("source_port", "")
        target_node_id = config.get("target_node", "")
        target_port = config.get("target_port", "")
        
        # Get nodes
        if source_node_id not in self.node_map:
            raise ValueError(f"Source node not found: {source_node_id}")
        
        if target_node_id not in self.node_map:
            raise ValueError(f"Target node not found: {target_node_id}")
        
        source_node = self.node_map[source_node_id]
        target_node = self.node_map[target_node_id]
        
        # Get ports
        source_output = None
        for port in source_node.output_ports():
            if port.name() == source_port:
                source_output = port
                break
        
        target_input = None
        for port in target_node.input_ports():
            if port.name() == target_port:
                target_input = port
                break
        
        if not source_output:
            raise ValueError(f"Source port not found: {source_port}")
        
        if not target_input:
            raise ValueError(f"Target port not found: {target_port}")
        
        # Connect the ports
        source_output.connect_to(target_input)
    
    def _get_node_data(self, graph_node) -> Dict[str, Any]:
        """
        Get data for a node as a dictionary.
        
        Args:
            graph_node: The NodeGraphQt node
            
        Returns:
            Node data dictionary
        """
        # Get node properties
        props = graph_node.properties
        
        # Node type mapping (reverse of what we use for creation)
        type_mapping = {
            LLMNode.NODE_NAME: "llm",
            DecisionNode.NODE_NAME: "decision",
            StorageNode.NODE_NAME: "storage",
            PythonNode.NODE_NAME: "python",
            ToolNode.NODE_NAME: "tool",
            CompositeNode.NODE_NAME: "composite"
        }
        
        # Get node type from node class name
        node_type = type_mapping.get(graph_node.type_)
        
        # Get node position
        pos = graph_node.pos()
        
        # Create node data
        node_data = {
            "id": props.get("id", graph_node.id),
            "type": node_type,
            "name": graph_node.name,
            "position": {"x": pos[0], "y": pos[1]},
            "parameters": {}
        }
        
        # Add node parameters
        for prop_name, prop_value in props.items():
            # Skip non-parameter properties
            if prop_name in ["id", "name", "type", "selected", "width", "height", "color"]:
                continue
            
            # Add to parameters
            node_data["parameters"][prop_name] = prop_value
        
        # Add input/output ports
        node_data["input_ports"] = [port.name() for port in graph_node.input_ports()]
        node_data["output_ports"] = [port.name() for port in graph_node.output_ports()]
        
        return node_data
    
    def _on_node_selected(self, node):
        """Handle node selection."""
        # Emit signal with selected node ID
        if node:
            self.node_selected.emit(node.id)
        else:
            self.node_selected.emit(None)
    
    def _on_node_created(self, node):
        """Handle node creation."""
        # Generate a unique ID for the node
        node_id = f"{node.type_}_{str(uuid.uuid4())[:8]}"
        node.set_property("id", node_id)
        
        # Add to node map
        self.node_map[node_id] = node
        
        # Emit workflow modified signal
        self.workflow_modified.emit()
        
        # Log
        if hasattr(self.main_window, "log_console"):
            self.main_window.log_console.log(f"Node created: {node.name} ({node_id})")
        
        # Set workflow as modified
        if hasattr(self.main_window, "modified"):
            self.main_window.modified = True
            self.main_window.update_title()
    
    def _on_node_deleted(self, node):
        """Handle node deletion."""
        # Remove from node map
        node_id = node.get_property("id")
        if node_id in self.node_map:
            del self.node_map[node_id]
        
        # Emit workflow modified signal
        self.workflow_modified.emit()
        
        # Log
        if hasattr(self.main_window, "log_console"):
            self.main_window.log_console.log(f"Node deleted: {node.name} ({node_id})")
        
        # Set workflow as modified
        if hasattr(self.main_window, "modified"):
            self.main_window.modified = True
            self.main_window.update_title()
    
    def _on_port_connected(self, output_port, input_port):
        """Handle port connection."""
        # Emit workflow modified signal
        self.workflow_modified.emit()
        
        # Log
        if hasattr(self.main_window, "log_console"):
            source_node = output_port.node.name
            target_node = input_port.node.name
            self.main_window.log_console.log(
                f"Connected {source_node}.{output_port.name()} to {target_node}.{input_port.name()}"
            )
        
        # Set workflow as modified
        if hasattr(self.main_window, "modified"):
            self.main_window.modified = True
            self.main_window.update_title()
    
    def _on_port_disconnected(self, output_port, input_port):
        """Handle port disconnection."""
        # Emit workflow modified signal
        self.workflow_modified.emit()
        
        # Log
        if hasattr(self.main_window, "log_console"):
            source_node = output_port.node.name
            target_node = input_port.node.name
            self.main_window.log_console.log(
                f"Disconnected {source_node}.{output_port.name()} from {target_node}.{input_port.name()}"
            )
        
        # Set workflow as modified
        if hasattr(self.main_window, "modified"):
            self.main_window.modified = True
            self.main_window.update_title()
    
    def _on_property_changed(self, node, prop_name, prop_value):
        """Handle node property changes."""
        # Emit workflow modified signal
        self.workflow_modified.emit()
        
        # Set workflow as modified
        if hasattr(self.main_window, "modified"):
            self.main_window.modified = True
            self.main_window.update_title()
    
    def add_node(self, node_config: Dict[str, Any]):
        """
        Add a new node to the canvas.
        
        Args:
            node_config: The node configuration
        """
        try:
            # Create the node
            self._create_node_from_config(node_config)
            
            # Emit workflow modified signal
            self.workflow_modified.emit()
            
            # Log success
            if hasattr(self.main_window, "log_console"):
                self.main_window.log_console.log(f"Added node: {node_config.get('name', '')}")
            
            # Set workflow as modified
            if hasattr(self.main_window, "modified"):
                self.main_window.modified = True
                self.main_window.update_title()
                
            return True
        
        except Exception as e:
            # Log error
            if hasattr(self.main_window, "log_console"):
                self.main_window.log_console.log(f"Error adding node: {str(e)}", "ERROR")
            return False
    
    def update_node(self, node_id: str, updated_node: Dict[str, Any]):
        """
        Update a node's properties.
        
        Args:
            node_id: The ID of the node to update
            updated_node: The updated node configuration
        """
        if node_id not in self.node_map:
            return
        
        graph_node = self.node_map[node_id]
        
        # Update node name
        if "name" in updated_node:
            graph_node.name = updated_node["name"]
        
        # Update node parameters
        if "parameters" in updated_node:
            for prop_name, prop_value in updated_node["parameters"].items():
                if hasattr(graph_node, prop_name) or graph_node.has_property(prop_name):
                    graph_node.set_property(prop_name, prop_value)
        
        # Update node ports (if needed)
        # This is more complex and would require removing and adding ports
        
        # Emit workflow modified signal
        self.workflow_modified.emit()
        
    # Drag and drop event handlers
    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.mimeData().hasFormat("application/x-node"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move events."""
        if event.mimeData().hasFormat("application/x-node"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def eventFilter(self, obj, event):
        """Filter events to handle drops on graph widget."""
        from PySide6.QtCore import QEvent
        
        if (obj == self.graph_widget and event.type() == QEvent.DragEnter):
            # Forward the drag enter event
            self.dragEnterEvent(event)
            return True
        elif (obj == self.graph_widget and event.type() == QEvent.DragMove):
            # Forward the drag move event
            self.dragMoveEvent(event)
            return True
        elif (obj == self.graph_widget and event.type() == QEvent.Drop):
            # Forward the drop event
            self.dropEvent(event)
            return True
        
        # Pass other events through
        return super().eventFilter(obj, event)
    
    def dropEvent(self, event):
        """Handle drop events for nodes."""
        if event.mimeData().hasFormat("application/x-node") or event.mimeData().hasText():
            try:
                # Try getting node data from MIME data
                if event.mimeData().hasFormat("application/x-node"):
                    node_data_str = bytes(event.mimeData().data("application/x-node")).decode()
                else:
                    node_data_str = event.mimeData().text()
                
                # Parse the node data
                node_data = json.loads(node_data_str)
                
                # Get drop position relative to the graph widget
                pos = event.pos()
                if hasattr(self, 'graph_widget'):
                    # Convert position to graph widget coordinates
                    pos = self.graph_widget.mapFromParent(pos)
                    
                    # Get the actual node graph viewer 
                    viewer = self.graph.viewer()
                    if viewer:
                        # Convert to scene coordinates if we have a viewer
                        pos = viewer.mapToScene(pos)
                
                # Update node position
                node_data["position"] = {"x": pos.x(), "y": pos.y()}
                
                # Add the node
                success = self.add_node(node_data)
                
                if hasattr(self.main_window, "log_console"):
                    self.main_window.log_console.log(f"Node dropped at ({pos.x()}, {pos.y()})")
                
                event.acceptProposedAction()
            except Exception as e:
                if hasattr(self.main_window, "log_console"):
                    self.main_window.log_console.log(f"Error in drop event: {str(e)}", "ERROR")
                event.ignore()
        else:
            event.ignore()