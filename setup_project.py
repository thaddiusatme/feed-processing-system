import os
import subprocess
import sys
from pathlib import Path


def create_directory_structure():
    """Create the project directory structure"""
    directories = [
        "src/feed_processor",
        "src/feed_processor/core",
        "src/feed_processor/analysis",
        "src/feed_processor/integrations",
        "tests",
        "tests/unit",
        "tests/integration",
        "config",
        "logs",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        # Create __init__.py files in Python package directories
        if directory.startswith("src"):
            init_file = Path(directory) / "__init__.py"
            init_file.touch(exist_ok=True)


def create_config_files():
    """Create configuration files"""
    # Create .env.example
    env_example = """# API Keys
INOREADER_TOKEN=your_token_here
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=your_base_id_here
MAKE_WEBHOOK_URL=your_webhook_url_here

# Processing Configuration
RATE_LIMIT=0.2
MAX_RETRIES=3
LOG_LEVEL=INFO
"""
    with open(".env.example", "w") as f:
        f.write(env_example)

    # Create .gitignore
    gitignore = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/

# Environment Variables
.env

# IDE
.idea/
.vscode/
*.swp
*.swo

# Logs
logs/
*.log

# Testing
.coverage
.pytest_cache/
htmlcov/

# Distribution
dist/
build/
"""
    with open(".gitignore", "w") as f:
        f.write(gitignore)


def setup_virtual_environment():
    """Set up virtual environment and install dependencies"""
    try:
        # Create virtual environment
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)

        # Determine the pip path based on operating system
        pip_path = "venv/Scripts/pip" if sys.platform == "win32" else "venv/bin/pip"

        # Upgrade pip
        subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)

        # Install dependencies
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)

        # Install spacy model
        subprocess.run([pip_path, "install", "en_core_web_lg"], check=True)

        print("Virtual environment setup complete!")

    except subprocess.CalledProcessError as e:
        print(f"Error setting up virtual environment: {e}")
        sys.exit(1)


def main():
    # Create project structure
    print("Creating project directory structure...")
    create_directory_structure()

    # Create configuration files
    print("Creating configuration files...")
    create_config_files()

    # Copy feed processor code
    print("Setting up source files...")
    with open("src/feed_processor/core/processor.py", "w") as f:
        f.write("# Feed processor implementation will go here\n")

    # Setup virtual environment and install dependencies
    print("Setting up virtual environment and installing dependencies...")
    setup_virtual_environment()

    print("\nProject setup complete! Next steps:")
    print("1. Create a .env file based on .env.example")
    print("2. Activate the virtual environment:")
    if sys.platform == "win32":
        print("   - Windows: .\\venv\\Scripts\\activate")
    else:
        print("   - Unix/MacOS: source venv/bin/activate")
    print("3. Start implementing the feed processor")


if __name__ == "__main__":
    main()
