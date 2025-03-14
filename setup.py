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