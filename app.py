from flask import Flask, render_template, request, redirect, url_for, send_file, session, Response, jsonify
from pymongo import MongoClient, errors as pymongo_errors
from bson.objectid import ObjectId
import pandas as pd
from io import BytesIO
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "fallback_secret")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "ACM")

client = MongoClient(MONGO_URI)
db = client[MONGO_DBNAME]

teams_collection = db["hackathon_workshop"]

def init_db():
    """
    Ensure indexes or prepare collection.
    """
    try:
        teams_collection.create_index("team_lead_email", unique=False)
    except Exception as e:
        app.logger.warning(f"Index creation error: {e}")

def doc_to_json(doc):
    """
    Convert a MongoDB document to JSON-serializable dict for templates / exports.
    """
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        try:
            doc["_id"] = str(doc["_id"])
        except Exception:
            doc["_id"] = doc.get("_id")
    for k, v in doc.items():
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/treasure')
def treasure():
    return render_template('treasure.html')

@app.route('/team_register', methods=['GET', 'POST'])
def team_register():
    if request.method == 'POST':
        try:
            doc = {
                "team_name": request.form.get('team_name', '').strip(),
                "team_lead_name": request.form.get('team_lead_name', '').strip(),
                "team_lead_email": request.form.get('team_lead_email', '').strip(),
                "team_lead_phone": request.form.get('team_lead_phone', '').strip(),
                "team_lead_reg_no": request.form.get('team_lead_reg_no', '').strip(),
                "member1_name": request.form.get('member_1_name', '').strip(),
                "member1_email": request.form.get('member_1_email', '').strip(),
                "member1_reg_no": request.form.get('member_1_reg_no', '').strip(),
                "member2_name": request.form.get('member_2_name', '').strip(),
                "member2_email": request.form.get('member_2_email', '').strip(),
                "member2_reg_no": request.form.get('member_2_reg_no', '').strip(),
                "member3_name": request.form.get('member_3_name', '').strip(),
                "member3_email": request.form.get('member_3_email', '').strip(),
                "member3_reg_no": request.form.get('member_3_reg_no', '').strip(),
                "created_at": datetime.utcnow()
            }
            if not doc["team_name"] or not doc["team_lead_email"]:
                return render_template('team_register.html', error="Team name and team lead email are required.", form=request.form), 400

            res = teams_collection.insert_one(doc)
            inserted = teams_collection.find_one({"_id": res.inserted_id})
            return render_template('download_info.html', data=doc_to_json(inserted))
        except pymongo_errors.DuplicateKeyError:
            return render_template('team_register.html', error="A team with that identifier already exists.", form=request.form), 409
        except Exception as e:
            app.logger.exception("Error inserting team")
            return render_template('team_register.html', error=f"An error occurred: {e}", form=request.form), 500

    return render_template('team_register.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        ADMIN_USER = os.getenv("ADMIN_USER", "admin")
        ADMIN_PASS = os.getenv("ADMIN_PASS", "acmvitap")

        if username == ADMIN_USER and password == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error="Invalid credentials. Try again.")
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' in session:
        return render_template('admin_dashboard.html')
    return redirect(url_for('admin_login'))

@app.route('/view_registered_teams')
def view_registered_teams():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    try:
        teams_cursor = teams_collection.find().sort("created_at", -1)
        teams = [doc_to_json(t) for t in teams_cursor]
    except Exception as e:
        app.logger.exception("Error fetching teams")
        teams = []
    return render_template('registered_details.html', teams=teams)

@app.route('/export_excel')
def export_excel():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    try:
        teams_list = list(teams_collection.find())
        serializable = [doc_to_json(t) for t in teams_list]
        if serializable:
            df = pd.DataFrame(serializable)
        else:
            df = pd.DataFrame()
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Teams')
        output.seek(0)
        return send_file(output, download_name="team_details.xlsx", as_attachment=True)
    except Exception as e:
        app.logger.exception("Error exporting to Excel")
        return "Failed to export", 500

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

@app.route('/download_info', methods=['POST'])
def download_info():
    team_info = request.form
    download_content = f"""
Team Name: {team_info.get('team_name','')}
Team Lead: {team_info.get('team_lead_name','')}
Team Lead Email: {team_info.get('team_lead_email','')}
Team Lead Phone: {team_info.get('team_lead_phone','')}
Team Lead Registration Number: {team_info.get('team_lead_reg_no','')}
Member 1: {team_info.get('member_1_name','')} ({team_info.get('member_1_email','')}) | Reg No: {team_info.get('member_1_reg_no','')}
Member 2: {team_info.get('member_2_name','')} ({team_info.get('member_2_email','')}) | Reg No: {team_info.get('member_2_reg_no','')}
Member 3: {team_info.get('member_3_name','')} ({team_info.get('member_3_email','')}) | Reg No: {team_info.get('member_3_reg_no','')}
"""
    return Response(download_content, mimetype="text/plain",
                    headers={"Content-Disposition": "attachment;filename=team_registration.txt"})

@app.route('/upcoming_events')
def upcoming_events():
    return render_template('upcoming_events.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
