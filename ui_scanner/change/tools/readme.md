工具文件                                                       
                                                                 
  tools/                                                         
  ├── config.yaml          # 配置文件（白名单、自定义规则）      
  ├── id_rules.py          # 命名规则（30+                     
  组件缩写映射、合规检查、建议生成）
  ├── utils.py             #
  公共工具（文件遍历、XML解析、颜色输出）
  ├── scanner.py           # 扫描工具（扫描布局、生成CSV报告）
  ├── fixer.py             # 修复工具（全项目同步替换）
  └── requirements.txt     # 依赖（PyYAML）
                                                                 
  使用方法
                                                                 
  # 1. 扫描项目，生成报告                                      
  python3 tools/scanner.py /path/to/your/android/project --output
   id_report.csv

  # 2. 查看报告，手动调整建议 ID（编辑 CSV 中的 suggested_id 列）

  # 3. 预览模式修复（不实际修改）
  python3 tools/fixer.py /path/to/your/android/project --report
  id_report.csv --dry-run

  # 4. 确认后执行修复
  python3 tools/fixer.py /path/to/your/android/project --report
  id_report.csv --execute                                        
   
  关键特性                                                       
                                                               
  - 30+ 组件缩写映射 — 覆盖常见 Android 组件
  - 智能拆分 — 自动识别页面名前缀（含下划线的 item_product 等）
  - 全项目同步 —
  XML、R.id、ViewBinding、Navigation、Menu、values/ids.xml
  - 安全机制 — 默认 dry-run、自动 .bak 备份、冲突检测
  - CSV 报告 — 可手动调整后再执行