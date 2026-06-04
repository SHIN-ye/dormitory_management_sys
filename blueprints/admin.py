from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from models import db, User, Building, Announcement, OperationLog, CheckoutRequest, TransferRequest
from utils import role_required, log_operation, export_excel

# 用户管理, 操作日志
bp = Blueprint("admin", __name__)


# ============================================================
# 用户管理
# ============================================================

def _build_user_query(search):
    q = User.query
    if search:
        q = q.filter(User.username.contains(search))
    return q.order_by(User.id)


@bp.route("/users")
@role_required("admin")
def user_list():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    pagination = _build_user_query(search).paginate(page=page, per_page=15)
    return render_template("users.html", users=pagination.items, pagination=pagination, search=search)


@bp.route("/users/export")
@role_required("admin")
def user_export():
    search = request.args.get("search", "").strip()
    q = User.query.options(db.joinedload(User.building))
    if search:
        q = q.filter(User.username.contains(search))
    users = q.order_by(User.id).all()
    return export_excel(
        "用户列表",
        ["ID", "用户名", "角色", "管辖宿舍楼"],
        [[u.id, u.username, u.role, u.building.name if u.building else "-"] for u in users],
    )


@bp.route("/user/add", methods=["GET", "POST"])
@role_required("admin")
def user_add():
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if len(password) < 4:
            flash("密码至少4位", "warning")
            return render_template("user_form.html", user=None, buildings=Building.query.all())
        building_id = request.form.get("building_id")
        u = User(
            username=request.form["username"],
            password=generate_password_hash(password),
            role=request.form["role"],
            building_id=int(building_id) if building_id and request.form["role"] == "dorm_manager" else None,
        )
        db.session.add(u)
        db.session.commit()
        log_operation(f"添加用户「{u.username}」({u.role})", "user", u.id)
        flash("用户添加成功", "success")
        return redirect(url_for("admin.user_list"))
    buildings = Building.query.all()
    return render_template("user_form.html", user=None, buildings=buildings)


@bp.route("/user/<int:uid>/edit", methods=["GET", "POST"])
@role_required("admin")
def user_edit(uid):
    u = User.query.get_or_404(uid)
    if request.method == "POST":
        u.username = request.form["username"]
        new_pw = request.form.get("password", "").strip()
        if new_pw:
            if len(new_pw) < 4:
                flash("密码至少4位", "warning")
                return render_template("user_form.html", user=u, buildings=Building.query.all())
            u.password = generate_password_hash(new_pw)
        u.role = request.form["role"]
        building_id = request.form.get("building_id")
        u.building_id = int(building_id) if building_id and request.form["role"] == "dorm_manager" else None
        db.session.commit()
        log_operation(f"修改用户「{u.username}」({u.role})", "user", u.id)
        flash("用户修改成功", "success")
        return redirect(url_for("admin.user_list"))
    buildings = Building.query.all()
    return render_template("user_form.html", user=u, buildings=buildings)


@bp.route("/user/<int:uid>/delete", methods=["POST"])
@role_required("admin")
def user_delete(uid):
    if uid == session["user_id"]:
        flash("不能删除自己", "danger")
        return redirect(url_for("admin.user_list"))
    u = User.query.get_or_404(uid)
    uname, urole = u.username, u.role
    if u.student_profile:
        u.student_profile.user_id = None
    CheckoutRequest.query.filter_by(reviewed_by=uid).update({"reviewed_by": None})
    TransferRequest.query.filter_by(reviewed_by=uid).update({"reviewed_by": None})
    Announcement.query.filter_by(user_id=uid).delete()
    OperationLog.query.filter_by(user_id=uid).delete()
    db.session.flush()
    db.session.delete(u)
    db.session.commit()
    log_operation(f"删除用户「{uname}」({urole})", "user", uid)
    flash("用户删除成功", "success")
    return redirect(url_for("admin.user_list"))


# ============================================================
# 操作日志
# ============================================================

@bp.route("/operation-logs")
@role_required("admin")
def operation_log_list():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    q = OperationLog.query.options(db.joinedload(OperationLog.user))
    if search:
        q = q.join(OperationLog.user).filter(
            db.or_(User.username.contains(search), OperationLog.action.contains(search))
        )
    pagination = q.order_by(OperationLog.created_at.desc()).paginate(page=page, per_page=20)
    return render_template("operation_logs.html", logs=pagination.items, pagination=pagination, search=search)


@bp.route("/operation-logs/export")
@role_required("admin")
def operation_log_export():
    search = request.args.get("search", "").strip()
    q = OperationLog.query.options(db.joinedload(OperationLog.user))
    if search:
        q = q.join(OperationLog.user).filter(
            db.or_(User.username.contains(search), OperationLog.action.contains(search))
        )
    logs = q.order_by(OperationLog.created_at.desc()).all()
    return export_excel(
        "操作日志",
        ["时间", "操作人", "角色", "操作内容", "IP地址"],
        [[log.created_at.strftime("%Y-%m-%d %H:%M:%S"), log.user.username,
          log.user.role, log.action, log.ip_address or "-"] for log in logs],
    )
