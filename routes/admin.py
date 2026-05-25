from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Doctor, Department, Appointment, Patient, ContactMessage, EmergencyContact, db
from functools import wraps
from routes.auth import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Doctors CRUD
@admin_bp.route('/doctors')
@admin_required
def list_doctors():
    doctors = Doctor.query.all()
    return render_template('admin/doctors_list.html', doctors=doctors)

@admin_bp.route('/doctors/add', methods=['GET', 'POST'])
@admin_required
def add_doctor():
    if request.method == 'POST':
        try:
            doctor = Doctor(
                name=request.form['name'],
                specialization=request.form['specialization'],
                experience=int(request.form['experience']),
                qualification=request.form['qualification'],
                phone=request.form['phone'],
                email=request.form['email'],
                image=request.form.get('image', ''),
                department_id=int(request.form['department_id']),
                availability=request.form.get('availability') == 'on'
            )
            db.session.add(doctor)
            db.session.commit()
            flash('Doctor added successfully!', 'success')
            return redirect(url_for('admin.list_doctors'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding doctor. Please try again.', 'error')
    
    departments = Department.query.all()
    return render_template('admin/doctor_form.html', departments=departments)

@admin_bp.route('/doctors/edit/<int:doctor_id>', methods=['GET', 'POST'])
@admin_required
def edit_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    
    if request.method == 'POST':
        try:
            doctor.name = request.form['name']
            doctor.specialization = request.form['specialization']
            doctor.experience = int(request.form['experience'])
            doctor.qualification = request.form['qualification']
            doctor.phone = request.form['phone']
            doctor.email = request.form['email']
            doctor.image = request.form.get('image', '')
            doctor.department_id = int(request.form['department_id'])
            doctor.availability = request.form.get('availability') == 'on'
            
            db.session.commit()
            flash('Doctor updated successfully!', 'success')
            return redirect(url_for('admin.list_doctors'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating doctor. Please try again.', 'error')
    
    departments = Department.query.all()
    return render_template('admin/doctor_form.html', doctor=doctor, departments=departments)

@admin_bp.route('/doctors/delete/<int:doctor_id>')
@admin_required
def delete_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    try:
        db.session.delete(doctor)
        db.session.commit()
        flash('Doctor deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting doctor. Please try again.', 'error')
    return redirect(url_for('admin.list_doctors'))

# Departments CRUD
@admin_bp.route('/departments')
@admin_required
def list_departments():
    departments = Department.query.all()
    return render_template('admin/departments_list.html', departments=departments)

@admin_bp.route('/departments/add', methods=['GET', 'POST'])
@admin_required
def add_department():
    if request.method == 'POST':
        try:
            department = Department(
                department_name=request.form['department_name'],
                department_code=request.form.get('department_code', ''),
                description=request.form['description'],
                department_type=request.form.get('department_type', 'OPD'),
                department_head_id=request.form.get('department_head_id') or None,
                floor_number=request.form.get('floor_number', ''),
                building_wing=request.form.get('building_wing', ''),
                phone_extension=request.form.get('phone_extension', ''),
                email=request.form.get('email', ''),
                status=request.form.get('status', 'active'),
                image=request.form.get('image', '')
            )
            db.session.add(department)
            db.session.commit()
            flash('Department added successfully!', 'success')
            return redirect(url_for('admin.list_departments'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding department: {str(e)}', 'error')
    
    doctors = Doctor.query.all()
    return render_template('admin/department_form.html', doctors=doctors)

@admin_bp.route('/departments/edit/<int:department_id>', methods=['GET', 'POST'])
@admin_required
def edit_department(department_id):
    department = Department.query.get_or_404(department_id)
    
    if request.method == 'POST':
        try:
            department.department_name = request.form['department_name']
            department.department_code = request.form.get('department_code', '')
            department.description = request.form['description']
            department.department_type = request.form.get('department_type', 'OPD')
            department.department_head_id = request.form.get('department_head_id') or None
            department.floor_number = request.form.get('floor_number', '')
            department.building_wing = request.form.get('building_wing', '')
            department.phone_extension = request.form.get('phone_extension', '')
            department.email = request.form.get('email', '')
            department.status = request.form.get('status', 'active')
            department.image = request.form.get('image', '')
            
            db.session.commit()
            flash('Department updated successfully!', 'success')
            return redirect(url_for('admin.list_departments'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating department: {str(e)}', 'error')
    
    doctors = Doctor.query.all()
    return render_template('admin/department_form.html', department=department, doctors=doctors)

@admin_bp.route('/departments/view/<int:department_id>')
@admin_required
def view_department(department_id):
    department = Department.query.get_or_404(department_id)
    return render_template('admin/department_view.html', department=department)

@admin_bp.route('/departments/delete/<int:department_id>')
@admin_required
def delete_department(department_id):
    department = Department.query.get_or_404(department_id)
    try:
        db.session.delete(department)
        db.session.commit()
        flash('Department deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting department. Please try again.', 'error')
    return redirect(url_for('admin.list_departments'))

# Appointments Management
@admin_bp.route('/appointments')
@admin_required
def list_appointments():
    appointments = Appointment.query.order_by(Appointment.created_at.desc()).all()
    return render_template('admin/appointments_list.html', appointments=appointments)

@admin_bp.route('/appointments/<int:appointment_id>/status/<status>')
@admin_required
def update_appointment_status(appointment_id, status):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.status = status
    db.session.commit()
    flash(f'Appointment status updated to {status}', 'success')
    return redirect(url_for('admin.list_appointments'))

@admin_bp.route('/appointments/delete/<int:appointment_id>')
@admin_required
def delete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    try:
        db.session.delete(appointment)
        db.session.commit()
        flash('Appointment deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting appointment. Please try again.', 'error')
    return redirect(url_for('admin.list_appointments'))

# Patients Management
@admin_bp.route('/patients')
@admin_required
def list_patients():
    patients = Patient.query.all()
    return render_template('admin/patients_list.html', patients=patients)

@admin_bp.route('/patients/delete/<int:patient_id>')
@admin_required
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    try:
        db.session.delete(patient)
        db.session.commit()
        flash('Patient deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting patient. Please try again.', 'error')
    return redirect(url_for('admin.list_patients'))

# Messages Management
@admin_bp.route('/messages')
@admin_required
def list_messages():
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages_list.html', messages=messages)

@admin_bp.route('/messages/delete/<int:message_id>')
@admin_required
def delete_message(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    try:
        db.session.delete(message)
        db.session.commit()
        flash('Message deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting message. Please try again.', 'error')
    return redirect(url_for('admin.list_messages'))

# Emergency Contacts Management
@admin_bp.route('/emergencies')
@admin_required
def list_emergencies():
    emergencies = EmergencyContact.query.order_by(EmergencyContact.created_at.desc()).all()
    return render_template('admin/emergencies_list.html', emergencies=emergencies)
