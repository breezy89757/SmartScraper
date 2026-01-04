"""
SmartScraper - AI 驅動的爬蟲生成器
FastAPI 主入口
"""
import os
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import io
import zipfile

from browser.playwright_client import PlaywrightClient
from agents.analyzer import PageAnalyzer
from agents.generator import ScraperGenerator
from sandbox.executor import SandboxExecutor

load_dotenv()

# 全域客戶端
browser_client: Optional[PlaywrightClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    global browser_client
    browser_client = PlaywrightClient()
    await browser_client.start()
    print("✅ Playwright 瀏覽器已啟動")
    yield
    await browser_client.stop()
    print("🛑 瀏覽器已關閉")


app = FastAPI(
    title="SmartScraper",
    description="AI 驅動的爬蟲生成器 - 輸入 URL + 目標，自動產生爬蟲程式碼",
    version="1.1.0",
    lifespan=lifespan
)

# 靜態檔案
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """首頁 - 網頁介面"""
    index_file = static_path / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>SmartScraper</h1><p>Static files not found</p>")


# ===== Request/Response Models =====

class AnalyzeRequest(BaseModel):
    url: str
    goal: str  # 例如 "抓取商品價格"


class GenerateRequest(BaseModel):
    url: str
    goal: str
    use_vision: bool = True


class ExecuteRequest(BaseModel):
    code: str
    url: str


class FullPipelineRequest(BaseModel):
    url: str
    goal: str
    use_vision: bool = True
    auto_execute: bool = True


class FixRequest(BaseModel):
    original_code: str
    url: str
    goal: str
    execution_result: str
    user_feedback: Optional[str] = ""


class DownloadRequest(BaseModel):
    code: str
    url: str
    filename: str = "scraper"


# ===== Endpoints =====

@app.get("/health")
async def health():
    return {"status": "ok", "browser": browser_client is not None}


@app.post("/analyze")
async def analyze_page(request: AnalyzeRequest):
    """
    分析網頁結構
    
    返回：建議的 selectors 和資料結構
    """
    if not browser_client:
        raise HTTPException(500, "瀏覽器未啟動")
    
    # 載入並分析網頁
    page_data = await browser_client.analyze_page(request.url)
    
    # AI 分析
    analyzer = PageAnalyzer()
    try:
        result = await analyzer.analyze(
            user_goal=request.goal,
            page_title=page_data.title,
            simplified_html=page_data.simplified_html,
            screenshot_base64=page_data.screenshot_base64
        )
        
        return {
            "page_title": page_data.title,
            "analysis": {
                "target": result.target_description,
                "selectors": result.suggested_selectors,
                "structure": result.data_structure,
                "page_type": result.page_type
            }
        }
    finally:
        await analyzer.close()


@app.post("/generate")
async def generate_scraper(request: GenerateRequest):
    """
    生成爬蟲程式碼
    
    完整流程：分析 → 生成程式碼
    """
    if not browser_client:
        raise HTTPException(500, "瀏覽器未啟動")
    
    # Step 1: 載入網頁
    page_data = await browser_client.analyze_page(request.url)
    
    # Step 2: 分析
    analyzer = PageAnalyzer()
    try:
        analysis = await analyzer.analyze(
            user_goal=request.goal,
            page_title=page_data.title,
            simplified_html=page_data.simplified_html,
            screenshot_base64=page_data.screenshot_base64 if request.use_vision else None
        )
    finally:
        await analyzer.close()
    
    # [Debug] 顯示分析結果
    print("\n" + "="*50)
    print("🤖 Analyzer 思考結果 (傳給 Generator 的規格書):")
    print("-" * 50)
    print(f"📌 目標描述: {analysis.target_description}")
    print(f"🔍 建議 Selectors: {analysis.suggested_selectors}")
    print(f"📐 預期資料結構: {analysis.data_structure}")
    print(f"📄 頁面類型: {analysis.page_type}")

    if analysis.usage:
        print(f"💰 Analyzer Usage: {analysis.usage}")
    print("="*50 + "\n")
    
    # Step 3: 生成程式碼
    generator = ScraperGenerator()
    try:
        code_result = await generator.generate(
            url=request.url,
            target_description=analysis.target_description,
            selectors=analysis.suggested_selectors,
            data_structure=analysis.data_structure,
            page_type=analysis.page_type
        )
        
        if code_result.usage:
            print(f"💰 Generator Usage: {code_result.usage}")
        
        return {
            "analysis": {
                "target": analysis.target_description,
                "selectors": analysis.suggested_selectors,
                "structure": analysis.data_structure
            },
            "generated_code": code_result.code,
            "imports": code_result.imports,
            "explanation": code_result.explanation
        }
    finally:
        await generator.close()


@app.post("/execute")
async def execute_code(request: ExecuteRequest):
    """
    在沙箱中執行程式碼
    
    ⚠️ 只執行受信任的程式碼
    """
    executor = SandboxExecutor()
    result = executor.execute(request.code, request.url)
    
    if result.success:
        return {
            "success": True,
            "data": result.data,
            "stdout": result.stdout
        }
    else:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": result.error,
                "stdout": result.stdout
            }
        )


@app.post("/fix")
async def fix_code(request: FixRequest):
    """
    AI 修正程式碼

    根據執行結果修正爬蟲程式碼
    """
    generator = ScraperGenerator()
    try:
        fixed_code = await generator.fix_code(
            original_code=request.original_code,
            url=request.url,
            goal=request.goal,
            error=request.execution_result,
            user_feedback=request.user_feedback
        )
        return {"fixed_code": fixed_code}
    finally:
        await generator.close()


@app.post("/full")
async def full_pipeline(request: FullPipelineRequest):
    """
    完整流程：分析 → 生成 → 執行
    
    一鍵完成爬蟲任務
    """
    if not browser_client:
        raise HTTPException(500, "瀏覽器未啟動")
    
    result = {
        "url": request.url,
        "goal": request.goal,
        "steps": {}
    }
    
    # Step 1: 載入網頁
    page_data = await browser_client.analyze_page(request.url)
    result["page_title"] = page_data.title
    
    # Step 2: 分析
    analyzer = PageAnalyzer()
    try:
        analysis = await analyzer.analyze(
            user_goal=request.goal,
            page_title=page_data.title,
            simplified_html=page_data.simplified_html,
            screenshot_base64=page_data.screenshot_base64 if request.use_vision else None
        )
        result["steps"]["analysis"] = {
            "target": analysis.target_description,
            "selectors": analysis.suggested_selectors,
            "structure": analysis.data_structure
        }
    finally:
        await analyzer.close()
    
    # Step 3: 生成程式碼
    generator = ScraperGenerator()
    try:
        code_result = await generator.generate(
            url=request.url,
            target_description=analysis.target_description,
            selectors=analysis.suggested_selectors,
            data_structure=analysis.data_structure,
            page_type=analysis.page_type
        )
        result["steps"]["generation"] = {
            "code": code_result.code,
            "explanation": code_result.explanation
        }
    finally:
        await generator.close()
    
    # Step 4: 執行 (如果啟用)
    if request.auto_execute:
        executor = SandboxExecutor()
        exec_result = executor.execute(code_result.code, request.url)
        result["steps"]["execution"] = {
            "success": exec_result.success,
            "data": exec_result.data if exec_result.success else None,
            "error": exec_result.error if not exec_result.success else None
        }
    
    return result


@app.post("/download")
async def download_scraper(request: DownloadRequest):
    """打包並下載爬蟲程式碼 (ZIP)"""
    try:
        # 0. 產生動態檔名 (e.g., scraper_stockq_org.zip)
        from urllib.parse import urlparse
        import re
        
        domain = urlparse(request.url).netloc
        safe_domain = re.sub(r'[^a-zA-Z0-9]', '_', domain)
        zip_filename = f"scraper_{safe_domain}"
        
        # 1. 準備檔案內容
        files = {}
        
        # scraper.py (Inject PEP 723 Metadata for uv run support)
        pep723_header = """# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "beautifulsoup4",
#     "pandas",
#     "openpyxl",
# ]
# ///
"""
        files[f"{request.filename}.py"] = pep723_header + "\n" + request.code
        
        # requirements.txt
        files["requirements.txt"] = "requests\nbeautifulsoup4\npandas\nopenpyxl"
        
        # run.bat (支援 uv 或 fallback 到 venv, 使用 GOTO 避免括號問題)
        files["run.bat"] = f"""@echo off
cd /d "%~dp0"
echo [SmartScraper] Checking for 'uv' package manager...

where uv >nul 2>nul
if %ERRORLEVEL% equ 0 goto USE_UV
goto USE_VENV

:USE_UV
echo [SmartScraper] 'uv' found! Using uv to run with isolated environment...
echo [SmartScraper] Running: uv run {request.filename}.py
uv run {request.filename}.py > result.txt 2>&1
goto DONE

:USE_VENV
echo [SmartScraper] 'uv' not found. Falling back to Python venv...

if not exist .venv (
    echo [SmartScraper] Creating virtual environment...
    python -m venv .venv
)

echo [SmartScraper] Activating venv...
call .venv\\Scripts\\activate.bat

echo [SmartScraper] Installing dependencies into venv...
pip install -r requirements.txt

echo [SmartScraper] Running scraper...
python {request.filename}.py > result.txt 2>&1

deactivate
goto DONE

:DONE
echo.
echo [SmartScraper] Done! Output saved to result.txt
pause
"""
        
        # setup_task.ps1 (自動排程)
        files["setup_task.ps1"] = f"""$TaskName = "SmartScraper-{safe_domain}"
$ScriptPath = "$PSScriptRoot\\{request.filename}.py"

# 檢查 uv
$UVPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source

if ($UVPath) {{
    $ExePath = "cmd.exe"
    # 注意: Windows 排程器 Argument 需要非常小心的跳脫引號
    # 我們希望執行: cmd /c "uv run "ScriptPath" > result.txt 2>&1"
    $Args = "/c uv run `"$ScriptPath`" > result.txt 2>&1"
    Write-Host "Using 'uv' for execution." -ForegroundColor Cyan
}} elseif ($PythonPath) {{
    $ExePath = "cmd.exe"
    $Args = "/c python `"$ScriptPath`" > result.txt 2>&1"
    Write-Host "Using 'python' for execution (Global Env)." -ForegroundColor Yellow
}} else {{
    Write-Error "Neither 'uv' nor 'python' found in PATH."
    exit 1
}}

$Action = New-ScheduledTaskAction -Execute $ExePath -Argument $Args -WorkingDirectory $PSScriptRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -Action $Action -Trigger $Trigger -TaskName $TaskName -Description "Daily SmartScraper execution for {request.url}" -Force

Write-Host "Task '$TaskName' registered successfully to run daily at 9:00 AM." -ForegroundColor Green
Write-Host "Logs will be saved to: $PSScriptRoot\\result.txt" -ForegroundColor Gray
"""

        # setup_task.bat (Wrapper for visibility)
        files["setup_task.bat"] = """@echo off
cd /d "%~dp0"
echo [SmartScraper] Setting up Windows Task Scheduler...
powershell -NoProfile -ExecutionPolicy Bypass -File "setup_task.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Task setup failed!
    echo Possible reasons:
    echo  1. Not running as Administrator (Right-click -> Run as Admin)
    echo  2. PowerShell execution policy blocks scripts
)
echo.
pause
"""

        # README.md
        files["README.md"] = f"""# 🕷️ {request.filename} ({domain})

Target: {request.url}

## 🚀 How to Run

### Method 1: Using `uv` (Recommended)
If you have `uv` installed (modern Python package manager), it will automatically create a virtual environment and run safely without polluting your system.

**Double-click `run.bat`**

### Method 2: Standard Python
If you don't have `uv`, `run.bat` will fall back to standard `pip install` + `python`.

## 📅 Auto-Scheduling

To run this scraper every day at 09:00 AM:

1.  **Right-click `setup_task.bat`**
2.  Select **"Run as Administrator"** (Required for Task Scheduler)
3.  Follow the prompts.

## 📂 Output
Results will be saved to `result.txt` in the same folder.
"""

        # 2. 建立 ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for name, content in files.items():
                zip_file.writestr(name, content)
        
        zip_buffer.seek(0)
        
        # 3. 回傳
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}.zip"'}
        )

    except Exception as e:
        print(f"❌ Download Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
