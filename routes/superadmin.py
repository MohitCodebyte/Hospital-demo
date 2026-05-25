from flask import Blueprint, render_template, request, redirect, url_for, flash, session

superadmin_bp = Blueprint('superadmin', __name__)

# Super Admin Login
@superadmin_bp.route('/superadmin/login', methods=['GET', 'POST'])
def superadmin_login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        # Temporary Super Admin Login
        # Later connect with MySQL super admin table

        if email == "superadmin@sahara.com" and password == "super123":

            session['superadmin_logged_in'] = True
            session['superadmin_name'] = "Super Admin"

            flash('Super Admin login successful!', 'success')

            return redirect(url_for('superadmin.superadmin_dashboard'))

        else:

            flash('Invalid super admin credentials!', 'danger')

    return render_template('superadmin_login.html')


# Super Admin Dashboard
@superadmin_bp.route('/superadmin/dashboard')
def superadmin_dashboard():

    if not session.get('superadmin_logged_in'):

        flash('Please login first.', 'warning')

        return redirect(url_for('superadmin.superadmin_login'))

    return render_template('superadmin_dashboard.html')


# Super Admin Logout
@superadmin_bp.route('/superadmin/logout')
def superadmin_logout():

    session.pop('superadmin_logged_in', None)
    session.pop('superadmin_name', None)

    flash('Super Admin logged out successfully.', 'info')

    return redirect(url_for('superadmin.superadmin_login'))