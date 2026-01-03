"""
Playwright 瀏覽器客戶端
負責載入網頁、截圖、提取 HTML
"""
import asyncio
from playwright.async_api import async_playwright, Page, Browser
from dataclasses import dataclass
from typing import Optional
import base64


@dataclass
class PageAnalysis:
    """網頁分析結果"""
    url: str
    title: str
    html: str
    screenshot_base64: str
    simplified_html: str  # 簡化的 HTML 結構


class PlaywrightClient:
    """Playwright 瀏覽器封裝"""
    
    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None
    
    async def start(self) -> None:
        """啟動瀏覽器"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
    
    async def stop(self) -> None:
        """關閉瀏覽器"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def analyze_page(self, url: str, max_retries: int = 2) -> PageAnalysis:
        """
        分析網頁：載入、截圖、提取 HTML
        
        Args:
            url: 目標網址
            max_retries: 最大重試次數
            
        Returns:
            PageAnalysis 包含截圖和 HTML
        """
        if not self._browser:
            await self.start()
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            page = await self._browser.new_page()
            
            try:
                # 載入網頁 (使用 domcontentloaded 加快速度)
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # 等待頁面穩定
                await page.wait_for_timeout(2000)
                
                # 取得基本資訊
                title = await page.title()
                
                # 截圖 (for GPT Vision)
                screenshot_bytes = await page.screenshot(full_page=False)
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
                
                # 取得完整 HTML
                html = await page.content()
                
                # 簡化 HTML (移除 script, style, 保留結構)
                simplified = await self._simplify_html(page)
                
                return PageAnalysis(
                    url=url,
                    title=title,
                    html=html,
                    screenshot_base64=screenshot_base64,
                    simplified_html=simplified
                )
                
            except Exception as e:
                last_error = e
                print(f"⚠️ 載入失敗 (嘗試 {attempt + 1}/{max_retries + 1}): {e}")
                
            finally:
                await page.close()
        
        # 所有重試都失敗
        raise Exception(f"無法載入網頁 {url}: {last_error}")
    
    async def _simplify_html(self, page: Page) -> str:
        """
        簡化 HTML：移除 script/style，只保留結構
        """
        simplified = await page.evaluate("""
            () => {
                const clone = document.body.cloneNode(true);
                
                // 移除不需要的元素
                const removeSelectors = ['script', 'style', 'noscript', 'svg', 'iframe'];
                removeSelectors.forEach(sel => {
                    clone.querySelectorAll(sel).forEach(el => el.remove());
                });
                
                // 簡化 - 只保留前 50 個有意義的元素
                const meaningful = [];
                const walk = (el, depth = 0) => {
                    if (meaningful.length >= 50) return;
                    if (depth > 5) return;
                    
                    const tag = el.tagName?.toLowerCase();
                    if (!tag) return;
                    
                    // 有文字或特定標籤才保留
                    const text = el.textContent?.trim().slice(0, 100);
                    if (text || ['table', 'tr', 'td', 'th', 'ul', 'ol', 'li', 'a', 'img'].includes(tag)) {
                        const id = el.id ? `#${el.id}` : '';
                        const cls = el.className ? `.${el.className.split(' ')[0]}` : '';
                        meaningful.push({
                            tag: tag + id + cls,
                            text: text?.slice(0, 50) || '',
                            depth
                        });
                    }
                    
                    for (const child of el.children) {
                        walk(child, depth + 1);
                    }
                };
                
                walk(clone);
                return meaningful.map(m => '  '.repeat(m.depth) + `<${m.tag}> ${m.text}`).join('\\n');
            }
        """)
        
        return simplified


# 測試用
async def main():
    client = PlaywrightClient()
    await client.start()
    
    try:
        result = await client.analyze_page("https://www.stockq.org/")
        print(f"Title: {result.title}")
        print(f"Simplified HTML:\n{result.simplified_html[:1000]}")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
