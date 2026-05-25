from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Patient, AdminUser, db
from functools import wraps
from models import InventoryItem

auth_bp = Blueprint('auth', __name__)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'patient_id' not in session and 'admin_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Patient Registration
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Check if email already exists
            existing_patient = Patient.query.filter_by(email=request.form['email']).first()
            if existing_patient:
                flash('Email already registered. Please login.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Create new patient
            patient = Patient(
                full_name=request.form['full_name'],
                email=request.form['email'],
                phone=request.form['phone'],
                gender=request.form['gender'],
                age=int(request.form['age']),
                address=request.form.get('address', '')
            )
            patient.set_password(request.form['password'])
            
            db.session.add(patient)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html')

# Patient Login
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    role = request.args.get('role', 'patient')
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        patient = Patient.query.filter_by(email=email).first()
        
        if patient and patient.check_password(password):

            session['patient_id'] = patient.id
            session['patient_name'] = patient.full_name
            session['role'] = patient.role

            flash(f'Welcome back, {patient.full_name}!', 'success')

            # ROLE BASED LOGIN

            if patient.role == 'doctor':
                session['doctor_logged_in'] = True
                session['doctor_id'] = patient.id
                session['doctor_name'] = patient.full_name

                return redirect(
                    url_for('doctors.doctor_dashboard')
                )

            elif patient.role == 'staff':

                return redirect(url_for('staff.staff_dashboard'))

            elif patient.role == 'superadmin':

                return redirect(url_for('superadmin.superadmin_dashboard'))

            else:

                return redirect(url_for('auth.patient_dashboard'))


            

        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', role=role)

# Admin Login
@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        admin = AdminUser.query.filter_by(username=username).first()
        
        if admin and admin.password == password:
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            session['admin_role'] = admin.role
            flash(f'Welcome Admin, {admin.username}!', 'success')
            return redirect(url_for('auth.admin_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('auth/admin_login.html')

# Logout
@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home.index'))

# Admin Dashboard
@auth_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    from models import Doctor, Department, Appointment, Patient, ContactMessage, EmergencyContact, InventoryItem

    stats = {
        'inventory_items': InventoryItem.query.count(),
        'doctors': Doctor.query.count(),
        'departments': Department.query.count(),
        'appointments': Appointment.query.count(),
        'patients': Patient.query.count(),
        'messages': ContactMessage.query.count(),
        'emergencies': EmergencyContact.query.count()
    }
    
    recent_appointments = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()
    recent_messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()
    all_users = Patient.query.all()
    
    return render_template(
                'admin/dashboard.html',
                stats=stats,
                recent_appointments=recent_appointments,
                recent_messages=recent_messages,
                all_users=all_users
            )

# Patient Dashboard
@auth_bp.route('/dashboard')
@login_required
def patient_dashboard():
    from models import Appointment
    
    patient_id = session.get('patient_id')
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.created_at.desc()).all()
    
    return render_template('auth/patient_dashboard.html', appointments=appointments)

# Change User Role
@auth_bp.route('/change-role/<int:user_id>', methods=['POST'])
@admin_required
def change_role(user_id):

    user = Patient.query.get_or_404(user_id)

    new_role = request.form.get('role')

    print("OLD ROLE:", user.role)

    user.role = new_role

    db.session.commit()

    db.session.refresh(user)

    print("NEW ROLE:", user.role)

    flash(
        f'{user.full_name} role updated to {new_role}',
        'success'
    )

    return redirect(
        url_for('admin.list_patients')
    )


# Settings Page
@auth_bp.route('/settings')
@admin_required
def settings():
    return render_template('admin/settings.html')
