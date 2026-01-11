"""
诊断脚本：分析页面真实结构，找到真正的文书数据行
使用方法：python debug_page_structure.py
"""
import asyncio
from playwright.async_api import async_playwright
import json
from pathlib import Path

async def debug_page_structure():
    async with async_playwright() as p:
        # 必须用有头模式，方便观察
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        print("1. 访问起始页面并提交搜索...")
        await page.goto('https://www.hshfy.sh.cn/shfy/gweb2017/flws_list_new.jsp?ajlb=aYWpsYj3QzMrCz')
        await page.wait_for_timeout(3000)
        
        # 尝试提交搜索
        print("2. 尝试提交表单...")
        await page.evaluate("document.querySelector('form').submit()")
        await page.wait_for_timeout(5000)  # 等待结果加载
        
        # 保存当前页面状态
        output_dir = Path("页面诊断")
        output_dir.mkdir(exist_ok=True)
        
        print("3. 保存完整页面截图...")
        await page.screenshot(path=output_dir / "full_page.png", full_page=True)
        
        print("4. 保存页面HTML源码...")
        html = await page.content()
        with open(output_dir / "page_source.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        print("5. 分析页面上的所有表格...")
        tables = await page.locator('table').all()
        print(f"   共找到 {len(tables)} 个表格")
        
        table_info = []
        for i, table in enumerate(tables):
            # 获取表格基本信息
            table_html = await table.inner_html()
            table_text = await table.inner_text()
            
            info = {
                "index": i,
                "row_count": await table.locator('tr').count(),
                "has_data_rows": await table.locator('tr:has(td)').count() > 0,
                "sample_text": table_text[:200] + "..." if len(table_text) > 200 else table_text,
                "contains_case_number": "案号" in table_text or "（202" in table_text,
                "contains_title": "标题" in table_text
            }
            table_info.append(info)
            
            print(f"\n   表格[{i}]:")
            print(f"     行数: {info['row_count']}")
            print(f"     有数据行: {info['has_data_rows']}")
            print(f"     包含案号: {info['contains_case_number']}")
            print(f"     包含标题: {info['contains_title']}")
            print(f"     示例文本: {info['sample_text']}")
            
            # 如果这个表格看起来像文书表格，进一步分析它的结构
            if info['contains_case_number'] and info['has_data_rows']:
                print(f"     ⚡ 这个可能是文书表格！详细分析...")
                
                # 截取这个表格的图片
                await table.screenshot(path=output_dir / f"table_{i}.png")
                
                # 分析表格结构
                rows = await table.locator('tr').all()
                for row_idx, row in enumerate(rows[:3]):  # 只分析前3行
                    cells = await row.locator('td, th').all()
                    print(f"       行{row_idx}: 有 {len(cells)} 个单元格")
                    for cell_idx, cell in enumerate(cells):
                        text = await cell.inner_text()
                        print(f"         单元格[{cell_idx}]: '{text}'")
        
        print("\n6. 尝试直接查找文书链接...")
        # 查找所有链接
        all_links = await page.locator('a').all()
        case_links = []
        
        for link in all_links:
            href = await link.get_attribute('href') or ''
            text = await link.inner_text()
            # 筛选可能是文书链接的
            if ('flws_view' in href or 'open' in href or '案' in text) and len(text) > 5:
                case_links.append({
                    "text": text[:50],
                    "href": href[:100]
                })
        
        print(f"   找到 {len(case_links)} 个可能是文书链接的元素")
        for link in case_links[:5]:  # 只显示前5个
            print(f"    文本: {link['text']}")
            print(f"    链接: {link['href']}")
        
        print("\n7. 保存分析结果...")
        analysis_result = {
            "tables": table_info,
            "potential_case_links": case_links[:10],  # 只保存前10个
            "page_title": await page.title(),
            "url": page.url
        }
        
        with open(output_dir / "analysis.json", "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        print("\n✅ 诊断完成！")
        print(f"请检查 '{output_dir}/' 文件夹中的文件：")
        print(f"  1. full_page.png - 整个页面截图")
        print(f"  2. page_source.html - 页面HTML源码（重要！）")
        print(f"  3. table_*.png - 可能的文书表格截图")
        print(f"  4. analysis.json - 分析结果")
        
        print("\n⚠️  关键步骤：请打开 'page_source.html' 文件")
        print("用文本编辑器或浏览器打开，搜索 '案号' 或 '（2025）'")
        print("找到文书数据所在的HTML代码段，截图发给我")
        
        # 保持浏览器打开供用户检查
        input("\n按回车键关闭浏览器...")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_page_structure())