"""
程式碼生成 Agent
使用 Codex 模型生成 Python 爬蟲程式碼
支援 Responses API 和 Completions API 自動切換
"""
import os
import json
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

from agents.openai_client import AzureOpenAIClient

load_dotenv()


@dataclass
class GeneratedCode:
    """生成的程式碼"""
    code: str                    # Python 程式碼
    imports: list                # 需要的 imports
    explanation: str             # 程式碼說明
    usage: Optional[dict] = None # Token 用量


class ScraperGenerator:
    """
    爬蟲程式碼生成器
    使用 Azure OpenAI Codex 生成 Python 程式碼
    """
    
    def __init__(self):
        deployment = os.getenv("AZURE_OPENAI_CODEX_DEPLOYMENT", "gpt-5.1-codex-max")
        self._client = AzureOpenAIClient(deployment=deployment)
    
    async def generate(
        self,
        url: str,
        target_description: str,
        selectors: list,
        data_structure: dict,
        page_type: str
    ) -> GeneratedCode:
        """
        生成爬蟲程式碼
        
        Args:
            url: 目標網址
            target_description: 要抓取什麼
            selectors: CSS selectors
            data_structure: 資料結構
            page_type: 頁面類型
        
        Returns:
            GeneratedCode
        """
        system_prompt = """你是一個 Python 爬蟲專家。根據給定的網頁資訊，生成可執行的爬蟲程式碼。

規則：
1. 使用 requests + BeautifulSoup
2. 程式碼必須是完整可執行的
3. 輸出 JSON 格式：
{
    "code": "完整的 Python 程式碼",
    "imports": ["import 語句列表"],
    "explanation": "程式碼說明"
}
4. 程式碼中定義一個 scrape(url) 函數，回傳 list[dict]
5. 加入錯誤處理
6. 不要使用任何危險函數 (exec, eval, os.system 等)"""

        user_prompt = f"""目標網址: {url}
抓取目標: {target_description}
建議的 CSS Selectors: {selectors}
資料結構: {data_structure}
頁面類型: {page_type}

請生成 Python 爬蟲程式碼。"""

        # 呼叫 API (自動選擇)
        response = await self._client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            json_mode=True
        )
        
        # 解析回應 - 嘗試提取 JSON
        content = response.content.strip()
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            import re
            # 嘗試從 markdown 代碼塊提取
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # 嘗試提取程式碼
                code_match = re.search(r'```python\s*(.*?)\s*```', content, re.DOTALL)
                code = code_match.group(1) if code_match else content
                data = {
                    "code": code,
                    "imports": [],
                    "explanation": "從回應中提取"
                }
        
        return GeneratedCode(
            code=data.get("code", ""),
            imports=data.get("imports", []),
            explanation=data.get("explanation", ""),
            usage=response.usage
        )
    
    async def fix_code(self, original_code: str, url: str, goal: str, error: str, user_feedback: str = "") -> str:
        """
        修正爬蟲程式碼
        """
        system_prompt = """你是一個 Python 爬蟲專家。使用者的爬蟲程式碼執行後返回空結果或錯誤。
請分析問題並修正程式碼。

規則：
1. 保持 scrape(url) 函數結構
2. 修正 CSS selector 或資料提取邏輯
3. 只輸出修正後的完整程式碼，不要解釋
4. 使用 requests + BeautifulSoup
5. 優先參考使用者的額外指示（如果有的話）"""

        user_prompt = f"""目標網址: {url}
使用者目標: {goal}

原始程式碼:
```python
{original_code}
```

執行結果:
{error}

使用者額外指示 (Feedback):
{user_feedback if user_feedback else "無"}

請求:
請根據上述執行結果和指示修正程式碼。
1. 若結果為 Null/空，請檢查 CSS Selector。
2. 若有 Exception，請修復語法或邏輯。
3. 確保符合沙箱安全限制 (僅用 requests, bs4, urllib, json)。"""

        response = await self._client.chat(
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
        return code_match.group(1) if code_match else content

    async def close(self):
        await self._client.close()


# 測試
async def main():
    generator = ScraperGenerator()
    
    result = await generator.generate(
        url="https://www.stockq.org/",
        target_description="抓取美元指數和美元日圓",
        selectors=["table tr td"],
        data_structure={"name": "string", "price": "number"},
        page_type="table"
    )
    
    print(f"程式碼:\n{result.code}")
    print(f"\n說明: {result.explanation}")
    
    await generator.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
