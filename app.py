from flask import *
from database import sqldb,isitordered,tickets,realWinners
from functools import wraps
from psycopg2.extras import DictCursor
from supabase import create_client,Client
import uuid

# Your Supabase credentials (found in Project Settings > API)
url = "https://uyomlejvshurhgcbijqm.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV5b21sZWp2c2h1cmhnY2JpanFtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjMyMjc3NCwiZXhwIjoyMDkxODk4Nzc0fQ.gRrvWbJRHe_20sB6e7mvMj0KoOGB7DgJ5FxztenEQDo" # Use service key for backend uploads

def upload_file(bucket,file,file_content,filename):
    supabase: Client = create_client(url, key)
    bucket_path = f"{filename}"
    try:
            response = supabase.storage.from_(bucket).upload(
                path=bucket_path,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            
            # 3. Get the Public URL to save in your PostgreSQL database
            image_url = supabase.storage.from_(bucket).get_public_url(bucket_path)
            
            return image_url
            
    except Exception as e:
        print(e)
        return False

app = Flask(__name__)

app.secret_key = "ciowdfdsfdfsssssssssssdwe"

@app.before_request
def perm():
    session.permanent = True

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if 'admin_id' or 'user_id' exists in the session
        if 'admin' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def item_info(id):
    with sqldb() as conn:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT price,itemname FROM items WHERE id = %s",(id,))
        item = cur.fetchone()
    return item

def userinfo(id):
    with sqldb() as conn:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT phone_number,fullname FROM users WHERE id = %s",(id,))
        item = cur.fetchone()
    return item

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/admin/login",methods=['POST'])
def login():
    with sqldb() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM admins WHERE username = %s AND password = %s",(request.form.get("username"),request.form.get('password')))
        admins = cur.fetchone()
    if admins:
        session['admin'] = admins[0]
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid credentials")
        return redirect(url_for('index'))

@app.route("/admin/dashboard")
@login_required
def dashboard():
    with sqldb() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM items")
        itemamt = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM orders")
        orderList = cur.fetchone()
    return render_template('dashboard.html',items=itemamt,order=orderList)

@app.route("/items")
@login_required
def items():
    with sqldb() as conn:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM items")
        items = cur.fetchall()
    return render_template("items.html",items=items)

@app.route("/add/items",methods=['GET','POST'])
@login_required
def add_items():
    if request.method == 'GET':
        return render_template('additems.html')
    elif request.method == 'POST':
        itemname = request.form.get('name')
        price = request.form['price']
        amt = request.form['amt']
        item_type = request.form['item_type']
        pic = request.files['picture']
        file_content = pic.read()
        file_name = f'{str(uuid.uuid4()).replace("-","")}.{pic.filename.split('.')[-1]}'
        imgurl = upload_file('items',pic,file_content,file_name)
        if imgurl:
            with sqldb() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO items(itemname,price,picture,amount,item_type) VALUES (%s,%s,%s,%s,%s)",(itemname,price,imgurl,amt,item_type))
            flash("Item added!","success")
            return redirect(url_for('items'))
        else:
            flash("Error occured while adding items!","error")
            return redirect(url_for('items'))
    else:
        return abort(405)
    
import os

@app.route('/delete/item/<item_id>')
@login_required
def delete_item(item_id):
    conn = sqldb()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    try:
        # 1. Fetch the image URL from your DB before making changes
        cur.execute("SELECT picture FROM items WHERE id = %s", (item_id,))
        item = cur.fetchone()
        
        if item:
            # Check if it has NOT been ordered yet
            if not isitordered(item_id):
                # --- SCENARIO: NEVER ORDERED (Safe to fully delete) ---
                image_url = item['picture']
                file_path = image_url.split('/')[-1] 
                
                # Delete from Supabase Storage
                supabase: Client = create_client(url, key)
                supabase.storage.from_("items").remove(image_url)
                
                # Delete from PostgreSQL database entirely
                cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
                conn.commit()
                
                flash("Item and its image were successfully deleted!", "success")
                
            else:
                # --- SCENARIO: ALREADY ORDERED (Just zero out amount) ---
                cur.execute("UPDATE items SET amount = 0 WHERE id = %s", (item_id,))
                conn.commit()
                
                flash("Item status updated to unavailable (amount = 0).", "success")
        else:
            flash("Item not found.", "warning")
            
    except Exception as e:
        conn.rollback() # Rollback if something crashes mid-way
        flash(f"Error during operation: {str(e)}", "danger")
    finally:
        cur.close()
        conn.close() # Good practice to close the connection too
        
    return redirect(url_for('items'))

@app.route("/prizes")
@login_required
def prizes():
    with sqldb() as conn:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM prizes")
        prizes = cur.fetchall()
        cur.execute("SELECT * FROM winner")
        winners=cur.fetchall()
    return render_template("prizes.html",prizes=prizes,winners=winners)

@app.route("/add/prizes",methods=['GET','POST'])
@login_required
def addprizes():
    if request.method == 'GET':
        return render_template("addprizes.html")
    elif request.method == 'POST':
        prize_name = request.form['name']
        amt = request.form['amt']
        picture = request.files['picture']
        filename = f'{str(uuid.uuid4()).replace("-",'')}.{picture.filename.split(".")[-1]}'
        prize_url = upload_file('prizes',picture,picture.read(),filename)
        if prize_url:
            with sqldb() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO prizes(prize,amount,picture) VALUES(%s,%s,%s)",(prize_name,amt,prize_url))
                conn.commit()
            flash("Prize added","success")
            return redirect(url_for('prizes'))
        else:
            flash("Error adding prizes",'error')
            return redirect(url_for('prizes'))
    else:
        return abort(405)
    
@app.route('/delete/prize/<item_id>')
@login_required
def delete_prizes(item_id):
    conn = sqldb()
    # 1. Fetch the image URL from your DB before deleting the row
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT picture FROM prizes WHERE id = %s", (item_id,))
    item = cur.fetchone()
    
    if item:
        image_url = item['picture']
        
        # 2. Extract the filename/path from the URL
        # If your URL is: https://.../inventory/items/bag.jpg
        # The path in the bucket is: items/bag.jpg
        file_path = image_url.split('/')[-1] 
        full_path = f"{file_path}"
        
        try:
            supabase: Client = create_client(url, key)
            # 3. Delete from Supabase Storage
            supabase.storage.from_("prizes").remove([file_path])
            
            # 4. Now delete from your PostgreSQL database
            cur.execute("DELETE FROM prizes WHERE id = %s", (item_id,))
            conn.commit()
            
            flash("prize and its image were successfully deleted!", "success")
        except Exception as e:
            flash(f"Error during deletion: {str(e)}", "danger")
    
    cur.close()
    return redirect(url_for('prizes'))

@app.route("/orders")
@login_required
def orderLists():
    with sqldb() as conn:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM orders")
        order_s = cur.fetchall()
    return render_template("orders.html",orders=order_s,item=item_info,user=userinfo)

@app.route("/mark/paid/<orderid>")
@login_required
def mark_paid(orderid):
    with sqldb() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE orders SET paid_status = %s WHERE order_id = %s",(True,orderid))
        conn.commit()
    flash("Order marked as delivered!")
    return redirect(url_for('dashboard'))

@app.route("/assign/winner/<prize>",methods=['GET',"POST"])
@login_required
def assign_winner(prize):
    if request.method == "GET":
        with sqldb() as conn:
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute("SELECT * FROM prizes WHERE id = %s",(prize,))
            prizeinfo = cur.fetchone()
        return render_template("assign.html",tickets=tickets(),prize=prizeinfo)
    elif request.method == 'POST':
        lotto_id = request.form.get('lotto')
        with sqldb() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO winner(user_,prize) VALUES(%s,%s)",(lotto_id,prize))
            cur.execute("UPDATE prizes SET amount = amount-1 WHERE id = %s",(prize,))
            conn.commit()
        flash("Winner successfully assigned!")
        return redirect(url_for('dashboard'))
    else:
        return abort(405)


@app.route("/winners")
@login_required
def winners():
    return render_template("winners.html",winners=realWinners())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)