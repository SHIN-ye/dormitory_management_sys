import re
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from models import db, Student, Room, Repair, Visitor, Fee, Building, Accommodation
from utils import login_required, role_required, get_manager_building_id, log_operation, export_excel, allowed_file, save_upload_file

# 服务管理（报修、访客、费用）
bp = Blueprint("services", __name__)


# ============================================================
# 报修管理
# ============================================================

def _build_repair_query(search, status_filter, manager_bid):
    q = Repair.query.options(
        db.joinedload(Repair.student),
        db.joinedload(Repair.room).joinedload(Room.building),
    )
    if manager_bid:
        q = q.join(Repair.room).filter(Room.building_id == manager_bid)
    if search:
        q = q.join(Repair.student).filter(db.or_(Repair.description.contains(search), Student.name.contains(search)))
    if status_filter:
        q = q.filter(Repair.status == status_filter)
    return q.order_by(Repair.report_date.desc())


@bp.route("/repairs")
@role_required("admin", "dorm_manager")
def repair_list():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)
    pagination = _build_repair_query(search, status_filter, get_manager_building_id()).paginate(page=page, per_page=15)
    return render_template("repairs.html", repairs=pagination.items, pagination=pagination, search=search, status_filter=status_filter)


@bp.route("/repairs/export")
@role_required("admin", "dorm_manager")
def repair_export():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    repairs = _build_repair_query(search, status_filter, get_manager_building_id()).all()
    return export_excel(
        "报修列表",
        ["学生学号", "学生姓名", "宿舍楼", "房间号", "描述", "报修日期", "完成日期", "状态"],
        [[r.student.sno, r.student.name, r.room.building.name, r.room.room_number,
          r.description, str(r.report_date), str(r.fix_date) if r.fix_date else "-", r.status]
         for r in repairs],
    )


@bp.route("/repair/add", methods=["GET", "POST"])
@role_required("admin", "dorm_manager")
def repair_add():
    if request.method == "POST":
        filename = None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            filename = save_upload_file(file, current_app.config["UPLOAD_FOLDER"])
        r = Repair(
            student_id=request.form["student_id"],
            room_id=request.form["room_id"],
            description=request.form["description"],
            image=filename,
            status="待处理",
            report_date=request.form.get("report_date", date.today()),
        )
        db.session.add(r)
        db.session.commit()
        flash("报修提交成功", "success")
        return redirect(url_for("services.repair_list"))
    students = Student.query.order_by(Student.sno).all()
    rooms = Room.query.filter_by(is_active=True)
    if get_manager_building_id():
        rooms = rooms.filter_by(building_id=get_manager_building_id())
    rooms = rooms.order_by(Room.building_id, Room.room_number).all()
    return render_template("repair_form.html", repair=None, students=students, rooms=rooms)


@bp.route("/repair/<int:rid>/status", methods=["POST"])
@role_required("admin", "dorm_manager")
def repair_status(rid):
    r = Repair.query.get_or_404(rid)
    new_status = request.form["status"]
    r.status = new_status
    file = request.files.get("image")
    if file and file.filename and allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        filename = save_upload_file(file, current_app.config["UPLOAD_FOLDER"])
        r.image = filename
    db.session.commit()
    log_operation(f"更新报修状态为「{new_status}」", "repair", rid)
    flash("状态更新成功", "success")
    return redirect(url_for("services.repair_list"))


# ============================================================
# 访客管理
# ============================================================

def _build_visitor_query(search, manager_bid):
    q = Visitor.query.options(db.joinedload(Visitor.student))
    if manager_bid:
        q = q.join(Visitor.student).join(
            Accommodation, db.and_(Accommodation.student_id == Student.id, Accommodation.status == "入住")
        ).join(Room).filter(Room.building_id == manager_bid)
    if search:
        q = q.join(Visitor.student).filter(db.or_(
            Visitor.visitor_name.contains(search),
            Visitor.id_card.contains(search),
            Student.name.contains(search),
        ))
    return q.order_by(Visitor.visit_date.desc())


@bp.route("/visitors")
@role_required("admin", "dorm_manager")
def visitor_list():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    pagination = _build_visitor_query(search, get_manager_building_id()).paginate(page=page, per_page=15)
    return render_template("visitors.html", visitors=pagination.items, pagination=pagination, search=search)


@bp.route("/visitors/export")
@role_required("admin", "dorm_manager")
def visitor_export():
    search = request.args.get("search", "").strip()
    visitors = _build_visitor_query(search, get_manager_building_id()).all()
    return export_excel(
        "访客列表",
        ["受访学生学号", "受访学生姓名", "访客姓名", "身份证号", "事由", "来访时间", "离开时间"],
        [[v.student.sno, v.student.name, v.visitor_name, v.id_card,
          v.reason or "-", str(v.visit_date), str(v.leave_date) if v.leave_date else "-"]
         for v in visitors],
    )


@bp.route("/visitor/add", methods=["GET", "POST"])
@role_required("admin", "dorm_manager")
def visitor_add():
    if request.method == "POST":
        id_card = request.form.get("id_card", "").strip()
        if not re.match(r"^\d{17}[\dXx]$", id_card):
            flash("身份证号格式不正确（18位）", "warning")
            return render_template("visitor_form.html", visitor=None, students=Student.query.order_by(Student.sno).all())
        v = Visitor(
            student_id=request.form["student_id"],
            visitor_name=request.form["visitor_name"],
            id_card=id_card,
            reason=request.form.get("reason"),
            visit_date=request.form["visit_date"],
            leave_date=request.form.get("leave_date") or None,
        )
        db.session.add(v)
        db.session.commit()
        flash("访客登记成功", "success")
        return redirect(url_for("services.visitor_list"))
    students = Student.query
    if get_manager_building_id():
        students = students.join(
            Accommodation, db.and_(Accommodation.student_id == Student.id, Accommodation.status == "入住")
        ).join(Room).filter(Room.building_id == get_manager_building_id())
    students = students.order_by(Student.sno).all()
    return render_template("visitor_form.html", visitor=None, students=students)


# ============================================================
# 费用管理
# ============================================================

def _build_fee_query(search, status_filter, manager_bid):
    q = Fee.query.options(
        db.joinedload(Fee.student),
        db.joinedload(Fee.room).joinedload(Room.building),
    )
    if manager_bid:
        q = q.join(Fee.room).filter(Room.building_id == manager_bid)
    if search:
        q = q.join(Fee.student).filter(db.or_(Fee.fee_type.contains(search), Student.name.contains(search)))
    if status_filter:
        q = q.filter(Fee.status == status_filter)
    return q.order_by(Fee.due_date.desc())


@bp.route("/fees")
@role_required("admin", "dorm_manager")
def fee_list():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)
    manager_bid = get_manager_building_id()
    pagination = _build_fee_query(search, status_filter, manager_bid).paginate(page=page, per_page=15)
    buildings = Building.query.all() if not manager_bid else Building.query.filter_by(id=manager_bid).all()
    return render_template("fees.html", fees=pagination.items, pagination=pagination, search=search, status_filter=status_filter, buildings=buildings)


@bp.route("/fees/export")
@role_required("admin", "dorm_manager")
def fee_export():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    fees = _build_fee_query(search, status_filter, get_manager_building_id()).all()
    return export_excel(
        "费用列表",
        ["学生学号", "学生姓名", "宿舍楼", "房间号", "费用类型", "金额", "截止日期", "缴费日期", "状态"],
        [[f.student.sno, f.student.name, f.room.building.name, f.room.room_number,
          f.fee_type, f.amount, str(f.due_date) if f.due_date else "-",
          str(f.pay_date) if f.pay_date else "-", f.status] for f in fees],
    )


@bp.route("/fee/add", methods=["GET", "POST"])
@role_required("admin", "dorm_manager")
def fee_add():
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("金额必须为正数", "warning")
            return render_template("fee_form.html", fee=None,
                students=Student.query.order_by(Student.sno).all(),
                rooms=Room.query.filter_by(is_active=True).order_by(Room.building_id, Room.room_number).all())
        f = Fee(
            student_id=request.form["student_id"],
            room_id=request.form["room_id"],
            fee_type=request.form["fee_type"],
            amount=amount,
            status="未缴",
            due_date=request.form.get("due_date") or None,
        )
        db.session.add(f)
        db.session.commit()
        log_operation(f"添加费用「{f.fee_type}」¥{f.amount}", "fee", f.id)
        flash("费用添加成功", "success")
        return redirect(url_for("services.fee_list"))
    students = Student.query.order_by(Student.sno).all()
    rooms = Room.query.filter_by(is_active=True)
    if get_manager_building_id():
        rooms = rooms.filter_by(building_id=get_manager_building_id())
    rooms = rooms.order_by(Room.building_id, Room.room_number).all()
    return render_template("fee_form.html", fee=None, students=students, rooms=rooms)


@bp.route("/fee/<int:fid>/pay", methods=["POST"])
@role_required("admin", "dorm_manager")
def fee_pay(fid):
    f = Fee.query.get_or_404(fid)
    if f.status == "已缴":
        flash("该费用已缴纳", "warning")
        return redirect(url_for("services.fee_list"))
    f.status = "已缴"
    f.pay_date = date.today()
    db.session.commit()
    log_operation(f"标记费用已缴「{f.fee_type}」¥{f.amount}", "fee", fid)
    flash("缴费成功", "success")
    return redirect(url_for("services.fee_list"))


@bp.route("/fees/batch", methods=["POST"])
@role_required("admin", "dorm_manager")
def fee_batch():
    building_id = request.form["building_id"]
    manager_bid = get_manager_building_id()
    if manager_bid and int(building_id) != manager_bid:
        flash("只能为自己管辖的宿舍楼批量生成费用", "danger")
        return redirect(url_for("services.fee_list"))
    fee_type = request.form["fee_type"]
    amount = request.form["amount"]
    due_date = request.form.get("due_date") or None
    try:
        from sqlalchemy import text
        result = db.session.execute(
            text("CALL sp_generate_fees(:bid, :ftype, :amt, :ddate)"),
            {"bid": building_id, "ftype": fee_type, "amt": amount, "ddate": due_date},
        )
        count = result.fetchone()[0]
        db.session.commit()
        log_operation(f"批量生成费用「{fee_type}」¥{amount}（{count}人）", "fee")
        flash(f"已为 {count} 名学生生成{fee_type}（{amount}元）", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"操作失败: {e}", "danger")
    return redirect(url_for("services.fee_list"))
