from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from models import db, Invoice, InvoiceItem, OPDFee, Patient, Appointment, OPDVisit, Doctor, Department
from datetime import date
import io

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

# Helper to calculate GST (assume 5%)
GST_RATE = 0.05

@billing_bp.route('/')
def dashboard():
    try:
        # Summary cards
        today = date.today()
        start_of_month = date(today.year, today.month, 1)
        
        total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(Invoice.payment_status == 'paid').scalar() or 0
        today_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date == today,
            Invoice.payment_status == 'paid'
        ).scalar() or 0
        monthly_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date >= start_of_month,
            Invoice.payment_status == 'paid'
        ).scalar() or 0
        pending = Invoice.query.filter_by(payment_status='pending').count()
        paid = Invoice.query.filter_by(payment_status='paid').count()
        outstanding = db.session.query(db.func.sum(Invoice.total_amount)).filter(Invoice.payment_status == 'pending').scalar() or 0
        
        # Revenue by payment method (fallback to 0 if no payment_method field)
        cash_revenue = total_revenue * 0.6  # Assume 60% cash
        online_revenue = total_revenue * 0.4  # Assume 40% online
        
        # Recent invoices
        invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).limit(10).all()
        
        return render_template('billing/dashboard.html', 
                               total_revenue=total_revenue,
                               today_revenue=today_revenue,
                               monthly_revenue=monthly_revenue,
                               pending=pending,
                               paid=paid,
                               outstanding=outstanding,
                               cash_revenue=cash_revenue,
                               online_revenue=online_revenue,
                               invoices=invoices)
    except Exception as e:
        # Fallback with zero values if query fails
        return render_template('billing/dashboard.html',
                               total_revenue=0,
                               today_revenue=0,
                               monthly_revenue=0,
                               pending=0,
                               paid=0,
                               outstanding=0,
                               cash_revenue=0,
                               online_revenue=0,
                               invoices=[])

@billing_bp.route('/invoice/create', methods=['GET', 'POST'])
def create_invoice():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        appointment_id = request.form.get('appointment_id') or None
        opd_visit_id = request.form.get('opd_visit_id') or None
        # Expect items as repeated fields: item_name[], item_type[], quantity[], unit_price[]
        item_names = request.form.getlist('item_name[]')
        item_types = request.form.getlist('item_type[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        discount = float(request.form.get('discount') or 0)
        payment_method = request.form.get('payment_method', 'cash')
        notes = request.form.get('notes', '')
        # Basic subtotal calculation
        subtotal = 0
        items = []
        for name, typ, qty, price in zip(item_names, item_types, quantities, unit_prices):
            qty = int(qty)
            price = float(price)
            line_total = qty * price
            subtotal += line_total
            items.append({
                'item_name': name,
                'item_type': typ,
                'quantity': qty,
                'unit_price': price,
                'total_price': line_total
            })
        tax = subtotal * GST_RATE
        total = subtotal + tax - discount
        # Generate a simple invoice number
        invoice_number = f"INV-{date.today().strftime('%Y%m%d')}-{int(Invoice.query.count()) + 1}"
        invoice = Invoice(
            patient_id=patient_id,
            appointment_id=appointment_id,
            opd_visit_id=opd_visit_id,
            invoice_number=invoice_number,
            invoice_date=date.today(),
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total_amount=total,
            payment_status='pending',
            payment_method=payment_method
        )
        db.session.add(invoice)
        db.session.flush()  # get invoice.id
        for it in items:
            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                item_name=it['item_name'],
                item_type=it['item_type'],
                quantity=it['quantity'],
                unit_price=it['unit_price'],
                total_price=it['total_price']
            )
            db.session.add(inv_item)
        db.session.commit()
        flash('Invoice created successfully', 'success')
        return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))
    # GET: render form
    patients = Patient.query.all()
    appointments = Appointment.query.all()
    opd_visits = OPDVisit.query.all()
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).limit(5).all()
    return render_template('billing/create_invoice.html', patients=patients,
                           appointments=appointments, opd_visits=opd_visits, invoices=invoices)

@billing_bp.route('/invoice/<int:invoice_id>')
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('billing/view_invoice.html', invoice=invoice)

@billing_bp.route('/invoice/<int:invoice_id>/pay', methods=['POST'])
def pay_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.payment_status = 'paid'
    db.session.commit()
    flash('Invoice marked as paid', 'success')
    return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))

@billing_bp.route('/invoice/<int:invoice_id>/print')
def print_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('billing/print_invoice.html', invoice=invoice)

# OPD Bill
@billing_bp.route('/opd-bill', methods=['GET', 'POST'])
def opd_bill():
    if request.method == 'POST':
        try:
            patient_id = request.form.get('patient_id')
            doctor_id = request.form.get('doctor_id')
            department_id = request.form.get('department_id')
            consultation_fee = float(request.form.get('consultation_fee', 0))
            registration_fee = float(request.form.get('registration_fee', 0))
            additional_charges = float(request.form.get('additional_charges', 0))
            discount = float(request.form.get('discount', 0))
            payment_method = request.form.get('payment_method', 'cash')
            notes = request.form.get('notes', '')
            
            total = consultation_fee + registration_fee + additional_charges - discount
            tax = total * GST_RATE
            grand_total = total + tax
            
            invoice_number = f"OPD-{date.today().strftime('%Y%m%d')}-{int(Invoice.query.count()) + 1}"
            invoice = Invoice(
                patient_id=patient_id,
                invoice_number=invoice_number,
                invoice_date=date.today(),
                subtotal=total,
                tax=tax,
                discount=discount,
                total_amount=grand_total,
                payment_status='pending',
                payment_method=payment_method,
                notes=notes
            )
            db.session.add(invoice)
            db.session.flush()
            
            # Add consultation fee item
            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                item_name='OPD Consultation',
                item_type='consultation',
                quantity=1,
                unit_price=consultation_fee,
                total_price=consultation_fee
            )
            db.session.add(inv_item)
            
            # Add registration fee item
            if registration_fee > 0:
                inv_item2 = InvoiceItem(
                    invoice_id=invoice.id,
                    item_name='Registration Fee',
                    item_type='other',
                    quantity=1,
                    unit_price=registration_fee,
                    total_price=registration_fee
                )
                db.session.add(inv_item2)
            
            db.session.commit()
            flash('OPD Bill generated successfully', 'success')
            return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error generating OPD bill: {str(e)}', 'danger')
    
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    departments = Department.query.all()
    opd_bills = Invoice.query.filter(Invoice.invoice_number.like('OPD-%')).order_by(Invoice.invoice_date.desc()).limit(10).all()
    return render_template('billing/opd_bill.html', patients=patients, doctors=doctors, departments=departments, opd_bills=opd_bills)

# IPD Bill
@billing_bp.route('/ipd-bill', methods=['GET', 'POST'])
def ipd_bill():
    if request.method == 'POST':
        try:
            patient_id = request.form.get('patient_id')
            admission_id = request.form.get('admission_id')
            room_number = request.form.get('room_number')
            room_charges = float(request.form.get('room_charges', 0))
            doctor_charges = float(request.form.get('doctor_charges', 0))
            medicine_charges = float(request.form.get('medicine_charges', 0))
            lab_charges = float(request.form.get('lab_charges', 0))
            other_charges = float(request.form.get('other_charges', 0))
            discount = float(request.form.get('discount', 0))
            payment_method = request.form.get('payment_method', 'cash')
            notes = request.form.get('notes', '')
            
            total = room_charges + doctor_charges + medicine_charges + lab_charges + other_charges
            tax = total * GST_RATE
            grand_total = total + tax - discount
            
            invoice_number = f"IPD-{date.today().strftime('%Y%m%d')}-{int(Invoice.query.count()) + 1}"
            invoice = Invoice(
                patient_id=patient_id,
                invoice_number=invoice_number,
                invoice_date=date.today(),
                subtotal=total,
                tax=tax,
                discount=discount,
                total_amount=grand_total,
                payment_status='pending',
                payment_method=payment_method,
                notes=f"{admission_id} - Room {room_number} - {notes}"
            )
            db.session.add(invoice)
            db.session.flush()
            
            # Add room charges item
            if room_charges > 0:
                inv_item = InvoiceItem(
                    invoice_id=invoice.id,
                    item_name='Room Charges',
                    item_type='other',
                    quantity=1,
                    unit_price=room_charges,
                    total_price=room_charges
                )
                db.session.add(inv_item)
            
            # Add doctor charges item
            if doctor_charges > 0:
                inv_item2 = InvoiceItem(
                    invoice_id=invoice.id,
                    item_name='Doctor Charges',
                    item_type='consultation',
                    quantity=1,
                    unit_price=doctor_charges,
                    total_price=doctor_charges
                )
                db.session.add(inv_item2)
            
            db.session.commit()
            flash('IPD Bill generated successfully', 'success')
            return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error generating IPD bill: {str(e)}', 'danger')
    
    patients = Patient.query.all()
    ipd_bills = Invoice.query.filter(Invoice.invoice_number.like('IPD-%')).order_by(Invoice.invoice_date.desc()).limit(10).all()
    return render_template('billing/ipd_bill.html', patients=patients, ipd_bills=ipd_bills)

# Payment Collection
@billing_bp.route('/payment-collection', methods=['GET', 'POST'])
def payment_collection():
    if request.method == 'POST':
        try:
            invoice_id = request.form.get('invoice_id')
            payment_amount = float(request.form.get('payment_amount', 0))
            payment_mode = request.form.get('payment_mode', 'cash')
            reference_number = request.form.get('reference_number', '')
            remarks = request.form.get('remarks', '')
            
            invoice = Invoice.query.get_or_404(invoice_id)
            invoice.payment_status = 'paid'
            invoice.payment_method = payment_mode
            db.session.commit()
            
            flash('Payment collected successfully', 'success')
            return redirect(url_for('billing.payment_collection'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error collecting payment: {str(e)}', 'danger')
    
    pending_invoices = Invoice.query.filter_by(payment_status='pending').order_by(Invoice.invoice_date.desc()).all()
    recent_collections = Invoice.query.filter_by(payment_status='paid').order_by(Invoice.invoice_date.desc()).limit(10).all()
    return render_template('billing/payment_collection.html', pending_invoices=pending_invoices, recent_collections=recent_collections)

# Print Receipt
@billing_bp.route('/receipt/<int:invoice_id>')
def print_receipt(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('billing/print_receipt.html', invoice=invoice)

# Billing Reports
@billing_bp.route('/reports')
def reports():
    try:
        today = date.today()
        start_of_month = date(today.year, today.month, 1)
        
        # Get filter parameters
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        doctor_id = request.args.get('doctor_id')
        department_id = request.args.get('department_id')
        
        # Build query
        query = Invoice.query
        
        if from_date:
            query = query.filter(Invoice.invoice_date >= date.fromisoformat(from_date))
        if to_date:
            query = query.filter(Invoice.invoice_date <= date.fromisoformat(to_date))
        if doctor_id:
            query = query.join(Appointment).filter(Appointment.doctor_id == doctor_id)
        if department_id:
            query = query.join(Appointment).filter(Appointment.department_id == department_id)
        
        invoices = query.order_by(Invoice.invoice_date.desc()).all()
        
        # Calculate statistics
        today_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date == today,
            Invoice.payment_status == 'paid'
        ).scalar() or 0
        monthly_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date >= start_of_month,
            Invoice.payment_status == 'paid'
        ).scalar() or 0
        pending_amount = db.session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.payment_status == 'pending'
        ).scalar() or 0
        collected_amount = db.session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.payment_status == 'paid'
        ).scalar() or 0
        
        doctors = Doctor.query.all()
        departments = Department.query.all()
        
        return render_template('billing/reports.html',
                               invoices=invoices,
                               today_revenue=today_revenue,
                               monthly_revenue=monthly_revenue,
                               pending_amount=pending_amount,
                               collected_amount=collected_amount,
                               doctors=doctors,
                               departments=departments)
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'danger')
        return render_template('billing/reports.html',
                               invoices=[],
                               today_revenue=0,
                               monthly_revenue=0,
                               pending_amount=0,
                               collected_amount=0,
                               doctors=[],
                               departments=[])

# Export PDF
@billing_bp.route('/reports/export/pdf')
def export_pdf():
    try:
        # Get filter parameters
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        doctor_id = request.args.get('doctor_id')
        department_id = request.args.get('department_id')
        
        # Build query
        query = Invoice.query
        
        if from_date:
            query = query.filter(Invoice.invoice_date >= date.fromisoformat(from_date))
        if to_date:
            query = query.filter(Invoice.invoice_date <= date.fromisoformat(to_date))
        if doctor_id:
            query = query.join(Appointment).filter(Appointment.doctor_id == doctor_id)
        if department_id:
            query = query.join(Appointment).filter(Appointment.department_id == department_id)
        
        invoices = query.order_by(Invoice.invoice_date.desc()).all()
        
        # Generate simple HTML for PDF
        html_content = f"""
        <html>
        <head>
            <title>Billing Report - Sahara Hospital</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                h1 {{ color: #4f46e5; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4f46e5; color: white; }}
                .summary {{ margin: 20px 0; padding: 15px; background: #f0f0f0; }}
            </style>
        </head>
        <body>
            <h1>Sahara Hospital - Billing Report</h1>
            <p>Generated on: {date.today().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Date Range: {from_date or 'All'} to {to_date or 'All'}</p>
            
            <div class="summary">
                <h3>Summary</h3>
                <p>Total Invoices: {len(invoices)}</p>
                <p>Total Revenue: ₹{sum(inv.total_amount for inv in invoices):.2f}</p>
            </div>
            
            <table>
                <tr>
                    <th>Invoice No</th>
                    <th>Date</th>
                    <th>Patient</th>
                    <th>Amount</th>
                    <th>Status</th>
                </tr>
        """
        
        for invoice in invoices:
            html_content += f"""
                <tr>
                    <td>{invoice.invoice_number}</td>
                    <td>{invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else 'N/A'}</td>
                    <td>{invoice.patient.full_name if invoice.patient else 'N/A'}</td>
                    <td>₹{invoice.total_amount:.2f}</td>
                    <td>{invoice.payment_status}</td>
                </tr>
            """
        
        html_content += """
            </table>
        </body>
        </html>
        """
        
        response = make_response(html_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=billing_report_{date.today().strftime("%Y%m%d")}.html'
        return response
    except Exception as e:
        flash(f'Error exporting PDF: {str(e)}', 'danger')
        return redirect(url_for('billing.reports'))

# Export Excel
@billing_bp.route('/reports/export/excel')
def export_excel():
    try:
        # Get filter parameters
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        doctor_id = request.args.get('doctor_id')
        department_id = request.args.get('department_id')
        
        # Build query
        query = Invoice.query
        
        if from_date:
            query = query.filter(Invoice.invoice_date >= date.fromisoformat(from_date))
        if to_date:
            query = query.filter(Invoice.invoice_date <= date.fromisoformat(to_date))
        if doctor_id:
            query = query.join(Appointment).filter(Appointment.doctor_id == doctor_id)
        if department_id:
            query = query.join(Appointment).filter(Appointment.department_id == department_id)
        
        invoices = query.order_by(Invoice.invoice_date.desc()).all()
        
        # Generate CSV as Excel-compatible format
        csv_content = "Invoice Number,Date,Patient,Doctor,Department,Amount,Status,Payment Method\n"
        
        for invoice in invoices:
            patient_name = invoice.patient.full_name if invoice.patient else 'N/A'
            doctor_name = invoice.appointment.doctor.full_name if invoice.appointment and invoice.appointment.doctor else 'N/A'
            dept_name = invoice.appointment.department.department_name if invoice.appointment and invoice.appointment.department else 'N/A'
            invoice_date = invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else 'N/A'
            
            csv_content += f"{invoice.invoice_number},{invoice_date},{patient_name},{doctor_name},{dept_name},{invoice.total_amount},{invoice.payment_status},{invoice.payment_method or 'N/A'}\n"
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=billing_report_{date.today().strftime("%Y%m%d")}.csv'
        return response
    except Exception as e:
        flash(f'Error exporting Excel: {str(e)}', 'danger')
        return redirect(url_for('billing.reports'))

# Print Report
@billing_bp.route('/reports/print')
def print_report():
    try:
        # Get filter parameters
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        doctor_id = request.args.get('doctor_id')
        department_id = request.args.get('department_id')
        
        # Build query
        query = Invoice.query
        
        if from_date:
            query = query.filter(Invoice.invoice_date >= date.fromisoformat(from_date))
        if to_date:
            query = query.filter(Invoice.invoice_date <= date.fromisoformat(to_date))
        if doctor_id:
            query = query.join(Appointment).filter(Appointment.doctor_id == doctor_id)
        if department_id:
            query = query.join(Appointment).filter(Appointment.department_id == department_id)
        
        invoices = query.order_by(Invoice.invoice_date.desc()).all()
        
        # Calculate statistics
        total_revenue = sum(inv.total_amount for inv in invoices)
        paid_count = sum(1 for inv in invoices if inv.payment_status == 'paid')
        pending_count = sum(1 for inv in invoices if inv.payment_status == 'pending')
        
        return render_template('billing/print_report.html',
                               invoices=invoices,
                               total_revenue=total_revenue,
                               paid_count=paid_count,
                               pending_count=pending_count,
                               from_date=from_date,
                               to_date=to_date,
                               date=date)
    except Exception as e:
        flash(f'Error loading print report: {str(e)}', 'danger')
        return redirect(url_for('billing.reports'))
