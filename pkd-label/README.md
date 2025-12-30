# pkd-label

Script for PKD (Polska Klasyfikacja Działalności) code data fetching via scraping the pkd.com.pl website.
It is intentionally not using BeautifulSoup (or a similar HTML parsing library) as a challenge (and sake of simplicity).

## Requirements

- Python >=3.12
- [uv](https://github.com/astral-sh/uv)

## Installation

This project uses `uv` for dependency management.

```bash
uv sync
```

## Usage

```bash
uv run main.py <PKD codes separated by spaces>
```