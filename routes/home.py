from flask import Blueprint, render_template
from models import Department, Doctor, EmergencyContact, db

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def index():
    departments = Department.query.limit(6).all()
    doctors = Doctor.query.filter_by(availability=True).limit(6).all()
    emergency = EmergencyContact.query.first()
    return render_template('home.html', departments=departments, doctors=doctors, emergency=emergency)

@home_bp.route('/about')
def about():
    return render_template('about.html')
