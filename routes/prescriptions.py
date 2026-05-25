from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, make_response
from datetime import date
from models import db, Patient, Doctor, Prescription, PrescriptionMedicine, OPDVisit, Appointment
from functools import wraps
import os

prescriptions_bp = Blueprint('prescriptions', __name__, url_prefix='/prescriptions')

# Decorator for doctor access
def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor_id' not in session:
            flash('Doctor access required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Prescription List
@prescriptions_bp.route('/')
@doctor_required
def index():
    doctor_id = session.get('doctor_id')
    prescriptions = Prescription.query.filter_by(doctor_id=doctor_id).order_by(Prescription.prescription_date.desc()).all()
    return render_template('prescriptions/index.html', prescriptions=prescriptions)

# Create Prescription
@prescriptions_bp.route('/create', methods=['GET', 'POST'])
@doctor_required
def create():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        doctor_id = session.get('doctor_id')
        appointment_id = request.form.get('appointment_id')
        opd_visit_id = request.form.get('opd_visit_id')
        diagnosis = request.form.get('diagnosis')
        notes = request.form.get('notes')
        
        # Create prescription
        prescription = Prescription(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=appointment_id if appointment_id else None,
            opd_visit_id=opd_visit_id if opd_visit_id else None,
            diagnosis=diagnosis,
            notes=notes,
            prescription_date=date.today()
        )
        
        db.session.add(prescription)
        db.session.commit()
        
        # Add medicines
        medicine_names = request.form.getlist('medicine_name[]')
        dosages = request.form.getlist('dosage[]')
        frequencies = request.form.getlist('frequency[]')
        durations = request.form.getlist('duration[]')
        instructions_list = request.form.getlist('instructions[]')
        
        for i in range(len(medicine_names)):
            if medicine_names[i]:
                medicine = PrescriptionMedicine(
                    prescription_id=prescription.id,
                    medicine_name=medicine_names[i],
                    dosage=dosages[i],
                    frequency=frequencies[i],
                    duration=durations[i],
                    instructions=instructions_list[i] if i < len(instructions_list) else ''
                )
                db.session.add(medicine)
        
        db.session.commit()
        flash('Prescription created successfully.', 'success')
        return redirect(url_for('prescriptions.view', prescription_id=prescription.id))
    
    patients = Patient.query.all()
    appointments = Appointment.query.filter_by(doctor_id=session.get('doctor_id'), status='confirmed').all()
    opd_visits = OPDVisit.query.filter_by(doctor_id=session.get('doctor_id'), status='completed').all()
    
    return render_template('prescriptions/create.html', patients=patients, appointments=appointments, opd_visits=opd_visits)

# View Prescription
@prescriptions_bp.route('/<int:prescription_id>')
@doctor_required
def view(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    return render_template('prescriptions/view.html', prescription=prescription)

# Download PDF Prescription
@prescriptions_bp.route('/download/<int:prescription_id>')
@doctor_required
def download_pdf(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    
    # Generate simple text-based prescription (for production, use ReportLab or WeasyPrint)
    prescription_text = f"""
SAHARA HOSPITAL - PRESCRIPTION
{'='*50}
Date: {prescription.prescription_date}
Prescription ID: {prescription.id}

PATIENT DETAILS
{'-'*50}
Name: {prescription.patient.full_name}
Age: {prescription.patient.age}
Gender: {prescription.patient.gender}
Phone: {prescription.patient.phone}

DOCTOR DETAILS
{'-'*50}
Dr. {prescription.doctor.name}
{prescription.doctor.specialization}
{prescription.doctor.qualification}

DIAGNOSIS
{'-'*50}
{prescription.diagnosis}

MEDICINES
{'-'*50}
"""
    for medicine in prescription.medicines:
        prescription_text += f"""
• {medicine.medicine_name}
  Dosage: {medicine.dosage}
  Frequency: {medicine.frequency}
  Duration: {medicine.duration}
  Instructions: {medicine.instructions or 'N/A'}
"""
    
    if prescription.notes:
        prescription_text += f"""
NOTES
{'-'*50}
{prescription.notes}
"""
    
    prescription_text += f"""
{'='*50}
Sahara Hospital - Premium Healthcare
123 Healthcare Avenue, Medical City
Phone: +1 234 567 8900
"""
    
    # Create response
    response = make_response(prescription_text)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Content-Disposition'] = f'attachment; filename=prescription_{prescription_id}.txt'
    
    return response

# Edit Prescription
@prescriptions_bp.route('/edit/<int:prescription_id>', methods=['GET', 'POST'])
@doctor_required
def edit(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    
    if request.method == 'POST':
        prescription.diagnosis = request.form.get('diagnosis')
        prescription.notes = request.form.get('notes')
        
        # Delete existing medicines
        for medicine in prescription.medicines:
            db.session.delete(medicine)
        
        # Add new medicines
        medicine_names = request.form.getlist('medicine_name[]')
        dosages = request.form.getlist('dosage[]')
        frequencies = request.form.getlist('frequency[]')
        durations = request.form.getlist('duration[]')
        instructions_list = request.form.getlist('instructions[]')
        
        for i in range(len(medicine_names)):
            if medicine_names[i]:
                medicine = PrescriptionMedicine(
                    prescription_id=prescription.id,
                    medicine_name=medicine_names[i],
                    dosage=dosages[i],
                    frequency=frequencies[i],
                    duration=durations[i],
                    instructions=instructions_list[i] if i < len(instructions_list) else ''
                )
                db.session.add(medicine)
        
        db.session.commit()
        flash('Prescription updated successfully.', 'success')
        return redirect(url_for('prescriptions.view', prescription_id=prescription.id))
    
    return render_template('prescriptions/edit.html', prescription=prescription)

# Delete Prescription
@prescriptions_bp.route('/delete/<int:prescription_id>')
@doctor_required
def delete(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    db.session.delete(prescription)
    db.session.commit()
    flash('Prescription deleted successfully.', 'success')
    return redirect(url_for('prescriptions.index'))

# Patient Prescription History
@prescriptions_bp.route('/patient/<int:patient_id>')
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    prescriptions = Prescription.query.filter_by(patient_id=patient_id).order_by(Prescription.prescription_date.desc()).all()
    return render_template('prescriptions/patient_history.html', patient=patient, prescriptions=prescriptions)
