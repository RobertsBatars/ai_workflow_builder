"""
Log console widget for displaying messages and logs.
"""
import time
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QHBoxLayout,
    QPushButton, QComboBox, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QTextCharFormat, QColor, QBrush, QTextCursor


class LogConsole(QWidget):
    """
    Console widget for displaying logs and messages.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Log storage
        self.logs = []
        self.log_levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
        self.log_colors = {
            "INFO": QColor(0, 0, 0),       # Black
            "WARNING": QColor(255, 165, 0), # Orange
            "ERROR": QColor(255, 0, 0),     # Red
            "DEBUG": QColor(128, 128, 128)  # Gray
        }
        
        # Set up UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components."""
        # Main layout
        self.layout = QVBoxLayout(self)
        
        # Controls layout
        self.controls_layout = QHBoxLayout()
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_logs)
        self.controls_layout.addWidget(self.clear_button)
        
        # Filter combo box
        self.level_label = QLabel("Level:")
        self.controls_layout.addWidget(self.level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItem("All")
        for level in self.log_levels:
            self.level_combo.addItem(level)
        self.level_combo.currentTextChanged.connect(self.filter_logs)
        self.controls_layout.addWidget(self.level_combo)
        
        # Autoscroll checkbox
        self.autoscroll_button = QPushButton("Autoscroll")
        self.autoscroll_button.setCheckable(True)
        self.autoscroll_button.setChecked(True)
        self.controls_layout.addStretch()
        self.controls_layout.addWidget(self.autoscroll_button)
        
        # Add controls layout to main layout
        self.layout.addLayout(self.controls_layout)
        
        # Log text widget
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log_text.setMaximumBlockCount(1000)  # Limit number of lines
        self.layout.addWidget(self.log_text)
        
        # Set margins
        self.layout.setContentsMargins(2, 2, 2, 2)
        
        # Apply initial styling
        self.apply_styling()
    
    def apply_styling(self):
        """Apply styling to the widget."""
        # Style the log text area
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                font-family: monospace;
                font-size: 9pt;
            }
        """)
    
    def log(self, message: str, level: str = "INFO"):
        """
        Add a log message to the console.
        
        Args:
            message: The message to log
            level: Log level (INFO, WARNING, ERROR, DEBUG)
        """
        # Validate log level
        if level not in self.log_levels:
            level = "INFO"
        
        # Create log entry
        timestamp = time.strftime("%H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        
        # Store the log
        self.logs.append(log_entry)
        
        # Format and display the log
        self._display_log(log_entry)
        
        # Auto-scroll if enabled
        if self.autoscroll_button.isChecked():
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
    
    def _display_log(self, log_entry: Dict[str, Any]):
        """
        Format and display a log entry.
        
        Args:
            log_entry: The log entry to display
        """
        # Check if this log should be displayed based on current filter
        current_filter = self.level_combo.currentText()
        if current_filter != "All" and log_entry["level"] != current_filter:
            return
        
        # Format the log message
        timestamp = log_entry["timestamp"]
        level = log_entry["level"]
        message = log_entry["message"]
        
        formatted_message = f"[{timestamp}] [{level}] {message}"
        
        # Set text color based on log level
        cursor = self.log_text.textCursor()
        format = QTextCharFormat()
        format.setForeground(QBrush(self.log_colors[level]))
        
        # Add the formatted message
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(formatted_message + "\n", format)
    
    def clear_logs(self):
        """Clear all logs from the console."""
        self.logs = []
        self.log_text.clear()
    
    def filter_logs(self, level: str):
        """
        Filter logs by level.
        
        Args:
            level: The log level to filter by, or "All" for all logs
        """
        # Clear the display
        self.log_text.clear()
        
        # Redisplay logs with the new filter
        for log_entry in self.logs:
            if level == "All" or log_entry["level"] == level:
                self._display_log(log_entry)
    
    def export_logs(self, file_path: str):
        """
        Export logs to a file.
        
        Args:
            file_path: Path to save the log file
        """
        try:
            with open(file_path, "w") as f:
                for log in self.logs:
                    timestamp = log["timestamp"]
                    level = log["level"]
                    message = log["message"]
                    f.write(f"[{timestamp}] [{level}] {message}\n")
            return True
        except Exception as e:
            self.log(f"Error exporting logs: {str(e)}", "ERROR")
            return False