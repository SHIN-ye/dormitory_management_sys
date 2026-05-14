-- ============================================================
-- 学生公寓管理系统 — 数据库高级特性
-- 存储过程 / 函数 / 触发器 / 事务
-- ============================================================

USE dormitory_management;

-- ============================================================
-- 1. 存储过程：入住登记
-- 原子操作：检查 → 插入 → 更新房间人数
-- 事务由应用层（SQLAlchemy）管理
-- ============================================================
DELIMITER $$

DROP PROCEDURE IF EXISTS sp_checkin$$
CREATE PROCEDURE sp_checkin(
    IN p_student_id INT,
    IN p_room_id INT,
    IN p_check_in_date DATE
)
BEGIN
    DECLARE v_capacity INT;
    DECLARE v_occupied INT;
    DECLARE v_existing INT;

    -- 检查学生是否已入住
    SELECT COUNT(*) INTO v_existing
    FROM accommodation
    WHERE student_id = p_student_id AND status = '入住';

    IF v_existing > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该学生已入住，请先退宿';
    END IF;

    -- 锁定房间行并检查容量
    SELECT capacity, occupied INTO v_capacity, v_occupied
    FROM room WHERE id = p_room_id FOR UPDATE;

    IF v_occupied >= v_capacity THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该房间已满';
    END IF;

    -- 插入入住记录
    INSERT INTO accommodation(student_id, room_id, check_in_date, status)
    VALUES(p_student_id, p_room_id, p_check_in_date, '入住');

    -- 更新房间已住人数
    UPDATE room SET occupied = occupied + 1 WHERE id = p_room_id;
END$$


-- ============================================================
-- 2. 存储过程：批量生成费用
-- 为指定宿舍楼所有在住学生统一生成费用
-- ============================================================
DROP PROCEDURE IF EXISTS sp_generate_fees$$
CREATE PROCEDURE sp_generate_fees(
    IN p_building_id INT,
    IN p_fee_type VARCHAR(16),
    IN p_amount FLOAT,
    IN p_due_date DATE
)
BEGIN
    DECLARE v_count INT DEFAULT 0;

    INSERT INTO fee(student_id, room_id, fee_type, amount, status, due_date)
    SELECT a.student_id, a.room_id, p_fee_type, p_amount, '未缴', p_due_date
    FROM accommodation a
    JOIN room r ON a.room_id = r.id
    WHERE r.building_id = p_building_id AND a.status = '入住';

    SET v_count = ROW_COUNT();
    SELECT v_count AS affected_rows;
END$$


-- ============================================================
-- 3. 存储过程：宿舍调换
-- 原子操作：校验 → 迁移住宿记录 → 更新两间房人数
-- 事务由应用层（SQLAlchemy）管理
-- ============================================================
DROP PROCEDURE IF EXISTS sp_room_transfer$$
CREATE PROCEDURE sp_room_transfer(
    IN p_accommodation_id INT,
    IN p_to_room_id INT
)
BEGIN
    DECLARE v_from_room_id INT;
    DECLARE v_to_capacity INT;
    DECLARE v_to_occupied INT;

    -- 获取当前房间ID
    SELECT room_id INTO v_from_room_id
    FROM accommodation WHERE id = p_accommodation_id FOR UPDATE;

    IF v_from_room_id = p_to_room_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '不能调换到同一房间';
    END IF;

    -- 检查目标房间容量
    SELECT capacity, occupied INTO v_to_capacity, v_to_occupied
    FROM room WHERE id = p_to_room_id FOR UPDATE;

    IF v_to_occupied >= v_to_capacity THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '目标房间已满';
    END IF;

    -- 迁移住宿记录
    UPDATE accommodation SET room_id = p_to_room_id WHERE id = p_accommodation_id;

    -- 更新两间房的 occupied
    UPDATE room SET occupied = occupied - 1 WHERE id = v_from_room_id;
    UPDATE room SET occupied = occupied + 1 WHERE id = p_to_room_id;
END$$


-- ============================================================
-- 4. 函数：宿舍楼入住率
-- 返回指定宿舍楼的总入住率（百分比）
-- ============================================================
DROP FUNCTION IF EXISTS fn_occupancy_rate$$
CREATE FUNCTION fn_occupancy_rate(p_building_id INT)
RETURNS DECIMAL(5,2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_capacity INT DEFAULT 0;
    DECLARE v_occupied INT DEFAULT 0;
    DECLARE v_rate DECIMAL(5,2) DEFAULT 0.00;

    SELECT COALESCE(SUM(capacity), 0), COALESCE(SUM(occupied), 0)
    INTO v_capacity, v_occupied
    FROM room WHERE building_id = p_building_id;

    IF v_capacity > 0 THEN
        SET v_rate = v_occupied / v_capacity * 100;
    END IF;

    RETURN v_rate;
END$$


-- ============================================================
-- 5. 触发器：报修完成自动记录修复日期
-- ============================================================
DROP TRIGGER IF EXISTS trg_repair_complete$$
CREATE TRIGGER trg_repair_complete
BEFORE UPDATE ON repair
FOR EACH ROW
BEGIN
    IF NEW.status = '已完成' AND OLD.status != '已完成' THEN
        SET NEW.fix_date = CURDATE();
    END IF;
END$$


-- ============================================================
-- 6. 触发器：退宿自动减少房间人数
-- ============================================================
DROP TRIGGER IF EXISTS trg_accommodation_checkout$$
CREATE TRIGGER trg_accommodation_checkout
AFTER UPDATE ON accommodation
FOR EACH ROW
BEGIN
    IF NEW.status = '已退宿' AND OLD.status = '入住' THEN
        UPDATE room SET occupied = occupied - 1 WHERE id = NEW.room_id;
    END IF;
END$$


DELIMITER ;

-- 验证
SELECT '===== 数据库高级特性已创建 =====' AS status;
SHOW PROCEDURE STATUS WHERE Db = 'dormitory_management';
SHOW FUNCTION STATUS WHERE Db = 'dormitory_management';
SHOW TRIGGERS WHERE `Table` IN ('repair', 'accommodation');
