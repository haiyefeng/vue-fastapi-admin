from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `api` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `path` VARCHAR(100) NOT NULL  COMMENT 'API路径',
    `method` VARCHAR(6) NOT NULL  COMMENT '请求方法',
    `summary` VARCHAR(500) NOT NULL  COMMENT '请求简介',
    `tags` VARCHAR(100) NOT NULL  COMMENT 'API标签',
    KEY `idx_api_created_78d19f` (`created_at`),
    KEY `idx_api_updated_643c8b` (`updated_at`),
    KEY `idx_api_path_9ed611` (`path`),
    KEY `idx_api_method_a46dfb` (`method`),
    KEY `idx_api_summary_400f73` (`summary`),
    KEY `idx_api_tags_04ae27` (`tags`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `auditlog` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` INT NOT NULL  COMMENT '用户ID',
    `username` VARCHAR(64) NOT NULL  COMMENT '用户名称' DEFAULT '',
    `module` VARCHAR(64) NOT NULL  COMMENT '功能模块' DEFAULT '',
    `summary` VARCHAR(128) NOT NULL  COMMENT '请求描述' DEFAULT '',
    `method` VARCHAR(10) NOT NULL  COMMENT '请求方法' DEFAULT '',
    `path` VARCHAR(255) NOT NULL  COMMENT '请求路径' DEFAULT '',
    `status` INT NOT NULL  COMMENT '状态码' DEFAULT -1,
    `response_time` INT NOT NULL  COMMENT '响应时间(单位ms)' DEFAULT 0,
    `request_args` JSON   COMMENT '请求参数',
    `response_body` JSON   COMMENT '返回数据',
    KEY `idx_auditlog_created_cc33d0` (`created_at`),
    KEY `idx_auditlog_updated_2f871f` (`updated_at`),
    KEY `idx_auditlog_user_id_4b93fa` (`user_id`),
    KEY `idx_auditlog_usernam_b187b3` (`username`),
    KEY `idx_auditlog_module_04058b` (`module`),
    KEY `idx_auditlog_summary_3e27da` (`summary`),
    KEY `idx_auditlog_method_4270a2` (`method`),
    KEY `idx_auditlog_path_b99502` (`path`),
    KEY `idx_auditlog_status_2a72d2` (`status`),
    KEY `idx_auditlog_respons_8caa87` (`response_time`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `dept` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(20) NOT NULL UNIQUE COMMENT '部门名称',
    `desc` VARCHAR(500)   COMMENT '备注',
    `is_deleted` BOOL NOT NULL  COMMENT '软删除标记' DEFAULT 0,
    `order` INT NOT NULL  COMMENT '排序' DEFAULT 0,
    `parent_id` INT NOT NULL  COMMENT '父部门ID' DEFAULT 0,
    KEY `idx_dept_created_4b11cf` (`created_at`),
    KEY `idx_dept_updated_0c0bd1` (`updated_at`),
    KEY `idx_dept_name_c2b9da` (`name`),
    KEY `idx_dept_is_dele_466228` (`is_deleted`),
    KEY `idx_dept_order_ddabe1` (`order`),
    KEY `idx_dept_parent__a71a57` (`parent_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `deptclosure` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `ancestor` INT NOT NULL  COMMENT '父代',
    `descendant` INT NOT NULL  COMMENT '子代',
    `level` INT NOT NULL  COMMENT '深度' DEFAULT 0,
    KEY `idx_deptclosure_created_96f6ef` (`created_at`),
    KEY `idx_deptclosure_updated_41fc08` (`updated_at`),
    KEY `idx_deptclosure_ancesto_fbc4ce` (`ancestor`),
    KEY `idx_deptclosure_descend_2ae8b1` (`descendant`),
    KEY `idx_deptclosure_level_ae16b2` (`level`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `menu` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(20) NOT NULL  COMMENT '菜单名称',
    `remark` JSON   COMMENT '保留字段',
    `menu_type` VARCHAR(7)   COMMENT '菜单类型',
    `icon` VARCHAR(100)   COMMENT '菜单图标',
    `path` VARCHAR(100) NOT NULL  COMMENT '菜单路径',
    `order` INT NOT NULL  COMMENT '排序' DEFAULT 0,
    `parent_id` INT NOT NULL  COMMENT '父菜单ID' DEFAULT 0,
    `is_hidden` BOOL NOT NULL  COMMENT '是否隐藏' DEFAULT 0,
    `component` VARCHAR(100) NOT NULL  COMMENT '组件',
    `keepalive` BOOL NOT NULL  COMMENT '存活' DEFAULT 1,
    `redirect` VARCHAR(100)   COMMENT '重定向',
    KEY `idx_menu_created_b6922b` (`created_at`),
    KEY `idx_menu_updated_e6b0a1` (`updated_at`),
    KEY `idx_menu_name_b9b853` (`name`),
    KEY `idx_menu_path_bf95b2` (`path`),
    KEY `idx_menu_order_606068` (`order`),
    KEY `idx_menu_parent__bebd15` (`parent_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `pet_cat` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `code` VARCHAR(32) NOT NULL UNIQUE COMMENT '猫的标识，如 orange',
    `name` VARCHAR(32) NOT NULL  COMMENT '猫的名字，如 橘猫',
    `persona` VARCHAR(32) NOT NULL  COMMENT '性格，如 元气/毒舌/温柔',
    `order` INT NOT NULL  COMMENT '展示顺序' DEFAULT 0,
    `unlock` JSON NOT NULL  COMMENT '解锁条件，[{field, op, value}] 与关系；空数组表示初始猫',
    `is_active` BOOL NOT NULL  COMMENT '是否启用' DEFAULT 1,
    KEY `idx_pet_cat_created_c92c62` (`created_at`),
    KEY `idx_pet_cat_updated_4cddc2` (`updated_at`),
    KEY `idx_pet_cat_code_f27f26` (`code`)
) CHARACTER SET utf8mb4 COMMENT='猫的定义，全用户共享的只读配置';
CREATE TABLE IF NOT EXISTS `pet_line` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `code` VARCHAR(64) NOT NULL UNIQUE COMMENT '台词标识，如 t_overdue',
    `cat_code` VARCHAR(32)   COMMENT '专属于哪只猫；为空表示通用兜底',
    `page` VARCHAR(32) NOT NULL  COMMENT '生效页面：today/quadrant/habit/pet 等',
    `priority` INT NOT NULL  COMMENT '优先级，同页面取最高的一条' DEFAULT 0,
    `conditions` JSON NOT NULL  COMMENT '页面上下文触发条件，[{field, op, value}]',
    `texts` JSON NOT NULL  COMMENT '文案变体数组，客户端按日期种子轮换',
    `unlock` JSON NOT NULL  COMMENT '解锁条件；未达成时这句话不会出现',
    KEY `idx_pet_line_created_ddeb27` (`created_at`),
    KEY `idx_pet_line_updated_621f5a` (`updated_at`),
    KEY `idx_pet_line_code_76c4a5` (`code`),
    KEY `idx_pet_line_cat_cod_c5ae30` (`cat_code`),
    KEY `idx_pet_line_page_a89cbd` (`page`)
) CHARACTER SET utf8mb4 COMMENT='猫的台词，全用户共享的只读配置';
CREATE TABLE IF NOT EXISTS `role` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(20) NOT NULL UNIQUE COMMENT '角色名称',
    `desc` VARCHAR(500)   COMMENT '角色描述',
    KEY `idx_role_created_7f5f71` (`created_at`),
    KEY `idx_role_updated_5dd337` (`updated_at`),
    KEY `idx_role_name_e5618b` (`name`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `username` VARCHAR(20) NOT NULL UNIQUE COMMENT '用户名称',
    `alias` VARCHAR(30)   COMMENT '姓名',
    `email` VARCHAR(255) NOT NULL UNIQUE COMMENT '邮箱',
    `phone` VARCHAR(20)   COMMENT '电话',
    `password` VARCHAR(128)   COMMENT '密码',
    `is_active` BOOL NOT NULL  COMMENT '是否激活' DEFAULT 1,
    `is_superuser` BOOL NOT NULL  COMMENT '是否为超级管理员' DEFAULT 0,
    `last_login` DATETIME(6)   COMMENT '最后登录时间',
    `dept_id` INT   COMMENT '部门ID',
    `openid` VARCHAR(64)  UNIQUE COMMENT '微信openid',
    KEY `idx_user_created_b19d59` (`created_at`),
    KEY `idx_user_updated_dfdb43` (`updated_at`),
    KEY `idx_user_usernam_9987ab` (`username`),
    KEY `idx_user_alias_6f9868` (`alias`),
    KEY `idx_user_email_1b4f1c` (`email`),
    KEY `idx_user_phone_4e3ecc` (`phone`),
    KEY `idx_user_is_acti_83722a` (`is_active`),
    KEY `idx_user_is_supe_b8a218` (`is_superuser`),
    KEY `idx_user_last_lo_af118a` (`last_login`),
    KEY `idx_user_dept_id_d4490b` (`dept_id`),
    KEY `idx_user_openid_86255c` (`openid`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `categories` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '分类ID',
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(100) NOT NULL  COMMENT '分类名称',
    `icon` VARCHAR(50)   COMMENT '图标 (FontAwesome class 或 emoji)',
    `type` VARCHAR(17) NOT NULL  COMMENT '分类类型' DEFAULT 'user_custom',
    `display_order` INT NOT NULL  COMMENT '显示顺序' DEFAULT 0,
    `is_archived` BOOL NOT NULL  COMMENT '是否归档' DEFAULT 0,
    `user_id` BIGINT COMMENT '所属用户 (系统预设可为NULL)',
    UNIQUE KEY `uid_categories_user_id_7f9e4d` (`user_id`, `name`),
    CONSTRAINT `fk_categori_user_22e2b8e4` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_categories_created_814054` (`created_at`),
    KEY `idx_categories_updated_c650c2` (`updated_at`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `goal` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(100) NOT NULL  COMMENT '计划/目标名称',
    `description` LONGTEXT   COMMENT '描述',
    `target_date` DATE   COMMENT '目标完成日期',
    `is_archived` BOOL NOT NULL  COMMENT '归档后从主列表隐藏，历史保留' DEFAULT 0,
    `category_id` INT COMMENT '归属分类',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_goal_categori_402da9de` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_goal_user_dbf78696` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_goal_created_015609` (`created_at`),
    KEY `idx_goal_updated_c31eba` (`updated_at`)
) CHARACTER SET utf8mb4 COMMENT='计划/目标模型';
CREATE TABLE IF NOT EXISTS `habit` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(100) NOT NULL  COMMENT '习惯名称',
    `icon` VARCHAR(50)   COMMENT '图标，emoji 或简短文本',
    `color_hex` VARCHAR(7)   COMMENT '颜色代码',
    `frequency_type` VARCHAR(13) NOT NULL  COMMENT '频率类型',
    `frequency_config` JSON   COMMENT 'weekly_days: {\"days\": [1,3,5]}（ISO 星期一=1）；weekly_count: {\"count\": 3}；interval_days: {\"interval\": 2}；daily 不需要配置',
    `default_quadrant` VARCHAR(24) NOT NULL  COMMENT '生成待办的默认象限' DEFAULT 'important_not_urgent',
    `goal_desc` VARCHAR(100)   COMMENT '目标描述，如「30分钟」，仅展示',
    `reminder_time` TIME(6)   COMMENT '每日提醒时间，写入生成待办的 reminder_at',
    `is_paused` BOOL NOT NULL  COMMENT '暂停后停止生成新待办，历史保留' DEFAULT 0,
    `is_archived` BOOL NOT NULL  COMMENT '归档后从主列表隐藏，历史保留' DEFAULT 0,
    `goal_id` BIGINT COMMENT '关联的计划，为空表示未关联',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_habit_goal_c25b9036` FOREIGN KEY (`goal_id`) REFERENCES `goal` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_habit_user_1b77138a` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_habit_created_930994` (`created_at`),
    KEY `idx_habit_updated_f15603` (`updated_at`)
) CHARACTER SET utf8mb4 COMMENT='习惯模型：按频率规则惰性生成带 habit_id 的 TodoItem，勾掉即打卡';
CREATE TABLE IF NOT EXISTS `pet_profile` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `active_cat_code` VARCHAR(32) NOT NULL  COMMENT '当前陪伴的猫' DEFAULT 'orange',
    `pet_name` VARCHAR(20)   COMMENT '用户给猫起的名字',
    `stats` JSON NOT NULL  COMMENT '分维度累计计数，键为维度名、值为累计次数',
    `owned_cats` JSON NOT NULL  COMMENT '已解锁的猫，元素含 cat_id 与解锁时间戳 at',
    `visit_streak` INT NOT NULL  COMMENT '连续来访天数' DEFAULT 1,
    `last_seen_at` DATETIME(6)   COMMENT '最近一次来访时间',
    `user_id` BIGINT NOT NULL UNIQUE COMMENT '所属用户',
    CONSTRAINT `fk_pet_prof_user_da568df0` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_pet_profile_created_94f54d` (`created_at`),
    KEY `idx_pet_profile_updated_3befe3` (`updated_at`)
) CHARACTER SET utf8mb4 COMMENT='养成猫的用户状态，一人一行。';
CREATE TABLE IF NOT EXISTS `projects` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '项目/清单ID',
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(100) NOT NULL  COMMENT '项目/清单名称',
    `type` VARCHAR(7) NOT NULL  COMMENT '类型 (项目或清单)' DEFAULT 'project',
    `color_hex` VARCHAR(7)   COMMENT '颜色代码 (如 #RRGGBB)',
    `is_archived` BOOL NOT NULL  COMMENT '是否归档' DEFAULT 0,
    `category_id` INT COMMENT '所属分类',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_projects_categori_98ff598e` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_projects_user_65c1f1c1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_projects_created_f282c7` (`created_at`),
    KEY `idx_projects_updated_514ed4` (`updated_at`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `review` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `period_type` VARCHAR(7) NOT NULL  COMMENT '回顾周期类型',
    `period_start` DATE NOT NULL  COMMENT '周期开始日期',
    `period_end` DATE NOT NULL  COMMENT '周期结束日期',
    `answers` JSON NOT NULL  COMMENT '七步提问法答案，key 为 step1~step7',
    `status` VARCHAR(9) NOT NULL  COMMENT '草稿/已完成' DEFAULT 'draft',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    UNIQUE KEY `uid_review_user_id_ec7dad` (`user_id`, `period_type`, `period_start`),
    CONSTRAINT `fk_review_user_c0877390` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_review_created_3fd92f` (`created_at`),
    KEY `idx_review_updated_476781` (`updated_at`)
) CHARACTER SET utf8mb4 COMMENT='周期回顾模型：数据回顾区实时聚合计算不落库，这里只存七步反思答案与状态';
CREATE TABLE IF NOT EXISTS `todo_item` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `title` VARCHAR(200) NOT NULL  COMMENT '待办事项标题',
    `quadrant_type` VARCHAR(24) NOT NULL  COMMENT '象限类型',
    `due_date` DATETIME(6)   COMMENT '截止时间',
    `notes` LONGTEXT   COMMENT '备注信息',
    `reminder_at` DATETIME(6)   COMMENT '提醒时间，仅存储与展示，不做推送',
    `generated_date` DATE   COMMENT '习惯待办的所属日期，仅习惯生成的待办有值；用于幂等判断，与用户可改的 due_date 语义分离',
    `is_completed` BOOL NOT NULL  COMMENT '是否已完成' DEFAULT 0,
    `completed_at` DATETIME(6)   COMMENT '完成时间',
    `user_id` INT NOT NULL  COMMENT '用户ID',
    `goal_id` BIGINT COMMENT '关联的计划，为空表示未关联',
    `habit_id` BIGINT COMMENT '所属习惯，非空表示是习惯生成的打卡待办',
    `project_id` INT COMMENT '所属项目，为空则属于收件箱',
    CONSTRAINT `fk_todo_ite_goal_dd895e5e` FOREIGN KEY (`goal_id`) REFERENCES `goal` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_todo_ite_habit_828dc61f` FOREIGN KEY (`habit_id`) REFERENCES `habit` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_todo_ite_projects_814f2da2` FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`) ON DELETE SET NULL,
    KEY `idx_todo_item_created_eeac08` (`created_at`),
    KEY `idx_todo_item_updated_6bce99` (`updated_at`),
    KEY `idx_todo_item_quadran_60e405` (`quadrant_type`),
    KEY `idx_todo_item_is_comp_c86728` (`is_completed`),
    KEY `idx_todo_item_user_id_c0de6a` (`user_id`)
) CHARACTER SET utf8mb4 COMMENT='待办事项模型';
CREATE TABLE IF NOT EXISTS `sub_task` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `title` VARCHAR(200) NOT NULL  COMMENT '子任务标题',
    `is_completed` BOOL NOT NULL  COMMENT '是否已完成' DEFAULT 0,
    `order` INT NOT NULL  COMMENT '显示顺序，创建时按序递增赋值' DEFAULT 0,
    `todo_item_id` BIGINT NOT NULL COMMENT '所属待办事项',
    CONSTRAINT `fk_sub_task_todo_ite_d9717cd5` FOREIGN KEY (`todo_item_id`) REFERENCES `todo_item` (`id`) ON DELETE CASCADE,
    KEY `idx_sub_task_created_d31d98` (`created_at`),
    KEY `idx_sub_task_updated_d06034` (`updated_at`)
) CHARACTER SET utf8mb4 COMMENT='子任务模型';
CREATE TABLE IF NOT EXISTS `time_block` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `start_time` DATETIME(6) NOT NULL  COMMENT '开始时间',
    `end_time` DATETIME(6) NOT NULL  COMMENT '结束时间',
    `todo_item_id` BIGINT NOT NULL COMMENT '所属待办事项',
    `user_id` BIGINT NOT NULL COMMENT '所属用户，冗余存储，按用户+日期范围直查',
    CONSTRAINT `fk_time_blo_todo_ite_96e7736a` FOREIGN KEY (`todo_item_id`) REFERENCES `todo_item` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_time_blo_user_66cd8246` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_time_block_created_00727e` (`created_at`),
    KEY `idx_time_block_updated_0edfe7` (`updated_at`)
) CHARACTER SET utf8mb4 COMMENT='时间块模型：一个待办事项可以有多个时间块，用于日历排程';
CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `role_api` (
    `role_id` BIGINT NOT NULL,
    `api_id` BIGINT NOT NULL,
    FOREIGN KEY (`role_id`) REFERENCES `role` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`api_id`) REFERENCES `api` (`id`) ON DELETE CASCADE,
    UNIQUE KEY `uidx_role_api_role_id_ba4286` (`role_id`, `api_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `role_menu` (
    `role_id` BIGINT NOT NULL,
    `menu_id` BIGINT NOT NULL,
    FOREIGN KEY (`role_id`) REFERENCES `role` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`menu_id`) REFERENCES `menu` (`id`) ON DELETE CASCADE,
    UNIQUE KEY `uidx_role_menu_role_id_90801c` (`role_id`, `menu_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `user_role` (
    `user_id` BIGINT NOT NULL,
    `role_id` BIGINT NOT NULL,
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`role_id`) REFERENCES `role` (`id`) ON DELETE CASCADE,
    UNIQUE KEY `uidx_user_role_user_id_d0bad3` (`user_id`, `role_id`)
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
