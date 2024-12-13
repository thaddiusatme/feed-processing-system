from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="feed_processor",
    version="1.0.0",
    author="Thaddius Cho",
    author_email="thaddius@thaddius.me",
    description="A robust Python-based feed processing system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/thaddiusatme/feed-processing-system",
    project_urls={
        "Bug Tracker": "https://github.com/thaddiusatme/feed-processing-system/issues",
        "Documentation": "https://thaddiusatme.github.io/feed-processing-system/",
    },
    packages=find_packages(exclude=["tests*", "docs*"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: News/Diary",
    ],
    python_requires=">=3.12",
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "spacy>=3.7.2",
        "textstat>=0.7.3",
        "rake-nltk>=1.0.6",
        "pyairtable>=2.2.1",
        "pybreaker>=1.0.1",
        "prometheus-client>=0.17.1",
        "structlog>=23.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.1",
            "black>=23.7.0",
            "flake8>=6.1.0",
            "mypy>=1.5.1",
            "sphinx>=7.1.2",
            "sphinx-rtd-theme>=1.3.0",
        ],
    },
)