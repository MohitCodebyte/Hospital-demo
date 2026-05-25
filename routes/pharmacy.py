from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, MedicineMaster, MedicineBatch, MedicinePurchase, MedicineIssue, MedicineIssueItem, Supplier, Patient
from datetime import date
import uuid

pharmacy_bp = Blueprint('pharmacy', __name__, url_prefix='/pharmacy')

def _generate_batch_number():
    return f"B-{uuid.uuid4().hex[:6].upper()}"

@pharmacy_bp.route('/')
def dashboard():
    medicines = MedicineMaster.query.all()
    batches = MedicineBatch.query.order_by(MedicineBatch.expiry_date).all()
    purchases = MedicinePurchase.query.order_by(MedicinePurchase.purchase_date.desc()).limit(5).all()
    issues = MedicineIssue.query.order_by(MedicineIssue.issue_date.desc()).limit(5).all()
    return render_template('pharmacy/dashboard.html', medicines=medicines, batches=batches, purchases=purchases, issues=issues)

@pharmacy_bp.route('/medicine/create', methods=['GET', 'POST'])
def create_medicine():
    if request.method == 'POST':
        name = request.form['medicine_name']
        category = request.form['category']
        dosage_form = request.form.get('dosage_form')
        manufacturer = request.form.get('manufacturer')
        min_stock = int(request.form.get('min_stock', 10))
        unit = request.form.get('unit', 'Tablet')
        med = MedicineMaster(
            medicine_name=name,
            category=category,
            dosage_form=dosage_form,
            manufacturer=manufacturer,
            min_stock=min_stock,
            unit=unit
        )
        db.session.add(med)
        db.session.commit()
        flash('Medicine added', 'success')
        return redirect(url_for('pharmacy.dashboard'))
    return render_template('pharmacy/create_medicine.html')

@pharmacy_bp.route('/purchase/create', methods=['GET', 'POST'])
def create_purchase():
    if request.method == 'POST':
        supplier_id = request.form['supplier_id']
        purchase_date = request.form.get('purchase_date') or date.today()
        purchase = MedicinePurchase(
            supplier_id=supplier_id,
            purchase_date=purchase_date,
            invoice_number=f"PUR-{date.today().strftime('%Y%m%d')}-{int(MedicinePurchase.query.count())+1}",
            subtotal=0,
            cgst=0,
            sgst=0,
            discount=0,
            total_amount=0
        )
        db.session.add(purchase)
        db.session.flush()
        # Expect batch entries arrays
        med_ids = request.form.getlist('medicine_id')
        qtys = request.form.getlist('quantity')
        rates = request.form.getlist('rate')
        expiry_dates = request.form.getlist('expiry_date')
        total = 0
        for med_id, qty, rate, exp in zip(med_ids, qtys, rates, expiry_dates):
            qty = int(qty)
            rate = float(rate)
            line_total = qty * rate
            total += line_total
            batch = MedicineBatch(
                medicine_id=med_id,
                batch_number=_generate_batch_number(),
                expiry_date=exp,
                purchase_price=rate,
                sale_price=rate * 1.2,  # simple markup
                initial_qty=qty,
                current_qty=qty,
                supplier_id=supplier_id,
                purchase_id=purchase.id
            )
            db.session.add(batch)
        purchase.subtotal = total
        purchase.total_amount = total  # no tax for demo
        db.session.commit()
        flash('Purchase recorded', 'success')
        return redirect(url_for('pharmacy.dashboard'))
    suppliers = Supplier.query.all()
    medicines = MedicineMaster.query.all()
    return render_template('pharmacy/create_purchase.html', suppliers=suppliers, medicines=medicines)

@pharmacy_bp.route('/issue/create', methods=['GET', 'POST'])
def create_issue():
    if request.method == 'POST':
        patient_id = request.form['patient_id']
        issue_date = request.form.get('issue_date') or date.today()
        issue = MedicineIssue(
            patient_id=patient_id,
            issue_date=issue_date,
            subtotal=0,
            cgst=0,
            sgst=0,
            discount=0,
            total_amount=0,
            payment_status='pending'
        )
        db.session.add(issue)
        db.session.flush()
        batch_ids = request.form.getlist('batch_id')
        qtys = request.form.getlist('quantity')
        total = 0
        for batch_id, qty in zip(batch_ids, qtys):
            qty = int(qty)
            batch = MedicineBatch.query.get(batch_id)
            line_price = batch.sale_price * qty
            total += line_price
            item = MedicineIssueItem(
                medicine_issue_id=issue.id,
                batch_id=batch.id,
                quantity=qty,
                rate=batch.sale_price,
                total_price=line_price
            )
            db.session.add(item)
            # update batch quantity
            batch.current_qty = max(batch.current_qty - qty, 0)
        issue.subtotal = total
        issue.total_amount = total
        db.session.commit()
        flash('Medicine issued', 'success')
        return redirect(url_for('pharmacy.dashboard'))
    patients = Patient.query.all()
    batches = MedicineBatch.query.filter(MedicineBatch.current_qty > 0).all()
    return render_template('pharmacy/create_issue.html', patients=patients, batches=batches)
