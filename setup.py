from setuptools import setup, find_packages

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
    install_requires=open("requirements.txt").read().splitlines(),
)