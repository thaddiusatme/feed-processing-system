from setuptools import setup, find_packages

# Core requirements
INSTALL_REQUIRES = [
    "requests>=2.31.0",
    "python-dotenv>=1.0.0",
    "chardet>=4.0.0",
    "aiohttp>=3.9.1",
    "cachetools>=5.3.2",
    "spacy>=3.7.2",
    "textstat>=0.7.3",
    "rake-nltk>=1.0.6",
    "pyairtable>=2.2.1",
    "pybreaker>=1.0.1",
    "structlog>=23.2.0",
    "prometheus-client>=0.17.1",
    "feedparser>=6.0.0",
    "click>=8.0.0",
]

# Development requirements
EXTRAS_REQUIRE = {
    "dev": [
        "pytest>=7.4.3",
        "pytest-cov>=4.1.0",
        "pytest-mock>=3.12.0",
        "pytest-asyncio>=0.23.2",
        "black>=23.11.0",
        "flake8>=6.1.0",
        "mypy>=1.7.1",
        "isort>=5.12.0",
        "pre-commit>=3.5.0",
        "types-requests>=2.31.0.10",
        "types-python-dateutil>=2.8.19.14",
        "sphinx>=7.2.6",
        "sphinx-rtd-theme>=1.3.0",
    ],
    "test": [
        "pytest>=7.4.3",
        "pytest-cov>=4.1.0",
        "pytest-mock>=3.12.0",
        "pytest-asyncio>=0.23.2",
    ],
}

setup(
    name="feed_processor",
    version="1.0.0",
    author="Thaddius Cho",
    author_email="thaddius@thaddius.me",
    description="A robust Python-based feed processing system",
    long_description=open("README.md", "r", encoding="utf-8").read(),
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
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
)