from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Building, Room
from utils import role_required, log_operation, export_excel

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
        if floors < 1:
            flash("楼层数至少为1", "warning")
            return render_template("building_form.html", building=None)
        b = Building(
            name=request.form["name"],
            floors=floors,
            address=request.form.get("address", ""),
            manager=request.form.get("manager", ""),
        )
        db.session.add(b)
        db.session.commit()
        log_operation(f"添加宿舍楼「{b.name}」", "building", b.id)
        flash("添加成功", "success")
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
# 房间
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
        ["宿舍楼", "房间号", "类型", "容量", "已住", "价格(元/年)"],
        [[r.building.name, r.room_number, r.room_type, r.capacity, r.occupied, r.price] for r in rooms],
    )


@bp.route("/room/add", methods=["GET", "POST"])
@role_required("admin")
def room_add():
    if request.method == "POST":
        capacity = int(request.form.get("capacity", 4))
        if capacity < 1:
            flash("房间容量至少为1", "warning")
            return render_template("room_form.html", room=None, buildings=Building.query.all())
        r = Room(
            room_number=request.form["room_number"],
            building_id=request.form["building_id"],
            capacity=capacity,
            occupied=request.form.get("occupied", 0),
            room_type=request.form.get("room_type", "四人间"),
            price=request.form.get("price", 1200.0),
        )
        db.session.add(r)
        db.session.commit()
        log_operation(f"添加房间「{r.room_number}」", "room", r.id)
        flash("添加成功", "success")
        return redirect(url_for("buildings.room_list"))
    buildings = Building.query.all()
    return render_template("room_form.html", room=None, buildings=buildings)


@bp.route("/room/<int:rid>/edit", methods=["GET", "POST"])
@role_required("admin")
def room_edit(rid):
    r = Room.query.get_or_404(rid)
    if request.method == "POST":
        capacity = int(request.form.get("capacity", 4))
        if capacity < 1:
            flash("房间容量至少为1", "warning")
            return render_template("room_form.html", room=r, buildings=Building.query.all())
        r.room_number = request.form["room_number"]
        r.building_id = request.form["building_id"]
        r.capacity = capacity
        r.occupied = request.form.get("occupied", 0)
        r.room_type = request.form.get("room_type", "四人间")
        r.price = request.form.get("price", 1200.0)
        db.session.commit()
        log_operation(f"修改房间「{r.room_number}」", "room", r.id)
        flash("修改成功", "success")
        return redirect(url_for("buildings.room_list"))
    buildings = Building.query.all()
    return render_template("room_form.html", room=r, buildings=buildings)


@bp.route("/room/<int:rid>/delete", methods=["POST"])
@role_required("admin")
def room_delete(rid):
    r = Room.query.get_or_404(rid)
    rn = r.room_number
    db.session.delete(r)
    db.session.commit()
    log_operation(f"删除房间「{rn}」", "room", rid)
    flash("删除成功", "success")
    return redirect(url_for("buildings.room_list"))
