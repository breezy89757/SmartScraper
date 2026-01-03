"""
SmartScraper - AI 驅動的爬蟲生成器
FastAPI 主入口
"""
import os
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

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
    version="0.1.0",
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


class FixRequest(BaseModel):
    original_code: str
    url: str
    goal: str
    execution_result: str


@app.post("/fix")
async def fix_code(request: FixRequest):
    """
    AI 修正程式碼

    根據執行結果修正爬蟲程式碼
    """
    from agents.openai_client import AzureOpenAIClient
    import os

    deployment = os.getenv("AZURE_OPENAI_CODEX_DEPLOYMENT", "gpt-5.1-codex-max")
    client = AzureOpenAIClient(deployment=deployment)

    system_prompt = """你是一個 Python 爬蟲專家。使用者的爬蟲程式碼執行後返回空結果或錯誤。
請分析問題並修正程式碼。

規則：
1. 保持 scrape(url) 函數結構
2. 修正 CSS selector 或資料提取邏輯
3. 只輸出修正後的完整程式碼，不要解釋
4. 使用 requests + BeautifulSoup"""

    user_prompt = f"""目標網址: {request.url}
使用者目標: {request.goal}

原始程式碼:
```python
{request.original_code}
```

執行結果:
{request.execution_result}

請求:
請根據上述執行結果修正程式碼。
1. 如果是爬取失敗 (空結果/Null)，請嘗試檢查 CSS Selector 或 HTML 結構 (可嘗試尋找不同特徵)。
2. 如果是執行錯誤 (Exception)，請修正語法或邏輯錯誤。
3. 確保程式碼可以在受限沙箱中執行 (使用 requests, bs4, 避免 os/sys)。"""

    try:
        response = await client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )

        # 提取程式碼
        content = response.content.strip()
        import re
        code_match = re.search(r'```python\s*(.*?)\s*```', content, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1)
        else:
            fixed_code = content

        return {"fixed_code": fixed_code}

    finally:
        await client.close()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
