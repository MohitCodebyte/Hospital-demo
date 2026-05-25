from flask import Blueprint, render_template
from datetime import date, timedelta
from models import db, Invoice, InvoiceItem, StockPurchase, InventoryItem, MedicineIssue, MedicineIssueItem, LabOrder, Patient, Appointment
from datetime import date

financial_analytics_bp = Blueprint('financial_analytics', __name__, url_prefix='/financial-analytics')

@financial_analytics_bp.route('/')
def dashboard():
    # Revenue
    total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(Invoice.payment_status == 'paid').scalar() or 0
    # Inventory expenses: sum of purchase totals from StockPurchase
    total_inventory_expense = db.session.query(db.func.sum(StockPurchase.total_amount)).scalar() or 0
    # Pharmacy sales: sum of invoice items where item_type='medicine'
    pharmacy_sales = db.session.query(db.func.sum(InvoiceItem.total_price)).filter(InvoiceItem.item_type == 'medicine').scalar() or 0
    # Lab revenue: sum of invoice items where item_type='lab_test'
    lab_revenue = db.session.query(db.func.sum(InvoiceItem.total_price)).filter(InvoiceItem.item_type == 'lab_test').scalar() or 0
    # Patient growth: count of patients per month for last 6 months
    patient_growth = []
    for i in range(6):
        month_start = date.today().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        count = db.session.query(Patient.id).filter(Patient.created_at >= month_start, Patient.created_at < month_end).count()
        patient_growth.append({'month': month_start.strftime('%Y-%m'), 'count': count})
    # Appointment trends: similar last 6 months
    appointment_trends = []
    for i in range(6):
        month_start = date.today().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        count = db.session.query(Appointment.id).filter(Appointment.appointment_date >= month_start, Appointment.appointment_date < month_end).count()
        appointment_trends.append({'month': month_start.strftime('%Y-%m'), 'count': count})
    return render_template('analytics/financial_dashboard.html', total_revenue=total_revenue,
                           total_inventory_expense=total_inventory_expense,
                           pharmacy_sales=pharmacy_sales,
                           lab_revenue=lab_revenue,
                           patient_growth=patient_growth,
                           appointment_trends=appointment_trends)
