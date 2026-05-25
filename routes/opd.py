from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date
from models import db, Patient, Doctor, Department, OPDVisit, OPDFee
from functools import wraps
import qrcode
import os
from models import Appointment

opd_bp = Blueprint('opd', __name__, url_prefix='/opd')

# Decorator for doctor access
def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor_id' not in session:
            flash('Doctor access required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator for staff access
def staff_required(f):

    @wraps(f)

    def decorated_function(*args, **kwargs):

        if (
            session.get('role') != 'staff'
            and session.get('role') != 'doctor'
            and session.get('role') != 'superadmin'
            and not session.get('admin_id')
        ):

            flash(
                'Staff access required.',
                'warning'
            )

            return redirect(
                url_for('auth.login')
            )

        return f(*args, **kwargs)

    return decorated_function

# OPD Dashboard
@opd_bp.route('/dashboard')
@doctor_required
def dashboard():
    today = date.today()
    today_visits = OPDVisit.query.filter_by(visit_date=today).order_by(OPDVisit.token_number).all()
    waiting_count = OPDVisit.query.filter_by(visit_date=today, status='waiting').count()
    in_progress_count = OPDVisit.query.filter_by(visit_date=today, status='in_progress').count()
    completed_count = OPDVisit.query.filter_by(visit_date=today, status='completed').count()
    
    return render_template('opd/dashboard.html', 
                          today_visits=today_visits,
                          waiting_count=waiting_count,
                          in_progress_count=in_progress_count,
                          completed_count=completed_count)

# Patient Check-in
@opd_bp.route('/checkin', methods=['GET', 'POST'])
def checkin():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        
        chief_complaint = request.form.get('chief_complaint')
        doctor_id = request.form.get('doctor_id')
        
        # Get next token number for today
        today = date.today()
        last_visit = OPDVisit.query.filter_by(visit_date=today).order_by(OPDVisit.token_number.desc()).first()
        token_number = (last_visit.token_number + 1) if last_visit else 1
        
        # Create OPD visit
        visit = OPDVisit(
            patient_id=patient_id,
            doctor_id=doctor_id,
            token_number=token_number,
            visit_date=today,
            check_in_time=datetime.now().time(),
            status='waiting',
            chief_complaint=chief_complaint
        )
        
        db.session.add(visit)
        db.session.commit()
        
        flash(f'Patient checked in successfully. Token Number: {token_number}', 'success')
        return redirect(url_for('opd.dashboard'))
    
    patients = Patient.query.all()
    doctors = Doctor.query.filter_by(availability=True).all()
    return render_template('opd/checkin.html', patients=patients, doctors=doctors)

# Patient Queue
@opd_bp.route('/queue')
@doctor_required
def queue():
    today = date.today()
    waiting_patients = OPDVisit.query.filter_by(visit_date=today, status='waiting').order_by(OPDVisit.token_number).all()
    in_progress_patients = OPDVisit.query.filter_by(visit_date=today, status='in_progress').all()
    
    return render_template('opd/queue.html', 
                          waiting_patients=waiting_patients,
                          in_progress_patients=in_progress_patients)

# Start Consultation
@opd_bp.route('/start/<int:visit_id>')
@doctor_required
def start_consultation(visit_id):
    visit = OPDVisit.query.get_or_404(visit_id)
    visit.status = 'in_progress'
    visit.check_in_time = datetime.now().time()
    db.session.commit()
    
    flash('Consultation started.', 'success')
    return redirect(url_for('opd.consultation', visit_id=visit_id))

# Consultation Page
@opd_bp.route('/consultation/<int:visit_id>', methods=['GET', 'POST'])
@doctor_required
def consultation(visit_id):
    visit = OPDVisit.query.get_or_404(visit_id)
    
    if request.method == 'POST':
        # Update vitals
        vitals = {
            'bp': request.form.get('bp'),
            'pulse': request.form.get('pulse'),
            'temp': request.form.get('temp'),
            'weight': request.form.get('weight'),
            'height': request.form.get('height')
        }
        visit.vitals = vitals
        visit.notes = request.form.get('notes')
        
        db.session.commit()
        flash('Consultation notes saved.', 'success')
        return redirect(url_for('opd.complete_consultation', visit_id=visit_id))
    
    return render_template('opd/consultation.html', visit=visit)

# Complete Consultation
@opd_bp.route('/complete/<int:visit_id>')
@doctor_required
def complete_consultation(visit_id):
    visit = OPDVisit.query.get_or_404(visit_id)
    visit.status = 'completed'
    visit.check_out_time = datetime.now().time()
    db.session.commit()
    
    flash('Consultation completed.', 'success')
    return redirect(url_for('opd.dashboard'))

# Patient Visit History
@opd_bp.route('/history/<int:patient_id>')
def visit_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    visits = OPDVisit.query.filter_by(patient_id=patient_id).order_by(OPDVisit.visit_date.desc()).all()
    
    return render_template('opd/history.html', patient=patient, visits=visits)

# OPD Fees Management
@opd_bp.route('/fees')
def fees():
    fees = OPDFee.query.filter_by(is_active=True).all()
    departments = Department.query.all()
    doctors = Doctor.query.all()
    
    return render_template('opd/fees.html', fees=fees, departments=departments, doctors=doctors)

# Add OPD Fee
@opd_bp.route('/fees/add', methods=['POST'])
def add_fee():
    department_id = request.form.get('department_id')
    doctor_id = request.form.get('doctor_id')
    fee_name = request.form.get('fee_name')
    fee_amount = request.form.get('fee_amount')
    
    fee = OPDFee(
        department_id=department_id,
        doctor_id=doctor_id if doctor_id else None,
        fee_name=fee_name,
        fee_amount=fee_amount
    )
    
    db.session.add(fee)
    db.session.commit()
    
    flash('OPD fee added successfully.', 'success')
    return redirect(url_for('opd.fees'))

# Deactivate Fee
@opd_bp.route('/fees/deactivate/<int:fee_id>')
def deactivate_fee(fee_id):
    fee = OPDFee.query.get_or_404(fee_id)
    fee.is_active = False
    db.session.commit()
    
    flash('OPD fee deactivated.', 'success')
    return redirect(url_for('opd.fees'))

# Staff OPD Panel
@opd_bp.route('/staff')
@staff_required
def staff_panel():
    doctors = Doctor.query.filter_by(availability=True).all()
    departments = Department.query.all()
    return render_template('opd/staff_panel.html', doctors=doctors, departments=departments, patient=None)

# Search Patient by Token
@opd_bp.route('/search', methods=['POST'])
@staff_required
def search_by_token():
    token_number = request.form.get('token_number')
    patient = OPDVisit.query.filter_by(
        token_number=token_number
    ).order_by(
        OPDVisit.id.desc()
    ).first()
    if patient:
        patient.visit_id = patient.id
    doctors = Doctor.query.filter_by(availability=True).all()
    departments = Department.query.all()
    
    if not patient:
        flash('Patient not found with this token number.', 'warning')
        return render_template('opd/staff_panel.html', doctors=doctors, departments=departments, patient=None)
    
    return render_template('opd/staff_panel.html', doctors=doctors, departments=departments, patient=patient)

# Search by Token URL Parameter
@opd_bp.route('/search/<token_number>')
@staff_required
def search_token_url(token_number):
    patient = OPDVisit.query.filter_by(
        token_number=token_number
    ).order_by(
        OPDVisit.id.desc()
    ).first()
    if patient:
        patient.visit_id = patient.id
    doctors = Doctor.query.filter_by(availability=True).all()
    departments = Department.query.all()
    
    if not patient:
        flash('Patient not found with this token number.', 'warning')
        return render_template('opd/staff_panel.html', doctors=doctors, departments=departments, patient=None)
    
    return render_template('opd/staff_panel.html', doctors=doctors, departments=departments, patient=patient)

# Generate OPD Slip
@opd_bp.route('/staff-panel/opd-slip/<int:visit_id>')
@staff_required
def generate_opd_slip(visit_id):
    visit = OPDVisit.query.get_or_404(visit_id)
    
    # Generate QR code for OPD slip
    qr_data = f"Token: {visit.token_number}\nPatient: {visit.patient.full_name}\nDoctor: Dr. {visit.doctor.name}\nDepartment: {visit.doctor.department.department_name}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code
    qr_filename = f"opd_slip_{visit.id}_{visit.token_number.replace('-', '_')}.png"
    qr_path = os.path.join('static', 'uploads', 'qr', qr_filename)
    img.save(qr_path)
    
    return render_template('opd/opd_slip.html', visit=visit, qr_filename=qr_filename)

# Reception Dashboard
@opd_bp.route('/reception')
@staff_required
def reception():
    today = date.today()
    departments = Department.query.all()
    doctors = Doctor.query.filter_by(availability=True).all()
    
    # Get queue status
    waiting_count = OPDVisit.query.filter_by(visit_date=today, status='waiting').count()
    in_progress_count = OPDVisit.query.filter_by(visit_date=today, status='in_progress').count()
    completed_count = OPDVisit.query.filter_by(visit_date=today, status='completed').count()
    
    # Get live queue
    live_queue = OPDVisit.query.filter_by(visit_date=today).order_by(OPDVisit.token_number).all()
    
    return render_template('opd/reception.html',
                          departments=departments,
                          doctors=doctors,
                          waiting_count=waiting_count,
                          in_progress_count=in_progress_count,
                          completed_count=completed_count,
                          live_queue=live_queue)

# Assign Doctor to Patient
@opd_bp.route('/reception/assign-doctor/<int:visit_id>', methods=['POST'])
@staff_required
def assign_doctor(visit_id):
    visit = OPDVisit.query.get_or_404(visit_id)
    doctor_id = request.form.get('doctor_id')
    
    visit.doctor_id = doctor_id
    db.session.commit()
    
    flash('Doctor assigned successfully.', 'success')
    return redirect(url_for('opd.reception'))

# Update Patient Status
@opd_bp.route('/reception/update-status/<int:visit_id>', methods=['POST'])
@staff_required
def update_status(visit_id):
    visit = OPDVisit.query.get_or_404(visit_id)
    status = request.form.get('status')
    
    visit.status = status
    if status == 'in_progress' and not visit.check_in_time:
        visit.check_in_time = datetime.now().time()
    elif status == 'completed':
        visit.check_out_time = datetime.now().time()
    
    db.session.commit()
    
    flash('Status updated successfully.', 'success')
    return redirect(url_for('opd.reception'))

# Update Patient Details
@opd_bp.route('/update-patient/<int:visit_id>', methods=['POST'])
@staff_required
def update_patient_details(visit_id):

    visit = OPDVisit.query.get_or_404(visit_id)

    # Update patient details
    visit.patient.full_name = request.form.get('full_name')
    visit.patient.phone = request.form.get('phone')
    visit.patient.gender = request.form.get('gender')
    visit.patient.age = int(request.form.get('age', 0))

    # Update symptoms
    visit.chief_complaint = request.form.get('symptoms')
    doctor_id = request.form.get('doctor_id')

    # if doctor_id:
    #     visit.doctor_id = int(doctor_id)

    # Update department & doctor
    department_id = request.form.get('department_id')
    doctor_id = request.form.get('doctor_id')

    # Update selected doctor directly
    if doctor_id and doctor_id.strip():

        visit.doctor_id = int(doctor_id)

    # If doctor not selected, auto assign from department
    elif department_id:

        new_doctor = Doctor.query.filter_by(
            department_id=department_id,
            availability=True
        ).first()

        if new_doctor:
            visit.doctor_id = new_doctor.id

    # SAVE CHANGES
    db.session.add(visit)
    db.session.add(visit.patient)
    db.session.commit()

    db.session.refresh(visit)
    db.session.refresh(visit.patient)
    db.session.refresh(visit.doctor)

    flash(
        'Patient details updated successfully.',
        'success'
    )

    return redirect(
        url_for(
            'opd.search_token_url',
            token_number=visit.token_number
        )
    )

# Call Next Patient
@opd_bp.route('/reception/call-next/<int:department_id>')
@staff_required
def call_next(department_id):
    today = date.today()
    next_patient = OPDVisit.query.filter_by(
        visit_date=today, 
        status='waiting'
    ).join(Doctor).filter(
        Doctor.department_id == department_id
    ).order_by(OPDVisit.token_number).first()
    
    if next_patient:
        next_patient.status = 'in_progress'
        next_patient.check_in_time = datetime.now().time()
        db.session.commit()
        flash(f'Calling patient {next_patient.patient.full_name} (Token: {next_patient.token_number})', 'success')
    else:
        flash('No patients waiting in this department.', 'info')
    
    return redirect(url_for('opd.reception'))

# Fetch Patient Details
@opd_bp.route('/reception/fetch-patient', methods=['POST'])
@staff_required
def fetch_patient():
    search_term = request.form.get('search_term')
    
    # Search by patient ID or OPD number
    patient = Patient.query.filter(
        (Patient.id == search_term) | 
        (Patient.email == search_term) |
        (Patient.phone == search_term)
    ).first()
    
    if patient:
        return {
            'success': True,
            'patient': {
                'id': patient.id,
                'name': patient.full_name,
                'email': patient.email,
                'phone': patient.phone,
                'age': patient.age,
                'gender': patient.gender,
                'address': patient.address
            }
        }
    else:
        return {'success': False, 'message': 'Patient not found'}

# Generate OPD Token
@opd_bp.route('/reception/generate-token', methods=['POST'])
@staff_required
def generate_token():
    patient_id = request.form.get('patient_id')
    department_id = request.form.get('department_id')
    doctor_id = request.form.get('doctor_id')
    chief_complaint = request.form.get('chief_complaint')
    
    # Get next token number for today
    today = date.today()
    last_visit = OPDVisit.query.filter_by(visit_date=today).order_by(OPDVisit.token_number.desc()).first()
    token_number = (last_visit.token_number + 1) if last_visit else 1
    
    # Create OPD visit
    visit = OPDVisit(
        patient_id=patient_id,
        doctor_id=doctor_id,
        token_number=token_number,
        visit_date=today,
        check_in_time=datetime.now().time(),
        status='waiting',
        chief_complaint=chief_complaint
    )
    
    db.session.add(visit)
    db.session.commit()
    
    flash(f'OPD Token #{token_number} generated successfully.', 'success')
    return redirect(url_for('opd.print_slip', visit_id=visit.id))

# Print OPD Slip
@opd_bp.route('/reception/print-slip/<int:visit_id>')
@staff_required
def print_slip(visit_id):
    visit = OPDVisit.query.get_or_404(visit_id)
    return render_template('opd/print_slip.html', visit=visit)


# =====================================
# PATIENT OPD TOKEN PAGE
# =====================================

@opd_bp.route('/token')
def patient_token():
    departments = Department.query.all()
    return render_template('opd/patient_token.html', departments=departments)
@opd_bp.route('/token/submit', methods=['POST'])
def patient_submit_token():

    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    department_id = request.form.get('department_id')
    symptoms = request.form.get('symptoms')
    gender = request.form.get('gender')
    age = request.form.get('age')
    is_emergency = request.form.get('is_emergency')

    # Get department
    department = Department.query.get_or_404(
        department_id
    )

    # Assign available doctor
    doctor = Doctor.query.filter_by(
        department_id=department_id,
        availability=True
    ).first()

    if not doctor:

        flash(
            'No doctor available in this department.',
            'warning'
        )

        return redirect(
            url_for('opd.patient_token')
        )

    # Find existing patient
    patient = Patient.query.filter_by(
        phone=phone
    ).first()

    # Create new patient
    if not patient:

        patient = Patient(
            full_name=full_name,
            phone=phone,
            email=f"{phone}@saharahospital.com",
            gender=gender,
            age=int(age),
            password='temp_password'
        )

        db.session.add(patient)
        db.session.flush()

    # Generate token number
    today = date.today()

    last_visit = OPDVisit.query.filter_by(
        visit_date=today
    ).order_by(
        OPDVisit.id.desc()
    ).first()

    if last_visit and last_visit.token_number:

        try:

            last_token_num = int(
                str(last_visit.token_number).split('-')[1]
            )

        except:

            last_token_num = 100

    else:

        last_token_num = 100

    token_number = f"OPD-{last_token_num + 1}"

    # Create OPD Visit
    visit = OPDVisit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        token_number=token_number,
        visit_date=today,
        check_in_time=datetime.now().time(),
        status='waiting',
        chief_complaint=symptoms
    )

    db.session.add(visit)
    db.session.commit()

    # Queue Position
    waiting_visits = OPDVisit.query.filter_by(
        visit_date=today,
        status='waiting'
    ).order_by(
        OPDVisit.id
    ).all()

    queue_position = 0

    for i, v in enumerate(waiting_visits):

        if v.id == visit.id:

            queue_position = i + 1
            break

    estimated_wait = queue_position * 10

    # Create QR folder
    qr_folder = os.path.join(
        'static',
        'uploads',
        'qr'
    )

    os.makedirs(
        qr_folder,
        exist_ok=True
    )

    # Generate QR code
    qr_data = f"""
    Token: {token_number}
    Patient: {full_name}
    Doctor: Dr. {doctor.name}
    Department: {department.department_name}
    """

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5
    )

    qr.add_data(qr_data)

    qr.make(
        fit=True
    )

    img = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    qr_filename = f"qr_{visit.id}.png"

    qr_path = os.path.join(
        qr_folder,
        qr_filename
    )

    img.save(qr_path)

    flash(
        f'OPD Token {token_number} generated successfully.',
        'success'
    )

    return render_template(
        'opd/token_success.html',
        visit=visit,
        queue_position=queue_position,
        estimated_wait=estimated_wait,
        qr_filename=qr_filename
    )
    
    
# =====================================
# APPROVE APPOINTMENT
# =====================================

@opd_bp.route('/approve-appointment/<int:appointment_id>')
@staff_required
def approve_appointment(appointment_id):

    from models import Appointment

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
        url_for(
            'doctors.view_appointment',
            appointment_id=appointment.id
        )
    )

# =====================================
# REJECT APPOINTMENT
# =====================================

@opd_bp.route('/reject-appointment/<int:appointment_id>')
@staff_required
def reject_appointment(appointment_id):


    appointment = Appointment.query.get_or_404(
        appointment_id
    )

    appointment.status = 'cancelled'

    db.session.commit()

    flash(
        'Appointment rejected.',
        'danger'
    )

    return redirect(
        url_for(
            'doctors.view_appointment',
            appointment_id=appointment.id
        )
    )