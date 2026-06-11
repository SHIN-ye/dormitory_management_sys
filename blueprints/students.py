import re
from datetime import date, datetime
import openpyxl
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from models import db, Student, User
from utils import role_required, log_operation, export_excel

# 学生CRUD、批量导入（Excel）
bp = Blueprint("students", __name__)


def _build_student_query(search):
    q = Student.query
    if search:
        q = q.filter(db.or_(
            Student.sno.contains(search),
            Student.name.contains(search),
            Student.major.contains(search),
            Student.class_name.contains(search),
            Student.phone.contains(search),
        ))
    return q.order_by(Student.sno)


@bp.route("/students")
@role_required("admin")
def student_list():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    pagination = _build_student_query(search).paginate(page=page, per_page=15)
    return render_template("students.html", students=pagination.items, pagination=pagination, search=search)


@bp.route("/students/export")
@role_required("admin")
def student_export():
    search = request.args.get("search", "").strip()
    students = _build_student_query(search).all()
    return export_excel(
        "学生列表",
        ["学号", "姓名", "性别", "出生日期", "手机", "专业", "班级"],
        [[s.sno, s.name, s.gender or "-", str(s.birth) if s.birth else "-",
          s.phone or "-", s.major or "-", s.class_name or "-"] for s in students],
    )


@bp.route("/student/add", methods=["GET", "POST"])
@role_required("admin")
def student_add():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        if phone and not re.match(r"^1\d{10}$", phone):
            flash("手机号格式不正确（11位数字，以1开头）", "warning")
            return render_template("student_form.html", student=None)
        s = Student(
            sno=request.form["sno"],
            name=request.form["name"],
            gender=request.form.get("gender"),
            birth=request.form.get("birth") or None,
            phone=phone or None,
            major=request.form.get("major"),
            class_name=request.form.get("class_name"),
        )
        db.session.add(s)
        db.session.commit()
        log_operation(f"添加学生「{s.name}」({s.sno})", "student", s.id)
        flash("添加成功", "success")
        return redirect(url_for("students.student_list"))
    return render_template("student_form.html", student=None)


@bp.route("/student/<int:sid>/edit", methods=["GET", "POST"])
@role_required("admin")
def student_edit(sid):
    s = Student.query.get_or_404(sid)
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        if phone and not re.match(r"^1\d{10}$", phone):
            flash("手机号格式不正确（11位数字，以1开头）", "warning")
            return render_template("student_form.html", student=s)
        s.sno = request.form["sno"]
        s.name = request.form["name"]
        s.gender = request.form.get("gender")
        s.birth = request.form.get("birth") or None
        s.phone = phone or None
        s.major = request.form.get("major")
        s.class_name = request.form.get("class_name")
        db.session.commit()
        log_operation(f"修改学生「{s.name}」({s.sno})", "student", s.id)
        flash("修改成功", "success")
        return redirect(url_for("students.student_list"))
    return render_template("student_form.html", student=s)


@bp.route("/student/<int:sid>/delete", methods=["POST"])
@role_required("admin")
def student_delete(sid):
    s = Student.query.get_or_404(sid)
    name, sno = s.name, s.sno
    db.session.delete(s)
    db.session.commit()
    log_operation(f"删除学生「{name}」({sno})", "student", sid)
    flash("删除成功", "success")
    return redirect(url_for("students.student_list"))


@bp.route("/students/generate-accounts", methods=["POST"])
@role_required("admin")
def generate_accounts():
    """为所有未绑定登录账号的学生批量生成初始账号
    默认用户名 = 学号，默认密码 = 学号（首次登录后可修改）
    """
    students_without_user = Student.query.filter(Student.user_id.is_(None)).all()
    if not students_without_user:
        flash("所有学生都已绑定登录账号", "info")
        return redirect(url_for("students.student_list"))

    created = 0
    skipped = 0
    errors = []
    for s in students_without_user:
        # 检查学号是否已被占用为用户名
        existing = User.query.filter_by(username=s.sno).first()
        if existing:
            skipped += 1
            errors.append(f"{s.sno} {s.name}：用户名已存在")
            continue
        u = User(
            username=s.sno,
            password=generate_password_hash(s.sno),
            role="student",
        )
        db.session.add(u)
        db.session.flush()
        s.user_id = u.id
        created += 1

    db.session.commit()
    log_operation(f"批量生成学生账号（{created}成功 {skipped}跳过 {len(errors)}错误）", "student")
    if created:
        flash(f"已为 {created} 名学生生成登录账号（用户名=学号，密码=学号），请提醒学生登录后修改密码", "success")
    if skipped:
        flash(f"{skipped} 名学生跳过（用户名已存在）", "warning")
    for err in errors:
        flash(f"跳过: {err}", "info")
    return redirect(url_for("students.student_list"))


@bp.route("/students/import", methods=["GET", "POST"])
@role_required("admin")
def student_import():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("请选择文件", "warning")
            return redirect(url_for("students.student_import"))

        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("xlsx", "xls"):
            flash("仅支持 .xlsx 或 .xls 格式", "danger")
            return redirect(url_for("students.student_import"))

        try:
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
        except Exception as e:
            flash(f"无法解析 Excel 文件: {e}", "danger")
            return redirect(url_for("students.student_import"))

        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not rows:
            flash("文件为空", "warning")
            return redirect(url_for("students.student_import"))

        headers = [str(h).strip() if h else "" for h in rows[0]]
        col_map = {}
        for i, h in enumerate(headers):
            if h in ("学号", "sno"):
                col_map["sno"] = i
            elif h in ("姓名", "name"):
                col_map["name"] = i
            elif h in ("性别", "gender"):
                col_map["gender"] = i
            elif h in ("出生日期", "birth"):
                col_map["birth"] = i
            elif h in ("手机", "phone"):
                col_map["phone"] = i
            elif h in ("专业", "major"):
                col_map["major"] = i
            elif h in ("班级", "class_name", "班级名称"):
                col_map["class_name"] = i

        if "sno" not in col_map or "name" not in col_map:
            flash("表头必须包含'学号'和'姓名'列", "danger")
            return redirect(url_for("students.student_import"))

        success = 0
        fail = 0
        errors = []
        seen_snos = set()

        for row_idx, row in enumerate(rows[1:], start=2):
            sno = str(row[col_map["sno"]]).strip() if row[col_map["sno"]] is not None else ""
            name = str(row[col_map["name"]]).strip() if row[col_map["name"]] is not None else ""

            if not sno or not name:
                fail += 1
                errors.append(f"第{row_idx}行: 学号或姓名为空")
                continue

            if sno in seen_snos:
                fail += 1
                errors.append(f"第{row_idx}行: 学号 {sno} 与文件中其他行重复")
                continue
            seen_snos.add(sno)

            if Student.query.filter_by(sno=sno).first():
                fail += 1
                errors.append(f"第{row_idx}行: 学号 {sno} 已存在")
                continue

            gender = str(row[col_map["gender"]]).strip() if "gender" in col_map and row[col_map["gender"]] is not None else None
            phone = str(row[col_map["phone"]]).strip() if "phone" in col_map and row[col_map["phone"]] is not None else None
            major = str(row[col_map["major"]]).strip() if "major" in col_map and row[col_map["major"]] is not None else None
            class_name = str(row[col_map["class_name"]]).strip() if "class_name" in col_map and row[col_map["class_name"]] is not None else None

            birth = None
            if "birth" in col_map and row[col_map["birth"]] is not None:
                raw = row[col_map["birth"]]
                if isinstance(raw, datetime):
                    birth = raw.date()
                elif isinstance(raw, date):
                    birth = raw
                elif isinstance(raw, str):
                    raw = raw.strip()
                    if raw:
                        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
                            try:
                                birth = datetime.strptime(raw, fmt).date()
                                break
                            except ValueError:
                                pass

            savepoint = db.session.begin_nested()
            try:
                s = Student(
                    sno=sno, name=name, gender=gender, birth=birth,
                    phone=phone, major=major, class_name=class_name,
                )
                db.session.add(s)
                db.session.flush()
            except Exception as e:
                savepoint.rollback()
                fail += 1
                errors.append(f"第{row_idx}行: 数据库错误 - {e}")
                continue

            success += 1

        db.session.commit()
        log_operation(f"批量导入学生（{success}成功 {fail}失败）", "student")
        results = {"success": success, "fail": fail, "errors": errors}
        return render_template("student_import.html", results=results)

    return render_template("student_import.html", results=None)
