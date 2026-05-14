# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 学生公寓管理系统 — 数据库系统及应用 课程设计

## 项目概况

- **选题**：学生公寓管理系统（PPT 选题5）
- **架构**：B/S，Flask + MySQL
- **课程**：数据库系统及应用，2026 春季学期
- **平台**：MySQL 8.0，Python 3.x

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Jinja2 模板 + HTML + CSS |
| 后端 | Flask 3.x，Flask-SQLAlchemy ORM |
| 数据库 | MySQL 8.0，PyMySQL 驱动，utf8mb4 字符集 |
| 认证 | Session-based，login_required + role_required 双层装饰器；werkzeug scrypt 哈希 |
| Excel | openpyxl 3.1.5 |

## 项目结构

```
lab2/
├── app.py              # Flask 主应用（65 路由 + 3 CLI）
├── models.py           # 12 数据模型
├── config.py           # 配置（数据库 + 上传）
├── db_advanced.sql     # 存储过程/函数/触发器 DDL
├── requirements.txt    # Python 依赖
├── 需求分析.md          # 完整需求分析 + ER 图
├── static/
│   ├── css/style.css
│   └── uploads/        # 报修现场照片/视频
└── templates/          # 32 模板
    ├── _pagination.html # 通用分页宏
    ├── base.html       # 侧边栏布局（按角色动态菜单）
    ├── login.html / index.html
    ├── buildings.html / building_form.html
    ├── rooms.html / room_form.html
    ├── students.html / student_form.html / student_import.html
    ├── accommodations.html / accommodation_form.html
    ├── checkout_requests.html  # 退宿审核列表
    ├── transfer_requests.html  # 调换审核列表
    ├── operation_logs.html     # 操作日志列表
    ├── repairs.html / repair_form.html
    ├── visitors.html / visitor_form.html
    ├── fees.html / fee_form.html
    ├── announcements.html / announcement_form.html
    ├── users.html / user_form.html
    ├── my_accommodation.html / my_repairs.html
    ├── my_fees.html / my_visitors.html / my_profile.html
    ├── change_password.html
```

## 数据库模型（12 表）

| 模型 | 表名 | 关键字段 |
|---|---|---|
| Building | building | name(UK), floors, address, manager |
| Room | room | room_number, building_id(FK,级联), capacity, occupied, room_type, price |
| Student | student | sno(UK), name, gender, birth, phone, major, class_name, user_id(FK,UK,可空) |
| Accommodation | accommodation | student_id(FK), room_id(FK), check_in/out_date, status |
| Repair | repair | student_id(FK), room_id(FK), description, image, status, report/fix_date |
| Visitor | visitor | student_id(FK), visitor_name, id_card, reason, visit/leave_date |
| Fee | fee | student_id(FK), room_id(FK), fee_type, amount, status, due/pay_date |
| CheckoutRequest | checkout_request | student_id(FK), accommodation_id(FK), status(pending/approved/rejected), request_date, reviewed_by(FK), review_date |
| TransferRequest | transfer_request | student_id(FK), from_accommodation_id(FK), to_room_id(FK), status(pending/approved/rejected), request_date, reviewed_by(FK), review_date |
| User | user | username(UK), password(256), role, building_id(FK,可空) |
| Announcement | announcement | title, content, created_at, user_id(FK) |
| OperationLog | operation_log | user_id(FK), action, target_type, target_id, ip_address, created_at |

**关系**：Building 1:N Room（级联），Room 1:N Accommodation/Repair/Fee/TransferRequest(to_room)，Student 1:N Accommodation/Repair/Visitor/Fee/CheckoutRequest/TransferRequest，Accommodation 1:N CheckoutRequest/TransferRequest，User 1:N Announcement/CheckoutRequest(reviewed_by)/TransferRequest(reviewed_by)/OperationLog，User 1:1 Student（可选），User N:1 Building（仅 dorm_manager）

## 角色权限（3 角色）

| 角色 | 能访问 |
|---|---|
| **student** | /、/my/*、/announcements、/change-password、/uploads/* |
| **dorm_manager** | student 全部 + 入住/退宿审核/宿舍调换、报修处理、访客管理、费用管理、公告管理。**仅限管辖宿舍楼**（User.building_id 限定） |
| **admin** | 全部功能：dorm_manager 全部 + 宿舍楼/房间/学生 CRUD + 用户管理 + 批量导入 + 操作日志 |

### 宿管员管辖范围（building scope）

`get_manager_building_id()` 辅助函数：dorm_manager 返回 `User.building_id`，admin 返回 `None`（不限）。影响的路由：
- 入住/退宿审核/宿舍调换/报修/费用列表 — JOIN Room 过滤 `building_id`
- 访客列表 — JOIN Student → Accommodation → Room 过滤
- 新增表单 — 房间/学生下拉仅显示管辖楼数据
- 首页仪表盘 — 统计/入住率/最近报修仅限管辖楼
- 批量费用 — 校验 building_id 仅限管辖楼

## 关键 CLI 命令

```bash
# 重置数据库（删表重建 + 种子数据）
python -c "from app import app; from app import reset_db; reset_db()"

# 导入存储过程/函数/触发器（首次或 db_advanced.sql 变更后）
python -c "from app import app; from app import init_advanced; init_advanced()"

# 启动开发服务器
python app.py
```

## 数据库高级特性

| 类型 | 名称 | 功能 |
|---|---|---|
| **事务** | `sp_checkin` | 入住原子操作（检查重复 → 锁行 → 容量校验 → INSERT + UPDATE） |
| **事务** | `sp_room_transfer` | 调换原子操作（锁两间房 → 容量校验 → UPDATE accommodation + 两间房 occupied） |
| **触发器** | `trg_repair_complete` | 报修"已完成"时自动 set fix_date |
| **触发器** | `trg_accommodation_checkout` | 退宿时自动 room.occupied - 1 |
| **存储过程** | `sp_generate_fees` | 为整栋楼在住学生批量生成费用 |
| **函数** | `fn_occupancy_rate(building_id)` | 返回宿舍楼入住率百分比 |

SQL 源文件：[db_advanced.sql](db_advanced.sql)

## 报修文件上传

- 保存路径：`static/uploads/`，文件名 UUID 重命名
- 白名单：png/jpg/jpeg/gif/bmp/webp + mp4/webm/avi/mov
- 列表页区分图片（缩略图点击放大）和视频（内嵌播放器）
- `repair_form.html` 和 `my_repairs.html` 均含 `accept="image/*,video/*"`

## 搜索筛选与分页

所有 10 个管理列表页均支持搜索、分页和 Excel 导出：

| 页面 | 搜索字段 | 额外筛选器 |
|---|---|---|
| 宿舍楼管理 | 名称/地址/管理员 | — |
| 房间管理 | 房间号 | 宿舍楼下拉 |
| 学生管理 | 学号/姓名/专业/班级/手机 | — |
| 入住管理 | 学生姓名 | 状态（入住/已退宿） |
| 报修管理 | 描述/学生姓名 | 状态（待处理/处理中/已完成） |
| 费用管理 | 费用类型/学生姓名 | 状态（未缴/已缴） |
| 访客管理 | 访客姓名/身份证号/受访学生 | — |
| 用户管理 | 用户名 | — |
| 公告管理 | 标题/内容 | — |

分页默认 15 条/页，分页栏仅在超过 1 页时显示。路由通过 `page`、`search`、`status` 查询参数驱动。分页复用 [templates/_pagination.html](templates/_pagination.html) 宏，接受 `search` 和 `extra_params` 保留当前筛选状态。

## 批量导入学生

`/students/import` — admin 专属，上传 Excel（.xlsx/.xls）批量导入。openpyxl 解析。

- 自动映射中文表头：学号、姓名、性别、出生日期、手机、专业、班级
- 必填列：学号 + 姓名
- 校验：文件内重复学号 + 数据库已存在学号
- 日期解析：支持 Excel 日期格式、`YYYY-MM-DD`、`YYYY/MM/DD`、`YYYY.MM.DD`
- 逐行错误收集，失败行不影响成功行

## 密码安全

- werkzeug `generate_password_hash`（scrypt）哈希存储，`check_password_hash` 验证
- `user.password` 列 `String(256)`
- 涉及点：登录、新增用户、编辑用户、修改密码、种子数据（4 个默认用户均哈希）

## 其他功能

- **修改密码**：`/change-password`，所有角色可访问，验证原密码后修改
- **批量费用**：`/fees/batch` 调用 `sp_generate_fees` 为整栋楼在住学生生成费用
- **退宿流程**：学生端"我的住宿"申请 → 创建 `CheckoutRequest`(pending) → 宿管员"退宿审核"审批 → 批准后自动更新 accommodation + `trg_accommodation_checkout` 触发器扣减 room.occupied；拒绝则申请关闭。学生不可重复申请
- **宿舍调换**：学生端"我的住宿"选择同楼空房间申请调换 → 创建 `TransferRequest`(pending) → 宿管员"宿舍调换"审批 → 批准后调用 `sp_room_transfer` 原子迁移住宿记录并更新两间房 occupied；拒绝则申请关闭。学生不可重复申请
- 首页按角色分流：学生端展示个人住宿/室友/报修/费用；管理员端展示全局统计 + 各楼入住率（调用 `fn_occupancy_rate`）
- **操作日志**：自动记录所有敏感操作（增删改），含操作人、时间、IP。`log_operation()` 辅助函数独立事务写入，admin 专有页面查看/搜索
- **Excel 导出**：所有 10 个列表页均支持"导出Excel"按钮，导出当前搜索/筛选条件下的全部数据为 .xlsx 文件。`export_excel()` 辅助函数使用 openpyxl 生成带粗体表头、自适应列宽的工作簿。导出保留当前搜索和状态筛选参数

## 课程要求完成度

### 已完成
- [x] B/S 架构 + MySQL + Python
- [x] 9 实体 ER 图（见 需求分析.md）
- [x] 三角色权限系统 + 宿管员管辖范围隔离
- [x] 基本 CRUD（6 实体 + 公告 + 用户管理）
- [x] 图片/视频文件管理（报修现场照片）
- [x] 存储过程 + 函数 + 触发器 + 事务
- [x] 全列表搜索/筛选 + 分页
- [x] 密码修改 + scrypt 哈希加密
- [x] 批量导入学生（Excel）
- [x] 退宿审批流程（申请 → 审核 → 批准/拒绝 + 触发器联动）
- [x] 宿舍调换流程（申请 → 审核 → 批准后 sp_room_transfer 原子迁移 + 两间房 occupied 联动）
- [x] 操作日志（审计追踪，admin 可查看/搜索）
- [x] Excel 导出（10 列表页，保留搜索/筛选条件）
- [x] 需求分析文档（含 ER 图和业务规则）

### 待完成（文档类）
1. **DDL 建表语句** — 从 ORM 反向导出
2. **3NF 模式分解说明**
3. **课程设计报告** — 整合需求分析 + ER 图 + 运行截图 + 源码

### 关键日期
- **6月1日**：提交选题说明 + 需求分析 + ER 图
- **期末考前**：课堂展示（3分钟）+ 提交最终报告

## 默认账号

| 用户名 | 密码 | 角色 | 管辖楼 |
|---|---|---|---|
| admin | admin123 | 系统管理员 | — |
| manager | manager123 | 宿管员 | 学生公寓1号楼 |
| manager2 | manager123 | 宿管员 | 学生公寓2号楼 |
| student1 | 123456 | 学生（张三，1号楼101） | — |
