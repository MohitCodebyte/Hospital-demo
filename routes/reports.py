from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory
from datetime import date
from models import db, Patient, Doctor, MedicalReport
from functools import wraps
import os
from werkzeug.utils import secure_filename

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# Decorator for doctor access
def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor_id' not in session:
            flash('Doctor access required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator for admin access
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required.', 'warning')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Reports Dashboard
@reports_bp.route('/dashboard')
@doctor_required
def dashboard():
    doctor_id = session.get('doctor_id')
    reports = MedicalReport.query.filter_by(doctor_id=doctor_id).order_by(MedicalReport.report_date.desc()).limit(20).all()
    return render_template('reports/dashboard.html', reports=reports)

# All Reports
@reports_bp.route('/all')
@doctor_required
def all_reports():
    doctor_id = session.get('doctor_id')
    reports = MedicalReport.query.filter_by(doctor_id=doctor_id).order_by(MedicalReport.report_date.desc()).all()
    return render_template('reports/all_reports.html', reports=reports)

# Upload Report
@reports_bp.route('/upload', methods=['GET', 'POST'])
@doctor_required
def upload():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        report_type = request.form.get('report_type')
        report_title = request.form.get('report_title')
        report_date = request.form.get('report_date')
        description = request.form.get('description')
        is_confidential = request.form.get('is_confidential') == 'on'
        
        # Handle file upload
        file = request.files.get('file')
        file_path = None
        file_name = None
        file_size = 0
        
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads', 'reports')
            os.makedirs(upload_folder, exist_ok=True)
            
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            file_name = filename
            file_size = os.path.getsize(file_path)
        
        report = MedicalReport(
            patient_id=patient_id,
            doctor_id=session.get('doctor_id'),
            report_type=report_type,
            report_title=report_title,
            report_date=date.fromisoformat(report_date) if report_date else date.today(),
            description=description,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            is_confidential=is_confidential
        )
        
        db.session.add(report)
        db.session.commit()
        
        flash('Medical report uploaded successfully.', 'success')
        return redirect(url_for('reports.view_report', report_id=report.id))
    
    patients = Patient.query.all()
    return render_template('reports/upload.html', patients=patients)

# View Report
@reports_bp.route('/view/<int:report_id>')
@doctor_required
def view_report(report_id):
    report = MedicalReport.query.get_or_404(report_id)
    return render_template('reports/view_report.html', report=report)

# Download Report
@reports_bp.route('/download/<int:report_id>')
@doctor_required
def download_report(report_id):
    report = MedicalReport.query.get_or_404(report_id)
    
    if report.file_path and os.path.exists(report.file_path):
        return send_from_directory(
            os.path.dirname(report.file_path),
            os.path.basename(report.file_path),
            as_attachment=True
        )
    else:
        flash('File not found.', 'error')
        return redirect(url_for('reports.view_report', report_id=report_id))

# Delete Report
@reports_bp.route('/delete/<int:report_id>')
@doctor_required
def delete_report(report_id):
    report = MedicalReport.query.get_or_404(report_id)
    
    # Delete file if exists
    if report.file_path and os.path.exists(report.file_path):
        os.remove(report.file_path)
    
    db.session.delete(report)
    db.session.commit()
    
    flash('Medical report deleted successfully.', 'success')
    return redirect(url_for('reports.all_reports'))

# Patient Report History
@reports_bp.route('/patient/<int:patient_id>')
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    reports = MedicalReport.query.filter_by(patient_id=patient_id).order_by(MedicalReport.report_date.desc()).all()
    return render_template('reports/patient_history.html', patient=patient, reports=reports)

# Admin Reports Management
@reports_bp.route('/admin/all')
@admin_required
def admin_all_reports():
    reports = MedicalReport.query.order_by(MedicalReport.report_date.desc()).all()
    return render_template('reports/admin_all_reports.html', reports=reports)

# Alias route for Admin Reports (sidebar compatibility)
@reports_bp.route('/admin')
@admin_required
def admin_reports_alias():
    return admin_all_reports()

# Patient History route (admin view)
@reports_bp.route('/patient_history/<int:patient_id>')
@admin_required
def admin_patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    reports = MedicalReport.query.filter_by(patient_id=patient_id).order_by(MedicalReport.report_date.desc()).all()
    return render_template('reports/patient_history.html', patient=patient, reports=reports)
