from django.contrib import messages
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST


LOW_STOCK_LIMIT = 50
AVAILABLE_YEARS = [2023, 2024, 2025]
DEFAULT_STATS_YEAR = 2024


# Helper functions.

def dictfetchall(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dictfetchone(cursor):
    columns = [column[0] for column in cursor.description]
    row = cursor.fetchone()
    return dict(zip(columns, row)) if row else None


def fetch_all(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return dictfetchall(cursor)


def fetch_one(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return dictfetchone(cursor)


def execute_sql(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])


def get_stats_year(request):
    year = request.GET.get("year", DEFAULT_STATS_YEAR)
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = DEFAULT_STATS_YEAR
    if year not in AVAILABLE_YEARS:
        year = DEFAULT_STATS_YEAR
    return year


def next_code(table, column, prefix, width):
    row = fetch_one(
        f"""
        SELECT MAX(CAST(SUBSTRING({column}, %s) AS UNSIGNED)) AS max_no
        FROM {table}
        WHERE {column} LIKE %s
        """,
        [len(prefix) + 1, f"{prefix}%"],
    )
    next_no = (row["max_no"] or 0) + 1
    return f"{prefix}{next_no:0{width}d}"


def selected_role(request):
    return request.session.get("role", "Admin")


def dashboard_redirect(request):
    role = selected_role(request)
    if role == "Distributor":
        return redirect("distributor_orders")
    if role == "Doctor":
        return redirect("doctor_prescribe")
    if role == "Pharmacist":
        return redirect("pharmacist_inventory")
    return redirect("admin_dashboard")


# Admin dashboard pages.


def admin_dashboard(request):
    year = get_stats_year(request)
    stats = build_admin_statistics(year)
    context = {
        "prescription_count": stats["today_prescriptions"],
        "low_stock_count": stats["low_stock_count"] + stats["expiring_batch_count"],
        "pending_orders": stats["pending_orders"],
        "chart_labels": stats["labels"],
        "chart_data": stats["prescription_data"],
        "inventory_data": stats["inventory_data"],
        "expired_data": stats["expired_data"],
        "latest_orders": stats["latest_orders"],
        "low_stock_items": stats["low_stock_items"],
        "expiring_batches": stats["expiring_batches"],
        "stats_year": year,
        "available_years": AVAILABLE_YEARS,
    }
    return render(request, "admin/dashboard.html", context)


def admin_statistics_api(request):
    year = get_stats_year(request)
    return JsonResponse(build_admin_statistics(year))


def build_admin_statistics(year):
    today = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM prescription
        WHERE pr_date = CURDATE()
        """
    )
    low_stock = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM store
        WHERE inventory < %s
        """,
        [LOW_STOCK_LIMIT],
    )
    expiring = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM medicine_batch
        WHERE expiration_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 90 DAY)
        """
    )
    pending_orders = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM hospital_order
        WHERE LOWER(ho_status) NOT IN ('completed', 'delivered')
        """
    )

    prescription_rows = fetch_all(
        """
        SELECT MONTH(pr_date) AS month_no, COUNT(*) AS total
        FROM prescription
        WHERE YEAR(pr_date) = %s
        GROUP BY MONTH(pr_date)
        """,
        [year],
    )
    inventory_rows = fetch_all(
        """
        SELECT MONTH(store_date) AS month_no, SUM(inventory) AS total
        FROM store
        WHERE YEAR(store_date) = %s
        GROUP BY MONTH(store_date)
        """,
        [year],
    )
    expired_rows = fetch_all(
        """
        SELECT MONTH(expiration_date) AS month_no, COUNT(*) AS total
        FROM medicine_batch
        WHERE YEAR(expiration_date) = %s
        GROUP BY MONTH(expiration_date)
        """,
        [year],
    )

    latest_orders = fetch_all(
        """
        SELECT ho.ho_ID AS ho_id, h.h_name, ho.ho_date, ho.ho_status, d.d_name
        FROM hospital_order ho
        JOIN hospital h ON h.h_ID = ho.h_ID
        JOIN distributor d ON d.d_ID = ho.d_ID
        ORDER BY ho.ho_date DESC, ho.ho_ID DESC
        LIMIT 8
        """
    )
    low_stock_items = fetch_all(
        """
        SELECT s.s_ID AS s_id, s.inventory, m.m_ID AS m_id, m.m_name, p.p_ID AS p_id
        FROM store s
        JOIN medicine m ON m.m_ID = s.m_ID
        JOIN pharmacy p ON p.p_ID = s.p_ID
        WHERE s.inventory < %s
        ORDER BY s.inventory ASC
        LIMIT 8
        """,
        [LOW_STOCK_LIMIT],
    )
    expiring_batches = fetch_all(
        """
        SELECT mb.mb_ID AS mb_id, m.m_name, mb.expiration_date
        FROM medicine_batch mb
        JOIN medicine m ON m.m_ID = mb.m_ID
        WHERE mb.expiration_date <= DATE_ADD(CURDATE(), INTERVAL 90 DAY)
        ORDER BY mb.expiration_date ASC
        LIMIT 8
        """
    )

    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return {
        "year": year,
        "labels": labels,
        "today_prescriptions": today["total"],
        "low_stock_count": low_stock["total"],
        "expiring_batch_count": expiring["total"],
        "pending_orders": pending_orders["total"],
        "prescription_data": month_series(prescription_rows),
        "inventory_data": month_series(inventory_rows),
        "expired_data": month_series(expired_rows),
        "latest_orders": latest_orders,
        "low_stock_items": low_stock_items,
        "expiring_batches": expiring_batches,
    }


def month_series(rows):
    values = [0] * 12
    for row in rows:
        values[int(row["month_no"]) - 1] = int(row["total"] or 0)
    return values


# Admin medicine pages.


def admin_medicines(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            execute_sql(
                """
                INSERT INTO medicine (m_ID, m_name, unit_price, manufacturer)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    request.POST.get("m_id") or next_code("medicine", "m_ID", "MED-", 7),
                    request.POST.get("m_name"),
                    request.POST.get("unit_price"),
                    request.POST.get("manufacturer"),
                ],
            )
            messages.success(request, "Medicine added.")
        elif action == "update":
            execute_sql(
                """
                UPDATE medicine
                SET m_name = %s, unit_price = %s, manufacturer = %s
                WHERE m_ID = %s
                """,
                [
                    request.POST.get("m_name"),
                    request.POST.get("unit_price"),
                    request.POST.get("manufacturer"),
                    request.POST.get("m_id"),
                ],
            )
            messages.success(request, "Medicine updated.")
        elif action == "delete":
            execute_sql("DELETE FROM medicine WHERE m_ID = %s", [request.POST.get("m_id")])
            messages.success(request, "Medicine deleted.")
        return redirect("admin_medicines")

    query = request.GET.get("q", "").strip()
    params = []
    where = ""
    if query:
        where = "WHERE m_ID LIKE %s OR m_name LIKE %s OR manufacturer LIKE %s"
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]
    medicines = fetch_all(
        f"""
        SELECT m_ID AS m_id, m_name, unit_price, manufacturer
        FROM medicine
        {where}
        ORDER BY m_name
        LIMIT 200
        """,
        params,
    )
    return render(request, "admin/medicines.html", {"medicines": medicines, "query": query})


def medicine_management(request):
    return admin_medicines(request)


# Admin user pages.


def doctor_users(request):
    if request.method == "POST":
        handle_doctor_post(request)
        return redirect("doctor_users")
    doctors = fetch_all(
        """
        SELECT dc.dc_ID AS dc_id, dc.dc_first_name, dc.dc_last_name, dc.dc_department,
               dc.dc_phone1, dc.dc_phone2, dc.h_ID AS h_id, h.h_name
        FROM doctor dc
        JOIN hospital h ON h.h_ID = dc.h_ID
        ORDER BY dc.dc_ID
        LIMIT 200
        """
    )
    hospitals = fetch_all("SELECT h_ID AS h_id, h_name FROM hospital ORDER BY h_ID")
    return render(request, "admin/users/doctor.html", {"doctors": doctors, "hospitals": hospitals})


def handle_doctor_post(request):
    action = request.POST.get("action")
    if action == "delete":
        execute_sql("DELETE FROM doctor WHERE dc_ID = %s", [request.POST.get("dc_id")])
        messages.success(request, "Doctor deleted.")
        return
    params = [
        request.POST.get("dc_first_name"),
        request.POST.get("dc_last_name"),
        request.POST.get("dc_department"),
        request.POST.get("dc_phone1"),
        request.POST.get("dc_phone2"),
        request.POST.get("h_id"),
        request.POST.get("dc_password") or 123456,
    ]
    if action == "create":
        execute_sql(
            """
            INSERT INTO doctor
                (dc_ID, dc_first_name, dc_last_name, dc_department, dc_phone1, dc_phone2, h_ID, dc_password)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [request.POST.get("dc_id") or next_code("doctor", "dc_ID", "DC-", 7)] + params,
        )
        messages.success(request, "Doctor added.")
    elif action == "update":
        execute_sql(
            """
            UPDATE doctor
            SET dc_first_name = %s, dc_last_name = %s, dc_department = %s,
                dc_phone1 = %s, dc_phone2 = %s, h_ID = %s, dc_password = %s
            WHERE dc_ID = %s
            """,
            params + [request.POST.get("dc_id")],
        )
        messages.success(request, "Doctor updated.")


def pharmacist_users(request):
    if request.method == "POST":
        handle_pharmacist_post(request)
        return redirect("pharmacist_users")
    pharmacists = fetch_all(
        """
        SELECT ph.ph_ID AS ph_id, ph.ph_firstname, ph.ph_lastname, ph.ph_phone1, ph.ph_phone2,
               ph.p_ID AS p_id, p.p_location
        FROM pharmacist ph
        JOIN pharmacy p ON p.p_ID = ph.p_ID
        ORDER BY ph.ph_ID
        LIMIT 200
        """
    )
    pharmacies = fetch_all("SELECT p_ID AS p_id, p_location FROM pharmacy ORDER BY p_ID")
    return render(
        request,
        "admin/users/phaemacist.html",
        {"pharmacists": pharmacists, "pharmacies": pharmacies},
    )


def handle_pharmacist_post(request):
    action = request.POST.get("action")
    if action == "delete":
        execute_sql("DELETE FROM pharmacist WHERE ph_ID = %s", [request.POST.get("ph_id")])
        messages.success(request, "Pharmacist deleted.")
        return
    params = [
        request.POST.get("p_id"),
        request.POST.get("ph_firstname"),
        request.POST.get("ph_lastname"),
        request.POST.get("ph_phone1"),
        request.POST.get("ph_phone2"),
        request.POST.get("ph_password") or 123456,
    ]
    if action == "create":
        execute_sql(
            """
            INSERT INTO pharmacist
                (ph_ID, p_ID, ph_firstname, ph_lastname, ph_phone1, ph_phone2, ph_password)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [request.POST.get("ph_id") or next_code("pharmacist", "ph_ID", "PHARM-", 3)] + params,
        )
        messages.success(request, "Pharmacist added.")
    elif action == "update":
        execute_sql(
            """
            UPDATE pharmacist
            SET p_ID = %s, ph_firstname = %s, ph_lastname = %s,
                ph_phone1 = %s, ph_phone2 = %s, ph_password = %s
            WHERE ph_ID = %s
            """,
            params + [request.POST.get("ph_id")],
        )
        messages.success(request, "Pharmacist updated.")


def distributor_users(request):
    if request.method == "POST":
        handle_distributor_post(request)
        return redirect("distributor_users")
    distributors = fetch_all(
        """
        SELECT d_ID AS d_id, d_name, d_address
        FROM distributor
        ORDER BY d_ID
        LIMIT 200
        """
    )
    return render(request, "admin/users/distributor.html", {"distributors": distributors})


def handle_distributor_post(request):
    action = request.POST.get("action")
    if action == "delete":
        execute_sql("DELETE FROM distributor WHERE d_ID = %s", [request.POST.get("d_id")])
        messages.success(request, "Distributor deleted.")
        return
    params = [
        request.POST.get("d_name"),
        request.POST.get("d_address"),
        request.POST.get("d_password") or 123456,
    ]
    if action == "create":
        execute_sql(
            """
            INSERT INTO distributor (d_ID, d_name, d_address, d_password)
            VALUES (%s, %s, %s, %s)
            """,
            [request.POST.get("d_id") or next_code("distributor", "d_ID", "DIS-", 3)] + params,
        )
        messages.success(request, "Distributor added.")
    elif action == "update":
        execute_sql(
            """
            UPDATE distributor
            SET d_name = %s, d_address = %s, d_password = %s
            WHERE d_ID = %s
            """,
            params + [request.POST.get("d_id")],
        )
        messages.success(request, "Distributor updated.")


def admin_users_admins(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            execute_sql("DELETE FROM admin WHERE admin_id = %s", [request.POST.get("admin_id")])
        elif action == "create":
            execute_sql(
                "INSERT INTO admin (admin_id, admin_name, admin_password) VALUES (%s, %s, %s)",
                [
                    request.POST.get("admin_id"),
                    request.POST.get("admin_name"),
                    request.POST.get("admin_password"),
                ],
            )
        elif action == "update":
            execute_sql(
                "UPDATE admin SET admin_name = %s, admin_password = %s WHERE admin_id = %s",
                [
                    request.POST.get("admin_name"),
                    request.POST.get("admin_password"),
                    request.POST.get("admin_id"),
                ],
            )
        return redirect("admin_users_admins")
    admins = fetch_all("SELECT admin_id, admin_name FROM admin ORDER BY admin_id")
    return render(request, "admin/users/admin.html", {"admins": admins})


def admin_suppliers(request):
    if request.method == "POST":
        handle_distributor_post(request)
        return redirect("admin_suppliers")
    distributors = fetch_all("SELECT d_ID AS d_id, d_name, d_address FROM distributor ORDER BY d_ID")
    records = fetch_all(
        """
        SELECT s.supply_ID AS supply_id, s.quantity, s.p_ID AS p_id, p.p_location,
               ho.ho_ID AS ho_id, ho.ho_date, ho.ho_status, h.h_name, d.d_name
        FROM supply s
        JOIN hospital_order ho ON ho.ho_ID = s.ho_ID
        JOIN pharmacy p ON p.p_ID = s.p_ID
        JOIN hospital h ON h.h_ID = ho.h_ID
        JOIN distributor d ON d.d_ID = ho.d_ID
        ORDER BY ho.ho_date DESC, s.supply_ID DESC
        LIMIT 200
        """
    )
    return render(
        request,
        "admin/suppliers.html",
        {"distributors": distributors, "records": records},
    )


# Doctor pages.


def doctor_prescribe(request):
    return render(request, "doctor/prescribe.html")


# Pharmacist pages.


def pharmacist_inventory(request):
    stores = fetch_all(
        """
        SELECT s.s_ID AS s_id, s.inventory, s.store_date, m.m_ID AS m_id, m.m_name, p.p_ID AS p_id
        FROM store s
        JOIN medicine m ON m.m_ID = s.m_ID
        JOIN pharmacy p ON p.p_ID = s.p_ID
        ORDER BY s.inventory ASC
        LIMIT 200
        """
    )
    return render(request, "pharmacist/inventory.html", {"stores": stores})


def pharmacist_audit(request):
    return render(request, "pharmacist/audit.html")


# Distributor pages.


def current_distributor_id(request):
    return request.session.get("user_id") or request.GET.get("d_id")


def distributor_orders(request):
    distributor_id = current_distributor_id(request)
    if request.method == "POST":
        order_id = request.POST.get("ho_id")
        order = fetch_one(
            """
            SELECT ho_status
            FROM hospital_order
            WHERE ho_ID = %s AND d_ID = COALESCE(%s, d_ID)
            """,
            [order_id, distributor_id],
        )
        next_status = {
            "paid": "shipping",
            "shipping": "completed",
        }
        new_status = next_status.get((order["ho_status"] or "").lower()) if order else None
        if not new_status:
            messages.error(request, "This order cannot move to another status.")
            return redirect("distributor_orders")

        execute_sql(
            """
            UPDATE hospital_order
            SET ho_status = %s
            WHERE ho_ID = %s AND d_ID = COALESCE(%s, d_ID)
            """,
            [new_status, order_id, distributor_id],
        )
        messages.success(request, "Order status updated.")
        return redirect("distributor_orders")

    params = []
    where = ""
    if distributor_id:
        where = "WHERE ho.d_ID = %s"
        params.append(distributor_id)
    orders = fetch_all(
        f"""
        SELECT ho.ho_ID AS ho_id, ho.ho_date, ho.ho_status, ho.d_ID AS d_id,
               h.h_ID AS h_id, h.h_name, h.h_address,
               COALESCE(SUM(CAST(s.quantity AS UNSIGNED)), 0) AS total_quantity,
               CASE
                   WHEN LOWER(ho.ho_status) = 'paid' THEN 'shipping'
                   WHEN LOWER(ho.ho_status) = 'shipping' THEN 'completed'
                   ELSE ''
               END AS next_status
        FROM hospital_order ho
        JOIN hospital h ON h.h_ID = ho.h_ID
        LEFT JOIN supply s ON s.ho_ID = ho.ho_ID
        {where}
        GROUP BY ho.ho_ID, ho.ho_date, ho.ho_status, ho.d_ID, h.h_ID, h.h_name, h.h_address
        ORDER BY ho.ho_date DESC, ho.ho_ID DESC
        LIMIT 200
        """,
        params,
    )
    return render(
        request,
        "distributor/order.html",
        {"orders": orders, "distributor_id": distributor_id},
    )


def distributor_shipments(request):
    distributor_id = current_distributor_id(request)
    if request.method == "POST":
        execute_sql(
            """
            INSERT INTO medicine_batch (mb_ID, m_ID, production_date, expiration_date)
            VALUES (%s, %s, %s, %s)
            """,
            [
                request.POST.get("mb_id") or next_code("medicine_batch", "mb_ID", "MB-", 5),
                request.POST.get("m_id"),
                request.POST.get("production_date"),
                request.POST.get("expiration_date"),
            ],
        )
        messages.success(request, "Medicine batch recorded.")
        return redirect("distributor_shipments")

    params = []
    where = "WHERE LOWER(ho.ho_status) IN ('shipping', 'completed', 'delivered')"
    if distributor_id:
        where += " AND ho.d_ID = %s"
        params.append(distributor_id)
    shipments = fetch_all(
        f"""
        SELECT ho.ho_ID AS ho_id, ho.ho_date, ho.ho_status, h.h_name,
               s.supply_ID AS supply_id, s.quantity, s.p_ID AS p_id
        FROM hospital_order ho
        JOIN hospital h ON h.h_ID = ho.h_ID
        LEFT JOIN supply s ON s.ho_ID = ho.ho_ID
        {where}
        ORDER BY ho.ho_date DESC, ho.ho_ID DESC
        LIMIT 200
        """,
        params,
    )
    batches = fetch_all(
        """
        SELECT mb.mb_ID AS mb_id, mb.production_date, mb.expiration_date, m.m_ID AS m_id, m.m_name
        FROM medicine_batch mb
        JOIN medicine m ON m.m_ID = mb.m_ID
        ORDER BY mb.production_date DESC, mb.mb_ID DESC
        LIMIT 80
        """
    )
    medicines = fetch_all(
        """
        SELECT m_ID AS m_id, m_name
        FROM medicine
        ORDER BY m_name
        """
    )
    return render(
        request,
        "distributor/shipments.html",
        {
            "shipments": shipments,
            "batches": batches,
            "medicines": medicines,
            "distributor_id": distributor_id,
        },
    )


# Login pages.


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        role = request.POST.get("role")

        auth_sql = {
            "Admin": (
                """
                SELECT admin_id AS user_id, admin_name AS user_name
                FROM admin
                WHERE admin_id = %s AND admin_password = %s
                """,
                "admin_dashboard",
            ),
            "Distributor": (
                """
                SELECT d_ID AS user_id, d_name AS user_name
                FROM distributor
                WHERE d_ID = %s AND d_password = %s
                """,
                "distributor_orders",
            ),
            "Doctor": (
                """
                SELECT dc_ID AS user_id, CONCAT(dc_first_name, ' ', dc_last_name) AS user_name
                FROM doctor
                WHERE dc_ID = %s AND dc_password = %s
                """,
                "doctor_prescribe",
            ),
            "Pharmacist": (
                """
                SELECT ph_ID AS user_id, CONCAT(ph_firstname, ' ', ph_lastname) AS user_name
                FROM pharmacist
                WHERE ph_ID = %s AND ph_password = %s
                """,
                "pharmacist_inventory",
            ),
        }
        if role in auth_sql:
            sql, route_name = auth_sql[role]
            user = fetch_one(sql, [username, password])
            if user:
                request.session["role"] = role
                request.session["user_id"] = user["user_id"]
                request.session["user_name"] = user["user_name"]
                return redirect(route_name)

        return render(request, "login.html", {"error": "Invalid username or password"})

    return render(request, "login.html")


@require_POST
def logout_view(request):
    request.session.flush()
    return redirect("login")
