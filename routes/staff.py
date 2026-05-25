from flask import Blueprint, render_template, redirect, url_for, flash, session
from models import Appointment

staff_bp = Blueprint('staff', __name__)


# ==============================
# STAFF DASHBOARD
# ==============================



@staff_bp.route('/staff/dashboard')
def staff_dashboard():

    if session.get('role') != 'staff':

        flash('Access denied! Staff login required.', 'danger')
        return redirect(url_for('auth.login'))

    pending_appointments = Appointment.query.filter_by(
        status='pending'
    ).order_by(
        Appointment.created_at.desc()
    ).all()

    return render_template(
        'staff_dashboard.html',
        pending_appointments=pending_appointments
    )

# ==============================
# STAFF LOGOUT
# ==============================

@staff_bp.route('/staff/logout')
def staff_logout():

    session.clear()

    flash('Staff logged out successfully.', 'info')

    return redirect(url_for('auth.login'))


@staff_bp.route('/staff/appointments')
def staff_appointments():

    if session.get('role') != 'staff':

        flash('Staff login required.', 'danger')

        return redirect(url_for('auth.login'))

    pending_appointments = Appointment.query.order_by(
        Appointment.id.desc()
    ).all()

    return render_template(
        'staff_appointments.html',
        appointments=pending_appointments
    )