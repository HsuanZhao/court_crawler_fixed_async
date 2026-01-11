"""
上海市高级人民法院文书抓取工具（修复翻页检测问题版）
使用方法：python sh_court_fixed_async_page.py
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
    def __init__(self, headless=False, max_cases=30, output_dir="抓取结果"):
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
            'pages': 0,
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
    
    async def analyze_page_control(self, page):
        """分析分页控件并打印详细信息"""
        try:
            print("🔍 分析分页控件...")
            
            # 等待分页控件加载
            try:
                await page.wait_for_selector('div.meneame, .meneame, center#flws_list_content', timeout=5000)
            except:
                print("  ⚠️ 等待分页控件超时")
            
            # 获取分页区域的所有HTML
            page_control_script = """
            () => {
                const pageDiv = document.querySelector('div.meneame') || 
                               document.querySelector('.meneame') ||
                               document.querySelector('center#flws_list_content');
                
                if (!pageDiv) {
                    return {html: '未找到分页控件', links: []};
                }
                
                const html = pageDiv.innerHTML;
                const links = [];
                
                // 查找所有链接
                const allLinks = pageDiv.querySelectorAll('a');
                allLinks.forEach((link, index) => {
                    links.push({
                        index: index,
                        href: link.getAttribute('href') || '',
                        onclick: link.getAttribute('onclick') || '',
                        text: link.textContent || link.innerText || '',
                        outerHTML: link.outerHTML
                    });
                });
                
                // 查找当前页码
                const currentSpan = pageDiv.querySelector('span.current');
                const currentPage = currentSpan ? (currentSpan.textContent || currentSpan.innerText) : '';
                
                return {
                    html: html,
                    links: links,
                    currentPage: currentPage,
                    hasCurrentSpan: !!currentSpan,
                    totalLinks: allLinks.length
                };
            }
            """
            
            result = await page.evaluate(page_control_script)
            
            print(f"  分页控件HTML（前500字符）: {result['html'][:500]}...")
            print(f"  当前页码: {result['currentPage']}")
            print(f"  是否有current span: {result['hasCurrentSpan']}")
            print(f"  总链接数: {result['totalLinks']}")
            
            # 打印所有链接详细信息
            print(f"  链接详细信息:")
            for link in result['links']:
                print(f"    [{link['index']}] text='{link['text']}' onclick='{link['onclick']}' href='{link['href']}'")
            
            return result
            
        except Exception as e:
            print(f"❌ 分页控件分析失败: {e}")
            return None
    
    async def check_and_go_next_page(self, page, current_page_num):
        """检查并跳转到下一页"""
        try:
            print(f"🔍 尝试翻页，当前应该是第{current_page_num}页")
            
            # 先分析分页控件
            page_info = await self.analyze_page_control(page)
            
            if not page_info:
                print("❌ 无法获取分页信息")
                return False, current_page_num
            
            # 查找下一页链接
            next_page_num = current_page_num + 1
            
            # 方法1：查找包含下一页数字的链接
            print(f"  方法1: 查找页码 {next_page_num} 的链接")
            for link in page_info['links']:
                # 检查onclick中的页码
                if link['onclick']:
                    # 匹配 goPage 或 soPage
                    matches = re.findall(r'(?:goPage|soPage)\s*\(\s*[\'\"]?(\d+)[\'\"]?\s*\)', link['onclick'])
                    for match in matches:
                        if int(match) == next_page_num:
                            print(f"    ✅ 找到onclick翻页链接: {link['onclick']}")
                            await page.evaluate(f"() => {{ {link['onclick']} }}")
                            await self.wait_for_page_load(page, next_page_num)
                            return True, next_page_num
                
                # 检查href中的页码
                if link['href'] and 'javascript:' in link['href']:
                    matches = re.findall(r'(?:goPage|soPage)\s*\(\s*[\'\"]?(\d+)[\'\"]?\s*\)', link['href'])
                    for match in matches:
                        if int(match) == next_page_num:
                            print(f"    ✅ 找到href翻页链接: {link['href']}")
                            await page.click(f'a[href="{link["href"]}"]')
                            await self.wait_for_page_load(page, next_page_num)
                            return True, next_page_num
            
            # 方法2：查找"下一页"文本的链接
            print(f"  方法2: 查找'下一页'文本的链接")
            for link in page_info['links']:
                if link['text'] and ('下一页' in link['text'] or 'next' in link['text'].lower()):
                    print(f"    ✅ 找到'下一页'文本链接: {link['text']}")
                    
                    if link['onclick']:
                        await page.evaluate(f"() => {{ {link['onclick']} }}")
                    elif link['href']:
                        await page.click(f'a[href="{link["href"]}"]')
                    else:
                        # 直接点击
                        await page.locator('a').nth(link['index']).click()
                    
                    await self.wait_for_page_load(page, next_page_num)
                    return True, next_page_num
            
            # 方法3：尝试点击当前页之后的第一个链接
            print(f"  方法3: 尝试点击当前页后的链接")
            if page_info['currentPage']:
                try:
                    current_page = int(page_info['currentPage'])
                    # 查找比当前页大的第一个链接
                    for link in page_info['links']:
                        if link['onclick']:
                            matches = re.findall(r'(?:goPage|soPage)\s*\(\s*[\'\"]?(\d+)[\'\"]?\s*\)', link['onclick'])
                            for match in matches:
                                page_num = int(match)
                                if page_num > current_page:
                                    print(f"    ✅ 找到页码 {page_num} 的链接")
                                    await page.evaluate(f"() => {{ {link['onclick']} }}")
                                    await self.wait_for_page_load(page, page_num)
                                    return True, page_num
                except:
                    pass
            
            # 方法4：如果只有数字链接，尝试点击最后一个链接
            print(f"  方法4: 尝试最后一个数字链接")
            if page_info['links']:
                last_link = page_info['links'][-1]
                if last_link['onclick']:
                    matches = re.findall(r'(?:goPage|soPage)\s*\(\s*[\'\"]?(\d+)[\'\"]?\s*\)', last_link['onclick'])
                    if matches:
                        last_page = int(matches[-1])
                        if last_page > current_page_num:
                            print(f"    ✅ 点击最后页码链接: {last_page}")
                            await page.evaluate(f"() => {{ {last_link['onclick']} }}")
                            await self.wait_for_page_load(page, last_page)
                            return True, last_page
            
            print("❌ 未找到有效的翻页方法")
            return False, current_page_num
            
        except Exception as e:
            print(f"❌ 翻页失败: {e}")
            return False, current_page_num
    
    async def wait_for_page_load(self, page, page_num):
        """等待页面加载完成"""
        print(f"⏳ 等待第{page_num}页加载...")
        
        # 等待网络空闲
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)
        except:
            print("  ⚠️ 等待networkidle超时")
        
        # 等待文书行重新出现
        try:
            await page.wait_for_selector('tr[id^="tr"]', timeout=10000)
        except:
            print("  ⚠️ 等待文书行超时")
        
        # 额外等待时间
        await self.random_delay(2, 3)
        
        # 检查文书数量
        rows_count = await page.locator('tr[id^="tr"]').count()
        print(f"✅ 第{page_num}页加载完成，有 {rows_count} 个文书")
        
        return True
    
    async def extract_case_data(self, page, current_page=1):
        """提取文书数据"""
        print(f"📊 提取第{current_page}页文书数据...")
        
        cases = []
        try:
            # 等待文书行出现
            await page.wait_for_selector('tr[id^="tr"]', timeout=15000)
            
            # 找到所有文书行
            case_rows = await page.locator('tr[id^="tr"]').all()
            print(f"找到 {len(case_rows)} 个文书行")
            
            for i, row in enumerate(case_rows):
                try:
                    # 获取行属性
                    row_id = await row.get_attribute('id') or f"tr_{current_page}_{i}"
                    onclick_attr = await row.get_attribute('onclick') or ""
                    
                    # 提取加密参数
                    detail_param = ""
                    if onclick_attr:
                        match = re.search(r"showone\('([^']+)'\)", onclick_attr)
                        if match:
                            detail_param = match.group(1)
                    
                    # 提取所有单元格
                    cells = await row.locator('td').all()
                    
                    if len(cells) >= 7:
                        # 分别获取每个单元格的文本
                        case_number = await cells[0].inner_text()
                        title = await cells[1].inner_text()
                        doc_type = await cells[2].inner_text()
                        
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
                            'row_index': i,
                            'page_number': current_page
                        }
                        
                        # 构建详情页URL
                        if detail_param:
                            base_url = "https://www.hshfy.sh.cn/shfy/web/flws_view.jsp"
                            case_data['detail_url'] = f"{base_url}?pa={detail_param}"
                        else:
                            case_data['detail_url'] = ""
                        
                        cases.append(case_data)
                        print(f"  已提取: {case_data['case_number']} (第{current_page}页)")
                        
                except Exception as e:
                    print(f"  第{current_page}页第{i}行提取失败: {str(e)[:100]}")
                    continue
            
            self.stats['total'] += len(case_rows)
            print(f"✅ 成功提取 {len(cases)} 个文书 (第{current_page}页)")
            return cases
            
        except Exception as e:
            print(f"❌ 第{current_page}页数据提取失败: {e}")
            await page.screenshot(path=self.output_dir / f'extract_error_page{current_page}.png')
            return cases
    
    async def crawl_detail_page(self, context, case_data, main_page):
        """抓取详情页内容"""
        print(f"📄 打开详情页: {case_data['case_number']} (第{case_data['page_number']}页)")
        
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
            print(f"✅ 详情页抓取成功 (第{case_data['page_number']}页)")
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
        print("上海市高级人民法院文书抓取（修复翻页检测版）")
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
            
            current_page = 1
            total_processed = 0
            
            while total_processed < self.max_cases:
                print(f"\n📄 处理第 {current_page} 页")
                print(f"当前累计处理: {total_processed}/{self.max_cases}")
                
                # 等待页面稳定
                if current_page > 1:
                    print("🔄 等待翻页后页面稳定...")
                    await self.random_delay(3, 4)
                
                # 提取当前页文书
                cases = await self.extract_case_data(page, current_page)
                
                if not cases:
                    print("⚠️ 未提取到文书数据")
                    break
                
                # 计算本页需要处理多少文书
                remaining = self.max_cases - total_processed
                cases_to_process = cases[:remaining]
                
                print(f"📊 本页处理 {len(cases_to_process)} 个文书 (剩余需求: {remaining})")
                
                # 抓取详情页
                for i, case in enumerate(cases_to_process):
                    print(f"\n[{total_processed + i + 1}/{self.max_cases}] {case['case_number']} (第{current_page}页)")
                    
                    detail_data = await self.crawl_detail_page(context, case, page)
                    if detail_data:
                        self.all_cases.append(detail_data)
                        total_processed += 1
                        print(f"  已保存到列表 (累计: {total_processed}/{self.max_cases})")
                    
                    # 每抓取2个就保存一次（避免丢失数据）
                    if (total_processed % 2 == 0) and total_processed > 0:
                        await self.save_data()
                    
                    # 延迟（避免请求过快）
                    if total_processed < self.max_cases:
                        delay = random.uniform(2, 4)
                        print(f"  等待 {delay:.1f}秒...")
                        await asyncio.sleep(delay)
                
                # 更新进度
                self.stats['pages'] = current_page
                
                # 检查是否还需要继续翻页
                if total_processed >= self.max_cases:
                    print(f"✅ 已达到目标数量 {self.max_cases}")
                    break
                
                # 尝试翻页
                print(f"\n🔄 尝试翻页到第{current_page + 1}页...")
                success, new_page = await self.check_and_go_next_page(page, current_page)
                
                if success:
                    current_page = new_page
                    print(f"✅ 成功翻页到第{current_page}页")
                else:
                    print("❌ 翻页失败，停止抓取")
                    break
            
            # 最终保存
            await self.save_data()
            
            # 统计信息
            self.stats['end'] = datetime.now().isoformat()
            start = datetime.fromisoformat(self.stats['start'])
            end = datetime.fromisoformat(self.stats['end'])
            duration = (end - start).total_seconds()
            
            print("\n" + "=" * 50)
            print("✅ 抓取完成！")
            print(f"   发现文书总数: {self.stats['total']}")
            print(f"   处理页数: {self.stats['pages']}")
            print(f"   成功抓取: {self.stats['success']}")
            print(f"   失败: {self.stats['failed']}")
            print(f"   目标数量: {self.max_cases}")
            print(f"   实际抓取: {len(self.all_cases)}")
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
        'max_cases': 30,    # 测试用30个，会自动翻页
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