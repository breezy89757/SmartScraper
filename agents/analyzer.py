"""
頁面分析 Agent
使用 Azure OpenAI 理解網頁結構和使用者意圖
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
class AnalysisResult:
    """分析結果"""
    target_description: str      # 目標描述
    suggested_selectors: list    # 建議的 CSS selectors
    data_structure: dict         # 預期資料結構
    page_type: str               # 頁面類型 (表格、列表、單頁等)


class PageAnalyzer:
    """
    頁面分析 Agent
    使用 Azure OpenAI 分析網頁結構
    """
    
    def __init__(self):
        deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.2-chat")
        self._client = AzureOpenAIClient(deployment=deployment)
    
    async def analyze(
        self,
        user_goal: str,
        page_title: str,
        simplified_html: str,
        screenshot_base64: Optional[str] = None
    ) -> AnalysisResult:
        """
        分析網頁並理解使用者意圖
        
        Args:
            user_goal: 使用者想要抓取什麼
            page_title: 網頁標題
            simplified_html: 簡化的 HTML 結構
            screenshot_base64: 截圖 (用於 Vision 分析)
        
        Returns:
            AnalysisResult
        """
        # 建構 prompt
        system_prompt = """你是一個網頁爬蟲專家。分析給定的網頁結構，根據使用者的目標，
找出最佳的資料擷取策略。

你需要輸出 JSON 格式：
{
    "target_description": "描述要抓取的內容",
    "suggested_selectors": ["CSS selector 1", "CSS selector 2"],
    "data_structure": {"field1": "string", "field2": "number"},
    "page_type": "table|list|single|other"
}"""

        user_prompt = f"""網頁標題: {page_title}

使用者目標: {user_goal}

網頁結構:
{simplified_html[:3000]}

請分析並給出 JSON 格式的回應。"""

        # 建構 messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 如果有截圖，使用 Vision (只有 Completions API 支援)
        if screenshot_base64:
            messages[1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_base64}"
                        }
                    }
                ]
            }
        
        # 呼叫 API (自動選擇)
        response = await self._client.chat(
            messages=messages,
            temperature=0.3,
            json_mode=True
        )
        
        # 解析回應 - 嘗試提取 JSON
        content = response.content.strip()
        
        # 嘗試直接解析
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # 嘗試從 markdown 代碼塊提取
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # 嘗試找任何 JSON 物件
                json_match = re.search(r'\{[^{}]*"target_description"[^{}]*\}', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    # 返回預設值
                    print(f"⚠️ 無法解析回應: {content[:200]}")
                    data = {
                        "target_description": "無法解析",
                        "suggested_selectors": [],
                        "data_structure": {},
                        "page_type": "other"
                    }
        
        return AnalysisResult(
            target_description=data.get("target_description", ""),
            suggested_selectors=data.get("suggested_selectors", []),
            data_structure=data.get("data_structure", {}),
            page_type=data.get("page_type", "other")
        )
    
    async def close(self):
        await self._client.close()


# 測試
async def main():
    analyzer = PageAnalyzer()
    
    result = await analyzer.analyze(
        user_goal="抓取美元指數和美元日圓的價格",
        page_title="StockQ 國際股市指數",
        simplified_html="<table><tr><td>美元指數</td><td>98.42</td></tr></table>"
    )
    
    print(f"目標: {result.target_description}")
    print(f"Selectors: {result.suggested_selectors}")
    print(f"結構: {result.data_structure}")
    
    await analyzer.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
