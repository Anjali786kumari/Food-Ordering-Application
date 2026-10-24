"""Seed the MongoDB database with an admin and demo menu. Run once after deployment."""
import os
from werkzeug.security import generate_password_hash
from app import create_app
from app.store import col, next_id, now

ADMIN_EMAIL=os.getenv("ADMIN_EMAIL","admin@food.com").strip().lower()
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","Admin@123")
MENU=[
("Margherita Pizza","Classic tomato and mozzarella","Pizza",249,20),
("Paneer Tikka Pizza","Smoky paneer, onions, capsicum","Pizza",329,15),
("Veg Burger","Crispy patty with cheese and lettuce","Burgers",129,30),
("Chicken Burger","Grilled chicken, mayo, pickles","Burgers",169,25),
("Paneer Butter Masala","Creamy tomato gravy","Main Course",259,18),
("Veg Biryani","Fragrant basmati with vegetables","Main Course",219,22),
("Masala Dosa","Crisp dosa with potato filling","South Indian",119,25),
("French Fries","Salted and crispy","Sides",89,40),
("Cold Coffee","Chilled and creamy","Beverages",99,35),
("Gulab Jamun (2 pcs)","Warm syrupy dessert","Desserts",69,3)]
app=create_app() 
with app.app_context():
    users=col("users")
    if not users.find_one({"email":ADMIN_EMAIL}):
        users.insert_one({"id":next_id("users"),"name":"Admin","email":ADMIN_EMAIL,
          "password_hash":generate_password_hash(ADMIN_PASSWORD),"role":"admin","created_at":now()})
        print(f"Admin created: {ADMIN_EMAIL}")
    if col("menu_items").count_documents({})==0:
        for name,desc,cat,price,stock in MENU:
            col("menu_items").insert_one({"id":next_id("menu_items"),"name":name,"description":desc,
              "category":cat,"price":price,"stock":stock,"is_available":True,"image_url":None,"created_at":now()})
        print(f"Inserted {len(MENU)} menu items")
    print("Seed complete. Keep admin credentials private.")
