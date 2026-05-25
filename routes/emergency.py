from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import EmergencyContact, db

emergency_bp = Blueprint('emergency', __name__)

@emergency_bp.route('/')
def index():
    emergency = EmergencyContact.query.first()
    return render_template('emergency.html', emergency=emergency)

@emergency_bp.route('/submit', methods=['POST'])
def submit():
    try:
        emergency = EmergencyContact(
            patient_name=request.form['patient_name'],
            phone=request.form['phone'],
            emergency_type=request.form['emergency_type'],
            message=request.form.get('message', '')
        )
        db.session.add(emergency)
        db.session.commit()
        flash('Emergency request submitted successfully!', 'success')
        return redirect(url_for('emergency.index'))
    except Exception as e:
        db.session.rollback()
        flash('Error submitting emergency request. Please try again.', 'error')
        return redirect(url_for('emergency.index'))
