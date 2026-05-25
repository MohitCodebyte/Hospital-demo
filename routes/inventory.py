from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory
from datetime import date, datetime
from werkzeug.utils import secure_filename
import os
from models import (
    db, InventoryItem, Supplier, StockPurchase, StockPurchaseItem,
    StockLedger, StockIssue, StockIssueItem, Department, StockRequest
)
from routes.auth import admin_required

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

# Inventory Dashboard
@inventory_bp.route("/")
@admin_required
def dashboard():
    total_items = InventoryItem.query.count()
    low_stock_count = InventoryItem.query.filter(
        InventoryItem.quantity <= InventoryItem.minimum_stock
    ).count()
    
    # Calculate current stock value
    items_list = InventoryItem.query.all()
    current_stock_value = sum((item.quantity * (item.purchase_price or 0.0)) for item in items_list)
    
    # Monthly expense from purchases
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    monthly_purchases = StockPurchase.query.filter(StockPurchase.purchase_date >= start_of_month).all()
    monthly_expense = sum(p.total_amount for p in monthly_purchases)
    
    recent_purchases = StockPurchase.query.order_by(StockPurchase.created_at.desc()).limit(5).all()
    recent_issues = StockIssue.query.order_by(StockIssue.created_at.desc()).limit(5).all()
    
    return render_template(
        "inventory/dashboard.html",
        total_items=total_items,
        low_stock_count=low_stock_count,
        current_stock_value=current_stock_value,
        monthly_expense=monthly_expense,
        recent_purchases=recent_purchases,
        recent_issues=recent_issues
    )

# Supplier Management CRUD
@inventory_bp.route("/suppliers")
@admin_required
def suppliers():
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    return render_template("inventory/suppliers.html", suppliers=suppliers_list)

@inventory_bp.route("/suppliers/add", methods=["GET", "POST"])
@admin_required
def add_supplier():
    if request.method == "POST":
        try:
            name = request.form["name"]
            contact_person = request.form.get("contact_person", "")
            email = request.form.get("email", "")
            phone = request.form.get("phone", "")
            address = request.form.get("address", "")
            gst_number = request.form.get("gst_number", "")
            
            existing = Supplier.query.filter_by(name=name).first()
            if existing:
                flash("Supplier with this name already exists!", "danger")
                return redirect(url_for("inventory.suppliers"))
                
            supplier = Supplier(
                name=name,
                contact_person=contact_person,
                email=email,
                phone=phone,
                address=address,
                gst_number=gst_number
            )
            db.session.add(supplier)
            db.session.commit()
            flash("Supplier added successfully!", "success")
            return redirect(url_for("inventory.suppliers"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding supplier: {str(e)}", "danger")
            
    return render_template("inventory/supplier_form.html", action="Add")

@inventory_bp.route("/suppliers/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    if request.method == "POST":
        try:
            supplier.name = request.form["name"]
            supplier.contact_person = request.form.get("contact_person", "")
            supplier.email = request.form.get("email", "")
            supplier.phone = request.form.get("phone", "")
            supplier.address = request.form.get("address", "")
            supplier.gst_number = request.form.get("gst_number", "")
            
            db.session.commit()
            flash("Supplier updated successfully!", "success")
            return redirect(url_for("inventory.suppliers"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating supplier: {str(e)}", "danger")
            
    return render_template("inventory/supplier_form.html", supplier=supplier, action="Edit")

@inventory_bp.route("/suppliers/delete/<int:id>")
@admin_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    try:
        db.session.delete(supplier)
        db.session.commit()
        flash("Supplier deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting supplier: {str(e)}", "danger")
    return redirect(url_for("inventory.suppliers"))

# Add New Stock (Multi-item entry)
@inventory_bp.route("/add", methods=["GET", "POST"])
@admin_required
def add_stock():
    if request.method == "POST":
        try:
            supplier_id = int(request.form["supplier_id"])
            challan_number = request.form.get("challan_number", "")
            purchase_date_str = request.form["purchase_date"]
            purchase_date = date.fromisoformat(purchase_date_str) if purchase_date_str else date.today()
            entry_date = date.today()
            
            # File Upload (Challan PDF)
            file = request.files.get("challan_pdf")
            challan_filename = None
            if file and file.filename:
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "static", "uploads", "challans"
                )
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                challan_filename = filename
                
            item_ids = request.form.getlist("item_id[]")
            quantities = request.form.getlist("quantity[]")
            rates = request.form.getlist("rate[]")
            cgst_rates = request.form.getlist("cgst_rate[]")
            sgst_rates = request.form.getlist("sgst_rate[]")
            discounts = request.form.getlist("discount[]")
            
            subtotal = 0.0
            purchase_items = []
            
            for i in range(len(item_ids)):
                if not item_ids[i] or not quantities[i]:
                    continue
                itm_id = int(item_ids[i])
                qty = int(quantities[i])
                rate = float(rates[i])
                cgst_r = float(cgst_rates[i]) if cgst_rates[i] else 0.0
                sgst_r = float(sgst_rates[i]) if sgst_rates[i] else 0.0
                disc = float(discounts[i]) if discounts[i] else 0.0
                
                item_total = (qty * rate) + (qty * rate * (cgst_r + sgst_r) / 100.0) - disc
                subtotal += (qty * rate)
                
                purchase_item = StockPurchaseItem(
                    item_id=itm_id,
                    quantity=qty,
                    rate=rate,
                    cgst_rate=cgst_r,
                    sgst_rate=sgst_r,
                    discount_amount=disc,
                    total_amount=item_total
                )
                purchase_items.append(purchase_item)
                
                # Update item stock & price
                item = InventoryItem.query.get(itm_id)
                item.quantity += qty
                item.purchase_price = rate
                
            cgst_total = sum(pi.quantity * pi.rate * (pi.cgst_rate / 100.0) for pi in purchase_items)
            sgst_total = sum(pi.quantity * pi.rate * (pi.sgst_rate / 100.0) for pi in purchase_items)
            discount_total = sum(pi.discount_amount for pi in purchase_items)
            grand_total = subtotal + cgst_total + sgst_total - discount_total
            
            # Save Purchase
            purchase = StockPurchase(
                supplier_id=supplier_id,
                purchase_date=purchase_date,
                entry_date=entry_date,
                challan_number=challan_number,
                challan_pdf=challan_filename,
                subtotal=subtotal,
                cgst=cgst_total,
                sgst=sgst_total,
                discount=discount_total,
                total_amount=grand_total,
                payment_status="paid"
            )
            db.session.add(purchase)
            db.session.flush() # gets purchase.id
            
            # Save Purchase Items & Ledger logs
            for p_item in purchase_items:
                p_item.stock_purchase_id = purchase.id
                db.session.add(p_item)
                db.session.flush()
                
                ledger = StockLedger(
                    item_id=p_item.item_id,
                    transaction_type="purchase",
                    quantity=p_item.quantity,
                    reference_id=p_item.id,
                    notes=f"Stock Purchase. Challan #{challan_number}"
                )
                db.session.add(ledger)
                
            db.session.commit()
            flash("Stock purchase recorded and inventory updated successfully!", "success")
            return redirect(url_for("inventory.items"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error checking in stock: {str(e)}", "danger")
            
    suppliers = Supplier.query.all()
    items = InventoryItem.query.order_by(InventoryItem.item_name).all()
    today = date.today()
    return render_template("inventory/add_stock_form.html", suppliers=suppliers, items=items, today=today)

# Add single item catalog definition
@inventory_bp.route("/add-item", methods=["GET", "POST"], endpoint="add_item")
@admin_required
def add_item_definition():
    if request.method == "POST":
        try:
            item = InventoryItem(
                item_code=request.form["item_code"],
                item_name=request.form["item_name"],
                category=request.form["category"],
                quantity=0,
                minimum_stock=int(request.form["minimum_stock"]),
                unit=request.form["unit"],
                purchase_price=0.0
            )
            db.session.add(item)
            db.session.commit()
            flash("New item defined in inventory catalog!", "success")
            return redirect(url_for("inventory.items"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error defining item: {str(e)}", "danger")
            
    return render_template("inventory/add_item.html")

# Existing edit item route (modified to handle missing items gracefully)
@inventory_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
@admin_required
def edit_item(item_id):
    item = InventoryItem.query.get(item_id)
    if not item:
        flash(f"Item with ID {item_id} not found.", "warning")
        return redirect(url_for('inventory.items'))
    if request.method == "POST":
        try:
            item.item_name = request.form["item_name"]
            item.category = request.form["category"]
            item.minimum_stock = int(request.form["minimum_stock"])
            item.unit = request.form["unit"]
            db.session.commit()
            flash("Item configuration updated!", "success")
            return redirect(url_for("inventory.items"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
    return render_template("inventory/edit_item.html", item=item)


# Alias routes for underscore URLs (validation compatibility)

@inventory_bp.route("/add_item", methods=["GET", "POST"])
@admin_required
def add_item_alias():
    return add_item_definition()

@inventory_bp.route("/edit_item/<int:item_id>", methods=["GET", "POST"])
@admin_required
def edit_item_alias(item_id):
    return edit_item(item_id)

@inventory_bp.route("/request_stock", methods=["GET", "POST"])
@admin_required
def request_stock_alias():
    return request_stock()

@inventory_bp.route("/add_stock", methods=["GET", "POST"])
@admin_required
def add_stock_alias():
    return add_stock()

@inventory_bp.route("/issue_stock", methods=["GET", "POST"])
@admin_required
def issue_stock_alias():
    return issue_stock()

@inventory_bp.route("/live", methods=["GET"])
@admin_required
def live_inventory_alias():
    return items()

@inventory_bp.route("/challan_reports", methods=["GET"])
@admin_required
def challan_reports_alias():
    return challan_reports()

# Delete item definition
@inventory_bp.route("/delete/<int:item_id>")
@admin_required
def delete_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash("Item removed from catalog.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Cannot delete item with transaction history: {str(e)}", "danger")
    return redirect(url_for("inventory.items"))

# Issue Stock to Department
@inventory_bp.route("/issue", methods=["GET", "POST"])
@admin_required
def issue_stock():
    if request.method == "POST":
        try:
            dept_id = int(request.form["department_id"])
            issued_to = request.form["issued_to"]
            issued_by = session.get("admin_username", "Admin")
            issue_date = date.today()
            
            item_ids = request.form.getlist("item_id[]")
            quantities = request.form.getlist("quantity[]")
            
            issue_items = []
            for i in range(len(item_ids)):
                if not item_ids[i] or not quantities[i]:
                    continue
                itm_id = int(item_ids[i])
                qty = int(quantities[i])
                
                # Check stock levels
                item = InventoryItem.query.get(itm_id)
                if not item or item.quantity < qty:
                    flash(f"Insufficient stock for {item.item_name if item else 'item'}!", "danger")
                    return redirect(url_for("inventory.issue_stock"))
                    
                # Deduct stock
                item.quantity -= qty
                
                issue_item = StockIssueItem(
                    item_id=itm_id,
                    quantity=qty
                )
                issue_items.append(issue_item)
                
            # Create StockIssue record
            issue = StockIssue(
                department_id=dept_id,
                issued_by=issued_by,
                issued_to=issued_to,
                issue_date=issue_date,
                status="completed"
            )
            db.session.add(issue)
            db.session.flush() # gets issue.id
            
            # Save Issue items & Ledger logs
            for iss_item in issue_items:
                iss_item.stock_issue_id = issue.id
                db.session.add(iss_item)
                db.session.flush()
                
                ledger = StockLedger(
                    item_id=iss_item.item_id,
                    transaction_type="issue",
                    quantity=-iss_item.quantity, # Negative for check-out
                    department_id=dept_id,
                    reference_id=iss_item.id,
                    notes=f"Issued to {issue.department.department_name} Dept (Recv: {issued_to})"
                )
                db.session.add(ledger)
                
            db.session.commit()
            flash("Stock issued successfully and inventory levels updated!", "success")
            return redirect(url_for("inventory.items"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error issuing stock: {str(e)}", "danger")
            
    departments = Department.query.all()
    items = InventoryItem.query.filter(InventoryItem.quantity > 0).all()
    issues = StockIssue.query.order_by(StockIssue.issue_date.desc()).all()
    today = date.today()
    return render_template("inventory/issue_stock_form.html", departments=departments, items=items, issues=issues, today=today)

# Live Inventory / Items Catalog
@inventory_bp.route("/items")
@admin_required
def items():
    inventory_items = InventoryItem.query.order_by(InventoryItem.item_name).all()
    today = date.today()
    for item in inventory_items:
        # Expiring checking
        item.expiring = False
        if item.expiry_date:
            days_to_exp = (item.expiry_date - today).days
            item.expiring = 0 <= days_to_exp <= 90
    return render_template("inventory/items.html", items=inventory_items)

# Stock Ledger List
@inventory_bp.route("/ledger")
@admin_required
def ledger():
    ledger_entries = StockLedger.query.order_by(StockLedger.transaction_date.desc()).all()
    today = date.today()
    return render_template("inventory/ledger.html", ledger=ledger_entries, today=today)

# Department Stock Request Tracker (Mock layout returning clean structure)
@inventory_bp.route("/request-stock", methods=["GET", "POST"])
@admin_required
def request_stock():
    """Handle stock request creation and display dashboard.

    GET: renders the request form with overview cards and pending request table.
    POST: validates quantity against available stock, creates a StockRequest record.
    """
    # Gather overview statistics
    total_items = InventoryItem.query.count()
    pending_count = StockRequest.query.filter_by(status='pending').count()
    approved_count = StockRequest.query.filter_by(status='approved').count()
    rejected_count = StockRequest.query.filter_by(status='rejected').count()
    low_stock_count = InventoryItem.query.filter(InventoryItem.quantity <= InventoryItem.minimum_stock).count()
    total_departments = Department.query.count()

    # Quick statistics
    # Most requested item (by request count)
    most_requested = (
        db.session.query(InventoryItem.item_name, db.func.count(StockRequest.id).label('req_count'))
        .join(StockRequest, StockRequest.item_id == InventoryItem.id)
        .group_by(InventoryItem.id)
        .order_by(db.desc('req_count'))
        .first()
    )
    most_requested_item = most_requested.item_name if most_requested else "N/A"
    most_requested_count = most_requested.req_count if most_requested else 0

    # Lowest stock item
    lowest_stock = InventoryItem.query.order_by(InventoryItem.quantity).first()
    lowest_stock_item = lowest_stock.item_name if lowest_stock else "N/A"
    lowest_stock_qty = lowest_stock.quantity if lowest_stock else 0

    # Latest request
    latest_req = StockRequest.query.order_by(StockRequest.request_date.desc()).first()
    latest_request_info = (
        f"{latest_req.item.item_name} ({latest_req.quantity})" if latest_req else "N/A"
    )

    # Total requests this month
    from datetime import date
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    month_requests = StockRequest.query.filter(StockRequest.request_date >= start_of_month).count()

    if request.method == "POST":
        try:
            dept_id = int(request.form["department_id"])
            item_id = int(request.form["item_id"])
            qty = int(request.form["quantity"])
            priority = request.form.get("priority", "Normal")
            notes = request.form.get("notes", "")

            # Load the item to verify stock
            item = InventoryItem.query.get(item_id)
            if not item:
                flash("Selected item does not exist.", "danger")
                return redirect(url_for('inventory.request_stock'))

            if qty > item.quantity:
                flash("Requested quantity exceeds available stock.", "warning")
                return redirect(url_for('inventory.request_stock'))

            new_req = StockRequest(
                department_id=dept_id,
                item_id=item_id,
                quantity=qty,
                notes=notes,
                request_date=date.today(),
                status="pending",
                priority=priority,
            )
            db.session.add(new_req)
            db.session.commit()
            flash("Stock request submitted successfully", "success")
            return redirect(url_for('inventory.request_stock'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error submitting request: {str(e)}", "danger")
            return redirect(url_for('inventory.request_stock'))

    # GET handling – load all items (including zero stock) sorted alphabetically
    items = InventoryItem.query.order_by(InventoryItem.item_name).all()
    departments = Department.query.all()

    # Filtering for pending requests table
    query = StockRequest.query
    # Search item name
    search_item = request.args.get('search_item')
    if search_item:
        query = query.join(InventoryItem).filter(InventoryItem.item_name.ilike(f"%{search_item}%"))
    # Filter by department
    filter_dept = request.args.get('department_id')
    if filter_dept:
        query = query.filter_by(department_id=int(filter_dept))
    # Filter by status
    filter_status = request.args.get('status')
    if filter_status:
        query = query.filter_by(status=filter_status)
    # Filter by priority
    filter_priority = request.args.get('priority')
    if filter_priority:
        query = query.filter_by(priority=filter_priority)

    pending_requests = query.order_by(StockRequest.request_date.desc()).all()
    return render_template(
        "inventory/request_stock.html",
        departments=departments,
        items=items,
        requests=pending_requests,
        stats={
            "total_items": total_items,
            "pending": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
            "low_stock": low_stock_count,
            "departments": total_departments,
            "most_requested_item": most_requested_item,
            "most_requested_count": most_requested_count,
            "lowest_stock_item": lowest_stock_item,
            "lowest_stock_qty": lowest_stock_qty,
            "latest_request": latest_request_info,
            "month_requests": month_requests
        }
    )

# Challan Registry (GRN PDF Storage)
@inventory_bp.route("/challans")
@admin_required
def challans():
    purchases = StockPurchase.query.order_by(StockPurchase.purchase_date.desc()).all()
    today = date.today()
    return render_template("inventory/challans.html", purchases=purchases, today=today)

@inventory_bp.route("/challan/download/<filename>")
@admin_required
def download_challan(filename):
    upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "challans")
    return send_from_directory(upload_folder, filename, as_attachment=True)

# Challan Reports & Purchase Analytics
@inventory_bp.route("/challan-reports")
@admin_required
def challan_reports():
    # Vendor summaries
    suppliers_list = Supplier.query.all()
    vendor_summaries = []
    for s in suppliers_list:
        purchases = StockPurchase.query.filter_by(supplier_id=s.id).all()
        total_p = sum(p.total_amount for p in purchases)
        vendor_summaries.append({
            "supplier_name": s.name,
            "gst_number": s.gst_number,
            "purchase_count": len(purchases),
            "total_spent": total_p
        })
        
    # Category-wise purchase totals
    category_summary = {}
    purchase_items = StockPurchaseItem.query.all()
    for item in purchase_items:
        cat = item.item.category
        category_summary[cat] = category_summary.get(cat, 0.0) + item.total_amount
        
    # Monthly purchase totals
    monthly_summary = {}
    all_purchases = StockPurchase.query.all()
    for p in all_purchases:
        month_key = p.purchase_date.strftime("%B %Y")
        monthly_summary[month_key] = monthly_summary.get(month_key, 0.0) + p.total_amount
        
    return render_template(
        "inventory/challan_reports.html",
        vendor_summaries=vendor_summaries,
        category_summary=category_summary,
        monthly_summary=monthly_summary
    )