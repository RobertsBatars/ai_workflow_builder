#!/usr/bin/env python3
"""
Setup script for AI Workflow Builder.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ai-workflow-builder",
    version="1.0.0",
    author="AI Workflow Builder Team",
    description="A node-based interface for creating AI agent workflows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ai-workflow-builder",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pyside6>=6.0.0",
        "litellm>=1.0.0",
        "faiss-cpu>=1.7.0", 
        "docker>=6.0.0",
        "fastapi>=0.95.0",
        "pydantic>=2.0.0",
        "watchdog>=3.0.0",
        "nodegraphqt>=0.5.0",
        "uvicorn>=0.22.0",
        "numpy>=1.20.0",
        "aiohttp>=3.8.0",
        "requests>=2.28.0"
    ],
    entry_points={
        "console_scripts": [
            "ai-workflow-builder=ai_workflow_builder.__main__:main",
        ],
    },
)