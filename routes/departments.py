from flask import Blueprint, render_template
from models import Department, Doctor, db

departments_bp = Blueprint('departments', __name__)

@departments_bp.route('/')
def index():
    departments = Department.query.all()
    return render_template('departments.html', departments=departments)

@departments_bp.route('/<int:department_id>')
def detail(department_id):
    department = Department.query.get_or_404(department_id)
    doctors = Doctor.query.filter_by(department_id=department_id).all()
    return render_template('department_detail.html', department=department, doctors=doctors)
