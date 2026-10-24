from decimal import Decimal, InvalidOperation
from io import BytesIO
import base64
from PIL import Image, UnidentifiedImageError
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..store import col, next_id, now
from ..utils import role_required

bp=Blueprint("menu",__name__)

def menu_out(item, include_stock=False):
    d={"id":item["id"],"name":item["name"],"description":item.get("description",""),
       "category":item.get("category","General"),"price":float(item["price"]),
       "in_stock":bool(item.get("is_available",True) and item.get("stock",0)>0),
       "image_url":item.get("image_url")}
    if include_stock:
        d["stock"]=item.get("stock",0); d["is_available"]=item.get("is_available",True)
    return d

def parse_price(v):
    try:
        p=Decimal(str(v))
        return p if p>0 else None
    except (InvalidOperation,TypeError,ValueError):
        return None

@bp.get("")
def list_menu():
    query={"is_available":True}
    category=request.args.get("category")
    search=request.args.get("q")
    if category: query["category"]=category
    if search: query["name"]={"$regex":search,"$options":"i"}
    items=list(col("menu_items").find(query).sort([("category",1),("name",1)]))
    return jsonify(count=len(items),items=[menu_out(i) for i in items])

@bp.get("/<int:item_id>")
def get_item(item_id):
    item=col("menu_items").find_one({"id":item_id,"is_available":True})
    if not item: return jsonify(error="Menu item not found"),404
    return jsonify(item=menu_out(item))

@bp.post("")
@role_required("admin")
def create_item():
    data=request.get_json(silent=True) or {}
    name=(data.get("name") or "").strip()
    price=parse_price(data.get("price"))
    stock=data.get("stock",0)
    if not name: return jsonify(error="name is required"),400
    if price is None: return jsonify(error="price must be a positive number"),400
    if not isinstance(stock,int) or isinstance(stock,bool) or stock<0:
        return jsonify(error="stock must be a non-negative integer"),400
    item={"id":next_id("menu_items"),"name":name,"description":(data.get("description") or "").strip(),
          "category":(data.get("category") or "General").strip(),"price":float(price),
          "stock":stock,"is_available":bool(data.get("is_available",True)),
          "image_url":None,"created_at":now()}
    col("menu_items").insert_one(item)
    return jsonify(message="Menu item created",item=menu_out(item,True)),201

@bp.put("/<int:item_id>")
@role_required("admin")
def update_item(item_id):
    item=col("menu_items").find_one({"id":item_id})
    if not item: return jsonify(error="Menu item not found"),404
    data=request.get_json(silent=True) or {}
    updates={}
    if "name" in data:
        name=(data["name"] or "").strip()
        if not name: return jsonify(error="name cannot be empty"),400
        updates["name"]=name
    if "description" in data: updates["description"]=(data["description"] or "").strip()
    if "category" in data: updates["category"]=(data["category"] or "General").strip()
    if "price" in data:
        p=parse_price(data["price"])
        if p is None: return jsonify(error="price must be a positive number"),400
        updates["price"]=float(p)
    if "is_available" in data: updates["is_available"]=bool(data["is_available"])
    if updates: col("menu_items").update_one({"id":item_id},{"$set":updates})
    item.update(updates)
    return jsonify(message="Menu item updated",item=menu_out(item,True))

@bp.post("/<int:item_id>/image")
@jwt_required()
@role_required("admin")
def upload_image(item_id):
    item=col("menu_items").find_one({"id":item_id})
    if not item: return jsonify(error="Menu item not found"),404
    file=request.files.get("image")
    if not file: return jsonify(error="Choose an image file"),400
    if not file.mimetype or not file.mimetype.startswith("image/"):
        return jsonify(error="Only image files are allowed"),400
    try:
        image=Image.open(file.stream).convert("RGB")
        image.thumbnail((1000,1000))
        out=BytesIO()
        image.save(out,format="JPEG",quality=78,optimize=True)
        encoded=base64.b64encode(out.getvalue()).decode("ascii")
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify(error="The uploaded file is not a valid image"),400
    # Compressed images are stored as data URIs in MongoDB, avoiding ephemeral disk storage.
    image_url="data:image/jpeg;base64,"+encoded
    col("menu_items").update_one({"id":item_id},{"$set":{"image_url":image_url}})
    return jsonify(message="Dish photo saved",image_url=image_url)

@bp.delete("/<int:item_id>")
@role_required("admin")
def delete_item(item_id):
    result=col("menu_items").update_one({"id":item_id},{"$set":{"is_available":False}})
    if not result.matched_count: return jsonify(error="Menu item not found"),404
    return jsonify(message="Menu item removed from menu")
