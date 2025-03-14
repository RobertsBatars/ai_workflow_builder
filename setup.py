#!/usr/bin/env python3
"""
Setup script for AI Workflow Builder.
"""
from setuptools import setup, find_packages
import os
import re

# Read version from __init__.py
with open(os.path.join('ai_workflow_builder', '__init__.py'), 'r', encoding='utf-8') as f:
    version_file = f.read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        version = version_match.group(1)
    else:
        version = '0.0.0'  # fallback version

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ai-workflow-builder",
    version=version,
    author="AI Workflow Builder Team",
    description="A node-based interface for creating AI agent workflows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/RobertsBatars/ai_workflow_builder",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pyside6",
        "litellm",
        "faiss-cpu", 
        "docker",
        "fastapi",
        "pydantic",
        "watchdog",
        "Qt.py",
        "NodeGraphQt",
        "uvicorn",
        "numpy",
        "aiohttp",
        "requests",
        "tiktoken",
        "python-jose",
        "passlib",
        "python-multipart",
        "bcrypt",
        "cryptography"
    ],
    entry_points={
        "console_scripts": [
            "ai-workflow-builder=ai_workflow_builder.__main__:main",
        ],
    },
)