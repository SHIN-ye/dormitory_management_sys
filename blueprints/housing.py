from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import text
from models import db, Student, Room, Accommodation, CheckoutRequest, TransferRequest
from utils import login_required, role_required, get_manager_building_id, log_operation, export_excel

# 入住管理、退宿/调换申请+审核
bp = Blueprint("housing", __name__)


# ============================================================
# 入住管理
# ============================================================

def _build_accommodation_query(search, status_filter, manager_bid):
    q = Accommodation.query.options(
        db.joinedload(Accommodation.student),
        db.joinedload(Accommodation.room).joinedload(Room.building),
    )
    if manager_bid:
        q = q.join(Accommodation.room).filter(Room.building_id == manager_bid)
    if search:
        q = q.join(Accommodation.student).filter(Student.name.contains(search))
    if status_filter:
        q = q.filter(Accommodation.status == status_filter)
    return q.order_by(Accommodation.check_in_date.desc())


@bp.route("/accommodations")
@role_required("admin", "dorm_manager")
def accommodation_list():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)
    manager_bid = get_manager_building_id()
    pagination = _build_accommodation_query(search, status_filter, manager_bid).paginate(page=page, per_page=15)
    return render_template("accommodations.html", accs=pagination.items, pagination=pagination, search=search, status_filter=status_filter)


@bp.route("/accommodations/export")
@role_required("admin", "dorm_manager")
def accommodation_export():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    accs = _build_accommodation_query(search, status_filter, get_manager_building_id()).all()
    return export_excel(
        "入住记录",
        ["学生学号", "学生姓名", "宿舍楼", "房间号", "入住日期", "退宿日期", "状态"],
        [[a.student.sno, a.student.name, a.room.building.name, a.room.room_number,
          str(a.check_in_date), str(a.check_out_date) if a.check_out_date else "-", a.status]
         for a in accs],
    )


@bp.route("/accommodation/add", methods=["GET", "POST"])
@role_required("admin", "dorm_manager")
def accommodation_add():
    if request.method == "POST":
        student_id = request.form["student_id"]
        room_id = request.form["room_id"]
        check_in_date = request.form["check_in_date"]
        try:
            db.session.execute(
                text("CALL sp_checkin(:sid, :rid, :cdate)"),
                {"sid": student_id, "rid": room_id, "cdate": check_in_date},
            )
            db.session.commit()
            log_operation(f"为学生登记入住", "accommodation")
            flash("入住登记成功", "success")
        except Exception as e:
            db.session.rollback()
            msg = str(e)
            if "该学生已入住" in msg:
                flash("该学生已入住，请先退宿", "danger")
            elif "该房间已满" in msg:
                flash("该房间已满", "danger")
            else:
                flash(f"操作失败: {msg}", "danger")
            return redirect(url_for("housing.accommodation_add"))
        return redirect(url_for("housing.accommodation_list"))
    manager_bid = get_manager_building_id()
    students = Student.query.order_by(Student.sno).all()
    rooms = Room.query.filter_by(is_active=True)
    if manager_bid:
        rooms = rooms.filter_by(building_id=manager_bid)
    rooms = rooms.order_by(Room.building_id, Room.room_number).all()
    return render_template("accommodation_form.html", acc=None, students=students, rooms=rooms)


@bp.route("/accommodation/<int:aid>/checkout", methods=["POST"])
@role_required("admin", "dorm_manager")
def accommodation_checkout(aid):
    acc = Accommodation.query.get_or_404(aid)
    if acc.status == "已退宿":
        flash("该记录已退宿", "warning")
        return redirect(url_for("housing.accommodation_list"))
    acc.status = "已退宿"
    acc.check_out_date = date.today()
    db.session.commit()
    log_operation(f"办理退宿", "accommodation", aid)
    flash("退宿成功", "success")
    return redirect(url_for("housing.accommodation_list"))


# ============================================================
# 学生提交退宿/调换申请
# ============================================================

@bp.route("/my/accommodation/checkout-request", methods=["POST"])
@login_required
def checkout_request():
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student:
        flash("未关联学生信息", "warning")
        return redirect(url_for("main.index"))
    existing = CheckoutRequest.query.filter_by(
        student_id=student.id, status="pending"
    ).first()
    if existing:
        flash("已有退宿申请正在审核中", "warning")
        return redirect(url_for("main.my_accommodation"))
    acc = Accommodation.query.filter_by(
        student_id=student.id, status="入住"
    ).first()
    if not acc:
        flash("当前无在住记录", "warning")
        return redirect(url_for("main.my_accommodation"))
    req = CheckoutRequest(student_id=student.id, accommodation_id=acc.id)
    db.session.add(req)
    db.session.commit()
    flash("退宿申请已提交，请等待宿管审核", "success")
    return redirect(url_for("main.my_accommodation"))


@bp.route("/my/accommodation/transfer-request", methods=["POST"])
@login_required
def transfer_request():
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student:
        flash("未关联学生信息", "warning")
        return redirect(url_for("main.index"))
    existing = TransferRequest.query.filter_by(
        student_id=student.id, status="pending"
    ).first()
    if existing:
        flash("已有调换申请正在审核中", "warning")
        return redirect(url_for("main.my_accommodation"))
    acc = Accommodation.query.filter_by(
        student_id=student.id, status="入住"
    ).first()
    if not acc:
        flash("当前无在住记录", "warning")
        return redirect(url_for("main.my_accommodation"))
    to_room_id = request.form.get("to_room_id", type=int)
    if not to_room_id:
        flash("请选择目标房间", "warning")
        return redirect(url_for("main.my_accommodation"))
    target_room = Room.query.get_or_404(to_room_id)
    if not target_room.is_active:
        flash("目标房间已停用", "warning")
        return redirect(url_for("main.my_accommodation"))
    if target_room.occupied >= target_room.capacity:
        flash("目标房间已满", "warning")
        return redirect(url_for("main.my_accommodation"))
    if target_room.id == acc.room_id:
        flash("不能调换到当前房间", "warning")
        return redirect(url_for("main.my_accommodation"))
    req = TransferRequest(
        student_id=student.id,
        from_accommodation_id=acc.id,
        to_room_id=to_room_id,
    )
    db.session.add(req)
    db.session.commit()
    flash("调换申请已提交，请等待宿管审核", "success")
    return redirect(url_for("main.my_accommodation"))


# ============================================================
# 退宿审核
# ============================================================

def _build_checkout_query(manager_bid):
    q = CheckoutRequest.query.options(
        db.joinedload(CheckoutRequest.student),
        db.joinedload(CheckoutRequest.accommodation)
        .joinedload(Accommodation.room)
        .joinedload(Room.building),
        db.joinedload(CheckoutRequest.reviewer),
    )
    if manager_bid:
        q = q.join(CheckoutRequest.accommodation)\
             .join(Accommodation.room)\
             .filter(Room.building_id == manager_bid)
    return q.order_by(
        db.case((CheckoutRequest.status == "pending", 0), else_=1),
        CheckoutRequest.request_date.desc()
    )


@bp.route("/checkout-requests")
@role_required("admin", "dorm_manager")
def checkout_request_list():
    page = request.args.get("page", 1, type=int)
    pagination = _build_checkout_query(get_manager_building_id()).paginate(page=page, per_page=15)
    return render_template("checkout_requests.html", requests=pagination.items, pagination=pagination)


@bp.route("/checkout-requests/export")
@role_required("admin", "dorm_manager")
def checkout_request_export():
    reqs = _build_checkout_query(get_manager_building_id()).all()
    return export_excel(
        "退宿申请列表",
        ["学生学号", "学生姓名", "宿舍楼", "房间号", "入住日期", "申请日期", "状态", "审核人", "审核日期"],
        [[r.student.sno, r.student.name, r.accommodation.room.building.name,
          r.accommodation.room.room_number, str(r.accommodation.check_in_date),
          r.request_date.strftime("%Y-%m-%d %H:%M") if r.request_date else "",
          {"pending": "待审核", "approved": "已批准", "rejected": "已拒绝"}.get(r.status, r.status),
          r.reviewer.username if r.reviewer else "-",
          r.review_date.strftime("%Y-%m-%d %H:%M") if r.review_date else "-"]
         for r in reqs],
    )


@bp.route("/checkout-request/<int:rid>/approve", methods=["POST"])
@role_required("admin", "dorm_manager")
def checkout_request_approve(rid):
    req = CheckoutRequest.query.get_or_404(rid)
    if req.status != "pending":
        flash("该申请已处理", "warning")
        return redirect(url_for("housing.checkout_request_list"))
    acc = Accommodation.query.get(req.accommodation_id)
    manager_bid = get_manager_building_id()
    if manager_bid and acc.room.building_id != manager_bid:
        flash("无权处理该申请", "danger")
        return redirect(url_for("housing.checkout_request_list"))
    acc.status = "已退宿"
    acc.check_out_date = date.today()
    req.status = "approved"
    req.reviewed_by = session["user_id"]
    req.review_date = datetime.now()
    db.session.commit()
    log_operation(f"批准退宿申请 #{rid}", "checkout_request", rid)
    flash("退宿申请已批准", "success")
    return redirect(url_for("housing.checkout_request_list"))


@bp.route("/checkout-request/<int:rid>/reject", methods=["POST"])
@role_required("admin", "dorm_manager")
def checkout_request_reject(rid):
    req = CheckoutRequest.query.get_or_404(rid)
    if req.status != "pending":
        flash("该申请已处理", "warning")
        return redirect(url_for("housing.checkout_request_list"))
    acc = Accommodation.query.get(req.accommodation_id)
    manager_bid = get_manager_building_id()
    if manager_bid and acc.room.building_id != manager_bid:
        flash("无权处理该申请", "danger")
        return redirect(url_for("housing.checkout_request_list"))
    req.status = "rejected"
    req.reviewed_by = session["user_id"]
    req.review_date = datetime.now()
    db.session.commit()
    log_operation(f"拒绝退宿申请 #{rid}", "checkout_request", rid)
    flash("退宿申请已拒绝", "success")
    return redirect(url_for("housing.checkout_request_list"))


# ============================================================
# 宿舍调换审核
# ============================================================

def _build_transfer_query(manager_bid):
    q = TransferRequest.query.options(
        db.joinedload(TransferRequest.student),
        db.joinedload(TransferRequest.from_accommodation)
        .joinedload(Accommodation.room)
        .joinedload(Room.building),
        db.joinedload(TransferRequest.to_room).joinedload(Room.building),
        db.joinedload(TransferRequest.reviewer),
    )
    if manager_bid:
        q = q.join(TransferRequest.from_accommodation)\
             .join(Accommodation.room)\
             .filter(Room.building_id == manager_bid)
    return q.order_by(
        db.case((TransferRequest.status == "pending", 0), else_=1),
        TransferRequest.request_date.desc()
    )


@bp.route("/transfer-requests")
@role_required("admin", "dorm_manager")
def transfer_request_list():
    page = request.args.get("page", 1, type=int)
    pagination = _build_transfer_query(get_manager_building_id()).paginate(page=page, per_page=15)
    return render_template("transfer_requests.html", requests=pagination.items, pagination=pagination)


@bp.route("/transfer-requests/export")
@role_required("admin", "dorm_manager")
def transfer_request_export():
    reqs = _build_transfer_query(get_manager_building_id()).all()
    return export_excel(
        "调换申请列表",
        ["学生学号", "学生姓名", "原宿舍楼", "原房间号", "目标宿舍楼", "目标房间号", "申请日期", "状态", "审核人", "审核日期"],
        [[r.student.sno, r.student.name,
          r.from_accommodation.room.building.name, r.from_accommodation.room.room_number,
          r.to_room.building.name, r.to_room.room_number,
          r.request_date.strftime("%Y-%m-%d %H:%M") if r.request_date else "",
          {"pending": "待审核", "approved": "已批准", "rejected": "已拒绝"}.get(r.status, r.status),
          r.reviewer.username if r.reviewer else "-",
          r.review_date.strftime("%Y-%m-%d %H:%M") if r.review_date else "-"]
         for r in reqs],
    )


@bp.route("/transfer-request/<int:rid>/approve", methods=["POST"])
@role_required("admin", "dorm_manager")
def transfer_request_approve(rid):
    req = TransferRequest.query.get_or_404(rid)
    if req.status != "pending":
        flash("该申请已处理", "warning")
        return redirect(url_for("housing.transfer_request_list"))
    acc = Accommodation.query.get(req.from_accommodation_id)
    manager_bid = get_manager_building_id()
    if manager_bid and acc.room.building_id != manager_bid:
        flash("无权处理该申请", "danger")
        return redirect(url_for("housing.transfer_request_list"))
    try:
        db.session.execute(
            text("CALL sp_room_transfer(:aid, :rid)"),
            {"aid": req.from_accommodation_id, "rid": req.to_room_id},
        )
        req.status = "approved"
        req.reviewed_by = session["user_id"]
        req.review_date = datetime.now()
        db.session.commit()
        log_operation(f"批准调换申请 #{rid}", "transfer_request", rid)
        flash("调换申请已批准，房间已迁移", "success")
    except Exception as e:
        db.session.rollback()
        msg = str(e)
        if "不能调换到同一房间" in msg:
            flash("不能调换到同一房间", "danger")
        elif "目标房间已满" in msg:
            flash("目标房间已满", "danger")
        else:
            flash(f"操作失败: {msg}", "danger")
    return redirect(url_for("housing.transfer_request_list"))


@bp.route("/transfer-request/<int:rid>/reject", methods=["POST"])
@role_required("admin", "dorm_manager")
def transfer_request_reject(rid):
    req = TransferRequest.query.get_or_404(rid)
    if req.status != "pending":
        flash("该申请已处理", "warning")
        return redirect(url_for("housing.transfer_request_list"))
    acc = Accommodation.query.get(req.from_accommodation_id)
    manager_bid = get_manager_building_id()
    if manager_bid and acc.room.building_id != manager_bid:
        flash("无权处理该申请", "danger")
        return redirect(url_for("housing.transfer_request_list"))
    req.status = "rejected"
    req.reviewed_by = session["user_id"]
    req.review_date = datetime.now()
    db.session.commit()
    log_operation(f"拒绝调换申请 #{rid}", "transfer_request", rid)
    flash("调换申请已拒绝", "success")
    return redirect(url_for("housing.transfer_request_list"))
