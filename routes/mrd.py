from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import date, datetime
from models import (
    db, Patient, Appointment, OPDVisit, Prescription,
    MedicalReport, Invoice, FileTracking, Doctor, Department
)
from routes.auth import admin_required

mrd_bp = Blueprint("mrd", __name__, url_prefix="/mrd")

# MRD Dashboard
@mrd_bp.route("/")
@admin_required
def dashboard():
    stats = {
        "patients": Patient.query.count(),
        "appointments": Appointment.query.count(),
        "opd_visits": OPDVisit.query.count(),
        "prescriptions": Prescription.query.count(),
        "reports": MedicalReport.query.count(),
        "medical_files": FileTracking.query.count()
    }
    
    recent_patients = Patient.query.order_by(Patient.created_at.desc()).limit(10).all()
    
    # Current stock/expense figures for summary cards
    from models import StockPurchase, MedicinePurchase, InventoryItem
    total_medicine_purchase = sum(p.total_amount for p in MedicinePurchase.query.all())
    total_inventory_purchase = sum(p.total_amount for p in StockPurchase.query.all())
    current_stock_value = sum(item.quantity * (item.purchase_price or 0.0) for item in InventoryItem.query.all())
    
    return render_template(
        "mrd/dashboard.html",
        stats=stats,
        recent_patients=recent_patients,
        total_medicine_purchase=total_medicine_purchase,
        total_inventory_purchase=total_inventory_purchase,
        current_stock_value=current_stock_value
    )

# Full MRD Data with Search & Filters
@mrd_bp.route("/patients")
@admin_required
def patients():
    search = request.args.get("search", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    dept_id = request.args.get("department_id", "")
    doc_id = request.args.get("doctor_id", "")
    
    query = Patient.query
    
    # 1. Search by name/phone/email
    if search:
        query = query.filter(
            Patient.full_name.ilike(f"%{search}%") |
            Patient.phone.ilike(f"%{search}%") |
            Patient.email.ilike(f"%{search}%")
        )
        
    # 2. Filter by Date range (joined with appointment or visit date)
    if start_date or end_date:
        # Join Patient to Appointment to filter
        start = date.fromisoformat(start_date) if start_date else date(2000, 1, 1)
        end = date.fromisoformat(end_date) if end_date else date(2100, 12, 31)
        query = query.join(Patient.appointments).filter(Appointment.appointment_date.between(start, end)).distinct()
        
    # 3. Filter by Doctor / Department
    if doc_id:
        query = query.join(Patient.appointments).filter(Appointment.doctor_id == int(doc_id)).distinct()
    elif dept_id:
        query = query.join(Patient.appointments).join(Appointment.doctor).filter(Doctor.department_id == int(dept_id)).distinct()
        
    patients_list = query.order_by(Patient.full_name).all()
    
    doctors = Doctor.query.order_by(Doctor.name).all()
    departments = Department.query.order_by(Department.department_name).all()
    
    return render_template(
        "mrd/patients.html",
        patients=patients_list,
        search=search,
        start_date=start_date,
        end_date=end_date,
        dept_id=dept_id,
        doc_id=doc_id,
        doctors=doctors,
        departments=departments
    )

# Complete Patient Profile & Details
@mrd_bp.route("/patient/<int:patient_id>")
@admin_required
def patient_profile(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    visits = OPDVisit.query.filter_by(patient_id=patient.id).order_by(OPDVisit.visit_date.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.prescription_date.desc()).all()
    reports = MedicalReport.query.filter_by(patient_id=patient.id).order_by(MedicalReport.report_date.desc()).all()
    invoices = Invoice.query.filter_by(patient_id=patient.id).order_by(Invoice.invoice_date.desc()).all()
    file_record = FileTracking.query.filter_by(patient_id=patient.id).first()
    
    return render_template(
        "mrd/patient_profile.html",
        patient=patient,
        appointments=appointments,
        visits=visits,
        prescriptions=prescriptions,
        reports=reports,
        invoices=invoices,
        file_record=file_record
    )

# Chronological Visit Timeline
@mrd_bp.route("/timeline/<int:patient_id>")
@admin_required
def timeline(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.id).all()
    visits = OPDVisit.query.filter_by(patient_id=patient.id).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).all()
    reports = MedicalReport.query.filter_by(patient_id=patient.id).all()
    
    # Consolidate timeline events
    events = []
    for app in appointments:
        events.append({
            "type": "Appointment",
            "date": app.appointment_date,
            "title": f"Consultation Appointment with {app.doctor.name}",
            "description": f"Symptoms: {app.symptoms or 'Not specified'}. Status: {app.status}.",
            "icon": "fa-calendar-check",
            "color": "primary"
        })
    for v in visits:
        events.append({
            "type": "OPD Visit",
            "date": v.visit_date,
            "title": f"OPD check-in (Token: {v.token_number}) with {v.doctor.name}",
            "description": f"Complaint: {v.chief_complaint or 'None'}. Vitals: BP {v.vitals.get('bp','-') if v.vitals else '-'}, Pulse {v.vitals.get('pulse','-') if v.vitals else '-'}. Notes: {v.notes or ''}",
            "icon": "fa-stethoscope",
            "color": "success"
        })
    for p in prescriptions:
        meds = ", ".join([f"{m.medicine_name} ({m.dosage})" for m in p.medicines])
        events.append({
            "type": "Prescription",
            "date": p.prescription_date,
            "title": f"Prescription by {p.doctor.name}",
            "description": f"Diagnosis: {p.diagnosis}. Medicines: {meds}. Notes: {p.notes or ''}",
            "icon": "fa-file-prescription",
            "color": "warning"
        })
    for r in reports:
        events.append({
            "type": "Medical Report",
            "date": r.report_date,
            "title": f"{r.report_title} ({r.report_type})",
            "description": f"Uploaded report. Diagnosis / Notes: {r.description or ''}",
            "icon": "fa-file-medical-alt",
            "color": "info"
        })
        
    # Sort events by date descending
    events.sort(key=lambda x: x["date"], reverse=True)
    
    return render_template(
        "mrd/timeline.html",
        patient=patient,
        events=events
    )

# Alias routes for sidebar compatibility (underscore URLs and dashboard)

@mrd_bp.route('/dashboard')
@admin_required
def dashboard_alias():
    return dashboard()

@mrd_bp.route('/file_tracking')
@admin_required
def file_tracking_alias():
    return file_tracking()

@mrd_bp.route('/file_form')
@admin_required
def file_form_alias():
    return add_file_tracking()

# File Tracking
@mrd_bp.route("/file-tracking")
@admin_required
def file_tracking():
    files = FileTracking.query.order_by(FileTracking.file_number).all()
    today = date.today()
    return render_template("mrd/file_tracking.html", files=files, today=today)

@mrd_bp.route("/file-tracking/add", methods=["GET", "POST"])
@admin_required
def add_file_tracking():
    if request.method == "POST":
        try:
            patient_id = int(request.form["patient_id"])
            file_num = request.form["file_number"]
            location = request.form["current_location"]
            status = request.form["status"]
            notes = request.form.get("notes", "")
            
            # Check duplicate
            existing = FileTracking.query.filter_by(file_number=file_num).first()
            if existing:
                flash("File number already exists!", "danger")
                return redirect(url_for("mrd.file_tracking"))
                
            new_file = FileTracking(
                patient_id=patient_id,
                file_number=file_num,
                current_location=location,
                status=status,
                notes=notes
            )
            db.session.add(new_file)
            db.session.commit()
            flash("Medical record file registered successfully!", "success")
            return redirect(url_for("mrd.file_tracking"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error registering file: {str(e)}", "danger")
            
    patients = Patient.query.all()
    return render_template("mrd/file_form.html", patients=patients)

@mrd_bp.route("/file-tracking/issue/<int:id>", methods=["POST"])
@admin_required
def issue_file(id):
    file_rec = FileTracking.query.get_or_404(id)
    try:
        file_rec.status = "checked_out"
        file_rec.issued_to_staff = request.form["issued_to_staff"]
        file_rec.current_location = request.form["department_location"]
        file_rec.issue_date = datetime.utcnow()
        file_rec.return_date = None
        db.session.commit()
        flash(f"File {file_rec.file_number} checked out successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error checkout: {str(e)}", "danger")
    return redirect(url_for("mrd.file_tracking"))

@mrd_bp.route("/file-tracking/return/<int:id>", methods=["POST"])
@admin_required
def return_file(id):
    file_rec = FileTracking.query.get_or_404(id)
    try:
        file_rec.status = "archived"
        file_rec.current_location = request.form["archive_rack"]
        file_rec.return_date = datetime.utcnow()
        db.session.commit()
        flash(f"File {file_rec.file_number} returned and archived.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error checkin: {str(e)}", "danger")
    return redirect(url_for("mrd.file_tracking"))

# MRD Reports / Analytics
@mrd_bp.route("/reports")
@admin_required
def reports():
    today = date.today()
    
    # 1. Daily patient report (visits & appointments registered today)
    daily_visits = OPDVisit.query.filter_by(visit_date=today).count()
    daily_appointments = Appointment.query.filter_by(appointment_date=today).count()
    daily_admissions = daily_visits + daily_appointments
    
    # 2. Monthly patient report
    first_of_month = date(today.year, today.month, 1)
    monthly_visits = OPDVisit.query.filter(OPDVisit.visit_date >= first_of_month).count()
    monthly_appointments = Appointment.query.filter(Appointment.appointment_date >= first_of_month).count()
    
    # 3. Department caseload stats
    departments = Department.query.all()
    dept_stats = []
    for d in departments:
        # Appointments for doctors in this department
        app_count = Appointment.query.join(Appointment.doctor).filter(Doctor.department_id == d.id).count()
        visit_count = OPDVisit.query.join(OPDVisit.doctor).filter(Doctor.department_id == d.id).count()
        dept_stats.append({
            "name": d.department_name,
            "appointments": app_count,
            "visits": visit_count,
            "total_caseload": app_count + visit_count
        })
        
    return render_template(
        "mrd/mrd_reports.html",
        daily_admissions=daily_admissions,
        daily_visits=daily_visits,
        daily_appointments=daily_appointments,
        monthly_visits=monthly_visits,
        monthly_appointments=monthly_appointments,
        dept_stats=dept_stats
    )