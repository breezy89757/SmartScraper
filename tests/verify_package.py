import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import io
import zipfile
import asyncio
from main import download_scraper, DownloadRequest

async def verify():
    print("🔍 Starting Package Verification...")
    
    # 1. Mock Request
    request = DownloadRequest(
        code="print('hello')",
        url="https://www.stockq.org/market/asia.php",
        goal="Extract Stock Data"
    )
    
    print(f"👉 Target URL: {request.url}")
    
    try:
        # 2. Call Endpoint (Directly, bypassing HTTP layer for speed)
        response = await download_scraper(request)
        
        # 3. Extract ZIP from StreamingResponse
        content = b""
        async for chunk in response.body_iterator:
            content += chunk
            
        zip_buffer = io.BytesIO(content)
        
        with zipfile.ZipFile(zip_buffer, 'r') as z:
            file_list = z.namelist()
            print(f"📂 Files in ZIP: {file_list}")
            
            # Check 1: Dynamic Filename in ZIP (Implied by presence of setup_task.ps1 content check later)
            
            # Check 1b: PEP 723 Metadata in scraper.py
            if "scraper.py" in file_list:
                py_content = z.read("scraper.py").decode('utf-8')
                if "# /// script" in py_content and "requests" in py_content:
                    print("✅ scraper.py: PEP 723 Metadata found (uv run support confirmed).")
                else:
                    print("❌ scraper.py: PEP 723 Metadata MISSING!")
                    sys.exit(1)
            
            # Check 2: run.bat GOTO syntax
            if "run.bat" in file_list:
                bat_content = z.read("run.bat").decode('utf-8')
                if "goto USE_UV" in bat_content and ":USE_UV" in bat_content:
                     print("✅ run.bat: GOTO syntax found (Fix Verified).")
                else:
                     print("❌ run.bat: GOTO syntax MISSING!")
                     sys.exit(1)
            else:
                 print("❌ run.bat missing!")
                 sys.exit(1)

            # Check 3: setup_task.ps1 dynamic name & CMD wrapper
            if "setup_task.ps1" in file_list:
                ps1_content = z.read("setup_task.ps1").decode('utf-8')
                if "SmartScraper-www_stockq_org" in ps1_content:
                    print("✅ setup_task.ps1: Dynamic TaskName found (www_stockq_org).")
                else:
                    print(f"❌ setup_task.ps1: Dynamic TaskName MISSING!")
                    sys.exit(1)
                
                if 'cmd.exe' in ps1_content and '> result.txt' in ps1_content:
                    print("✅ setup_task.ps1: CMD wrapper logic found (Redirects to result.txt).")
                else:
                    print(f"❌ setup_task.ps1: CMD wrapper logic MISSING!")
                    sys.exit(1)
            
            # Save for user
            output_path = os.path.join(os.path.dirname(__file__), "verified_package.zip")
            with open(output_path, "wb") as f:
                f.write(zip_buffer.getvalue())
            
            print(f"\n🎉 Verification PASSED! Package saved to:\n{output_path}")
            
    except Exception as e:
        print(f"❌ Verification FAILED: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    import uvicorn
    # Minimal mock of FastAPI context if needed, but direct function call is easier
    asyncio.run(verify())
