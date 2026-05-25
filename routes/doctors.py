from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Appointment, Patient, Doctor, db
from datetime import datetime

doctors_bp = Blueprint('doctors', __name__)

# ==============================
# DOCTOR LOGIN
# ==============================

@doctors_bp.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        doctor = Doctor.query.filter_by(
            email=email
        ).first()

        if doctor and doctor.check_password(password):

            session['doctor_logged_in'] = True
            session['doctor_id'] = doctor.id
            session['doctor_name'] = doctor.name
            session['role'] = 'doctor'

            flash('Doctor login successful!', 'success')

            return redirect(url_for('doctors.doctor_dashboard'))

        else:

            flash('Invalid doctor credentials!', 'danger')

    return render_template('doctor_login.html')


# ==============================
# DOCTOR DASHBOARD
# ==============================

@doctors_bp.route('/doctor/dashboard')
def doctor_dashboard():
   

    if not session.get('doctor_logged_in'):

        flash('Please login first.', 'warning')

        return redirect(url_for('doctors.doctor_login'))


    patient_id = session.get('patient_id')

    patient = Patient.query.get(patient_id)

    doctor = Doctor.query.filter_by(
        email=patient.email
    ).first()

    if not doctor:

        flash(
            'Doctor profile not found.',
            'danger'
        )

        return redirect(url_for('auth.login'))

    doctor_id = doctor.id

    appointments = Appointment.query.filter_by(
        doctor_id=doctor_id
    ).all()

    total_patients = len(set([
        appointment.patient_id
        for appointment in appointments
    ]))

    total_appointments = len(appointments)

    pending_queue = len([
        appointment for appointment in appointments
        if appointment.status == 'pending'
    ])

    return render_template(
        'doctor_dashboard.html',
        total_patients=total_patients,
        total_appointments=total_appointments,
        pending_queue=pending_queue,
        appointments=appointments
    )

@doctors_bp.route('/doctor/appointment/<int:appointment_id>')
def view_appointment(appointment_id):

    if session.get('role') != 'doctor':
        return redirect(url_for('auth.login'))

    appointment = Appointment.query.get_or_404(appointment_id)

    return render_template(
        'doctor_appointment_detail.html',
        appointment=appointment
    )

# =====================================
# SCHEDULE APPOINTMENT
# =====================================

@doctors_bp.route(
    '/doctor/schedule/<int:appointment_id>',
    methods=['GET', 'POST']
)
def schedule_appointment(appointment_id):

    if session.get('role') != 'doctor':

        flash(
            'Doctor login required.',
            'danger'
        )

        return redirect(
            url_for('auth.login')
        )

    appointment = Appointment.query.get_or_404(
        appointment_id
    )

    if request.method == 'POST':

        appointment.appointment_date = datetime.strptime(
            request.form['appointment_date'],
            '%Y-%m-%d'
        ).date()

        appointment.appointment_time = datetime.strptime(
            request.form['appointment_time'],
            '%H:%M'
        ).time()

        appointment.status = 'confirmed'

        db.session.commit()

        flash(
            'Appointment scheduled successfully!',
            'success'
        )

        return redirect(
            url_for('doctors.doctor_dashboard')
        )

    return render_template(
        'schedule_appointment.html',
        appointment=appointment
    )
# ==============================
# DOCTOR LOGOUT
# ==============================

@doctors_bp.route('/doctor/logout')
def doctor_logout():

    session.pop('doctor_logged_in', None)
    session.pop('doctor_id', None)
    session.pop('doctor_name', None)
    session.pop('role', None)
    session.pop('patient_id', None)
    session.pop('patient_name', None)

    flash('Doctor logged out successfully.', 'info')

    return redirect(url_for('doctors.doctor_login'))


# ==============================
# ALL DOCTORS PAGE
# ==============================

@doctors_bp.route('/')
def index():

    doctors = Patient.query.filter_by(role='doctor').all()

    return render_template(
        'doctors.html',
        doctors=doctors
    )


# ==============================
# SINGLE DOCTOR DETAIL
# ==============================

@doctors_bp.route('/<int:doctor_id>')
def detail(doctor_id):

    doctor = Patient.query.get_or_404(doctor_id)

    return render_template(
        'doctor_detail.html',
        doctor=doctor
    )
    
# =====================================
# DOCTOR PATIENTS PANEL
# =====================================

@doctors_bp.route('/doctor/patients')
def doctor_patients():

    if session.get('role') != 'doctor':

        flash(
            'Doctor access required.',
            'danger'
        )

        return redirect(
            url_for('auth.login')
        )

    from models import OPDVisit

    doctor_id = session.get('doctor_id')

    patients = OPDVisit.query.filter_by(
        doctor_id=doctor_id
    ).order_by(
        OPDVisit.id.desc()
    ).all()

    return render_template(
        'doctor_patients.html',
        patients=patients
    )


@doctors_bp.route(
    '/doctor/appointment/<int:appointment_id>/approve'
)
def approve_appointment(appointment_id):

    appointment = Appointment.query.get_or_404(
        appointment_id
    )

    appointment.status = 'confirmed'

    db.session.commit()

    flash(
        'Appointment approved successfully.',
        'success'
    )

    return redirect(
        url_for('doctors.doctor_dashboard')
    )


@doctors_bp.route(
    '/doctor/appointment/<int:appointment_id>/reject'
)
def reject_appointment(appointment_id):

    appointment = Appointment.query.get_or_404(
        appointment_id
    )

    appointment.status = 'cancelled'

    db.session.commit()

    flash(
        'Appointment rejected successfully.',
        'warning'
    )

    return redirect(
        url_for('doctors.doctor_dashboard')
    )


@doctors_bp.route('/doctor/appointments')
def all_appointments():

    if session.get('role') != 'doctor':
        return redirect(url_for('auth.login'))

    patient = Patient.query.get(session.get('patient_id'))

    doctor = Doctor.query.filter_by(
        email=patient.email
    ).first()

    appointments = Appointment.query.filter_by(
        doctor_id=doctor.id
    ).order_by(
        Appointment.id.desc()
    ).all()

    print("TOTAL APPOINTMENTS =", len(appointments))

    for a in appointments:
        print(a.id, a.status)

    return render_template(
        'doctor_appointments.html',
        appointments=appointments
    )