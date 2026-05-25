from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import date, datetime
from models import (
    db, LabTest, LabOrder, LabOrderItem, Patient, Doctor, Invoice, InvoiceItem
)
from routes.auth import admin_required

laboratory_bp = Blueprint('laboratory', __name__, url_prefix='/laboratory')

# Laboratory Dashboard
@laboratory_bp.route('/')
@admin_required
def dashboard():
    orders = LabOrder.query.all()
    tests = LabTest.query.all()
    
    total_orders = len(orders)
    pending_orders = len([o for o in orders if o.status == 'pending'])
    completed_orders = len([o for o in orders if o.status == 'completed'])
    total_tests = len(tests)
    
    recent_orders = LabOrder.query.order_by(LabOrder.created_at.desc()).limit(10).all()
    
    return render_template(
        'laboratory/dashboard.html',
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
        total_tests=total_tests,
        recent_orders=recent_orders
    )

# Test Master Catalog CRUD
@laboratory_bp.route('/tests')
@admin_required
def tests():
    tests_list = LabTest.query.all()
    return render_template('laboratory/tests.html', tests=tests_list)

@laboratory_bp.route('/tests/add', methods=['GET', 'POST'])
@admin_required
def add_test():
    if request.method == 'POST':
        try:
            name = request.form['test_name']
            category = request.form['category']
            rate = float(request.form['rate'])
            normal_range = request.form.get('normal_range', '')
            unit = request.form.get('unit', '')
            
            # Check duplicate
            existing = LabTest.query.filter_by(test_name=name).first()
            if existing:
                flash('Lab test already exists in master!', 'danger')
                return redirect(url_for('laboratory.tests'))
                
            new_test = LabTest(
                test_name=name,
                category=category,
                rate=rate,
                normal_range=normal_range,
                unit=unit
            )
            db.session.add(new_test)
            db.session.commit()
            flash('Lab test added successfully to catalog!', 'success')
            return redirect(url_for('laboratory.tests'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding test: {str(e)}', 'danger')
            
    return render_template('laboratory/test_form.html', action='Add')

@laboratory_bp.route('/tests/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_test(id):
    test = LabTest.query.get_or_404(id)
    if request.method == 'POST':
        try:
            test.test_name = request.form['test_name']
            test.category = request.form['category']
            test.rate = float(request.form['rate'])
            test.normal_range = request.form.get('normal_range', '')
            test.unit = request.form.get('unit', '')
            
            db.session.commit()
            flash('Lab test updated successfully!', 'success')
            return redirect(url_for('laboratory.tests'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating test: {str(e)}', 'danger')
            
    return render_template('laboratory/test_form.html', test=test, action='Edit')

@laboratory_bp.route('/tests/delete/<int:id>')
@admin_required
def delete_test(id):
    test = LabTest.query.get_or_404(id)
    try:
        db.session.delete(test)
        db.session.commit()
        flash('Lab test removed from catalog.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting test: {str(e)}', 'danger')
    return redirect(url_for('laboratory.tests'))

# Lab Orders (Patients)
@laboratory_bp.route('/orders')
@admin_required
def orders():
    orders_list = LabOrder.query.order_by(LabOrder.order_date.desc()).all()
    return render_template('laboratory/orders.html', orders=orders_list)

@laboratory_bp.route('/orders/new', methods=['GET', 'POST'])
@admin_required
def new_order():
    if request.method == 'POST':
        try:
            patient_id = int(request.form['patient_id'])
            doc_id_str = request.form.get('doctor_id')
            doctor_id = int(doc_id_str) if doc_id_str else None
            order_date_str = request.form['order_date']
            order_date = date.fromisoformat(order_date_str) if order_date_str else date.today()
            
            test_ids = request.form.getlist('test_id[]')
            
            if not test_ids:
                flash('Please select at least one lab test!', 'danger')
                return redirect(url_for('laboratory.new_order'))
                
            subtotal = 0.0
            order_items = []
            
            for t_id in test_ids:
                if not t_id:
                    continue
                test = LabTest.query.get(int(t_id))
                if test:
                    subtotal += test.rate
                    item = LabOrderItem(test_id=test.id)
                    order_items.append(item)
                    
            # Generate billing invoice integration
            last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
            inv_idx = last_invoice.id + 1 if last_invoice else 1
            invoice_number = f'INV-LAB-{date.today().year}-{inv_idx:04d}'
            
            invoice = Invoice(
                patient_id=patient_id,
                invoice_number=invoice_number,
                invoice_date=order_date,
                subtotal=subtotal,
                tax=subtotal * 0.18, # 18% GST for Lab Tests
                discount=0.0,
                total_amount=subtotal * 1.18,
                payment_status='pending',
                notes='Automated Lab Order Invoice'
            )
            db.session.add(invoice)
            db.session.flush() # gets invoice.id
            
            # Create invoice items
            for item in order_items:
                test = LabTest.query.get(item.test_id)
                inv_item = InvoiceItem(
                    invoice_id=invoice.id,
                    item_name=f'Lab Test - {test.test_name}',
                    item_type='lab_test',
                    quantity=1,
                    unit_price=test.rate,
                    total_price=test.rate
                )
                db.session.add(inv_item)
                
            # Create LabOrder
            order = LabOrder(
                patient_id=patient_id,
                doctor_id=doctor_id,
                order_date=order_date,
                status='pending',
                payment_status='pending',
                invoice_id=invoice.id
            )
            db.session.add(order)
            db.session.flush()
            
            for item in order_items:
                item.lab_order_id = order.id
                db.session.add(item)
                
            db.session.commit()
            flash(f'Lab order placed successfully. Invoice {invoice_number} created.', 'success')
            return redirect(url_for('laboratory.orders'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error placing lab order: {str(e)}', 'danger')
            
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    tests = LabTest.query.order_by(LabTest.test_name).all()
    return render_template('laboratory/order_form.html', patients=patients, doctors=doctors, tests=tests)

# Lab Results Entry
@laboratory_bp.route('/orders/enter-results/<int:order_id>', methods=['GET', 'POST'])
@admin_required
def enter_results(order_id):
    order = LabOrder.query.get_or_404(order_id)
    if request.method == 'POST':
        try:
            item_ids = request.form.getlist('item_id[]')
            results = request.form.getlist('result_value[]')
            notes_list = request.form.getlist('notes[]')
            
            for i in range(len(item_ids)):
                item = LabOrderItem.query.get(int(item_ids[i]))
                if item:
                    item.result_value = results[i]
                    item.notes = notes_list[i]
                    item.result_date = datetime.utcnow()
                    
            order.status = 'completed'
            db.session.commit()
            flash('Lab results saved successfully!', 'success')
            return redirect(url_for('laboratory.orders'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving results: {str(e)}', 'danger')
            
    return render_template('laboratory/enter_results.html', order=order)

# View Printable Lab Report PDF Style
@laboratory_bp.route('/orders/report/<int:order_id>')
@admin_required
def view_report(order_id):
    order = LabOrder.query.get_or_404(order_id)
    return render_template('laboratory/report_print.html', order=order)
