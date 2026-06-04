from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from utils import login_required, log_operation

bp = Blueprint("auth", __name__)

# 登录/登出/修改密码
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash("登录成功", "success")
            return redirect(url_for("main.index"))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old_pw = request.form.get("old_password", "").strip()
        new_pw = request.form.get("new_password", "").strip()
        confirm_pw = request.form.get("confirm_password", "").strip()
        user = db.session.get(User, session["user_id"])
        if not user or not check_password_hash(user.password, old_pw):
            flash("原密码错误", "danger")
        elif len(new_pw) < 4:
            flash("新密码至少4位", "warning")
        elif new_pw != confirm_pw:
            flash("两次新密码不一致", "warning")
        else:
            user.password = generate_password_hash(new_pw)
            db.session.commit()
            log_operation("修改密码", "user", session["user_id"])
            flash("密码修改成功", "success")
            return redirect(url_for("main.index"))
    return render_template("change_password.html")
