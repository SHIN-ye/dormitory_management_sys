import os
import re
import uuid
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_from_directory
from sqlalchemy import text
from models import db, Student, Accommodation, Room, Repair, Visitor, Fee, Announcement, Building
from utils import login_required, role_required, get_manager_building_id, log_operation, export_excel, allowed_file, save_upload_file

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    latest_announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all()

    if session.get("role") == "student":
        student = Student.query.filter_by(user_id=session["user_id"]).first()
        my_accommodation = None
        roommates = []
        my_repairs = []
        my_fees = []
        if student:
            my_accommodation = Accommodation.query.filter_by(
                student_id=student.id, status="入住"
            ).first()
            if my_accommodation:
                roommates = Accommodation.query.options(
                    db.joinedload(Accommodation.student)
                ).filter(
                    Accommodation.room_id == my_accommodation.room_id,
                    Accommodation.status == "入住",
                    Accommodation.student_id != student.id,
                ).all()
            my_repairs = Repair.query.filter_by(student_id=student.id).order_by(Repair.report_date.desc()).limit(5).all()
            my_fees = Fee.query.filter_by(student_id=student.id).order_by(Fee.due_date.desc()).limit(5).all()
        return render_template("index.html",
            announcements=latest_announcements, is_student=True,
            student=student, my_accommodation=my_accommodation,
            roommates=roommates, my_repairs=my_repairs, my_fees=my_fees,
        )

    manager_bid = get_manager_building_id()
    stats = {
        "buildings": Building.query.count() if not manager_bid else 1,
        "rooms": Room.query.filter_by(building_id=manager_bid).count() if manager_bid else Room.query.count(),
        "students": Student.query.count(),
        "occupied": Accommodation.query.join(Room).filter(Accommodation.status == "入住", Room.building_id == manager_bid).count() if manager_bid else Accommodation.query.filter_by(status="入住").count(),
        "pending_repairs": Repair.query.join(Room).filter(Repair.status == "待处理", Room.building_id == manager_bid).count() if manager_bid else Repair.query.filter_by(status="待处理").count(),
        "unpaid_fees": Fee.query.join(Room).filter(Fee.status == "未缴", Room.building_id == manager_bid).count() if manager_bid else Fee.query.filter_by(status="未缴").count(),
    }
    buildings = Building.query.all() if not manager_bid else Building.query.filter_by(id=manager_bid).all()
    occupancy_rates = {}
    for b in buildings:
        row = db.session.execute(text("SELECT fn_occupancy_rate(:bid)"), {"bid": b.id}).fetchone()
        occupancy_rates[b.id] = float(row[0]) if row else 0.0
    recent_repairs = (Repair.query.join(Room).filter(Room.building_id == manager_bid).order_by(Repair.report_date.desc()).limit(5).all()
        if manager_bid else Repair.query.order_by(Repair.report_date.desc()).limit(5).all())
    return render_template("index.html", stats=stats, recent_repairs=recent_repairs,
        announcements=latest_announcements, is_student=False,
        buildings=buildings, occupancy_rates=occupancy_rates)


# ============================================================
# 公告管理
# ============================================================

@bp.route("/announcements")
@login_required
def announcement_list():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    q = Announcement.query.options(db.joinedload(Announcement.user))
    if search:
        q = q.filter(db.or_(Announcement.title.contains(search), Announcement.content.contains(search)))
    pagination = q.order_by(Announcement.created_at.desc()).paginate(page=page, per_page=15)
    return render_template("announcements.html", announcements=pagination.items, pagination=pagination, search=search)


@bp.route("/announcements/export")
@login_required
def announcement_export():
    search = request.args.get("search", "").strip()
    q = Announcement.query.options(db.joinedload(Announcement.user))
    if search:
        q = q.filter(db.or_(Announcement.title.contains(search), Announcement.content.contains(search)))
    announcements = q.order_by(Announcement.created_at.desc()).all()
    return export_excel(
        "公告列表",
        ["标题", "内容", "发布人", "发布时间"],
        [[a.title, a.content, a.user.username, a.created_at.strftime("%Y-%m-%d %H:%M")] for a in announcements],
    )


@bp.route("/announcement/add", methods=["GET", "POST"])
@role_required("admin", "dorm_manager")
def announcement_add():
    if request.method == "POST":
        a = Announcement(
            title=request.form["title"],
            content=request.form["content"],
            user_id=session["user_id"],
        )
        db.session.add(a)
        db.session.commit()
        log_operation(f"发布公告「{a.title}」", "announcement", a.id)
        flash("公告发布成功", "success")
        return redirect(url_for("main.announcement_list"))
    return render_template("announcement_form.html", announcement=None)


@bp.route("/announcement/<int:aid>/edit", methods=["GET", "POST"])
@role_required("admin", "dorm_manager")
def announcement_edit(aid):
    a = Announcement.query.get_or_404(aid)
    if request.method == "POST":
        a.title = request.form["title"]
        a.content = request.form["content"]
        db.session.commit()
        log_operation(f"修改公告「{a.title}」", "announcement", a.id)
        flash("公告修改成功", "success")
        return redirect(url_for("main.announcement_list"))
    return render_template("announcement_form.html", announcement=a)


@bp.route("/announcement/<int:aid>/delete", methods=["POST"])
@role_required("admin", "dorm_manager")
def announcement_delete(aid):
    a = Announcement.query.get_or_404(aid)
    title = a.title
    db.session.delete(a)
    db.session.commit()
    log_operation(f"删除公告「{title}」", "announcement", aid)
    flash("公告删除成功", "success")
    return redirect(url_for("main.announcement_list"))


# ============================================================
# 学生门户
# ============================================================

@bp.route("/my/accommodation")
@login_required
def my_accommodation():
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student:
        flash("未关联学生信息", "warning")
        return redirect(url_for("main.index"))
    acc = Accommodation.query.options(
        db.joinedload(Accommodation.room).joinedload(Room.building)
    ).filter_by(student_id=student.id, status="入住").first()
    roommates = []
    available_rooms = []
    if acc:
        roommates = Accommodation.query.options(
            db.joinedload(Accommodation.student)
        ).filter(
            Accommodation.room_id == acc.room_id,
            Accommodation.status == "入住",
            Accommodation.student_id != student.id,
        ).all()
        building_id = acc.room.building_id
        available_rooms = Room.query.filter(
            Room.building_id == building_id,
            Room.id != acc.room_id,
            Room.occupied < Room.capacity,
        ).order_by(Room.room_number).all()
    return render_template("my_accommodation.html", acc=acc, roommates=roommates, available_rooms=available_rooms)


@bp.route("/my/repairs", methods=["GET", "POST"])
@login_required
def my_repairs():
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student:
        flash("未关联学生信息", "warning")
        return redirect(url_for("main.index"))
    if request.method == "POST":
        filename = None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            filename = save_upload_file(file, current_app.config["UPLOAD_FOLDER"])
        r = Repair(
            student_id=student.id,
            room_id=request.form["room_id"],
            description=request.form["description"],
            image=filename,
            status="待处理",
            report_date=date.today(),
        )
        db.session.add(r)
        db.session.commit()
        flash("报修提交成功", "success")
        return redirect(url_for("main.my_repairs"))
    repairs = Repair.query.filter_by(student_id=student.id).order_by(Repair.report_date.desc()).all()
    my_rooms = Room.query.join(Accommodation).filter(
        Accommodation.student_id == student.id,
        Accommodation.status == "入住",
    ).all()
    return render_template("my_repairs.html", repairs=repairs, my_rooms=my_rooms)


@bp.route("/my/repairs/<int:rid>/cancel", methods=["POST"])
@login_required
def my_repair_cancel(rid):
    r = Repair.query.get_or_404(rid)
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student or r.student_id != student.id:
        flash("无权操作", "danger")
        return redirect(url_for("main.my_repairs"))
    if r.status != "待处理":
        flash("仅可撤销待处理状态的报修", "warning")
        return redirect(url_for("main.my_repairs"))
    r.status = "已撤销"
    db.session.commit()
    flash("报修已撤销", "success")
    return redirect(url_for("main.my_repairs"))


@bp.route("/my/fees")
@login_required
def my_fees():
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student:
        flash("未关联学生信息", "warning")
        return redirect(url_for("main.index"))
    fees = Fee.query.filter_by(student_id=student.id).order_by(Fee.due_date.desc()).all()
    return render_template("my_fees.html", fees=fees)


@bp.route("/my/visitors", methods=["GET", "POST"])
@login_required
def my_visitors():
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student:
        flash("未关联学生信息", "warning")
        return redirect(url_for("main.index"))
    if request.method == "POST":
        id_card = request.form.get("id_card", "").strip()
        if not re.match(r"^\d{17}[\dXx]$", id_card):
            flash("身份证号格式不正确（18位）", "warning")
            return redirect(url_for("main.my_visitors"))
        v = Visitor(
            student_id=student.id,
            visitor_name=request.form["visitor_name"],
            id_card=id_card,
            reason=request.form.get("reason"),
            visit_date=request.form["visit_date"],
            leave_date=request.form.get("leave_date") or None,
        )
        db.session.add(v)
        db.session.commit()
        flash("访客登记成功", "success")
        return redirect(url_for("main.my_visitors"))
    visitors = Visitor.query.filter_by(student_id=student.id).order_by(Visitor.visit_date.desc()).all()
    return render_template("my_visitors.html", visitors=visitors)


@bp.route("/my/profile", methods=["GET", "POST"])
@login_required
def my_profile():
    student = Student.query.filter_by(user_id=session["user_id"]).first()
    if not student:
        flash("未关联学生信息", "warning")
        return redirect(url_for("main.index"))
    if request.method == "POST":
        student.phone = request.form.get("phone")
        db.session.commit()
        flash("个人信息已更新", "success")
        return redirect(url_for("main.my_profile"))
    return render_template("my_profile.html", student=student)


@bp.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
