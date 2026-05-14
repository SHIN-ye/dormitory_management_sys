from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ============================================================
# 宿舍楼
# ============================================================
class Building(db.Model):
    __tablename__ = "building"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    floors = db.Column(db.Integer, default=6)
    address = db.Column(db.String(128))
    manager = db.Column(db.String(32))

    rooms = db.relationship("Room", backref="building", lazy=True, cascade="all, delete-orphan")


# ============================================================
# 房间
# ============================================================
class Room(db.Model):
    __tablename__ = "room"
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(16), nullable=False)
    building_id = db.Column(db.Integer, db.ForeignKey("building.id"), nullable=False)
    capacity = db.Column(db.Integer, default=4)
    occupied = db.Column(db.Integer, default=0)
    room_type = db.Column(db.String(16), default="四人间")
    price = db.Column(db.Float, default=1200.0)

    accommodations = db.relationship("Accommodation", backref="room", lazy=True)
    repairs = db.relationship("Repair", backref="room", lazy=True)
    fees = db.relationship("Fee", backref="room", lazy=True)

    __table_args__ = (db.UniqueConstraint("building_id", "room_number"),)


# ============================================================
# 学生
# ============================================================
class Student(db.Model):
    __tablename__ = "student"
    id = db.Column(db.Integer, primary_key=True)
    sno = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(32), nullable=False)
    gender = db.Column(db.String(4))
    birth = db.Column(db.Date)
    phone = db.Column(db.String(20))
    major = db.Column(db.String(64))
    class_name = db.Column(db.String(64))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=True)

    user = db.relationship("User", backref="student_profile", uselist=False)
    accommodations = db.relationship("Accommodation", backref="student", lazy=True)
    repairs = db.relationship("Repair", backref="student", lazy=True)
    visitors = db.relationship("Visitor", backref="student", lazy=True)
    fees = db.relationship("Fee", backref="student", lazy=True)


# ============================================================
# 入住记录
# ============================================================
class Accommodation(db.Model):
    __tablename__ = "accommodation"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date)
    status = db.Column(db.String(8), default="入住")  # 入住 / 已退宿


# ============================================================
# 报修记录
# ============================================================
class Repair(db.Model):
    __tablename__ = "repair"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    description = db.Column(db.String(256), nullable=False)
    image = db.Column(db.String(128))  # 现场照片文件名
    status = db.Column(db.String(8), default="待处理")  # 待处理 / 处理中 / 已完成
    report_date = db.Column(db.Date, nullable=False)
    fix_date = db.Column(db.Date)


# ============================================================
# 访客记录
# ============================================================
class Visitor(db.Model):
    __tablename__ = "visitor"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    visitor_name = db.Column(db.String(32), nullable=False)
    id_card = db.Column(db.String(18), nullable=False)
    reason = db.Column(db.String(128))
    visit_date = db.Column(db.DateTime, nullable=False)
    leave_date = db.Column(db.DateTime)


# ============================================================
# 费用记录
# ============================================================
class Fee(db.Model):
    __tablename__ = "fee"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    fee_type = db.Column(db.String(16), nullable=False)  # 住宿费 / 水电费 / 维修费
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(8), default="未缴")  # 未缴 / 已缴
    due_date = db.Column(db.Date)
    pay_date = db.Column(db.Date)


# ============================================================
# 退宿申请
# ============================================================
class CheckoutRequest(db.Model):
    __tablename__ = "checkout_request"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    accommodation_id = db.Column(db.Integer, db.ForeignKey("accommodation.id"), nullable=False)
    status = db.Column(db.String(16), default="pending")  # pending / approved / rejected
    request_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    review_date = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student", backref="checkout_requests")
    accommodation = db.relationship("Accommodation", backref="checkout_requests")
    reviewer = db.relationship("User")


# ============================================================
# 宿舍调换申请
# ============================================================
class TransferRequest(db.Model):
    __tablename__ = "transfer_request"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    from_accommodation_id = db.Column(db.Integer, db.ForeignKey("accommodation.id"), nullable=False)
    to_room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    status = db.Column(db.String(16), default="pending")  # pending / approved / rejected
    request_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    review_date = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student", backref="transfer_requests")
    from_accommodation = db.relationship("Accommodation", foreign_keys=[from_accommodation_id], backref="transfer_requests")
    to_room = db.relationship("Room")
    reviewer = db.relationship("User")


# ============================================================
# 公告
# ============================================================
class Announcement(db.Model):
    __tablename__ = "announcement"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# ============================================================
# 操作日志
# ============================================================
class OperationLog(db.Model):
    __tablename__ = "operation_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(256), nullable=False)
    target_type = db.Column(db.String(32))
    target_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship("User", backref="operation_logs")


# ============================================================
# 用户
# ============================================================
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), default="student")  # admin / dorm_manager / student
    building_id = db.Column(db.Integer, db.ForeignKey("building.id"), nullable=True)

    building = db.relationship("Building", backref="managers")
    announcements = db.relationship("Announcement", backref="user", lazy=True)
