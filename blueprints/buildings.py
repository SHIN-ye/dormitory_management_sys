from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Building, Room
from utils import role_required, log_operation, export_excel

# 宿舍楼CRUD、房间CRUD
bp = Blueprint("buildings", __name__)


# ============================================================
# 宿舍楼
# ============================================================

def _build_building_query(search):
    q = Building.query
    if search:
        q = q.filter(db.or_(
            Building.name.contains(search),
            Building.address.contains(search),
            Building.manager.contains(search),
        ))
    return q.order_by(Building.id)


@bp.route("/buildings")
@role_required("admin")
def building_list():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    pagination = _build_building_query(search).paginate(page=page, per_page=15)
    return render_template("buildings.html", buildings=pagination.items, pagination=pagination, search=search)


@bp.route("/buildings/export")
@role_required("admin")
def building_export():
    search = request.args.get("search", "").strip()
    buildings = _build_building_query(search).all()
    return export_excel(
        "宿舍楼列表",
        ["名称", "层数", "地址", "管理员"],
        [[b.name, f"{b.floors}层", b.address or "-", b.manager or "-"] for b in buildings],
    )


@bp.route("/building/add", methods=["GET", "POST"])
@role_required("admin")
def building_add():
    if request.method == "POST":
        floors = int(request.form.get("floors", 6))
        rooms_per_floor = int(request.form.get("rooms_per_floor", 3))
        if floors < 1:
            flash("楼层数至少为1", "warning")
            return render_template("building_form.html", building=None)
        if rooms_per_floor < 1 or rooms_per_floor > 99:
            flash("每层房间数应在1~99之间", "warning")
            return render_template("building_form.html", building=None)

        # 防止重名
        if Building.query.filter_by(name=request.form["name"].strip()).first():
            flash("宿舍楼名称已存在", "warning")
            return render_template("building_form.html", building=None)

        b = Building(
            name=request.form["name"].strip(),
            floors=floors,
            address=request.form.get("address", "").strip(),
            manager=request.form.get("manager", "").strip(),
        )
        db.session.add(b)
        db.session.flush()  # 拿到 b.id

        # 自动生成所有房间（每层 rooms_per_floor 间）
        suffix_width = len(str(rooms_per_floor))
        for floor in range(1, floors + 1):
            for rn_idx in range(1, rooms_per_floor + 1):
                room_number = f"{floor}{str(rn_idx).zfill(suffix_width)}"
                db.session.add(Room(
                    room_number=room_number,
                    building_id=b.id,
                    capacity=4,
                    occupied=0,
                    room_type="四人间",
                    price=1200.0,
                ))

        db.session.commit()
        total_rooms = floors * rooms_per_floor
        log_operation(f"添加宿舍楼「{b.name}」({floors}层×{rooms_per_floor}间={total_rooms}间)", "building", b.id)
        flash(f"添加成功，已自动生成 {total_rooms} 个房间", "success")
        return redirect(url_for("buildings.building_list"))
    return render_template("building_form.html", building=None)


@bp.route("/building/<int:bid>/edit", methods=["GET", "POST"])
@role_required("admin")
def building_edit(bid):
    b = Building.query.get_or_404(bid)
    if request.method == "POST":
        floors = int(request.form.get("floors", 6))
        if floors < 1:
            flash("楼层数至少为1", "warning")
            return render_template("building_form.html", building=b)
        b.name = request.form["name"]
        b.floors = floors
        b.address = request.form.get("address", "")
        b.manager = request.form.get("manager", "")
        db.session.commit()
        log_operation(f"修改宿舍楼「{b.name}」", "building", b.id)
        flash("修改成功", "success")
        return redirect(url_for("buildings.building_list"))
    return render_template("building_form.html", building=b)


@bp.route("/building/<int:bid>/delete", methods=["POST"])
@role_required("admin")
def building_delete(bid):
    b = Building.query.get_or_404(bid)
    name = b.name
    db.session.delete(b)
    db.session.commit()
    log_operation(f"删除宿舍楼「{name}」", "building", bid)
    flash("删除成功", "success")
    return redirect(url_for("buildings.building_list"))


# ============================================================
# 房间（只读管理：禁止增删，仅可编辑房型/容量/价格，可禁用/启用）
# ============================================================

def _build_room_query(search, bid):
    q = Room.query
    if bid:
        q = q.filter_by(building_id=bid)
    if search:
        q = q.filter(Room.room_number.contains(search))
    return q.order_by(Room.building_id, Room.room_number)


@bp.route("/rooms")
@role_required("admin")
def room_list():
    search = request.args.get("search", "").strip()
    bid = request.args.get("building_id", type=int)
    page = request.args.get("page", 1, type=int)
    pagination = _build_room_query(search, bid).paginate(page=page, per_page=15)
    buildings = Building.query.all()
    return render_template("rooms.html", rooms=pagination.items, buildings=buildings, current_building=bid, pagination=pagination, search=search)


@bp.route("/rooms/export")
@role_required("admin")
def room_export():
    search = request.args.get("search", "").strip()
    bid = request.args.get("building_id", type=int)
    rooms = _build_room_query(search, bid).all()
    return export_excel(
        "房间列表",
        ["宿舍楼", "房间号", "类型", "容量", "已住", "价格(元/年)", "状态"],
        [[r.building.name, r.room_number, r.room_type, r.capacity, r.occupied, r.price,
          "可用" if r.is_active else "已禁用"] for r in rooms],
    )


@bp.route("/room/<int:rid>/edit", methods=["GET", "POST"])
@role_required("admin")
def room_edit(rid):
    """仅允许修改房型、容量、价格（房间号由建筑结构决定不可改）"""
    r = Room.query.get_or_404(rid)
    if request.method == "POST":
        capacity = int(request.form.get("capacity", 4))
        if capacity < 1:
            flash("房间容量至少为1", "warning")
            return render_template("room_form.html", room=r)
        if capacity < r.occupied:
            flash(f"容量({capacity})不能小于已住人数({r.occupied})", "warning")
            return render_template("room_form.html", room=r)
        r.capacity = capacity
        r.room_type = request.form.get("room_type", "四人间")
        r.price = float(request.form.get("price", 1200.0))
        db.session.commit()
        log_operation(f"修改房间「{r.building.name}-{r.room_number}」", "room", r.id)
        flash("修改成功", "success")
        return redirect(url_for("buildings.room_list"))
    return render_template("room_form.html", room=r)


@bp.route("/room/<int:rid>/toggle-active", methods=["POST"])
@role_required("admin")
def room_toggle_active(rid):
    """禁用/启用房间（禁用后该房间不可用于入住和调换）"""
    r = Room.query.get_or_404(rid)
    r.is_active = not r.is_active
    db.session.commit()
    action = "启用" if r.is_active else "禁用"
    log_operation(f"{action}房间「{r.building.name}-{r.room_number}」", "room", r.id)
    flash(f"房间「{r.building.name}-{r.room_number}」已{action}", "success")
    return redirect(url_for("buildings.room_list"))
