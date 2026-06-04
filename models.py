from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ============================================================
# 宿舍楼
# ============================================================
class Building(db.Model): # 定义宿舍楼模型, 继承db.Model
    __tablename__ = "building"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    floors = db.Column(db.Integer, default=6) # 默认6层
    address = db.Column(db.String(128))
    manager = db.Column(db.String(32))

    rooms = db.relationship("Room", back_populates="building", lazy=True, cascade="all, delete-orphan") # 级联删除 lazy = ture 访问时才触发sql查询
    managers = db.relationship("User", back_populates="building")


# ============================================================
# 房间
# ============================================================
class Room(db.Model):
    __tablename__ = "room"
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(16), nullable=False)
    building_id = db.Column(db.Integer, db.ForeignKey("building.id"), nullable=False)
    capacity = db.Column(db.Integer, default=4)
    occupied = db.Column(db.Integer, default=0) # 已入驻人数
    room_type = db.Column(db.String(16), default="四人间")
    price = db.Column(db.Float, default=1200.0) # 住宿费

    building = db.relationship("Building", back_populates="rooms")
    accommodations = db.relationship("Accommodation", back_populates="room", lazy=True, cascade="all, delete-orphan")
    repairs = db.relationship("Repair", back_populates="room", lazy=True, cascade="all, delete-orphan")
    fees = db.relationship("Fee", back_populates="room", lazy=True, cascade="all, delete-orphan")
    transfer_requests_to = db.relationship("TransferRequest", back_populates="to_room", lazy=True, cascade="all, delete-orphan")

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
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), unique=True, nullable=True)

    user = db.relationship("User", back_populates="student_profile", uselist=False)
    accommodations = db.relationship("Accommodation", back_populates="student", lazy=True, cascade="all, delete-orphan")
    repairs = db.relationship("Repair", back_populates="student", lazy=True, cascade="all, delete-orphan")
    visitors = db.relationship("Visitor", back_populates="student", lazy=True, cascade="all, delete-orphan")
    fees = db.relationship("Fee", back_populates="student", lazy=True, cascade="all, delete-orphan")
    checkout_requests = db.relationship("CheckoutRequest", back_populates="student", lazy=True, cascade="all, delete-orphan")
    transfer_requests = db.relationship("TransferRequest", back_populates="student", lazy=True, cascade="all, delete-orphan")


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
    status = db.Column(db.String(8), default="入住")

    student = db.relationship("Student", back_populates="accommodations")
    room = db.relationship("Room", back_populates="accommodations")
    checkout_requests = db.relationship("CheckoutRequest", back_populates="accommodation", lazy=True, cascade="all, delete-orphan")
    transfer_requests = db.relationship("TransferRequest", back_populates="from_accommodation", lazy=True, cascade="all, delete-orphan")


# ============================================================
# 报修记录
# ============================================================
class Repair(db.Model):
    __tablename__ = "repair"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    description = db.Column(db.String(256), nullable=False) #问题描述
    image = db.Column(db.String(128))
    status = db.Column(db.String(8), default="待处理")
    report_date = db.Column(db.Date, nullable=False)
    fix_date = db.Column(db.Date) # 触发器自动写入当前日期

    student = db.relationship("Student", back_populates="repairs")
    room = db.relationship("Room", back_populates="repairs")


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

    student = db.relationship("Student", back_populates="visitors")


# ============================================================
# 费用记录
# ============================================================
class Fee(db.Model):
    __tablename__ = "fee"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    fee_type = db.Column(db.String(16), nullable=False) # 费用类型
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(8), default="未缴")
    due_date = db.Column(db.Date)
    pay_date = db.Column(db.Date)

    student = db.relationship("Student", back_populates="fees")
    room = db.relationship("Room", back_populates="fees")


# ============================================================
# 退宿申请
# ============================================================
class CheckoutRequest(db.Model):
    __tablename__ = "checkout_request"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    accommodation_id = db.Column(db.Integer, db.ForeignKey("accommodation.id"), nullable=False)
    status = db.Column(db.String(16), default="pending")
    request_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    review_date = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student", back_populates="checkout_requests")
    accommodation = db.relationship("Accommodation", back_populates="checkout_requests")
    reviewer = db.relationship("User") # 单向多对一关系


# ============================================================
# 宿舍调换申请
# ============================================================
class TransferRequest(db.Model):
    __tablename__ = "transfer_request"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    from_accommodation_id = db.Column(db.Integer, db.ForeignKey("accommodation.id"), nullable=False)
    to_room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    status = db.Column(db.String(16), default="pending")
    request_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    review_date = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student", back_populates="transfer_requests")
    from_accommodation = db.relationship("Accommodation", foreign_keys=[from_accommodation_id], back_populates="transfer_requests")
    to_room = db.relationship("Room", back_populates="transfer_requests_to")
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

    user = db.relationship("User", back_populates="announcements")


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
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp()) # 默认数据库当前时间戳

    user = db.relationship("User", back_populates="operation_logs")


# ============================================================
# 用户
# ============================================================
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), default="student")
    building_id = db.Column(db.Integer, db.ForeignKey("building.id"), nullable=True)

    building = db.relationship("Building", back_populates="managers")
    student_profile = db.relationship("Student", back_populates="user", uselist=False)
    announcements = db.relationship("Announcement", back_populates="user", lazy=True)
    operation_logs = db.relationship("OperationLog", back_populates="user", lazy=True)
