from flask import Blueprint, jsonify, request
from ..store import col, now
from ..utils import role_required
from .orders import order_out, restore_stock_and_cancel

bp=Blueprint("admin",__name__)
TRANSITIONS={"PLACED":{"CONFIRMED","CANCELLED"},"CONFIRMED":{"PREPARING","CANCELLED"},
"PREPARING":{"OUT_FOR_DELIVERY","CANCELLED"},"OUT_FOR_DELIVERY":{"DELIVERED"},"DELIVERED":set(),"CANCELLED":set()}
STATUSES=list(TRANSITIONS)

@bp.get("/orders")
@role_required("admin")
def all_orders():
    q={}; status=request.args.get("status"); uid=request.args.get("user_id",type=int)
    if status:q["status"]=status.upper()
    if uid:q["user_id"]=uid
    orders=list(col("orders").find(q).sort("created_at",-1))
    return jsonify(count=len(orders),orders=[order_out(o,True) for o in orders])

@bp.put("/orders/<int:order_id>/status")
@role_required("admin")
def update_order_status(order_id):
    o=col("orders").find_one({"id":order_id})
    if not o:return jsonify(error="Order not found"),404
    status=((request.get_json(silent=True) or {}).get("status") or "").upper()
    if status not in STATUSES:return jsonify(error=f"status must be one of {STATUSES}"),400
    if status not in TRANSITIONS[o["status"]]:return jsonify(error=f"Cannot move order from {o['status']} to {status}"),409
    if status=="CANCELLED":restore_stock_and_cancel(o)
    else:
        updates={"status":status,"updated_at":now()}
        if status=="DELIVERED" and o["payment_method"]=="COD":updates["payment_status"]="PAID"
        col("orders").update_one({"id":order_id},{"$set":updates});o.update(updates)
    return jsonify(message=f"Order marked {o['status']}",order=order_out(o,True))

@bp.get("/inventory")
@role_required("admin")
def inventory():
    low=request.args.get("low",type=int); q={"stock":{"$lte":low}} if low is not None else {}
    items=list(col("menu_items").find(q).sort([("stock",1),("name",1)]))
    from ..routes.menu import menu_out
    return jsonify(count=len(items),items=[menu_out(i,True) for i in items])

@bp.put("/inventory/<int:item_id>")
@role_required("admin")
def update_inventory(item_id):
    item=col("menu_items").find_one({"id":item_id})
    if not item:return jsonify(error="Menu item not found"),404
    data=request.get_json(silent=True) or {}; updates={}
    if "stock" in data:
        if not isinstance(data["stock"],int) or isinstance(data["stock"],bool) or data["stock"]<0:return jsonify(error="stock must be a non-negative integer"),400
        updates["stock"]=data["stock"]
    elif "adjust" in data:
        if not isinstance(data["adjust"],int) or isinstance(data["adjust"],bool):return jsonify(error="adjust must be an integer"),400
        if item.get("stock",0)+data["adjust"]<0:return jsonify(error="Stock cannot go below zero"),400
        updates["stock"]=item.get("stock",0)+data["adjust"]
    elif "is_available" not in data:return jsonify(error="Provide 'stock', 'adjust' or 'is_available'"),400
    if "is_available" in data:updates["is_available"]=bool(data["is_available"])
    col("menu_items").update_one({"id":item_id},{"$set":updates});item.update(updates)
    from ..routes.menu import menu_out
    return jsonify(message="Inventory updated",item=menu_out(item,True))
