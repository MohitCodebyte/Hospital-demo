from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import ContactMessage, db

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/')
def index():
    return render_template('contact.html')

@contact_bp.route('/submit', methods=['POST'])
def submit():
    try:
        contact = ContactMessage(
            name=request.form['name'],
            email=request.form['email'],
            subject=request.form.get('subject', ''),
            message=request.form['message']
        )
        db.session.add(contact)
        db.session.commit()
        flash('Message sent successfully!', 'success')
        return redirect(url_for('contact.index'))
    except Exception as e:
        db.session.rollback()
        flash('Error sending message. Please try again.', 'error')
        return redirect(url_for('contact.index'))
