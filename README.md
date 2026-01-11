某市高级人民法院文书抓取工具
================================

项目简介
---------
本工具用于抓取某市高级人民法院网站（https://www.XXXXX.XX.cn）的公开裁判文书数据。
包含两个主要脚本：
- court_fixed_async.py：主抓取程序，实现异步数据抓取
- debug_page_structure.py：页面诊断工具，用于分析网站结构

主要功能
---------
1. 主抓取程序 (court_fixed_async.py)
   - 自动访问某市高级人民法院文书查询页面
   - 模拟表单提交获取文书列表
   - 提取文书基本信息（案号、标题、文书类型、案由、审判部门、审级、结案日期等）
   - 打开详情页获取完整文书内容
   - 支持JSON和CSV格式数据导出

2. 诊断工具 (debug_page_structure.py)
   - 分析网站页面实际HTML结构
   - 识别所有表格元素和数据行
   - 检测可能的文书链接
   - 生成详细的诊断报告和截图

网站反爬虫技术及破解方法
--------------------------
1. 动态表单提交 ⚡
   【反爬技术】：搜索表单通过JavaScript动态处理，无法直接通过URL访问结果页
   【破解方法】：使用Playwright模拟真实浏览器提交表单
   【代码示例】：
   await page.evaluate("document.querySelector('form').submit()")
   await page.wait_for_timeout(5000)

2. 加密URL参数 🔐
   【反爬技术】：详情页URL参数采用加密处理，无法直接构造
   【破解方法】：从onclick属性中提取加密参数
   【代码示例】：
   onclick_attr = await row.get_attribute('onclick') or ""
   match = re.search(r"showone\('([^']+)'\)", onclick_attr)

3. 内容动态加载 📄
   【反爬技术】：文书列表数据通过AJAX动态加载，传统requests库无法获取
   【破解方法】：使用Playwright等待网络空闲状态和特定元素
   【代码示例】：
   await page.wait_for_load_state('networkidle', timeout=15000)
   await page.wait_for_selector('tr[id^="tr"]', timeout=10000)

4. 点击事件监听 🖱️
   【反爬技术】：必须通过点击行触发详情页打开，直接访问URL可能失败
   【破解方法】：监听新页面打开事件
   【代码示例】：
   async with context.expect_page() as new_page_info:
       await main_page.click(row_selector)
       detail_page = await new_page_info.value

5. 页面结构复杂 🏗️
   【反爬技术】：多层嵌套表格结构，无规律的行ID生成
   【破解方法】：使用多种选择器策略和多级容错
   【代码示例】：
   通过ID选择
   row_selector = f'tr[id="{case_data["row_id"]}"]'
   通过案号文本选择（备选）
   text_selector = f'text="{case_number_text}"'

6. 请求频率限制 ⏱️
   【反爬技术】：对快速连续请求进行限制
   【破解方法】：添加随机延迟，控制请求节奏
   【代码示例】：
   await asyncio.sleep(random.uniform(min_sec, max_sec))
   delay = random.uniform(2, 4)

技术亮点
---------
1. 异步架构优化：使用asyncio和playwright实现异步操作，提高效率
2. 错误处理与容错：多层级异常捕获，失败重试机制
3. 数据完整性保障：增量式保存，详细日志记录
4. 调试支持：自动保存错误截图和页面源码

使用说明
---------
【环境要求】：
Python 3.8+
playwright>=1.40.0
pandas>=2.0.0

【安装步骤】：
1. 安装Python依赖：pip install playwright pandas
2. 安装Playwright浏览器：playwright install chromium
3. 运行诊断工具（首次使用推荐）：python debug_page_structure.py
4. 运行主抓取程序：python sh_court_fixed_async.py

【配置说明】：
主程序配置参数：
config = {
    'start_url': 'https://www.XXXXX.XX.cn/XXXX/gweb2017/flws_list_new.jsp?ajlb=aYWpsYj3QzMrCz',
    'headless': False,  # 调试时建议设为False
    'max_cases': 9,     # 测试数量
    'output_dir': '抓取结果'
}

注意事项
---------
【法律合规性】：
- 仅抓取公开的裁判文书信息
- 尊重网站的使用条款和robots.txt
- 控制请求频率，避免对服务器造成负担

【技术限制】：
- 网站结构变化可能导致脚本失效
- 需要定期更新选择器和解析逻辑
- 加密算法变化可能需要重新分析

【数据使用】：
- 抓取的数据仅用于合法合规的研究和分析
- 遵守数据隐私和相关法律法规
- 不得用于商业用途或不当目的

故障排除
---------
1. 无法找到文书数据
   - 运行debug_page_structure.py分析页面结构
   - 检查网站是否已更新页面布局
   - 查看生成的HTML源码和截图

2. 详情页无法打开
   - 检查加密参数提取是否正确
   - 确认点击事件监听是否生效
   - 尝试直接访问详情URL

3. 数据提取不完整
   - 调整等待时间和选择器
   - 检查网络连接状态
   - 查看错误日志和截图

文件结构
---------
项目目录/
├── court_fixed_async.py    # 主抓取程序
├── debug_page_structure.py    # 页面诊断工具
├── README.md                  # 说明文档
├── 抓取结果/                  # 数据输出目录
│   ├── cases_20250111_143022.json
│   ├── cases_20250111_143022.csv
│   └── 简版_cases_20250111_143022.csv
└── 页面诊断/                  # 诊断输出目录
    ├── full_page.png
    ├── page_source.html
    ├── table_*.png
    └── analysis.json

更新日志
---------
v1.0.0 (2025-01-11)
- 初始版本发布
- 实现基本文书抓取功能
- 添加页面诊断工具
- 完善错误处理和日志记录

免责声明
---------
本工具仅用于技术研究和学习目的。使用者应遵守相关法律法规和网站使用条款，
对使用本工具产生的任何后果自行承担责任。开发者不对因使用本工具造成的任何
直接或间接损失负责。

================================
