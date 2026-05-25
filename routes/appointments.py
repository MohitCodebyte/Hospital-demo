from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from models import Appointment, Doctor, Department, Patient, db
from routes.auth import login_required

appointments_bp = Blueprint('appointments', __name__)

@appointments_bp.route('/')
@login_required
def index():
    return render_template('appointment.html', doctors=Doctor.query.all(), departments=Department.query.all())

@appointments_bp.route('/book', methods=['POST'])
@login_required
def book():
    try:
        patient_id = session.get('patient_id')
        
        if not patient_id:
            flash('Please login to book an appointment.', 'warning')
            return redirect(url_for('auth.login'))
        
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=request.form['doctor_id'],
            appointment_date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            appointment_time=datetime.strptime(request.form['time'], '%H:%M').time(),
            symptoms=request.form.get('symptoms', '')
        )
        db.session.add(appointment)
        db.session.commit()
        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('auth.patient_dashboard'))
    except Exception as e:
        db.session.rollback()
        flash('Error booking appointment. Please try again.', 'error')
        return redirect(url_for('appointments.index'))
