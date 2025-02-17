from dotenv import load_dotenv
import os
import datetime
import uuid
import pytz
from flask import Flask, request, jsonify, render_template, redirect, make_response
from flask_restful import Resource, Api
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from modules.websocks import MQTTWebSocketClient

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
api = Api(app)

# MongoDB connection from env
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['scheduler_db']
schedules_collection = db['schedules']

# MQTT WebSocket configuration from env
WEBSOCK_BROKER_ADDRESS = os.getenv("WEBSOCK_BROKER_ADDRESS", "mqtt.mstservices.tech")
WEBSOCK_PORT = int(os.getenv("WEBSOCK_PORT", "443"))
WEBSOCK_USE_SSL = os.getenv("WEBSOCK_USE_SSL", "True") == "True"
USE_CREDS = os.getenv("USE_CREDS", "True") == "True"
MQTT_USER = os.getenv("MQTT_USER", "mst")
MQTT_PASS = os.getenv("MQTT_PASS", "1212")
QOS = int(os.getenv("QOS", "0"))
CLEAN_SESSION = os.getenv("CLEAN_SESSION", "True") == "True"
RETAINED = os.getenv("RETAINED", "True") == "True"

# Our sample valid token
VALID_TOKEN = os.getenv("VALID_TOKEN")

# Define Indian timezone
INDIAN_TZ = pytz.timezone('Asia/Kolkata')

# Load device values from .env:
# e.g., PINS=D1,D2,D3,D4 and SWITCH_NAME=Light,Lamp,Fan,esp
PINS = os.getenv("PINS", "D1,D2,D3,D4").split(',')
SWITCH_NAMES = os.getenv("SWITCH_NAME", "Light,Lamp,Fan,esp").split(',')
devices = [{"value": p.strip(), "name": n.strip()} for p, n in zip(PINS, SWITCH_NAMES)]

# Make devices available in the template
@app.context_processor
def inject_devices():
    return dict(devices=devices)

# Initialize MQTT WebSocket Client using env vars and connect once
mqtt_client = MQTTWebSocketClient(
    host=WEBSOCK_BROKER_ADDRESS,
    port=WEBSOCK_PORT,
    username=MQTT_USER,
    password=MQTT_PASS,
    use_ssl=WEBSOCK_USE_SSL,
    clean_session=CLEAN_SESSION,
    retained=RETAINED,
    qos=QOS,
    use_creds=USE_CREDS
)
mqtt_client.connect()

# Initialize APScheduler in background mode
scheduler = BackgroundScheduler()
scheduler.start()

def schedule_job(schedule):
    """
    Schedules a job in APScheduler based on the schedule document using Indian time.
    For daily tasks, the time is in "HH:MM" format; for one-time tasks, an ISO datetime string is used.
    """
    schedule_id = schedule['_id']
    token = schedule['token']
    device = schedule['device']
    action = schedule['action']
    schedule_type = schedule['schedule_type']
    time_str = schedule['time']
    job_id = str(schedule_id)

    # Remove any existing job with this id
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    if schedule_type == "daily":
        hour, minute = map(int, time_str.split(":"))
        trigger = CronTrigger(hour=hour, minute=minute, timezone=INDIAN_TZ)
    else:
        scheduled_datetime = datetime.datetime.fromisoformat(time_str)
        if scheduled_datetime.tzinfo is None:
            scheduled_datetime = INDIAN_TZ.localize(scheduled_datetime)
        else:
            scheduled_datetime = scheduled_datetime.astimezone(INDIAN_TZ)
        trigger = DateTrigger(run_date=scheduled_datetime)

    scheduler.add_job(func=execute_schedule, trigger=trigger, args=[schedule_id], id=job_id)
    print(f"Scheduled job {job_id}: Device: {device}, Action: {action}, Type: {schedule_type}, Scheduled Time: {time_str} (IST)")

def execute_schedule(schedule_id):
    schedule = schedules_collection.find_one({"_id": schedule_id})
    if schedule is None:
        return
    # Check active flag before proceeding
    if not schedule.get("active", True):
        print(f"Skipping job {schedule_id} because schedule is inactive.")
        return
    if schedule['schedule_type'] == "one-time" and schedule.get('executed', False):
        return

    print(f"Executing job {schedule_id}: Device: {schedule['device']}, Action: {schedule['action']}, Scheduled Time: {schedule['time']} (IST)")
    topic = f"{schedule['token']}/{schedule['device']}"
    message = int(schedule['action'])
    mqtt_client.update_topic_value(topic, message)

    if schedule['schedule_type'] == "one-time":
        schedules_collection.update_one({"_id": schedule_id}, {"$set": {"executed": True}})
        try:
            scheduler.remove_job(str(schedule_id))
        except Exception:
            pass
    else:
        schedules_collection.update_one(
            {"_id": schedule_id},
            {"$set": {"last_triggered": datetime.datetime.now(INDIAN_TZ).isoformat()}}
        )

def token_required(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get('token') or (request.json and request.json.get('token'))
        if not token or token != VALID_TOKEN:
            return jsonify({"message": "Token is missing or invalid"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

class Login(Resource):
    def post(self):
        data = request.get_json()
        token = data.get("token")
        if token == VALID_TOKEN:
            # Set token in cookie and return response
            resp = make_response({"message": "Login successful", "token": token}, 200)
            resp.set_cookie("token", token, max_age=86400)
            return resp
        else:
            return {"message": "Invalid token"}, 401

class ScheduleList(Resource):
    @token_required
    def get(self):
        token = request.headers.get('token')
        schedules = list(schedules_collection.find({"token": token}))
        for schedule in schedules:
            schedule['_id'] = str(schedule['_id'])
        return jsonify(schedules)

    @token_required
    def post(self):
        data = request.get_json()
        token = data.get("token")
        device = data.get("device")
        action = data.get("action")
        schedule_type = data.get("schedule_type")
        time_str = data.get("time")
        if not all([token, device, action is not None, schedule_type, time_str]):
            return {"message": "Missing required fields"}, 400
        schedule_id = str(uuid.uuid4())
        schedule = {
            "_id": schedule_id,
            "token": token,
            "device": device,
            "action": action,
            "schedule_type": schedule_type,
            "time": time_str,
            "executed": False,
            "active": True
        }
        schedules_collection.insert_one(schedule)
        schedule_job(schedule)
        return {"message": "Schedule created", "schedule": schedule}, 201

class Schedule(Resource):
    @token_required
    def put(self, schedule_id):
        token = request.headers.get('token')
        data = request.get_json()
        update_data = {}
        for field in ["device", "action", "schedule_type", "time", "active"]:
            if field in data:
                update_data[field] = data[field]
        if not update_data:
            return {"message": "No fields to update"}, 400
        result = schedules_collection.update_one({"_id": schedule_id, "token": token}, {"$set": update_data})
        if result.matched_count == 0:
            return {"message": "Schedule not found"}, 404
        schedule = schedules_collection.find_one({"_id": schedule_id})
        schedule_job(schedule)
        return {"message": "Schedule updated", "schedule": schedule}, 200

    @token_required
    def delete(self, schedule_id):
        token = request.headers.get('token')
        result = schedules_collection.delete_one({"_id": schedule_id, "token": token})
        if result.deleted_count == 0:
            return {"message": "Schedule not found"}, 404
        try:
            scheduler.remove_job(schedule_id)
        except Exception:
            pass
        return {"message": "Schedule deleted"}, 200

api.add_resource(Login, '/api/login')
api.add_resource(ScheduleList, '/api/schedules')
api.add_resource(Schedule, '/api/schedules/<string:schedule_id>')

# Root route: if token cookie is present and valid, redirect to scheduler, else to login
@app.route("/")
def index():
    token = request.cookies.get("token")
    if token and token == VALID_TOKEN:
        return redirect("/scheduler")
    else:
        return redirect("/login")

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/scheduler', methods=['GET'])
def scheduler_page():
    return render_template('scheduler.html')

if __name__ == '__main__':
    # On startup, load existing unexecuted schedules from the database and schedule them
    for schedule in schedules_collection.find({"executed": False}):
        schedule_job(schedule)
    DEBUG = os.getenv("DEBUG", "True") == "True"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    app.run(debug=DEBUG, host=HOST, port=PORT,threaded=True)
