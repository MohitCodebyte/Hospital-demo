from flask import Blueprint, render_template, session
from datetime import date, timedelta
from models import db, Patient, Doctor, Appointment, OPDVisit, Prescription, Invoice
from sqlalchemy import func
from functools import wraps

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

# Decorator for admin access
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required.', 'warning')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Analytics Dashboard
@analytics_bp.route('/dashboard')
@admin_required
def dashboard():
    # Patient Statistics
    total_patients = Patient.query.count()
    new_patients_this_month = Patient.query.filter(
        Patient.created_at >= date.today().replace(day=1)
    ).count()
    
    # Appointment Statistics
    total_appointments = Appointment.query.count()
    today_appointments = Appointment.query.filter_by(appointment_date=date.today()).count()
    pending_appointments = Appointment.query.filter_by(status='pending').count()
    confirmed_appointments = Appointment.query.filter_by(status='confirmed').count()
    
    # OPD Statistics
    today_opd_visits = OPDVisit.query.filter_by(visit_date=date.today()).count()
    completed_opd_visits = OPDVisit.query.filter_by(status='completed').count()
    
    # Prescription Statistics
    total_prescriptions = Prescription.query.count()
    today_prescriptions = Prescription.query.filter_by(prescription_date=date.today()).count()
    
    # Revenue Statistics
    total_revenue = db.session.query(func.sum(Invoice.total_amount)).filter_by(payment_status='paid').scalar() or 0
    today_revenue = db.session.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date == date.today(),
        Invoice.payment_status == 'paid'
    ).scalar() or 0
    
    # Doctor Performance
    doctor_stats = db.session.query(
        Doctor.name,
        Doctor.specialization,
        func.count(Appointment.id).label('appointment_count'),
        func.count(Prescription.id).label('prescription_count')
    ).outerjoin(Appointment, Doctor.id == Appointment.doctor_id)\
     .outerjoin(Prescription, Doctor.id == Prescription.doctor_id)\
     .group_by(Doctor.id).all()
    
    # Department Statistics
    from models import Department
    dept_stats = db.session.query(
        Department.department_name,
        func.count(Doctor.id).label('doctor_count'),
        func.count(Appointment.id).label('appointment_count')
    ).outerjoin(Doctor, Department.id == Doctor.department_id)\
     .outerjoin(Appointment, Doctor.id == Appointment.doctor_id)\
     .group_by(Department.id).all()
    
    # Appointment trends (last 7 days)
    appointment_trends = []
    for i in range(7):
        day = date.today() - timedelta(days=i)
        count = Appointment.query.filter_by(appointment_date=day).count()
        appointment_trends.append({'date': day.strftime('%Y-%m-%d'), 'count': count})
    
    # Revenue trends (last 7 days)
    revenue_trends = []
    for i in range(7):
        day = date.today() - timedelta(days=i)
        revenue = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date == day,
            Invoice.payment_status == 'paid'
        ).scalar() or 0
        revenue_trends.append({'date': day.strftime('%Y-%m-%d'), 'revenue': float(revenue)})
    
    return render_template('analytics/dashboard.html',
                          total_patients=total_patients,
                          new_patients_this_month=new_patients_this_month,
                          total_appointments=total_appointments,
                          today_appointments=today_appointments,
                          pending_appointments=pending_appointments,
                          confirmed_appointments=confirmed_appointments,
                          today_opd_visits=today_opd_visits,
                          completed_opd_visits=completed_opd_visits,
                          total_prescriptions=total_prescriptions,
                          today_prescriptions=today_prescriptions,
                          total_revenue=float(total_revenue),
                          today_revenue=float(today_revenue),
                          doctor_stats=doctor_stats,
                          dept_stats=dept_stats,
                          appointment_trends=appointment_trends,
                          revenue_trends=revenue_trends)

# Patient Analytics
@analytics_bp.route('/patients')
@admin_required
def patients():
    # Patient demographics
    gender_distribution = db.session.query(
        Patient.gender,
        func.count(Patient.id).label('count')
    ).group_by(Patient.gender).all()
    
    age_groups = [
        ('0-18', Patient.query.filter(Patient.age.between(0, 18)).count()),
        ('19-30', Patient.query.filter(Patient.age.between(19, 30)).count()),
        ('31-45', Patient.query.filter(Patient.age.between(31, 45)).count()),
        ('46-60', Patient.query.filter(Patient.age.between(46, 60)).count()),
        ('60+', Patient.query.filter(Patient.age >= 60).count())
    ]
    
    # Patient registration trends
    registration_trends = []
    for i in range(6):
        month_start = date.today().replace(day=1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        count = Patient.query.filter(
            Patient.created_at >= month_start,
            Patient.created_at < month_end
        ).count()
        registration_trends.append({
            'month': month_start.strftime('%Y-%m'),
            'count': count
        })
    
    return render_template('analytics/patients.html',
                          gender_distribution=gender_distribution,
                          age_groups=age_groups,
                          registration_trends=registration_trends)

# Appointment Analytics
@analytics_bp.route('/appointments')
@admin_required
def appointments():
    # Appointment status distribution
    status_distribution = db.session.query(
        Appointment.status,
        func.count(Appointment.id).label('count')
    ).group_by(Appointment.status).all()
    
    # Appointments by department
    from models import Department
    dept_appointments = db.session.query(
        Department.department_name,
        func.count(Appointment.id).label('count')
    ).join(Doctor, Department.id == Doctor.department_id)\
     .join(Appointment, Doctor.id == Appointment.doctor_id)\
     .group_by(Department.id).all()
    
    # Daily appointment trends (last 30 days)
    daily_trends = []
    for i in range(30):
        day = date.today() - timedelta(days=i)
        count = Appointment.query.filter_by(appointment_date=day).count()
        daily_trends.append({'date': day.strftime('%Y-%m-%d'), 'count': count})
    
    return render_template('analytics/appointments.html',
                          status_distribution=status_distribution,
                          dept_appointments=dept_appointments,
                          daily_trends=daily_trends)

# Revenue Analytics
@analytics_bp.route('/revenue')
@admin_required
def revenue():
    # Revenue by payment method
    payment_methods = db.session.query(
        Invoice.payment_method,
        func.sum(Invoice.total_amount).label('total')
    ).filter_by(payment_status='paid').group_by(Invoice.payment_method).all()
    
    # Monthly revenue (last 12 months)
    monthly_revenue = []
    for i in range(12):
        month_start = date.today().replace(day=1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        revenue = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date >= month_start,
            Invoice.invoice_date < month_end,
            Invoice.payment_status == 'paid'
        ).scalar() or 0
        monthly_revenue.append({
            'month': month_start.strftime('%Y-%m'),
            'revenue': float(revenue)
        })
    
    # Top revenue sources
    top_sources = db.session.query(
        Invoice.item_type,
        func.sum(Invoice.total_amount).label('total')
    ).join(InvoiceItem, Invoice.id == InvoiceItem.invoice_id)\
     .filter(Invoice.payment_status == 'paid')\
     .group_by(Invoice.item_type)\
     .order_by(func.sum(Invoice.total_amount).desc())\
     .limit(5).all()
    
    return render_template('analytics/revenue.html',
                          payment_methods=payment_methods,
                          monthly_revenue=monthly_revenue,
                          top_sources=top_sources)

# Doctor Performance
@analytics_bp.route('/doctors')
@admin_required
def doctors():
    # Doctor performance metrics
    doctor_performance = db.session.query(
        Doctor.id,
        Doctor.name,
        Doctor.specialization,
        func.count(Appointment.id).label('total_appointments'),
        func.sum(func.case((Appointment.status == 'completed', 1), else_=0)).label('completed_appointments'),
        func.count(Prescription.id).label('total_prescriptions'),
        func.sum(Invoice.total_amount).label('total_revenue')
    ).outerjoin(Appointment, Doctor.id == Appointment.doctor_id)\
     .outerjoin(Prescription, Doctor.id == Prescription.doctor_id)\
     .outerjoin(Invoice, Doctor.id == Invoice.doctor_id)\
     .group_by(Doctor.id).all()
    
    return render_template('analytics/doctors.html',
                          doctor_performance=doctor_performance)
