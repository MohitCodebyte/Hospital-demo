from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from models import db, Patient, Doctor, Appointment, Notification, EmailLog
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

# Decorator for admin access
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required.', 'warning')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Notification Dashboard
@notifications_bp.route('/dashboard')
@admin_required
def dashboard():
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()
    return render_template('notifications/dashboard.html', notifications=notifications)

# Send Appointment Confirmation Email
@notifications_bp.route('/send-appointment-confirmation/<int:appointment_id>')
@admin_required
def send_appointment_confirmation(appointment_id):
    from models import Appointment
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Create notification
    notification = Notification(
        recipient_id=appointment.patient_id,
        recipient_type='patient',
        notification_type='appointment',
        title='Appointment Confirmed',
        message=f'Your appointment with Dr. {appointment.doctor.name} has been confirmed for {appointment.appointment_date} at {appointment.appointment_time}.',
        related_id=appointment.id
    )
    db.session.add(notification)
    
    # Send email
    try:
        send_email(
            recipient_email=appointment.patient.email,
            recipient_name=appointment.patient.full_name,
            subject='Appointment Confirmed - Sahara Hospital',
            email_type='appointment_confirmation',
            body=f"""
Dear {appointment.patient.full_name},

Your appointment has been confirmed.

Appointment Details:
- Doctor: Dr. {appointment.doctor.name}
- Date: {appointment.appointment_date}
- Time: {appointment.appointment_time}
- Department: {appointment.doctor.department.department_name}

Please arrive 15 minutes before your appointment time.

Best regards,
Sahara Hospital
"""
        )
        flash('Appointment confirmation sent successfully.', 'success')
    except Exception as e:
        flash(f'Failed to send email: {str(e)}', 'error')
    
    db.session.commit()
    return redirect(url_for('admin.list_appointments'))

# Send Appointment Reminder
@notifications_bp.route('/send-reminder/<int:appointment_id>')
@admin_required
def send_reminder(appointment_id):
    from models import Appointment
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Create notification
    notification = Notification(
        recipient_id=appointment.patient_id,
        recipient_type='patient',
        notification_type='appointment',
        title='Appointment Reminder',
        message=f'Reminder: Your appointment with Dr. {appointment.doctor.name} is scheduled for {appointment.appointment_date} at {appointment.appointment_time}.',
        related_id=appointment.id
    )
    db.session.add(notification)
    
    # Send email
    try:
        send_email(
            recipient_email=appointment.patient.email,
            recipient_name=appointment.patient.full_name,
            subject='Appointment Reminder - Sahara Hospital',
            email_type='reminder',
            body=f"""
Dear {appointment.patient.full_name},

This is a reminder for your upcoming appointment.

Appointment Details:
- Doctor: Dr. {appointment.doctor.name}
- Date: {appointment.appointment_date}
- Time: {appointment.appointment_time}

Please arrive 15 minutes before your appointment time.

Best regards,
Sahara Hospital
"""
        )
        flash('Reminder sent successfully.', 'success')
    except Exception as e:
        flash(f'Failed to send email: {str(e)}', 'error')
    
    db.session.commit()
    return redirect(url_for('admin.list_appointments'))

# Send Prescription Notification
@notifications_bp.route('/send-prescription/<int:prescription_id>')
@admin_required
def send_prescription_notification(prescription_id):
    from models import Prescription
    prescription = Prescription.query.get_or_404(prescription_id)
    
    # Create notification
    notification = Notification(
        recipient_id=prescription.patient_id,
        recipient_type='patient',
        notification_type='prescription',
        title='New Prescription',
        message=f'Dr. {prescription.doctor.name} has prescribed new medicines for you.',
        related_id=prescription.id
    )
    db.session.add(notification)
    
    # Send email
    try:
        medicines_text = '\n'.join([f"- {m.medicine_name}: {m.dosage}, {m.frequency}, {m.duration}" for m in prescription.medicines])
        
        send_email(
            recipient_email=prescription.patient.email,
            recipient_name=prescription.patient.full_name,
            subject='New Prescription - Sahara Hospital',
            email_type='prescription',
            body=f"""
Dear {prescription.patient.full_name},

Dr. {prescription.doctor.name} has prescribed the following medicines:

Diagnosis: {prescription.diagnosis}

Medicines:
{medicines_text}

Notes: {prescription.notes or 'N/A'}

Please follow the dosage instructions carefully.

Best regards,
Sahara Hospital
"""
        )
        flash('Prescription notification sent successfully.', 'success')
    except Exception as e:
        flash(f'Failed to send email: {str(e)}', 'error')
    
    db.session.commit()
    return redirect(url_for('prescriptions.index'))

# Send Billing Notification
@notifications_bp.route('/send-billing/<int:invoice_id>')
@admin_required
def send_billing_notification(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Create notification
    notification = Notification(
        recipient_id=invoice.patient_id,
        recipient_type='patient',
        notification_type='billing',
        title='Invoice Generated',
        message=f'Your invoice {invoice.invoice_number} has been generated. Amount: ${invoice.total_amount}',
        related_id=invoice.id
    )
    db.session.add(notification)
    
    # Send email
    try:
        send_email(
            recipient_email=invoice.patient.email,
            recipient_name=invoice.patient.full_name,
            subject=f'Invoice {invoice.invoice_number} - Sahara Hospital',
            email_type='billing',
            body=f"""
Dear {invoice.patient.full_name},

Your invoice has been generated.

Invoice Details:
- Invoice Number: {invoice.invoice_number}
- Invoice Date: {invoice.invoice_date}
- Total Amount: ${invoice.total_amount}
- Payment Status: {invoice.payment_status}

Please complete the payment at your earliest convenience.

Best regards,
Sahara Hospital
"""
        )
        flash('Billing notification sent successfully.', 'success')
    except Exception as e:
        flash(f'Failed to send email: {str(e)}', 'error')
    
    db.session.commit()
    return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))

# Email Logs
@notifications_bp.route('/email-logs')
@admin_required
def email_logs():
    logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(100).all()
    return render_template('notifications/email_logs.html', logs=logs)

# Helper function to send email
def send_email(recipient_email, recipient_name, subject, email_type, body):
    # Log email
    log = EmailLog(
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        body=body,
        email_type=email_type,
        status='sent'
    )
    
    try:
        # Configure email settings (update with your SMTP settings)
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_username = 'your-email@gmail.com'
        smtp_password = 'your-app-password'
        
        msg = MIMEMultipart()
        msg['From'] = smtp_username
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        
        db.session.add(log)
        db.session.commit()
        
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        db.session.add(log)
        db.session.commit()
        raise e
