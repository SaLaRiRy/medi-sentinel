-- MediSentinel 演示数据 v1（TICKET-026）—— DML-only，固定编号 + upsert，可重复执行。
--
-- 前置：alembic upgrade head（本文件不建表、不改 schema、不新增迁移）。
-- 加载：mysql -uroot -p medi_sentinel < server/seeds/demo_v1.sql
--
-- 设计要点
--   * 只用 `INSERT ... ON DUPLICATE KEY UPDATE`（MySQL 8 upsert），不 DELETE 任何行，
--     因此用户自建数据不受影响；重复执行两次结果一致。
--   * 所有编号固定落在 9001+ 段。低于该段的是既有数据（1 号患者、1–3 号 AI 会话、
--     1–3 号知识文件），本文件不与之冲突。
--   * 口令为明文：`core/security.py` 的 `verify_password` 直接做字符串相等比较
--     （FUNCTIONAL_SPEC 5.8），故写入的值就是口令本身——能直接通过登录校验。
--     演示账号：patient1 / doctor1 / admin1，口令均为 `123456`。
--   * 向量数据（Chroma）不在本文件：知识库分块与向量化由 013 的
--     `scripts/init_knowledge.py` 负责，本文件只写关系库表。
--   * 已知限制：`t_consult_session.user_id` 与账号表一样不建外键，这些引用由业务层
--     保证；若某个 9001+ 用户名已被既有数据占用，MySQL 会按唯一键更新那一行而不是
--     新建 9001 号，此时以既有行为准。

-- ---------------------------------------------------------------------------
-- 科室主数据（t_department）—— 医生与预约引用其编号
-- ---------------------------------------------------------------------------
INSERT INTO t_department (id, name, description, sort_order, status, create_time, update_time)
VALUES
  (9001, '内科', '内科常见病、慢性病的诊断与治疗', 1, 1, '2026-10-01 09:00:00', '2026-10-01 09:00:00'),
  (9002, '外科', '外科创伤、需手术疾病的诊疗', 2, 1, '2026-10-01 09:00:00', '2026-10-01 09:00:00'),
  (9003, '儿科', '0-14 岁儿童常见病诊疗', 3, 1, '2026-10-01 09:00:00', '2026-10-01 09:00:00'),
  (9004, '皮肤科', '皮肤、毛发与指甲相关疾病', 4, 1, '2026-10-01 09:00:00', '2026-10-01 09:00:00')
AS seeded
ON DUPLICATE KEY UPDATE
  name = seeded.name,
  description = seeded.description,
  sort_order = seeded.sort_order,
  status = seeded.status,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 患者账号（t_user）。password 为明文，登录校验直接字符串比对。
-- ---------------------------------------------------------------------------
INSERT INTO t_user (id, username, password, avatar, phone, status, create_time, update_time,
                    real_name, gender, age, allergy_history)
VALUES
  (9001, 'patient1', '123456', NULL, '13800009001', 1, '2026-10-01 09:05:00', '2026-10-01 09:05:00',
   '张三', 1, 34, NULL),
  (9002, 'patient2', '123456', NULL, '13800009002', 1, '2026-10-01 09:06:00', '2026-10-01 09:06:00',
   '李四', 2, 28, NULL),
  (9003, 'patient3', '123456', NULL, '13800009003', 1, '2026-10-01 09:07:00', '2026-10-01 09:07:00',
   '王五', 1, 45, '青霉素过敏')
AS seeded
ON DUPLICATE KEY UPDATE
  password = seeded.password,
  avatar = seeded.avatar,
  phone = seeded.phone,
  status = seeded.status,
  real_name = seeded.real_name,
  gender = seeded.gender,
  age = seeded.age,
  allergy_history = seeded.allergy_history,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 医生账号（t_doctor）—— department_id 关联上面的科室编号
-- ---------------------------------------------------------------------------
INSERT INTO t_doctor (id, username, password, avatar, phone, status, create_time, update_time,
                      real_name, department_id, title, specialty, introduction)
VALUES
  (9001, 'doctor1', '123456', NULL, '13900009001', 1, '2026-10-01 09:10:00', '2026-10-01 09:10:00',
   '陈医生', 9001, '主任医师', '高血压、糖尿病等慢性病管理', '从业二十年，擅长内科慢性病长期随访。'),
  (9002, 'doctor2', '123456', NULL, '13900009002', 1, '2026-10-01 09:11:00', '2026-10-01 09:11:00',
   '刘医生', 9002, '副主任医师', '普外科常见手术', '擅长腹部外科与创伤处理。'),
  (9003, 'doctor3', '123456', NULL, '13900009003', 1, '2026-10-01 09:12:00', '2026-10-01 09:12:00',
   '赵医生', 9003, '主治医师', '儿童呼吸道与消化道疾病', '儿科门诊一线医生。')
AS seeded
ON DUPLICATE KEY UPDATE
  password = seeded.password,
  avatar = seeded.avatar,
  phone = seeded.phone,
  status = seeded.status,
  real_name = seeded.real_name,
  department_id = seeded.department_id,
  title = seeded.title,
  specialty = seeded.specialty,
  introduction = seeded.introduction,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 管理员账号（t_admin）
-- ---------------------------------------------------------------------------
INSERT INTO t_admin (id, username, password, avatar, phone, status, create_time, update_time,
                     nickname, email)
VALUES
  (9001, 'admin1', '123456', NULL, '13700009001', 1, '2026-10-01 09:15:00', '2026-10-01 09:15:00',
   '系统管理员', 'admin1@medisentinel.demo')
AS seeded
ON DUPLICATE KEY UPDATE
  password = seeded.password,
  avatar = seeded.avatar,
  phone = seeded.phone,
  status = seeded.status,
  nickname = seeded.nickname,
  email = seeded.email,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 预约挂号（t_appointment）。状态：0 待确认 / 1 已确认 / 2 已完成 / 3 已取消。
-- ---------------------------------------------------------------------------
INSERT INTO t_appointment (id, user_id, doctor_id, department_id, visit_date, time_slot,
                           status, remark, create_time, update_time)
VALUES
  (9001, 9001, 9001, 9001, '2026-10-06', '09:00-09:30', 1, '高血压复诊', '2026-10-01 10:00:00', '2026-10-01 10:00:00'),
  (9002, 9001, 9002, 9002, '2026-10-07', '10:00-10:30', 0, '术后换药', '2026-10-01 10:05:00', '2026-10-01 10:05:00'),
  (9003, 9002, 9001, 9001, '2026-10-05', '14:00-14:30', 2, '血糖随访', '2026-10-01 10:10:00', '2026-10-01 10:10:00')
AS seeded
ON DUPLICATE KEY UPDATE
  user_id = seeded.user_id,
  doctor_id = seeded.doctor_id,
  department_id = seeded.department_id,
  visit_date = seeded.visit_date,
  time_slot = seeded.time_slot,
  status = seeded.status,
  remark = seeded.remark,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 健康档案（t_health_record）
-- ---------------------------------------------------------------------------
INSERT INTO t_health_record (id, user_id, doctor_id, record_type, diagnosis, treatment,
                             prescription, visit_date, create_time, update_time)
VALUES
  (9001, 9001, 9001, '门诊病历', '原发性高血压 2 级（中危）',
   '低盐低脂饮食，规律运动，监测血压。', '苯磺酸氨氯地平片 5mg 每日一次', '2026-09-20', '2026-09-20 09:30:00', '2026-09-20 09:30:00'),
  (9002, 9002, 9001, '门诊病历', '2 型糖尿病',
   '控制饮食，餐后运动，每周复诊。', '二甲双胍缓释片 0.5g 每日两次', '2026-09-25', '2026-09-25 10:00:00', '2026-09-25 10:00:00')
AS seeded
ON DUPLICATE KEY UPDATE
  user_id = seeded.user_id,
  doctor_id = seeded.doctor_id,
  record_type = seeded.record_type,
  diagnosis = seeded.diagnosis,
  treatment = seeded.treatment,
  prescription = seeded.prescription,
  visit_date = seeded.visit_date,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 人工问诊工单（t_doctor_consult）。状态：0 待回复 / 1 已回复。
-- doctor_id 为 NULL 表示「待分配」，对所有医生可见。
-- ---------------------------------------------------------------------------
INSERT INTO t_doctor_consult (id, user_id, doctor_id, chief_complaint, status, create_time, update_time)
VALUES
  (9001, 9001, 9001, '头痛：近一周反复头痛，血压偏高，晨起明显。', 1, '2026-10-02 08:30:00', '2026-10-02 09:00:00'),
  (9002, 9001, NULL, '咳嗽：干咳两周，夜间加重，无发热。', 0, '2026-10-03 20:10:00', '2026-10-03 20:10:00'),
  (9003, 9002, 9002, '腹痛：右下腹隐痛三天，进食后加重。', 0, '2026-10-03 21:00:00', '2026-10-03 21:00:00')
AS seeded
ON DUPLICATE KEY UPDATE
  user_id = seeded.user_id,
  doctor_id = seeded.doctor_id,
  chief_complaint = seeded.chief_complaint,
  status = seeded.status,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 医生回复（t_doctor_reply）—— consult_id 有真实外键，须在工单之后插入
-- ---------------------------------------------------------------------------
INSERT INTO t_doctor_reply (id, consult_id, doctor_id, content, create_time)
VALUES
  (9001, 9001, 9001, '已阅。血压偏高需先安静休息后复测，若持续 ≥180/110 请立即急诊。建议本周内科门诊复查并调整用药。', '2026-10-02 09:00:00')
AS seeded
ON DUPLICATE KEY UPDATE
  consult_id = seeded.consult_id,
  doctor_id = seeded.doctor_id,
  content = seeded.content;

-- ---------------------------------------------------------------------------
-- 健康科普文章（t_article）。status 1 已发布。
-- ---------------------------------------------------------------------------
INSERT INTO t_article (id, title, category, cover, summary, content, view_count, status,
                       create_time, update_time)
VALUES
  (9001, '高血压日常管理指南', '心血管', NULL, '低盐饮食、规律运动与家庭血压监测的要点。',
   '高血压是最常见的慢性病之一。建议每日食盐摄入不超过 5 克，保持规律有氧运动，并在固定时间测量血压并记录。', 128, 1, '2026-10-01 11:00:00', '2026-10-01 11:00:00'),
  (9002, '糖尿病饮食控制 7 条建议', '内分泌', NULL, '主食定量、粗细搭配、餐后运动。',
   '控制总热量是糖尿病饮食的核心。主食定量并粗细搭配，多吃蔬菜，限制含糖饮料，餐后适度运动有助于平稳血糖。', 96, 1, '2026-10-01 11:05:00', '2026-10-01 11:05:00'),
  (9003, '换季感冒预防小贴士', '呼吸', NULL, '勤洗手、多通风、保证睡眠。',
   '换季时呼吸道疾病高发。勤洗手、保持室内通风、保证充足睡眠与均衡饮食，可有效降低感冒发生概率。', 74, 1, '2026-10-01 11:10:00', '2026-10-01 11:10:00')
AS seeded
ON DUPLICATE KEY UPDATE
  title = seeded.title,
  category = seeded.category,
  cover = seeded.cover,
  summary = seeded.summary,
  content = seeded.content,
  view_count = seeded.view_count,
  status = seeded.status,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 系统公告（t_notice）
-- ---------------------------------------------------------------------------
INSERT INTO t_notice (id, title, content, status, create_time, update_time)
VALUES
  (9001, 'MediSentinel 演示环境上线', '本环境为演示数据，账号与病历均为虚构，请勿用于真实诊疗。', 1, '2026-10-01 08:00:00', '2026-10-01 08:00:00'),
  (9002, '国庆假期门诊安排', '10 月 1 日至 3 日门诊停诊，急诊 24 小时开放。', 1, '2026-10-01 08:05:00', '2026-10-01 08:05:00')
AS seeded
ON DUPLICATE KEY UPDATE
  title = seeded.title,
  content = seeded.content,
  status = seeded.status,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- AI 问诊会话（t_consult_session）—— user_id 关联患者账号
-- ---------------------------------------------------------------------------
INSERT INTO t_consult_session (id, user_id, title, message_count, create_time, update_time)
VALUES
  (9001, 9001, '反复头痛伴血压升高', 2, '2026-10-02 08:20:00', '2026-10-02 08:25:00'),
  (9002, 9001, '干咳两周夜间加重', 2, '2026-10-03 20:00:00', '2026-10-03 20:05:00')
AS seeded
ON DUPLICATE KEY UPDATE
  user_id = seeded.user_id,
  title = seeded.title,
  message_count = seeded.message_count,
  update_time = seeded.update_time;

-- ---------------------------------------------------------------------------
-- 会话消息（t_consult_message）—— session_id 有真实外键，须在会话之后插入
-- ---------------------------------------------------------------------------
INSERT INTO t_consult_message (id, session_id, role, content, references_json, graph_json,
                               cost_time, create_time)
VALUES
  (9001, 9001, 'user', '最近一周反复头痛，早晨起床时明显，血压有点高。', NULL, NULL, NULL, '2026-10-02 08:20:00'),
  (9002, 9001, 'assistant', '头痛伴血压升高需要重视。请先安静休息后复测血压，若持续偏高或出现剧烈头痛、视物模糊，请尽快就医。', NULL, NULL, 1350, '2026-10-02 08:25:00'),
  (9003, 9002, 'user', '干咳两周了，晚上更明显，没有发热。', NULL, NULL, NULL, '2026-10-03 20:00:00'),
  (9004, 9002, 'assistant', '持续两周的干咳建议排查咳嗽变异性哮喘或上气道咳嗽综合征，可先到呼吸内科就诊。', NULL, NULL, 1180, '2026-10-03 20:05:00')
AS seeded
ON DUPLICATE KEY UPDATE
  session_id = seeded.session_id,
  role = seeded.role,
  content = seeded.content,
  references_json = seeded.references_json,
  graph_json = seeded.graph_json,
  cost_time = seeded.cost_time;
