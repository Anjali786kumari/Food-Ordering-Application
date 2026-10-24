from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..store import col, next_id, now
from ..utils import current_user_id

bp=Blueprint("orders",__name__)
CANCELLABLE={"PLACED","CONFIRMED"}
STEPS={"PLACED","CONFIRMED","PREPARING","OUT_FOR_DELIVERY","DELIVERED","CANCELLED"}

def order_out(order,with_user=False):
    d={k:order.get(k) for k in ("id","status","payment_method","payment_status","total_amount","delivery_address","created_at","updated_at","items")}
    enriched = []
    for line in d.get("items", []):
        entry = dict(line)
        menu_item = col("menu_items").find_one({"id": entry.get("menu_item_id")}, {"image_url": 1})
        entry["image_url"] = menu_item.get("image_url") if menu_item else None
        enriched.append(entry)
        d["items"] = enriched
    if with_user:
        u=col("users").find_one({"id":order["user_id"]})
        d["customer"]={"id":u["id"],"name":u["name"],"email":u["email"]} if u else {"id":order["user_id"],"name":"Unknown"}
    return d

def restore_stock_and_cancel(order):
    for line in order.get("items",[]):
        col("menu_items").update_one({"id":line["menu_item_id"]},{"$inc":{"stock":line["quantity"]}})
    order["status"]="CANCELLED"
    if order.get("payment_status")=="PAID": order["payment_status"]="REFUNDED"
    order["updated_at"]=now()
    col("orders").update_one({"id":order["id"]},{"$set":{"status":order["status"],"payment_status":order["payment_status"],"updated_at":order["updated_at"]}})

@bp.post("")
@jwt_required()
def place_order():
    uid=current_user_id(); data=request.get_json(silent=True) or {}
    address=(data.get("delivery_address") or "").strip(); method=(data.get("payment_method") or "COD").upper()
    if not address: return jsonify(error="delivery_address is required"),400
    if method not in ("COD","ONLINE"): return jsonify(error="payment_method must be COD or ONLINE"),400
    cart=list(col("cart_items").find({"user_id":uid}))
    if not cart: return jsonify(error="Your cart is empty"),400
    items=[]; total=0; problems=[]
    for line in cart:
        m=col("menu_items").find_one({"id":line["menu_item_id"],"is_available":True})
        if not m: problems.append({"menu_item_id":line["menu_item_id"],"reason":"No longer available"}); continue
        if m.get("stock",0)<line["quantity"]:
            problems.append({"menu_item_id":m["id"],"name":m["name"],"reason":f"Only {m.get('stock',0)} left, you asked for {line['quantity']}"}); continue
        price=float(m["price"]); qty=line["quantity"]; total+=price*qty
        items.append({"menu_item_id": m["id"],"name": m["name"],"price": price,"quantity": qty,"line_total": round(price * qty, 2),"image_url": m.get("image_url")})
    if problems: return jsonify(error="Some items are unavailable",problems=problems),409
    # Atomic decrement prevents stock from going negative even if requests overlap.
    for line in items:
        result=col("menu_items").update_one({"id":line["menu_item_id"],"stock":{"$gte":line["quantity"]},"is_available":True},{"$inc":{"stock":-line["quantity"]}})
        if not result.modified_count:
            for done in items:
                if done is line: break
                col("menu_items").update_one({"id":done["menu_item_id"]},{"$inc":{"stock":done["quantity"]}})
            return jsonify(error=f"Stock changed for {line['name']}; refresh your cart"),409
    order={"id":next_id("orders"),"user_id":uid,"total_amount":round(total,2),"status":"PLACED",
           "payment_method":method,"payment_status":"PENDING","delivery_address":address,
           "created_at":now(),"updated_at":now(),"items":items}
    col("orders").insert_one(order); col("cart_items").delete_many({"user_id":uid})
    return jsonify(message="Order placed. Online payment is simulated." if method=="ONLINE" else "Order placed (Cash on Delivery).",order=order_out(order)),201

@bp.get("")
@jwt_required()
def my_orders():
    query={"user_id":current_user_id()}; status=request.args.get("status")
    if status: query["status"]=status.upper()
    orders=list(col("orders").find(query).sort("created_at",-1))
    return jsonify(count=len(orders),orders=[order_out(o) for o in orders])

@bp.get("/<int:order_id>")
@jwt_required()
def track_order(order_id):
    o=col("orders").find_one({"id":order_id,"user_id":current_user_id()})
    if not o: return jsonify(error="Order not found"),404
    return jsonify(order=order_out(o))

@bp.post("/<int:order_id>/pay")
@jwt_required()
def pay_order(order_id):
    o=col("orders").find_one({"id":order_id,"user_id":current_user_id()})
    if not o: return jsonify(error="Order not found"),404
    if o["payment_method"]!="ONLINE": return jsonify(error="This order is Cash on Delivery; no online payment needed"),400
    if o["status"]=="CANCELLED": return jsonify(error="Cannot pay for a cancelled order"),409
    if o["payment_status"]=="PAID": return jsonify(error="Order is already paid"),409
    col("orders").update_one({"id":order_id},{"$set":{"payment_status":"PAID","status":"CONFIRMED" if o["status"]=="PLACED" else o["status"],"updated_at":now()}})
    o.update(payment_status="PAID",status="CONFIRMED" if o["status"]=="PLACED" else o["status"])
    return jsonify(message="Payment successful (simulated)",order=order_out(o))

@bp.post("/<int:order_id>/cancel")
@jwt_required()
def cancel_order(order_id):
    o=col("orders").find_one({"id":order_id,"user_id":current_user_id()})
    if not o: return jsonify(error="Order not found"),404
    if o["status"] not in CANCELLABLE: return jsonify(error=f"Order cannot be cancelled once it is {o['status']}"),409
    restore_stock_and_cancel(o)
    return jsonify(message="Order cancelled",order=order_out(o))
