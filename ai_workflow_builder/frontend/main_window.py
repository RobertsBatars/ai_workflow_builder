"""
Main window for the AI Workflow Builder application.
"""
import os
import sys
import json
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QDockWidget, QMenu, QMenuBar, QToolBar, QPushButton,
    QFileDialog, QMessageBox, QLabel, QStatusBar
)
from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence

from .node_editor.canvas import NodeEditorCanvas
from .widgets.property_panel import PropertyPanel
from .widgets.toolbox import ToolboxWidget
from .widgets.log_console import LogConsole
from .utils.api_client import APIClient


class MainWindow(QMainWindow):
    """
    Main window for the AI Workflow Builder application.
    Contains the node editor canvas, property panel, toolbox, and log console.
    """
    def __init__(self, app: QApplication = None):
        super().__init__()
        
        # Store app reference
        self.app = app
        
        # Backend API client
        self.api_client = APIClient()
        
        # Current workflow data
        self.current_workflow = None
        self.current_workflow_path = None
        self.modified = False
        
        # Set up the UI
        self.setWindowTitle("AI Workflow Builder")
        self.resize(1280, 800)
        
        # Initialize settings
        self.settings = QSettings("AI Workflow Builder", "App")
        self.restore_geometry()
        
        # Create UI components
        self.setup_ui()
        self.setup_menubar()
        self.setup_toolbar()
        self.setup_statusbar()
        
        # Create a new empty workflow
        self.new_workflow()
    
    def setup_ui(self):
        """Set up the main UI components."""
        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a splitter for resizable panels
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel (toolbox)
        self.toolbox = ToolboxWidget(self)
        self.toolbox_dock = QDockWidget("Toolbox", self)
        self.toolbox_dock.setWidget(self.toolbox)
        self.toolbox_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.toolbox_dock)
        
        # Central area (node editor canvas)
        self.canvas = NodeEditorCanvas(self)
        self.canvas.node_selected.connect(self.on_node_selected)
        self.main_splitter.addWidget(self.canvas)
        
        # Right panel (property panel)
        self.property_panel = PropertyPanel(self)
        self.property_dock = QDockWidget("Properties", self)
        self.property_dock.setWidget(self.property_panel)
        self.property_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.property_dock)
        
        # Bottom panel (log console)
        self.log_console = LogConsole(self)
        self.log_dock = QDockWidget("Console", self)
        self.log_dock.setWidget(self.log_console)
        self.log_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        
        # Add main splitter to layout
        self.main_layout.addWidget(self.main_splitter)
        
        # Log startup message
        self.log_console.log("AI Workflow Builder started")
    
    def setup_menubar(self):
        """Set up the application menu bar."""
        # File menu
        self.file_menu = self.menuBar().addMenu("&File")
        
        # New workflow action
        self.new_action = QAction("&New Workflow", self)
        self.new_action.setShortcut(QKeySequence.New)
        self.new_action.triggered.connect(self.new_workflow)
        self.file_menu.addAction(self.new_action)
        
        # Open workflow action
        self.open_action = QAction("&Open Workflow...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_workflow)
        self.file_menu.addAction(self.open_action)
        
        # Save workflow action
        self.save_action = QAction("&Save Workflow", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_workflow)
        self.file_menu.addAction(self.save_action)
        
        # Save As workflow action
        self.save_as_action = QAction("Save Workflow &As...", self)
        self.save_as_action.setShortcut(QKeySequence.SaveAs)
        self.save_as_action.triggered.connect(self.save_workflow_as)
        self.file_menu.addAction(self.save_as_action)
        
        self.file_menu.addSeparator()
        
        # Export workflow as JSON action
        self.export_action = QAction("&Export to JSON...", self)
        self.export_action.triggered.connect(self.export_workflow)
        self.file_menu.addAction(self.export_action)
        
        # Import workflow from JSON action
        self.import_action = QAction("&Import from JSON...", self)
        self.import_action.triggered.connect(self.import_workflow)
        self.file_menu.addAction(self.import_action)
        
        self.file_menu.addSeparator()
        
        # Exit action
        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.exit_action)
        
        # Edit menu
        self.edit_menu = self.menuBar().addMenu("&Edit")
        
        # Undo action
        self.undo_action = QAction("&Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.edit_menu.addAction(self.undo_action)
        
        # Redo action
        self.redo_action = QAction("&Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.edit_menu.addAction(self.redo_action)
        
        self.edit_menu.addSeparator()
        
        # Cut action
        self.cut_action = QAction("Cu&t", self)
        self.cut_action.setShortcut(QKeySequence.Cut)
        self.cut_action.triggered.connect(self.cut)
        self.edit_menu.addAction(self.cut_action)
        
        # Copy action
        self.copy_action = QAction("&Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.copy)
        self.edit_menu.addAction(self.copy_action)
        
        # Paste action
        self.paste_action = QAction("&Paste", self)
        self.paste_action.setShortcut(QKeySequence.Paste)
        self.paste_action.triggered.connect(self.paste)
        self.edit_menu.addAction(self.paste_action)
        
        self.edit_menu.addSeparator()
        
        # Delete action
        self.delete_action = QAction("&Delete", self)
        self.delete_action.setShortcut(QKeySequence.Delete)
        self.delete_action.triggered.connect(self.delete)
        self.edit_menu.addAction(self.delete_action)
        
        # View menu
        self.view_menu = self.menuBar().addMenu("&View")
        
        # Toggle toolbox action
        self.toggle_toolbox_action = QAction("&Toolbox", self)
        self.toggle_toolbox_action.setCheckable(True)
        self.toggle_toolbox_action.setChecked(True)
        self.toggle_toolbox_action.triggered.connect(self.toggle_toolbox)
        self.view_menu.addAction(self.toggle_toolbox_action)
        
        # Toggle property panel action
        self.toggle_property_panel_action = QAction("&Property Panel", self)
        self.toggle_property_panel_action.setCheckable(True)
        self.toggle_property_panel_action.setChecked(True)
        self.toggle_property_panel_action.triggered.connect(self.toggle_property_panel)
        self.view_menu.addAction(self.toggle_property_panel_action)
        
        # Toggle log console action
        self.toggle_log_console_action = QAction("&Log Console", self)
        self.toggle_log_console_action.setCheckable(True)
        self.toggle_log_console_action.setChecked(True)
        self.toggle_log_console_action.triggered.connect(self.toggle_log_console)
        self.view_menu.addAction(self.toggle_log_console_action)
        
        # Workflow menu
        self.workflow_menu = self.menuBar().addMenu("&Workflow")
        
        # Run workflow action
        self.run_action = QAction("&Run Workflow", self)
        self.run_action.setShortcut("F5")
        self.run_action.triggered.connect(self.run_workflow)
        self.workflow_menu.addAction(self.run_action)
        
        # Stop workflow action
        self.stop_action = QAction("&Stop Workflow", self)
        self.stop_action.setShortcut("Shift+F5")
        self.stop_action.triggered.connect(self.stop_workflow)
        self.workflow_menu.addAction(self.stop_action)
        
        self.workflow_menu.addSeparator()
        
        # Validate workflow action
        self.validate_action = QAction("&Validate Workflow", self)
        self.validate_action.triggered.connect(self.validate_workflow)
        self.workflow_menu.addAction(self.validate_action)
        
        # Help menu
        self.help_menu = self.menuBar().addMenu("&Help")
        
        # About action
        self.about_action = QAction("&About", self)
        self.about_action.triggered.connect(self.show_about)
        self.help_menu.addAction(self.about_action)
    
    def setup_toolbar(self):
        """Set up the application toolbar."""
        self.toolbar = QToolBar("Main Toolbar", self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        
        # Add actions to toolbar
        self.toolbar.addAction(self.new_action)
        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.run_action)
        self.toolbar.addAction(self.stop_action)
    
    def setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)
        
        # Add permanent status labels
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label)
    
    def restore_geometry(self):
        """Restore window size and position from settings."""
        if self.settings.contains("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        if self.settings.contains("windowState"):
            self.restoreState(self.settings.value("windowState"))
    
    def save_geometry(self):
        """Save window size and position to settings."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.check_unsaved_changes():
            self.save_geometry()
            event.accept()
        else:
            event.ignore()
    
    def check_unsaved_changes(self):
        """Check for unsaved changes and prompt user if needed."""
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                return self.save_workflow()
            elif reply == QMessageBox.Cancel:
                return False
        
        return True
    
    def new_workflow(self):
        """Create a new empty workflow."""
        if not self.check_unsaved_changes():
            return
        
        # Clear current workflow
        self.current_workflow = {
            "name": "Untitled Workflow",
            "description": "",
            "nodes": [],
            "connections": [],
            "tools": [],
            "environment": {
                "virtualization": "none"
            },
            "metadata": {}
        }
        self.current_workflow_path = None
        self.modified = False
        
        # Update UI
        self.canvas.clear()
        self.property_panel.clear()
        self.update_title()
        
        self.log_console.log("New workflow created")
    
    def open_workflow(self):
        """Open a workflow from a checkpoint."""
        if not self.check_unsaved_changes():
            return
        
        # TODO: Implement checkpoint browser dialog
        # For now, just load the latest checkpoint
        try:
            # Get checkpoints from API
            checkpoints = self.api_client.get_checkpoints()
            
            if not checkpoints:
                QMessageBox.information(
                    self, "No Checkpoints",
                    "No saved workflows found."
                )
                return
            
            # TODO: Show a dialog to select a checkpoint
            # For now, just load the first one
            checkpoint_path = checkpoints[0]["path"]
            
            # Load the workflow
            workflow = self.api_client.load_checkpoint(checkpoint_path)
            
            if workflow:
                self.current_workflow = workflow
                self.current_workflow_path = checkpoint_path
                self.modified = False
                
                # Update UI
                self.canvas.load_workflow(workflow)
                self.property_panel.clear()
                self.update_title()
                
                self.log_console.log(f"Workflow loaded from {checkpoint_path}")
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error Opening Workflow",
                f"An error occurred while opening the workflow: {str(e)}"
            )
    
    def save_workflow(self):
        """Save the current workflow."""
        if self.current_workflow_path:
            # Save to existing path
            self._save_to_path(self.current_workflow_path)
            return True
        else:
            # No path set, use Save As
            return self.save_workflow_as()
    
    def save_workflow_as(self):
        """Save the current workflow to a new file."""
        try:
            # Save the workflow using the API
            result = self.api_client.save_workflow(self.current_workflow)
            
            if result["success"]:
                self.current_workflow_path = result["path"]
                self.modified = False
                self.update_title()
                
                self.log_console.log(f"Workflow saved to {result['path']}")
                return True
            else:
                QMessageBox.critical(
                    self, "Error Saving Workflow",
                    f"An error occurred while saving the workflow: {result['message']}"
                )
                return False
                
        except Exception as e:
            QMessageBox.critical(
                self, "Error Saving Workflow",
                f"An error occurred while saving the workflow: {str(e)}"
            )
            return False
    
    def _save_to_path(self, path):
        """Save the workflow to a specific path."""
        try:
            # Get workflow data from canvas
            workflow_data = self.canvas.get_workflow_data()
            self.current_workflow.update(workflow_data)
            
            # Save using the API
            result = self.api_client.save_workflow(self.current_workflow)
            
            if result["success"]:
                self.modified = False
                self.update_title()
                
                self.log_console.log(f"Workflow saved to {result['path']}")
                return True
            else:
                QMessageBox.critical(
                    self, "Error Saving Workflow",
                    f"An error occurred while saving the workflow: {result['message']}"
                )
                return False
                
        except Exception as e:
            QMessageBox.critical(
                self, "Error Saving Workflow",
                f"An error occurred while saving the workflow: {str(e)}"
            )
            return False
    
    def export_workflow(self):
        """Export the workflow to a JSON file."""
        # Get the save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Workflow", "", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            # Get workflow data from canvas
            workflow_data = self.canvas.get_workflow_data()
            self.current_workflow.update(workflow_data)
            
            # Save to file
            with open(file_path, "w") as f:
                json.dump(self.current_workflow, f, indent=2)
            
            self.log_console.log(f"Workflow exported to {file_path}")
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error Exporting Workflow",
                f"An error occurred while exporting the workflow: {str(e)}"
            )
    
    def import_workflow(self):
        """Import a workflow from a JSON file."""
        if not self.check_unsaved_changes():
            return
        
        # Get the open file path
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Workflow", "", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            # Load from file
            with open(file_path, "r") as f:
                workflow = json.load(f)
            
            # Validate workflow format
            # TODO: Implement more robust validation
            if "nodes" not in workflow or "connections" not in workflow:
                raise ValueError("Invalid workflow format")
            
            # Set as current workflow
            self.current_workflow = workflow
            self.current_workflow_path = None  # Not a checkpoint
            self.modified = True
            
            # Update UI
            self.canvas.load_workflow(workflow)
            self.property_panel.clear()
            self.update_title()
            
            self.log_console.log(f"Workflow imported from {file_path}")
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error Importing Workflow",
                f"An error occurred while importing the workflow: {str(e)}"
            )
    
    def update_title(self):
        """Update the window title with workflow info."""
        title = "AI Workflow Builder"
        
        if self.current_workflow:
            name = self.current_workflow.get("name", "Untitled Workflow")
            title = f"{name} - {title}"
            
            if self.modified:
                title = f"*{title}"
        
        self.setWindowTitle(title)
    
    def undo(self):
        """Undo the last operation."""
        # TODO: Implement undo functionality
        self.log_console.log("Undo not implemented yet")
    
    def redo(self):
        """Redo the last undone operation."""
        # TODO: Implement redo functionality
        self.log_console.log("Redo not implemented yet")
    
    def cut(self):
        """Cut selected nodes."""
        # TODO: Implement cut functionality
        self.log_console.log("Cut not implemented yet")
    
    def copy(self):
        """Copy selected nodes."""
        # TODO: Implement copy functionality
        self.log_console.log("Copy not implemented yet")
    
    def paste(self):
        """Paste nodes from clipboard."""
        # TODO: Implement paste functionality
        self.log_console.log("Paste not implemented yet")
    
    def delete(self):
        """Delete selected nodes."""
        # TODO: Implement delete functionality
        self.log_console.log("Delete not implemented yet")
    
    def toggle_toolbox(self, checked):
        """Toggle the toolbox visibility."""
        self.toolbox_dock.setVisible(checked)
    
    def toggle_property_panel(self, checked):
        """Toggle the property panel visibility."""
        self.property_dock.setVisible(checked)
    
    def toggle_log_console(self, checked):
        """Toggle the log console visibility."""
        self.log_dock.setVisible(checked)
    
    def run_workflow(self):
        """Run the current workflow."""
        # Update workflow data from canvas
        workflow_data = self.canvas.get_workflow_data()
        self.current_workflow.update(workflow_data)
        
        try:
            # Validate workflow before running
            validation = self.api_client.validate_workflow(self.current_workflow)
            
            if not validation.get("valid", False):
                QMessageBox.critical(
                    self, "Validation Error",
                    f"Workflow validation failed: {validation.get('errors', '')}"
                )
                return
            
            # Execute the workflow
            result = self.api_client.execute_workflow(self.current_workflow)
            
            # Store workflow ID for status updates
            self.current_workflow_id = result.get("workflow_id")
            
            # Update status
            self.status_label.setText("Running workflow...")
            self.log_console.log(f"Workflow execution started (ID: {self.current_workflow_id})")
            
            # TODO: Implement polling for workflow status updates
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error Running Workflow",
                f"An error occurred while running the workflow: {str(e)}"
            )
    
    def stop_workflow(self):
        """Stop the currently running workflow."""
        # TODO: Implement workflow stopping
        self.log_console.log("Stop workflow not implemented yet")
    
    def validate_workflow(self):
        """Validate the current workflow."""
        # Update workflow data from canvas
        workflow_data = self.canvas.get_workflow_data()
        self.current_workflow.update(workflow_data)
        
        try:
            # Validate using the API
            validation = self.api_client.validate_workflow(self.current_workflow)
            
            if validation.get("valid", False):
                QMessageBox.information(
                    self, "Validation Result",
                    "Workflow is valid and ready to run."
                )
                self.log_console.log("Workflow validation successful")
            else:
                QMessageBox.critical(
                    self, "Validation Error",
                    f"Workflow validation failed: {validation.get('errors', '')}"
                )
                self.log_console.log(f"Workflow validation failed: {validation.get('errors', '')}")
            
        except Exception as e:
            QMessageBox.critical(
                self, "Validation Error",
                f"An error occurred during validation: {str(e)}"
            )
    
    def on_node_selected(self, node_id):
        """Handle node selection."""
        # Update property panel with selected node data
        if node_id is None:
            self.property_panel.clear()
        else:
            node_data = self.canvas.get_node_data(node_id)
            if node_data:
                self.property_panel.load_node(node_data)
    
    def show_about(self):
        """Show the about dialog."""
        QMessageBox.about(
            self, "About AI Workflow Builder",
            "AI Workflow Builder\n\n"
            "A tool for creating and executing AI agent workflows.\n\n"
            "Version: 1.0.0"
        )