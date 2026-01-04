# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-04

### Added
- **Portable Package Export**: Download scrapers as ZIP files (`/download` endpoint).
- **Auto-Dependency Management**: Generated scrapers now include PEP 723 metadata for `uv run` support and a fallback `venv` setup.
- **Task Scheduler Integration**: `setup_task.bat` and PowerShell script to register daily scraper tasks on Windows.
- **PTT Gossiping Support**: Updated default example to handle landing pages like PTT.
- **Filename Parsing**: Frontend now correctly extracts dynamic filenames from headers.

### Changed
- **UI Overhaul**: Migrated to a professional dark theme.
- **README**: Rewritten to focus on engineering workflow and architecture.
- **Sandbox**: Enhanced import security whitelist (e.g., `urllib.parse` submodules).

### Fixed
- **Batch Script Syntax**: Fixed `run.bat` crashing due to parenthesis parsing in `echo` commands.
- **Download Filename**: Fixed issue where downloads had UUID filenames without extensions.

## [0.1.0] - 2025-12-31

### Added
- Initial release of SmartScraper.
- AI-powered visual analysis of webpages (Playwright + GPT-Vision).
- Code generation using OpenAI Codex.
- Secure Sandbox execution environment.
- Auto-Fix loop for refining scraper code.
