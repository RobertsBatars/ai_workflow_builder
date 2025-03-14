"""
Property panel widget for editing node properties.
"""
import json
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLabel, QLineEdit, QTextEdit, QComboBox, QSpinBox, 
    QDoubleSpinBox, QCheckBox, QPushButton, QGroupBox,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class PropertyPanel(QWidget):
    """
    Widget for displaying and editing node properties.
    Dynamically generates form fields based on node type.
    """
    node_modified = Signal(str, dict)  # Node ID, updated properties
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Parent window reference
        self.main_window = parent
        
        # Current node data
        self.current_node = None
        
        # Set up UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components."""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        
        # Title label
        self.title_label = QLabel("Properties")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.layout.addWidget(self.title_label)
        
        # Scroll area for property form
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Container widget for the form
        self.form_container = QWidget()
        self.form_layout = QFormLayout(self.form_container)
        self.form_layout.setContentsMargins(5, 5, 5, 5)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        # Set the container as the scroll area widget
        self.scroll_area.setWidget(self.form_container)
        self.layout.addWidget(self.scroll_area)
        
        # Node type info
        self.node_type_label = QLabel("")
        self.layout.addWidget(self.node_type_label)
        
        # Apply button
        self.apply_button = QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self.apply_changes)
        self.layout.addWidget(self.apply_button)
        
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
            self.scroll_area.setStyleSheet("""
                QScrollArea {
                    background-color: #2d2d2d;
                    border: 1px solid #444;
                }
            """)
            
            self.form_container.setStyleSheet("""
                QWidget {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                }
                QLabel {
                    font-weight: normal;
                    color: #e0e0e0;
                }
                QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    padding: 2px;
                }
                QGroupBox {
                    border: 1px solid #555;
                    border-radius: 3px;
                    margin-top: 0.5em;
                    padding-top: 0.5em;
                    color: #e0e0e0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #e0e0e0;
                }
            """)
            
            self.apply_button.setStyleSheet("""
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
            self.scroll_area.setStyleSheet("""
                QScrollArea {
                    background-color: #f8f8f8;
                    border: 1px solid #ddd;
                }
            """)
            
            self.form_container.setStyleSheet("""
                QLabel {
                    font-weight: normal;
                }
                QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: white;
                    border: 1px solid #ccc;
                    padding: 2px;
                }
                QGroupBox {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    margin-top: 0.5em;
                    padding-top: 0.5em;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
            
            self.apply_button.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #ddd;
                    padding: 4px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
        
        # Apply a specific style to the title label regardless of theme
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
    
    def clear(self):
        """Clear the property panel."""
        # Clear the form layout
        self._clear_form_layout()
        
        # Clear node info
        self.node_type_label.setText("")
        
        # Clear current node
        self.current_node = None
    
    def _clear_form_layout(self):
        """Clear all widgets from the form layout."""
        # Remove all widgets from the form layout
        while self.form_layout.rowCount() > 0:
            # Get the first row's widgets
            label_item = self.form_layout.itemAt(0, QFormLayout.LabelRole)
            field_item = self.form_layout.itemAt(0, QFormLayout.FieldRole)
            
            # Remove and delete the widgets
            if label_item and label_item.widget():
                label_widget = label_item.widget()
                self.form_layout.removeWidget(label_widget)
                label_widget.setParent(None)
                label_widget.deleteLater()
            
            if field_item and field_item.widget():
                field_widget = field_item.widget()
                self.form_layout.removeWidget(field_widget)
                field_widget.setParent(None)
                field_widget.deleteLater()
            
            # Remove the first row
            self.form_layout.removeRow(0)
    
    def load_node(self, node_data: Dict[str, Any]):
        """
        Load a node's data into the property panel.
        
        Args:
            node_data: The node data to display and edit
        """
        # Store the current node data
        self.current_node = node_data
        
        # Clear the form
        self._clear_form_layout()
        
        # Set node type info
        node_type = node_data.get("type", "unknown")
        self.node_type_label.setText(f"Type: {node_type}")
        
        # Add common fields
        self._add_text_field("ID:", node_data.get("id", ""), "id", readonly=True)
        self._add_text_field("Name:", node_data.get("name", ""), "name")
        self._add_text_field("Description:", node_data.get("description", ""), "description")
        
        # Add type-specific fields
        self._add_type_specific_fields(node_data)
    
    def _add_type_specific_fields(self, node_data: Dict[str, Any]):
        """
        Add type-specific form fields based on the node type.
        
        Args:
            node_data: The node data to display
        """
        node_type = node_data.get("type", "")
        parameters = node_data.get("parameters", {})
        
        # Add fields based on node type
        if node_type == "llm":
            # LLM Node specific fields
            self._add_group_box("LLM Configuration")
            self._add_text_field("Model:", parameters.get("model", ""), "parameters.model")
            self._add_text_area("System Prompt:", parameters.get("system_prompt", ""), "parameters.system_prompt")
            self._add_double_spin_box("Temperature:", parameters.get("temperature", 0.7), "parameters.temperature", 0.0, 2.0, 0.1)
            
            # Tools section (placeholder)
            self._add_group_box("Tools")
            self._add_label("Tools configuration coming soon...")
        
        elif node_type == "decision":
            # Decision Node specific fields
            self._add_group_box("Decision Configuration")
            self._add_text_field("Condition:", parameters.get("condition", ""), "parameters.condition")
            self._add_text_field("True Port:", parameters.get("true_port", "true"), "parameters.true_port")
            self._add_text_field("False Port:", parameters.get("false_port", "false"), "parameters.false_port")
        
        elif node_type == "storage":
            # Storage Node specific fields
            self._add_group_box("Storage Configuration")
            storage_type = parameters.get("storage_type", "static")
            
            # Storage type selector
            storage_types = ["static", "vector"]
            self._add_combo_box("Storage Type:", storage_types, storage_type, "parameters.storage_type")
            
            # Vector storage specific fields
            if storage_type == "vector":
                self._add_spin_box("Dimension:", parameters.get("dimension", 768), "parameters.dimension", 1, 4096)
            
            # Common storage fields
            self._add_checkbox("Persist:", parameters.get("persist", False), "parameters.persist")
        
        elif node_type == "python":
            # Python Node specific fields
            self._add_group_box("Python Configuration")
            
            # Security warning box
            warning_box = QGroupBox("⚠️ Security Warning")
            warning_box.setStyleSheet("QGroupBox { border: 1px solid red; }")
            warning_layout = QVBoxLayout(warning_box)
            
            warning_label = QLabel(
                "Executing custom Python code may pose security risks. "
                "Use Docker virtualization when running untrusted code."
            )
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet("color: red;")
            warning_layout.addWidget(warning_label)
            
            # Virtualization settings
            virt_layout = QHBoxLayout()
            virt_label = QLabel("Virtualization:")
            virt_combo = QComboBox()
            virt_combo.addItems(["none", "lightweight", "ubuntu"])
            virt_combo.setToolTip(
                "none: No isolation, runs directly in Python process (unsafe for untrusted code)\n"
                "lightweight: Docker container with minimal Python image\n"
                "ubuntu: Docker container with full Ubuntu system and Python"
            )
            
            # Get the current value from workflow environment or default to lightweight
            virt_value = "lightweight"
            if "virtualization" in parameters:
                virt_value = parameters.get("virtualization", "lightweight")
            
            # Set the combo box to the current value
            index = virt_combo.findText(virt_value)
            if index >= 0:
                virt_combo.setCurrentIndex(index)
            
            # Connect the combo box to update function
            def update_virtualization(text):
                self.property_values["parameters.virtualization"] = text
                
                # Show additional warning if "none" is selected
                if text == "none":
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        "Security Risk",
                        "Running Python code without virtualization is a security risk. "
                        "Only use this setting for trusted code in a secure environment."
                    )
            
            virt_combo.currentTextChanged.connect(update_virtualization)
            
            virt_layout.addWidget(virt_label)
            virt_layout.addWidget(virt_combo)
            warning_layout.addLayout(virt_layout)
            
            # Add the warning box to the form
            self.form_layout.addRow("", warning_box)
            
            # Code editor
            self._add_text_area("Code:", parameters.get("code", ""), "parameters.code", font_family="monospace")
            
            # Timeout setting
            timeout_layout = QHBoxLayout()
            timeout_label = QLabel("Execution Timeout (seconds):")
            timeout_spin = QSpinBox()
            timeout_spin.setMinimum(1)
            timeout_spin.setMaximum(300)  # 5 minutes max
            timeout_spin.setValue(parameters.get("timeout", 30))
            
            def update_timeout(value):
                self.property_values["parameters.timeout"] = value
            
            timeout_spin.valueChanged.connect(update_timeout)
            timeout_layout.addWidget(timeout_label)
            timeout_layout.addWidget(timeout_spin)
            self.form_layout.addRow("", timeout_layout)
            
            # Requirements section
            self._add_group_box("Requirements")
            reqs_layout = QVBoxLayout()
            reqs_label = QLabel("List of required packages (one per line):")
            reqs_text = QTextEdit()
            reqs_text.setPlainText("\n".join(parameters.get("requirements", [])))
            reqs_text.setMaximumHeight(100)
            
            def update_requirements():
                # Parse requirements from text
                req_text = reqs_text.toPlainText()
                req_list = [r.strip() for r in req_text.split("\n") if r.strip()]
                self.property_values["parameters.requirements"] = req_list
            
            reqs_text.textChanged.connect(update_requirements)
            reqs_layout.addWidget(reqs_label)
            reqs_layout.addWidget(reqs_text)
            self.form_layout.addRow("", reqs_layout)
        
        elif node_type == "tool":
            # Tool Node specific fields
            self._add_group_box("Tool Configuration")
            self._add_text_field("Tool Name:", parameters.get("tool_name", ""), "parameters.tool_name")
            
            # Tool parameters section (placeholder)
            self._add_group_box("Tool Parameters")
            self._add_label("Tool parameters configuration coming soon...")
        
        elif node_type == "composite":
            # Composite Node specific fields
            self._add_group_box("Composite Configuration")
            
            # Sub-workflow section (placeholder)
            self._add_label("Sub-workflow configuration coming soon...")
            
            # Add button to edit the sub-workflow
            edit_button = QPushButton("Edit Sub-Workflow")
            edit_button.clicked.connect(self._edit_sub_workflow)
            self.form_layout.addRow("", edit_button)
    
    def _add_text_field(self, label: str, value: str, property_path: str, readonly: bool = False):
        """Add a text field to the form."""
        field = QLineEdit(str(value))
        field.setReadOnly(readonly)
        if readonly:
            field.setStyleSheet("background-color: #f0f0f0;")
        
        field.setProperty("property_path", property_path)
        self.form_layout.addRow(label, field)
    
    def _add_text_area(self, label: str, value: str, property_path: str, font_family: str = None):
        """Add a text area to the form."""
        field = QTextEdit()
        field.setPlainText(str(value))
        field.setProperty("property_path", property_path)
        
        if font_family:
            font = QFont(font_family)
            field.setFont(font)
        
        self.form_layout.addRow(label, field)
    
    def _add_combo_box(self, label: str, options: List[str], value: str, property_path: str):
        """Add a combo box to the form."""
        field = QComboBox()
        field.addItems(options)
        
        # Set the current value
        index = field.findText(value)
        if index >= 0:
            field.setCurrentIndex(index)
        
        field.setProperty("property_path", property_path)
        self.form_layout.addRow(label, field)
    
    def _add_spin_box(self, label: str, value: int, property_path: str, minimum: int = 0, maximum: int = 9999):
        """Add a spin box to the form."""
        field = QSpinBox()
        field.setMinimum(minimum)
        field.setMaximum(maximum)
        field.setValue(int(value))
        field.setProperty("property_path", property_path)
        self.form_layout.addRow(label, field)
    
    def _add_double_spin_box(self, label: str, value: float, property_path: str, minimum: float = 0.0, maximum: float = 1.0, step: float = 0.1):
        """Add a double spin box to the form."""
        field = QDoubleSpinBox()
        field.setMinimum(minimum)
        field.setMaximum(maximum)
        field.setSingleStep(step)
        field.setValue(float(value))
        field.setProperty("property_path", property_path)
        self.form_layout.addRow(label, field)
    
    def _add_checkbox(self, label: str, checked: bool, property_path: str):
        """Add a checkbox to the form."""
        field = QCheckBox()
        field.setChecked(bool(checked))
        field.setProperty("property_path", property_path)
        self.form_layout.addRow(label, field)
    
    def _add_group_box(self, title: str):
        """Add a group box to the form."""
        # Add a spacer before the group box
        spacer = QLabel("")
        spacer.setMinimumHeight(10)
        self.form_layout.addRow("", spacer)
        
        # Add the group box title
        label = QLabel(title)
        label.setStyleSheet("font-weight: bold;")
        self.form_layout.addRow(label)
    
    def _add_label(self, text: str):
        """Add a label to the form."""
        label = QLabel(text)
        label.setWordWrap(True)
        self.form_layout.addRow("", label)
    
    def apply_changes(self):
        """Apply the changes to the node."""
        if not self.current_node:
            return
        
        # Create a copy of the current node
        updated_node = dict(self.current_node)
        
        # Collect values from all form fields
        for i in range(self.form_layout.rowCount()):
            field_item = self.form_layout.itemAt(i, QFormLayout.FieldRole)
            
            if field_item and field_item.widget():
                field = field_item.widget()
                property_path = field.property("property_path")
                
                if property_path:
                    # Get the field value based on widget type
                    value = self._get_field_value(field)
                    
                    # Update the node data
                    self._update_node_value(updated_node, property_path, value)
        
        # Emit signal with the updated node
        self.node_modified.emit(updated_node["id"], updated_node)
        
        # Log the change
        if hasattr(self.main_window, "log_console"):
            self.main_window.log_console.log(f"Updated properties for node {updated_node['id']}")
        
        # Set as modified
        if hasattr(self.main_window, "modified"):
            self.main_window.modified = True
            self.main_window.update_title()
    
    def _get_field_value(self, field):
        """Get the value from a form field based on its type."""
        if isinstance(field, QLineEdit):
            return field.text()
        elif isinstance(field, QTextEdit):
            return field.toPlainText()
        elif isinstance(field, QComboBox):
            return field.currentText()
        elif isinstance(field, QSpinBox):
            return field.value()
        elif isinstance(field, QDoubleSpinBox):
            return field.value()
        elif isinstance(field, QCheckBox):
            return field.isChecked()
        
        return None
    
    def _update_node_value(self, node: Dict[str, Any], property_path: str, value):
        """
        Update a value in the node data using a property path.
        
        Args:
            node: The node data to update
            property_path: The path to the property (e.g., "parameters.model")
            value: The new value
        """
        if not property_path:
            return
        
        # Split the path into parts
        parts = property_path.split(".")
        
        # Navigate to the target object
        target = node
        for i in range(len(parts) - 1):
            part = parts[i]
            
            if part not in target:
                target[part] = {}
            
            target = target[part]
        
        # Set the value
        target[parts[-1]] = value
    
    def _edit_sub_workflow(self):
        """Open the sub-workflow editor."""
        # TODO: Implement sub-workflow editor
        if hasattr(self.main_window, "log_console"):
            self.main_window.log_console.log("Sub-workflow editor not implemented yet")