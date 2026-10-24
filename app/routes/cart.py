from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..store import col, next_id
from ..utils import current_user_id

bp=Blueprint("cart",__name__)

def line_out(line):
    item=col("menu_items").find_one({"id":line["menu_item_id"]})
    if not item: return None
    price=float(item["price"]); qty=line["quantity"]
    return {"cart_item_id":line["id"],"menu_item_id":item["id"],"name":item["name"],
            "price":price,"quantity":qty,"line_total":round(price*qty,2),
            "in_stock":bool(item.get("is_available",True) and item.get("stock",0)>=qty and item.get("stock",0)>0),
            "image_url":item.get("image_url")}

def cart_response(uid,status=200,**extra):
    lines=[line_out(x) for x in col("cart_items").find({"user_id":uid}).sort("id",1)]
    lines=[x for x in lines if x]
    return jsonify(items=lines,item_count=len(lines),total=round(sum(x["line_total"] for x in lines),2),**extra),status

def positive_int(v): return isinstance(v,int) and not isinstance(v,bool) and v>0

@bp.get("")
@jwt_required()
def view_cart(): return cart_response(current_user_id())

@bp.post("/items")
@jwt_required()
def add_to_cart():
    uid=current_user_id(); data=request.get_json(silent=True) or {}
    item_id=data.get("menu_item_id"); qty=data.get("quantity",1)
    if not isinstance(item_id,int) or not positive_int(qty):
        return jsonify(error="menu_item_id and a positive integer quantity are required"),400
    item=col("menu_items").find_one({"id":item_id,"is_available":True})
    if not item: return jsonify(error="Menu item not found"),404
    existing=col("cart_items").find_one({"user_id":uid,"menu_item_id":item_id})
    new_qty=qty+(existing["quantity"] if existing else 0)
    if item.get("stock",0)<=0 or new_qty>item.get("stock",0):
        return jsonify(error=f"Only {item.get('stock',0)} of '{item['name']}' left in stock"),409
    if existing: col("cart_items").update_one({"id":existing["id"]},{"$set":{"quantity":new_qty}})
    else: col("cart_items").insert_one({"id":next_id("cart_items"),"user_id":uid,"menu_item_id":item_id,"quantity":qty})
    return cart_response(uid,201,message="Added to cart")

@bp.put("/items/<int:menu_item_id>")
@jwt_required()
def update_cart_item(menu_item_id):
    uid=current_user_id(); data=request.get_json(silent=True) or {}; qty=data.get("quantity")
    if not positive_int(qty): return jsonify(error="quantity must be a positive integer"),400
    line=col("cart_items").find_one({"user_id":uid,"menu_item_id":menu_item_id})
    item=col("menu_items").find_one({"id":menu_item_id,"is_available":True})
    if not line or not item: return jsonify(error="Item not in cart or no longer available"),404
    if qty>item.get("stock",0): return jsonify(error=f"Only {item.get('stock',0)} left in stock"),409
    col("cart_items").update_one({"id":line["id"]},{"$set":{"quantity":qty}})
    return cart_response(uid,message="Cart updated")

@bp.delete("/items/<int:menu_item_id>")
@jwt_required()
def remove_cart_item(menu_item_id):
    col("cart_items").delete_one({"user_id":current_user_id(),"menu_item_id":menu_item_id})
    return cart_response(current_user_id(),message="Item removed")

@bp.delete("")
@jwt_required()
def clear_cart():
    col("cart_items").delete_many({"user_id":current_user_id()})
    return cart_response(current_user_id(),message="Cart cleared")
