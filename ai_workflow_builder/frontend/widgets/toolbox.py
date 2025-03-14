"""
Toolbox widget for displaying available nodes and tools.
"""
import json
import uuid
from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QScrollArea, QPushButton, QMenu, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QDrag, QPixmap, QColor
from PySide6.QtCore import QMimeData, QPoint


class ToolboxWidget(QWidget):
    """
    Widget for displaying available node types and tools.
    Supports drag and drop to canvas.
    """
    node_dragged = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Parent window reference
        self.main_window = parent
        
        # For drag and drop tracking
        self._drag_start_pos = QPoint()
        
        # Node categories and types
        self.categories = {
            "AI Models": ["llm"],
            "Logic": ["decision"],
            "Data": ["storage"],
            "Code": ["python"],
            "Tools": ["tool"],
            "Advanced": ["composite"]
        }
        
        # Node type information
        self.node_info = {
            "llm": {
                "name": "LLM Node",
                "description": "Run LLMs with tool attachments",
                "category": "AI Models",
                "icon": "llm_icon.png"
            },
            "decision": {
                "name": "Decision Node",
                "description": "Branch workflows with conditions",
                "category": "Logic",
                "icon": "decision_icon.png"
            },
            "storage": {
                "name": "Storage Node",
                "description": "Store text or vector data",
                "category": "Data",
                "icon": "storage_icon.png"
            },
            "python": {
                "name": "Python Node",
                "description": "Execute custom Python code",
                "category": "Code",
                "icon": "python_icon.png"
            },
            "tool": {
                "name": "Tool Node",
                "description": "Use prebuilt or custom tools",
                "category": "Tools",
                "icon": "tool_icon.png"
            },
            "composite": {
                "name": "Composite Node",
                "description": "Encapsulate sub-workflows",
                "category": "Advanced",
                "icon": "composite_icon.png"
            }
        }
        
        # Set up UI
        self.setup_ui()
        
        # Populate node tree
        self.populate_node_tree()
    
    def setup_ui(self):
        """Set up the UI components."""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        
        # Title label
        self.title_label = QLabel("Node Toolbox")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.layout.addWidget(self.title_label)
        
        # Tree widget for node types
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderHidden(True)
        self.node_tree.setDragEnabled(True)
        self.node_tree.setAnimated(True)
        self.node_tree.setIndentation(20)
        self.node_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.node_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # Enable drag and drop
        self.node_tree.setDragDropMode(QTreeWidget.DragOnly)
        
        # Connect context menu event
        self.node_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.node_tree.customContextMenuRequested.connect(self.show_context_menu)
        
        # Connect mouse press event for tracking drag start
        self.node_tree.mousePressEvent = self._tree_mousePressEvent
        
        self.layout.addWidget(self.node_tree)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_nodes)
        self.layout.addWidget(self.refresh_button)
        
        # Apply styling
        self.apply_styling()
    
    def apply_styling(self):
        """Apply styling to the widget with theme detection."""
        # Check if system is using dark mode
        from PySide6.QtGui import QPalette
        from PySide6.QtCore import Qt
        
        # Get application palette
        palette = self.palette()
        is_dark_mode = palette.color(QPalette.Window).lightness() < 128
        
        if is_dark_mode:
            # Dark theme
            self.node_tree.setStyleSheet("""
                QTreeWidget {
                    background-color: #2d2d2d;
                    border: 1px solid #444;
                    color: #e0e0e0;
                }
                QTreeWidget::item {
                    padding: 2px;
                }
                QTreeWidget::item:selected {
                    background-color: #3a539b;
                    color: white;
                }
            """)
            
            self.refresh_button.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    border: 1px solid #555;
                    padding: 4px;
                    color: #e0e0e0;
                }
                QPushButton:hover {
                    background-color: #464646;
                }
            """)
        else:
            # Light theme
            self.node_tree.setStyleSheet("""
                QTreeWidget {
                    background-color: #f8f8f8;
                    border: 1px solid #ddd;
                }
                QTreeWidget::item {
                    padding: 2px;
                }
                QTreeWidget::item:selected {
                    background-color: #ddf;
                    color: black;
                }
            """)
            
            self.refresh_button.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #ddd;
                    padding: 4px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
    
    def populate_node_tree(self):
        """Populate the node tree with categories and node types."""
        # Clear the tree
        self.node_tree.clear()
        
        # Add categories and node types
        for category_name, node_types in self.categories.items():
            # Create category item
            category_item = QTreeWidgetItem(self.node_tree)
            category_item.setText(0, category_name)
            category_item.setFlags(category_item.flags() & ~Qt.ItemIsDragEnabled)
            
            # Add node types to category
            for node_type in node_types:
                if node_type in self.node_info:
                    info = self.node_info[node_type]
                    
                    # Create node type item
                    node_item = QTreeWidgetItem(category_item)
                    node_item.setText(0, info["name"])
                    node_item.setToolTip(0, info["description"])
                    node_item.setData(0, Qt.UserRole, node_type)
                    
                    # Set icon if available
                    # TODO: Load icons for node types
        
        # Expand all categories by default
        self.node_tree.expandAll()
    
    def refresh_nodes(self):
        """Refresh the node types from the backend."""
        try:
            # Get available node types from API
            if hasattr(self.main_window, "api_client"):
                node_types = self.main_window.api_client.get_node_types()
                
                # Update the node tree based on available types
                # TODO: Implement proper handling of returned node types
                
                self.populate_node_tree()
                
                # Log success
                if hasattr(self.main_window, "log_console"):
                    self.main_window.log_console.log("Node types refreshed successfully")
            
        except Exception as e:
            # Log error
            if hasattr(self.main_window, "log_console"):
                self.main_window.log_console.log(f"Error refreshing node types: {str(e)}", "ERROR")
    
    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """
        Handle double-click on a node type to add it to the canvas.
        
        Args:
            item: The clicked tree item
            column: The clicked column
        """
        # Check if it's a node item (not a category)
        if item.parent() is not None:
            # Get the node type
            node_type = item.data(0, Qt.UserRole)
            
            if node_type:
                # Create a new node of this type
                new_node = self.create_new_node(node_type)
                
                # Emit signal to add node to canvas
                self.node_dragged.emit(new_node)
    
    def show_context_menu(self, position: QPoint):
        """
        Show context menu for toolbox items.
        
        Args:
            position: The position to show the menu
        """
        # Get item at position
        item = self.node_tree.itemAt(position)
        
        if item and item.parent() is not None:
            # It's a node item, create context menu
            menu = QMenu()
            
            # Add actions
            add_action = menu.addAction("Add to Canvas")
            info_action = menu.addAction("Show Info")
            
            # Show menu and get result
            action = menu.exec_(self.node_tree.mapToGlobal(position))
            
            # Handle actions
            if action == add_action:
                # Get the node type
                node_type = item.data(0, Qt.UserRole)
                
                if node_type:
                    # Create a new node of this type
                    new_node = self.create_new_node(node_type)
                    
                    # Emit signal to add node to canvas
                    self.node_dragged.emit(new_node)
            
            elif action == info_action:
                # Show information about the node type
                node_type = item.data(0, Qt.UserRole)
                
                if node_type and node_type in self.node_info:
                    info = self.node_info[node_type]
                    
                    # Display node info
                    if hasattr(self.main_window, "log_console"):
                        self.main_window.log_console.log(
                            f"Node Type: {info['name']}\n"
                            f"Category: {info['category']}\n"
                            f"Description: {info['description']}",
                            "INFO"
                        )
    
    def create_new_node(self, node_type: str) -> Dict[str, Any]:
        """
        Create a new node configuration of the specified type.
        
        Args:
            node_type: The type of node to create
        
        Returns:
            Node configuration dictionary
        """
        # Generate a unique ID for the node
        node_id = f"{node_type}_{str(uuid.uuid4())[:8]}"
        
        # Get node type info
        info = self.node_info.get(node_type, {
            "name": node_type.capitalize(),
            "description": f"A {node_type} node"
        })
        
        # Create base node config
        node_config = {
            "id": node_id,
            "type": node_type,
            "name": info["name"],
            "description": info["description"],
            "position": {"x": 100, "y": 100},
            "parameters": {}
        }
        
        # Add type-specific default parameters
        if node_type == "llm":
            node_config["parameters"] = {
                "model": "gpt-4",
                "system_prompt": "You are a helpful assistant.",
                "temperature": 0.7,
                "tools": []
            }
        elif node_type == "decision":
            node_config["parameters"] = {
                "condition": "input > 0",
                "true_port": "true",
                "false_port": "false"
            }
        elif node_type == "storage":
            node_config["parameters"] = {
                "storage_type": "static", 
                "dimension": 768,
                "persist": False
            }
        elif node_type == "python":
            node_config["parameters"] = {
                "code": "def run(input_data):\n    # Your code here\n    return input_data",
                "requirements": []
            }
        elif node_type == "tool":
            node_config["parameters"] = {
                "tool_name": "",
                "tool_parameters": {}
            }
        elif node_type == "composite":
            node_config["parameters"] = {
                "workflow_json": {}
            }
        
        # Add default input/output ports
        if node_type == "llm":
            node_config["input_ports"] = ["prompt", "system_prompt", "temperature", "tools"]
            node_config["output_ports"] = ["response", "tool_calls", "error"]
        elif node_type == "decision":
            node_config["input_ports"] = ["value", "condition"]
            node_config["output_ports"] = ["true", "false", "error"]
        elif node_type == "storage" and node_config["parameters"]["storage_type"] == "static":
            node_config["input_ports"] = ["key", "value", "operation"]
            node_config["output_ports"] = ["result", "success", "error"]
        elif node_type == "storage" and node_config["parameters"]["storage_type"] == "vector":
            node_config["input_ports"] = ["text", "embedding", "query_embedding", "top_k", "operation"]
            node_config["output_ports"] = ["results", "success", "error"]
        elif node_type == "python":
            node_config["input_ports"] = ["input", "code", "timeout"]
            node_config["output_ports"] = ["output", "error"]
        elif node_type == "tool":
            node_config["input_ports"] = ["input", "parameters"]
            node_config["output_ports"] = ["output", "error"]
        elif node_type == "composite":
            node_config["input_ports"] = ["input"]
            node_config["output_ports"] = ["output", "error"]
        
        return node_config
    
    def mouseMoveEvent(self, event):
        """Override to handle drag and drop of nodes."""
        # Only start drag if mouse has moved far enough (prevents accidental drags)
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
            
        # Check if mouse has moved far enough to start a drag
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
            
        # Check if a node item is selected
        selected_item = self.node_tree.currentItem()
        if selected_item is None or selected_item.parent() is None:
            # No node item selected, let the parent handle as normal
            super().mouseMoveEvent(event)
            return
            
        # Get node type data
        node_type = selected_item.data(0, Qt.UserRole)
        if not node_type:
            super().mouseMoveEvent(event)
            return
        
        try:
            # Create node data
            node_data = self.create_new_node(node_type)
            node_json = json.dumps(node_data)
            
            # Start drag operation
            drag = QDrag(self)
            mime_data = QMimeData()
            
            # Set MIME data with JSON serialized node data
            mime_data.setText(node_json)
            mime_data.setData("application/x-node", node_json.encode())
            
            # Create a more visual drag pixmap with node name
            pixmap = QPixmap(120, 40)
            pixmap.fill(QColor(80, 80, 180, 200))
            
            # Add node name to pixmap
            from PySide6.QtGui import QPainter, QFont, QColor, QPen
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont()
            font.setBold(True)
            painter.setFont(font)
            node_name = self.node_info[node_type]["name"]
            painter.drawText(pixmap.rect(), Qt.AlignCenter, node_name)
            painter.end()
            
            # Set drag pixmap
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            
            # Set MIME data
            drag.setMimeData(mime_data)
            
            # Execute drag
            if hasattr(self.main_window, "log_console"):
                self.main_window.log_console.log(f"Starting drag for {node_name}")
                
            # Execute drag
            result = drag.exec_(Qt.CopyAction)
            
            # Signal that a node was dragged (whether dropped successfully or not)
            if result == Qt.IgnoreAction:
                if hasattr(self.main_window, "log_console"):
                    self.main_window.log_console.log(f"Drag cancelled for {node_name}")
            
        except Exception as e:
            if hasattr(self.main_window, "log_console"):
                self.main_window.log_console.log(f"Error in drag: {str(e)}", "ERROR")
        
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
            
    def _tree_mousePressEvent(self, event):
        """Custom handler for mouse press events on the tree widget."""
        # Store the position for potential drag operations
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            
        # Call the original event handler
        QTreeWidget.mousePressEvent(self.node_tree, event)