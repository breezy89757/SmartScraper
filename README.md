# 🕷️ SmartScraper

SmartScraper is an AI-powered tool designed to generate, execute, and refine Python web scrapers. It leverages LLMs (GPT-5.x/Codex) to bridge the gap between human intent and executable Playwright/BeautifulSoup code.

## Workflow
    
SmartScraper implements an **iterative generation** process to handle complex DOM structures:

1.  **Generate**: AI analyzes the webpage structure (HTML + Screenshot) and writes an initial script.
2.  **Execute**: The script is run in a secure, isolated sandbox.
3.  **Refine**: If execution fails or data is missing, the AI analyzes the error log and user feedback to patch the code automatically.

## Features

*   **Visual Analysis**: Uses GPT-Vision to understand page layout and identify target data tables/lists.
*   **Secure Sandbox**: Executes generated code in a restricted environment (whitelisted imports only, no FS/Network access beyond scraping).
*   **Recursive Correction**: The `/fix` endpoint accepts error logs and user feedback to patch the script intelligently.
*   **Portable Export**: Download the finalized scraper as a ZIP package with auto-scheduling scripts (`setup_task.ps1`) for deployment.

## 🛠️ Architecture

The system follows a 3-stage funnel designed for stability and cost-efficiency:

1.  **Browser Layer (Playwright)**
    *   Injects JavaScript to simplify the DOM, removing noise (`script`, `svg`, `style`) and limiting element depth (StockQ optimized: Limit 300 / Depth 8).
    *   Reduces token context by ~90% while retaining structural integrity.

2.  **Analyzer Agent (GPT-5.2)**
    *   Reads the simplified HTML + Screenshot.
    *   Outputs a JSON specification (Selectors, Data Structure) for the generator.

3.  **Generator Agent (Codex)**
    *   Translates the specification into robust Python code (`requests` + `BeautifulSoup` + `urllib`).
    *   Includes `User-Agent` rotation and reliable error handling.

## 📦 Installation & Usage

### Prerequisites
*   Python 3.10+
*   Azure OpenAI Endpoint (GPT-5.2-Chat & GPT-5.1-Codex)

### Setup
1.  Clone repository:
    ```bash
    git clone https://github.com/breezy89757/SmartScraper.git
    cd SmartScraper
    ```
2.  Install dependencies (using `uv` is recommended):
    ```bash
    uv sync
    ```
3.  Configure environment:
    *   Copy `.env.example` to `.env`
    *   Set `AZURE_OPENAI_API_KEY`, `ENDPOINT`, `DEPLOYMENT_NAME`.

### Running
```bash
uv run python main.py
```
Open browser at `http://localhost:8081`.

## 🔒 Security Note
This tool executes AI-generated code. While the `SandboxExecutor` restricts imports to a safe list (`requests`, `bs4`, `json`, `urllib`), **never run this server on a public-facing network without additional authentication layers**.
