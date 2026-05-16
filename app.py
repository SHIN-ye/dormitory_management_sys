from flask import Flask
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from config import Config
from models import db, Building, Room, Student, Accommodation, Repair, Visitor, Fee, User, Announcement


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    from blueprints.auth import bp as auth_bp
    from blueprints.main import bp as main_bp
    from blueprints.buildings import bp as buildings_bp
    from blueprints.students import bp as students_bp
    from blueprints.housing import bp as housing_bp
    from blueprints.services import bp as services_bp
    from blueprints.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(buildings_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(housing_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(admin_bp)

    return app


app = create_app()


# ============================================================
# CLI：初始化数据库
# ============================================================

@app.cli.command("init-db")
def init_db():
    """flask init-db: 创建表并插入示例数据"""
    db.create_all()

    b1 = Building(name="学生公寓1号楼", floors=6, address="校区A", manager="张阿姨")
    b2 = Building(name="学生公寓2号楼", floors=6, address="校区A", manager="李大叔")
    db.session.add_all([b1, b2])
    db.session.flush()

    rooms = []
    for b in [b1, b2]:
        for floor in range(1, 4):
            for rn in [f"{floor}01", f"{floor}02", f"{floor}03"]:
                rooms.append(Room(
                    room_number=rn, building_id=b.id, capacity=4,
                    occupied=0, room_type="四人间", price=1200.0,
                ))
    db.session.add_all(rooms)
    db.session.flush()

    users = [
        User(username="admin", password=generate_password_hash("admin123"), role="admin"),
        User(username="manager", password=generate_password_hash("manager123"), role="dorm_manager", building_id=b1.id),
        User(username="manager2", password=generate_password_hash("manager123"), role="dorm_manager", building_id=b2.id),
        User(username="student1", password=generate_password_hash("123456"), role="student"),
    ]
    db.session.add_all(users)
    db.session.flush()

    students = [
        Student(sno="20230101", name="张三", gender="男", birth="2004-03-12", phone="13800001111", major="计算机科学与技术", class_name="计科2301", user_id=users[3].id),
        Student(sno="20230102", name="李四", gender="女", birth="2004-07-18", phone="13800002222", major="软件工程", class_name="软工2301"),
        Student(sno="20230103", name="王五", gender="男", birth="2004-11-05", phone="13800003333", major="计算机科学与技术", class_name="计科2301"),
        Student(sno="20230104", name="赵六", gender="女", birth="2005-01-20", phone="13800004444", major="数学与应用数学", class_name="数学2301"),
    ]
    db.session.add_all(students)
    db.session.flush()

    accs = [
        Accommodation(student_id=students[0].id, room_id=rooms[0].id, check_in_date="2025-09-01", status="入住"),
        Accommodation(student_id=students[1].id, room_id=rooms[3].id, check_in_date="2025-09-01", status="入住"),
        Accommodation(student_id=students[2].id, room_id=rooms[0].id, check_in_date="2025-09-01", status="入住"),
        Accommodation(student_id=students[3].id, room_id=rooms[6].id, check_in_date="2025-09-01", status="入住"),
    ]
    rooms[0].occupied = 2
    rooms[3].occupied = 1
    rooms[6].occupied = 1
    db.session.add_all(accs)
    db.session.flush()

    repairs = [
        Repair(student_id=students[0].id, room_id=rooms[0].id, description="卫生间水龙头漏水", status="待处理", report_date="2025-12-10"),
        Repair(student_id=students[1].id, room_id=rooms[3].id, description="空调不制冷", status="已完成", report_date="2025-11-20", fix_date="2025-11-22"),
    ]
    db.session.add_all(repairs)

    visitors = [
        Visitor(student_id=students[0].id, visitor_name="张爸爸", id_card="410123198001011234", reason="探望", visit_date="2025-12-01 14:00:00", leave_date="2025-12-01 17:00:00"),
    ]
    db.session.add_all(visitors)

    fees = [
        Fee(student_id=students[0].id, room_id=rooms[0].id, fee_type="住宿费", amount=1200.0, status="已缴", due_date="2025-09-15", pay_date="2025-09-10"),
        Fee(student_id=students[0].id, room_id=rooms[0].id, fee_type="水电费", amount=150.0, status="未缴", due_date="2026-01-10"),
        Fee(student_id=students[1].id, room_id=rooms[3].id, fee_type="住宿费", amount=1200.0, status="未缴", due_date="2025-09-15"),
    ]
    db.session.add_all(fees)

    db.session.add(Announcement(
        title="欢迎使用学生公寓管理系统",
        content="系统已正式上线，请同学们及时查看费用信息，如有报修需求请通过系统提交。",
        user_id=users[0].id,
    ))

    db.session.commit()
    print("数据库初始化完成！")


@app.cli.command("reset-db")
def reset_db():
    """flask reset-db: 删除所有表并重新初始化"""
    db.drop_all()
    db.create_all()
    print("数据库已重置，正在导入种子数据...")
    init_db()


@app.cli.command("init-advanced")
def init_advanced():
    """flask init-advanced: 导入存储过程/函数/触发器"""
    import os as _os
    sql_path = _os.path.join(_os.path.dirname(__file__), "db_advanced.sql")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()
    statements = sql.replace("DELIMITER $$", "").replace("DELIMITER ;", "").split("$$")
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            try:
                db.session.execute(text(stmt))
            except Exception as e:
                print(f"跳过（可能已存在）: {str(e)[:80]}")
    db.session.commit()
    print("高级特性初始化完成！")


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
