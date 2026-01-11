"""
某市高级人民法院文书抓取工具（修复异步错误版）
使用方法：python court_fixed_async.py
"""

import asyncio
import json
import random
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from playwright.async_api import async_playwright

class FixedAsyncCourtCrawler:
    def __init__(self, headless=False, max_cases=3, output_dir="抓取结果"):
        self.headless = headless
        self.max_cases = max_cases
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.all_cases = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.json_file = self.output_dir / f"cases_{timestamp}.json"
        self.csv_file = self.output_dir / f"cases_{timestamp}.csv"
        
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'start': datetime.now().isoformat()
        }
    
    async def random_delay(self, min_sec=1, max_sec=3):
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def submit_search(self, page):
        """提交搜索表单"""
        print("🔍 提交搜索表单...")
        
        try:
            # 等待页面加载
            await page.wait_for_load_state('networkidle', timeout=15000)
            await self.random_delay(1, 2)
            
            # 直接通过JavaScript提交
            submit_script = """
            () => {
                const forms = document.querySelectorAll('form');
                if (forms.length > 0) {
                    forms[0].submit();
                    console.log('表单提交成功');
                    return true;
                }
                return false;
            }
            """
            
            result = await page.evaluate(submit_script)
            if result:
                print("✅ 表单已提交")
            
            # 等待结果加载
            print("⏳ 等待搜索结果...")
            await page.wait_for_timeout(5000)
            
            # 检查是否出现文书行
            has_case_rows = await page.locator('tr[id^="tr"]').count() > 0
            if has_case_rows:
                print("✅ 检测到文书数据行")
                return True
            else:
                print("⚠️ 未检测到文书行，继续尝试...")
                return True
                
        except Exception as e:
            print(f"❌ 表单提交失败: {e}")
            return False
    
    async def extract_case_data(self, page):
        """提取文书数据 - 修复异步调用"""
        print("📊 提取文书数据...")
        
        cases = []
        try:
            # 等待文书行出现
            await page.wait_for_selector('tr[id^="tr"]', timeout=10000)
            
            # 找到所有文书行
            case_rows = await page.locator('tr[id^="tr"]').all()
            print(f"找到 {len(case_rows)} 个文书行")
            
            # 限制处理数量
            rows_to_process = case_rows[:self.max_cases]
            
            for i, row in enumerate(rows_to_process):
                try:
                    # 获取行属性
                    row_id = await row.get_attribute('id') or f"tr{i}"
                    onclick_attr = await row.get_attribute('onclick') or ""
                    
                    # 提取加密参数
                    detail_param = ""
                    if onclick_attr:
                        match = re.search(r"showone\('([^']+)'\)", onclick_attr)
                        if match:
                            detail_param = match.group(1)
                    
                    # 提取所有单元格 - 修复：确保每个inner_text()都使用await
                    cells = await row.locator('td').all()
                    
                    if len(cells) >= 7:
                        # 分别获取每个单元格的文本
                        case_number = await cells[0].inner_text()
                        title = await cells[1].inner_text()
                        doc_type = await cells[2].inner_text()
                        
                        # 修复：await后再调用字符串方法
                        case_reason_text = await cells[3].inner_text()
                        case_reason = case_reason_text.replace('&nbsp;', '').strip()
                        
                        department_text = await cells[4].inner_text()
                        department = department_text.replace('&nbsp;', '').strip()
                        
                        level_text = await cells[5].inner_text()
                        level = level_text.replace('&nbsp;', '').strip()
                        
                        close_date = await cells[6].inner_text()
                        
                        case_data = {
                            'row_id': row_id,
                            'case_number': case_number.strip(),
                            'title': title.strip(),
                            'doc_type': doc_type.strip(),
                            'case_reason': case_reason,
                            'department': department,
                            'level': level,
                            'close_date': close_date.strip(),
                            'detail_param': detail_param,
                            'row_index': i
                        }
                        
                        # 构建详情页URL
                        if detail_param:
                            base_url = "https://www.XXXXX.XX.cn/XXXX/web/flws_view.jsp" #注意要替换网址
                            case_data['detail_url'] = f"{base_url}?pa={detail_param}"
                        else:
                            case_data['detail_url'] = ""
                        
                        cases.append(case_data)
                        print(f"  已提取: {case_data['case_number']}")
                        
                except Exception as e:
                    print(f"  第{i}行提取失败: {str(e)[:100]}")
                    continue
            
            self.stats['total'] = len(case_rows)
            print(f"✅ 成功提取 {len(cases)} 个文书")
            return cases
            
        except Exception as e:
            print(f"❌ 数据提取失败: {e}")
            await page.screenshot(path=self.output_dir / 'extract_error.png')
            return cases
    
    async def crawl_detail_page(self, context, case_data, main_page):
        """抓取详情页内容"""
        print(f"📄 打开详情页: {case_data['case_number']}")
        
        if not case_data.get('detail_url'):
            print("  ⚠️ 无详情链接，跳过")
            return None
        
        detail_page = None
        try:
            # 监听新页面打开
            async with context.expect_page() as new_page_info:
                # 点击对应的行
                try:
                    row_selector = f'tr[id="{case_data["row_id"]}"]'
                    if await main_page.locator(row_selector).count() > 0:
                        await main_page.click(row_selector)
                        print(f"  点击行: {case_data['row_id']}")
                    else:
                        # 备选：通过案号查找
                        case_number_text = case_data['case_number'].replace('(', '\\(').replace(')', '\\)')
                        text_selector = f'text="{case_number_text}"'
                        if await main_page.locator(text_selector).count() > 0:
                            await main_page.click(text_selector)
                            print(f"  点击案号文本: {case_data['case_number']}")
                except Exception as e:
                    print(f"  点击失败: {e}")
                    # 直接访问URL
                    detail_page = await context.new_page()
                    await detail_page.goto(case_data['detail_url'], timeout=30000)
            
            # 获取新页面
            if not detail_page:
                detail_page = await new_page_info.value
            
            # 等待详情页加载
            await detail_page.wait_for_load_state('networkidle', timeout=15000)
            await self.random_delay(0.5, 1.5)
            
            # 提取详情内容
            detail_content = await self.extract_detail_content(detail_page)
            
            # 合并数据
            full_data = {**case_data, **detail_content}
            
            self.stats['success'] += 1
            print(f"✅ 详情页抓取成功")
            return full_data
            
        except Exception as e:
            print(f"❌ 详情页失败: {str(e)[:100]}")
            self.stats['failed'] += 1
            return None
        finally:
            if detail_page:
                await detail_page.close()
    
    async def extract_detail_content(self, page):
        """提取详情页内容"""
        try:
            # 等待内容加载
            await page.wait_for_timeout(2000)
            
            # 获取页面内容
            content = await page.content()
            
            # 简单提取文本
            text = await page.locator('body').inner_text()
            cleaned_text = ' '.join(text.split())  # 合并多余空格
            
            return {
                'detail_text': cleaned_text[:5000] + '...' if len(cleaned_text) > 5000 else cleaned_text,
                'detail_url': page.url,
                'detail_fetched_at': datetime.now().isoformat(),
                'content_length': len(content)
            }
        except Exception as e:
            print(f"  详情内容提取失败: {e}")
            return {}
    
    async def save_data(self):
        """保存数据"""
        if not self.all_cases:
            print("⚠️ 无数据可保存")
            return
        
        print("💾 保存数据...")
        
        try:
            # 保存JSON
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_cases, f, ensure_ascii=False, indent=2)
            print(f"   JSON: {self.json_file}")
            
            # 保存CSV
            df = pd.DataFrame(self.all_cases)
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            print(f"   CSV: {self.csv_file}")
            
            # 保存简版CSV（不含长文本）
            if 'detail_text' in df.columns:
                simple_df = df.drop(columns=['detail_text'])
                simple_file = self.csv_file.with_name(f"简版_{self.csv_file.name}")
                simple_df.to_csv(simple_file, index=False, encoding='utf-8-sig')
                print(f"   简版CSV: {simple_file}")
                
        except Exception as e:
            print(f"❌ 保存失败: {e}")
    
    async def run(self, start_url):
        """主运行流程"""
        print("=" * 50)
        print("某市高级人民法院文书抓取（修复异步版）")
        print("=" * 50)
        
        playwright = None
        browser = None
        
        try:
            # 启动浏览器
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=['--start-maximized']
            )
            context = await browser.new_context(
                viewport={'width': 1200, 'height': 800}
            )
            
            # 打开页面
            page = await context.new_page()
            print(f"🌐 访问: {start_url}")
            await page.goto(start_url, timeout=30000)
            
            # 提交搜索
            if not await self.submit_search(page):
                print("❌ 搜索失败，程序结束")
                return
            
            # 提取列表
            print("\n📋 提取文书列表...")
            await self.random_delay(2, 3)
            cases = await self.extract_case_data(page)
            
            if not cases:
                print("⚠️ 未提取到文书数据")
                # 保存当前页面供调试
                await page.screenshot(path=self.output_dir / 'no_cases_debug.png')
                return
            
            print(f"📊 找到 {len(cases)} 个文书，开始抓取详情...")
            
            # 抓取详情页
            for i, case in enumerate(cases):
                print(f"\n[{i+1}/{len(cases)}] {case['case_number']}")
                
                detail_data = await self.crawl_detail_page(context, case, page)
                if detail_data:
                    self.all_cases.append(detail_data)
                    print(f"  已保存到列表")
                
                # 每抓取1个就保存一次（避免丢失数据）
                if (i + 1) % 1 == 0:
                    await self.save_data()
                
                # 延迟（避免请求过快）
                if i < len(cases) - 1:
                    delay = random.uniform(2, 4)
                    print(f"  等待 {delay:.1f}秒...")
                    await asyncio.sleep(delay)
            
            # 最终保存
            await self.save_data()
            
            # 统计信息
            self.stats['end'] = datetime.now().isoformat()
            start = datetime.fromisoformat(self.stats['start'])
            end = datetime.fromisoformat(self.stats['end'])
            duration = (end - start).total_seconds()
            
            print("\n" + "=" * 50)
            print("✅ 抓取完成！")
            print(f"   发现文书: {self.stats['total']}")
            print(f"   成功抓取: {self.stats['success']}")
            print(f"   失败: {self.stats['failed']}")
            print(f"   耗时: {duration:.1f}秒")
            print(f"   输出目录: {self.output_dir}")
            print("=" * 50)
            
        except Exception as e:
            print(f"\n❌ 程序运行异常: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
        finally:
            # 清理资源
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            
            # 最后保存一次
            if self.all_cases:
                await self.save_data()

async def main():
    """主函数"""
    config = {
        'start_url': 'https://www.hshfy.sh.cn/shfy/gweb2017/flws_list_new.jsp?ajlb=aYWpsYj3QzMrCz',
        'headless': False,  # 调试时设为False
        'max_cases': 9,     # 测试用9个
        'output_dir': '最终抓取测试'
    }
    
    print("配置:")
    for k, v in config.items():
        print(f"  {k}: {v}")
    
    crawler = FixedAsyncCourtCrawler(
        headless=config['headless'],
        max_cases=config['max_cases'],
        output_dir=config['output_dir']
    )
    
    await crawler.run(config['start_url'])

if __name__ == "__main__":

    asyncio.run(main())

