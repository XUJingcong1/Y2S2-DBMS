from django.contrib import messages
from django.db import DatabaseError, connection, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST


LOW_STOCK_LIMIT = 50
AVAILABLE_YEARS = [2023, 2024, 2025]
DEFAULT_STATS_YEAR = 2024
PROJECT_TODAY = "2025-04-30"
PROJECT_TIMESTAMP = 1745985600
CHART_METRICS = {
    "prescriptions": {
        "label": "Prescriptions Volume",
        "color": "#89cce7",
        "data_key": "prescription_data",
    },
    "inventory": {
        "label": "Inventory Trend",
        "color": "#a0d4a4",
        "data_key": "inventory_data",
    },
    "expired": {
        "label": "Expired Batches",
        "color": "#f16847",
        "data_key": "expired_data",
    },
}


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
        use_project_clock(cursor)
        cursor.execute(sql, params or [])
        return dictfetchall(cursor)


def fetch_one(sql, params=None):
    with connection.cursor() as cursor:
        use_project_clock(cursor)
        cursor.execute(sql, params or [])
        return dictfetchone(cursor)


def execute_sql(sql, params=None):
    with connection.cursor() as cursor:
        use_project_clock(cursor)
        cursor.execute(sql, params or [])


def use_project_clock(cursor):
    cursor.execute("SET time_zone = '+08:00'")
    cursor.execute("SET timestamp = %s", [PROJECT_TIMESTAMP])


def readable_database_error(error):
    message = str(error)
    if "Cannot prescribe: insufficient stock" in message:
        return "Cannot prescribe: insufficient stock for the selected medicine."
    if "Expiration date must be after production date" in message:
        return "Expiration date must be after production date."
    if "Medicine batch already expired" in message:
        return "Medicine batch already expired."
    if "foreign key" in message.lower():
        return "The selected record is invalid or no longer exists."
    return f"Database rejected the request: {message}"


def get_stats_year(request):
    year = request.GET.get("year", DEFAULT_STATS_YEAR)
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = DEFAULT_STATS_YEAR
    if year not in AVAILABLE_YEARS:
        year = DEFAULT_STATS_YEAR
    return year


def get_chart_metric(request):
    metric = request.GET.get("chart_metric", "prescriptions")
    if metric not in CHART_METRICS:
        metric = "prescriptions"
    return metric


def stats_cutoff(column, year):
    project_year = int(PROJECT_TODAY[:4])
    if year == project_year:
        return f"AND {column} <= %s", [PROJECT_TODAY]
    if year > project_year:
        return "AND 1 = 0", []
    return "", []


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
    chart_metric = get_chart_metric(request)
    stats = build_admin_statistics(year)
    chart_config = CHART_METRICS[chart_metric]
    context = {
        "prescription_count": stats["today_prescriptions"],
        "low_stock_count": stats["low_stock_count"] + stats["expiring_batch_count"],
        "pending_orders": stats["pending_orders"],
        "chart_labels": stats["labels"],
        "chart_data": stats[chart_config["data_key"]],
        "chart_metric": chart_metric,
        "chart_metric_label": chart_config["label"],
        "chart_metric_color": chart_config["color"],
        "chart_metrics": [
            {"key": key, "label": value["label"]}
            for key, value in CHART_METRICS.items()
        ],
        "inventory_data": stats["inventory_data"],
        "expired_data": stats["expired_data"],
        "latest_orders": stats["latest_orders"],
        "low_stock_items": stats["low_stock_items"],
        "expiring_batches": stats["expiring_batches"],
        "stats_year": year,
        "available_years": AVAILABLE_YEARS,
        "project_today": stats["project_today"],
    }
    return render(request, "admin/dashboard.html", context)


def admin_statistics_api(request):
    year = get_stats_year(request)
    stats = build_admin_statistics(year)
    chart_metric = get_chart_metric(request)
    chart_config = CHART_METRICS[chart_metric]
    stats["chart_metric"] = chart_metric
    stats["chart_metric_label"] = chart_config["label"]
    stats["chart_metric_color"] = chart_config["color"]
    stats["chart_data"] = stats[chart_config["data_key"]]
    return JsonResponse(stats)


def build_admin_statistics(year):
    today = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM prescription
        WHERE pr_date = %s
        """,
        [PROJECT_TODAY],
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
        WHERE expiration_date BETWEEN %s AND DATE_ADD(%s, INTERVAL 90 DAY)
        """,
        [PROJECT_TODAY, PROJECT_TODAY],
    )
    pending_orders = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM hospital_order
        WHERE LOWER(ho_status) NOT IN ('completed', 'delivered')
        """
    )

    prescription_cutoff, prescription_cutoff_params = stats_cutoff("pr_date", year)
    prescription_rows = fetch_all(
        f"""
        SELECT MONTH(pr_date) AS month_no, COUNT(*) AS total
        FROM prescription
        WHERE YEAR(pr_date) = %s
        {prescription_cutoff}
        GROUP BY MONTH(pr_date)
        """,
        [year] + prescription_cutoff_params,
    )
    inventory_cutoff, inventory_cutoff_params = stats_cutoff("store_date", year)
    inventory_rows = fetch_all(
        f"""
        SELECT MONTH(store_date) AS month_no, SUM(inventory) AS total
        FROM store
        WHERE YEAR(store_date) = %s
        {inventory_cutoff}
        GROUP BY MONTH(store_date)
        """,
        [year] + inventory_cutoff_params,
    )
    expired_cutoff, expired_cutoff_params = stats_cutoff("expiration_date", year)
    expired_rows = fetch_all(
        f"""
        SELECT MONTH(expiration_date) AS month_no, COUNT(*) AS total
        FROM medicine_batch
        WHERE YEAR(expiration_date) = %s
        {expired_cutoff}
        GROUP BY MONTH(expiration_date)
        """,
        [year] + expired_cutoff_params,
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
        WHERE mb.expiration_date BETWEEN %s AND DATE_ADD(%s, INTERVAL 90 DAY)
        ORDER BY mb.expiration_date ASC
        LIMIT 8
        """,
        [PROJECT_TODAY, PROJECT_TODAY],
    )

    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return {
        "year": year,
        "labels": labels,
        "today_prescriptions": today["total"],
        "low_stock_count": low_stock["total"],
        "expiring_batch_count": expiring["total"],
        "pending_orders": pending_orders["total"],
        "project_today": PROJECT_TODAY,
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
    query = request.GET.get("q", "").strip()
    params = []
    where = ""
    if query:
        where = """
        WHERE dc.dc_ID LIKE %s OR dc.dc_first_name LIKE %s OR dc.dc_last_name LIKE %s
              OR dc.dc_department LIKE %s OR dc.dc_phone1 LIKE %s OR dc.dc_phone2 LIKE %s
              OR h.h_name LIKE %s
        """
        keyword = f"%{query}%"
        params = [keyword, keyword, keyword, keyword, keyword, keyword, keyword]
    doctors = fetch_all(
        f"""
        SELECT dc.dc_ID AS dc_id, dc.dc_first_name, dc.dc_last_name, dc.dc_department,
               dc.dc_phone1, dc.dc_phone2, dc.h_ID AS h_id, h.h_name
        FROM doctor dc
        JOIN hospital h ON h.h_ID = dc.h_ID
        {where}
        ORDER BY dc.dc_ID
        LIMIT 200
        """,
        params,
    )
    hospitals = fetch_all("SELECT h_ID AS h_id, h_name FROM hospital ORDER BY h_ID")
    return render(
        request,
        "admin/users/doctor.html",
        {"doctors": doctors, "hospitals": hospitals, "query": query},
    )


def handle_doctor_post(request):
    action = request.POST.get("action")
    if action == "delete":
        execute_sql("DELETE FROM doctor WHERE dc_ID = %s", [request.POST.get("dc_id")])
        messages.success(request, "Doctor deleted.")
        return
    if action == "create":
        params = [
            request.POST.get("dc_first_name"),
            request.POST.get("dc_last_name"),
            request.POST.get("dc_department"),
            request.POST.get("dc_phone1"),
            request.POST.get("dc_phone2"),
            request.POST.get("h_id"),
            request.POST.get("dc_password") or 123456,
        ]
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
        fields = """
            dc_first_name = %s, dc_last_name = %s, dc_department = %s,
            dc_phone1 = %s, dc_phone2 = %s, h_ID = %s
        """
        params = [
            request.POST.get("dc_first_name"),
            request.POST.get("dc_last_name"),
            request.POST.get("dc_department"),
            request.POST.get("dc_phone1"),
            request.POST.get("dc_phone2"),
            request.POST.get("h_id"),
        ]
        password = (request.POST.get("dc_password") or "").strip()
        if password:
            fields += ", dc_password = %s"
            params.append(password)
        execute_sql(f"UPDATE doctor SET {fields} WHERE dc_ID = %s", params + [request.POST.get("dc_id")])
        messages.success(request, "Doctor updated.")


def pharmacist_users(request):
    if request.method == "POST":
        handle_pharmacist_post(request)
        return redirect("pharmacist_users")
    query = request.GET.get("q", "").strip()
    params = []
    where = ""
    if query:
        where = """
        WHERE ph.ph_ID LIKE %s OR ph.ph_firstname LIKE %s OR ph.ph_lastname LIKE %s
              OR ph.ph_phone1 LIKE %s OR ph.ph_phone2 LIKE %s
              OR ph.p_ID LIKE %s OR p.p_location LIKE %s
        """
        keyword = f"%{query}%"
        params = [keyword, keyword, keyword, keyword, keyword, keyword, keyword]
    pharmacists = fetch_all(
        f"""
        SELECT ph.ph_ID AS ph_id, ph.ph_firstname, ph.ph_lastname, ph.ph_phone1, ph.ph_phone2,
               ph.p_ID AS p_id, p.p_location
        FROM pharmacist ph
        JOIN pharmacy p ON p.p_ID = ph.p_ID
        {where}
        ORDER BY ph.ph_ID
        LIMIT 200
        """,
        params,
    )
    pharmacies = fetch_all("SELECT p_ID AS p_id, p_location FROM pharmacy ORDER BY p_ID")
    return render(
        request,
        "admin/users/phaemacist.html",
        {"pharmacists": pharmacists, "pharmacies": pharmacies, "query": query},
    )


def handle_pharmacist_post(request):
    action = request.POST.get("action")
    if action == "delete":
        execute_sql("DELETE FROM pharmacist WHERE ph_ID = %s", [request.POST.get("ph_id")])
        messages.success(request, "Pharmacist deleted.")
        return
    if action == "create":
        params = [
            request.POST.get("p_id"),
            request.POST.get("ph_firstname"),
            request.POST.get("ph_lastname"),
            request.POST.get("ph_phone1"),
            request.POST.get("ph_phone2"),
            request.POST.get("ph_password") or 123456,
        ]
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
        fields = """
            p_ID = %s, ph_firstname = %s, ph_lastname = %s,
            ph_phone1 = %s, ph_phone2 = %s
        """
        params = [
            request.POST.get("p_id"),
            request.POST.get("ph_firstname"),
            request.POST.get("ph_lastname"),
            request.POST.get("ph_phone1"),
            request.POST.get("ph_phone2"),
        ]
        password = (request.POST.get("ph_password") or "").strip()
        if password:
            fields += ", ph_password = %s"
            params.append(password)
        execute_sql(f"UPDATE pharmacist SET {fields} WHERE ph_ID = %s", params + [request.POST.get("ph_id")])
        messages.success(request, "Pharmacist updated.")


def distributor_users(request):
    if request.method == "POST":
        handle_distributor_post(request)
        return redirect("distributor_users")
    query = request.GET.get("q", "").strip()
    params = []
    where = ""
    if query:
        where = "WHERE d_ID LIKE %s OR d_name LIKE %s OR d_address LIKE %s"
        keyword = f"%{query}%"
        params = [keyword, keyword, keyword]
    distributors = fetch_all(
        f"""
        SELECT d_ID AS d_id, d_name, d_address
        FROM distributor
        {where}
        ORDER BY d_ID
        LIMIT 200
        """,
        params,
    )
    return render(request, "admin/users/distributor.html", {"distributors": distributors, "query": query})


def handle_distributor_post(request):
    action = request.POST.get("action")
    if action == "delete":
        execute_sql("DELETE FROM distributor WHERE d_ID = %s", [request.POST.get("d_id")])
        messages.success(request, "Distributor deleted.")
        return
    if action == "create":
        params = [
            request.POST.get("d_name"),
            request.POST.get("d_address"),
            request.POST.get("d_password") or 123456,
        ]
        execute_sql(
            """
            INSERT INTO distributor (d_ID, d_name, d_address, d_password)
            VALUES (%s, %s, %s, %s)
            """,
            [request.POST.get("d_id") or next_code("distributor", "d_ID", "DIS-", 3)] + params,
        )
        messages.success(request, "Distributor added.")
    elif action == "update":
        fields = "d_name = %s, d_address = %s"
        params = [request.POST.get("d_name"), request.POST.get("d_address")]
        password = (request.POST.get("d_password") or "").strip()
        if password:
            fields += ", d_password = %s"
            params.append(password)
        execute_sql(f"UPDATE distributor SET {fields} WHERE d_ID = %s", params + [request.POST.get("d_id")])
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
        action = request.POST.get("action")
        if action == "update_supply":
            try:
                execute_sql(
                    """
                    UPDATE supply
                    SET quantity = %s, p_ID = %s
                    WHERE supply_ID = %s
                    """,
                    [
                        request.POST.get("quantity"),
                        request.POST.get("p_id"),
                        request.POST.get("supply_id"),
                    ],
                )
                messages.success(request, "Supply record updated.")
            except DatabaseError as error:
                messages.error(request, readable_database_error(error))
        else:
            handle_distributor_post(request)
        return redirect("admin_suppliers")
    query = request.GET.get("q", "").strip()
    distributors = fetch_all("SELECT d_ID AS d_id, d_name, d_address FROM distributor ORDER BY d_ID")
    pharmacies = fetch_all("SELECT p_ID AS p_id, p_location FROM pharmacy ORDER BY p_ID")
    params = []
    where = ""
    if query:
        where = """
        WHERE s.supply_ID LIKE %s OR s.ho_ID LIKE %s OR h.h_name LIKE %s
              OR d.d_name LIKE %s OR s.p_ID LIKE %s OR ho.ho_status LIKE %s
        """
        keyword = f"%{query}%"
        params = [keyword, keyword, keyword, keyword, keyword, keyword]
    records = fetch_all(
        f"""
        SELECT s.supply_ID AS supply_id, s.quantity, s.p_ID AS p_id, p.p_location,
               ho.ho_ID AS ho_id, ho.ho_date, ho.ho_status, h.h_name, d.d_name
        FROM supply s
        JOIN hospital_order ho ON ho.ho_ID = s.ho_ID
        JOIN pharmacy p ON p.p_ID = s.p_ID
        JOIN hospital h ON h.h_ID = ho.h_ID
        JOIN distributor d ON d.d_ID = ho.d_ID
        {where}
        ORDER BY ho.ho_date DESC, s.supply_ID DESC
        LIMIT 200
        """,
        params,
    )
    return render(
        request,
        "admin/suppliers.html",
        {
            "distributors": distributors,
            "records": records,
            "pharmacies": pharmacies,
            "query": query,
        },
    )


# Doctor pages.


def current_doctor_id(request):
    try:
        return request.session["user_id"]
    except KeyError:
        return None


def require_doctor_session(request):
    doctor_id = current_doctor_id(request)
    if not doctor_id:
        messages.error(request, "Please log in as a doctor first.")
        return None
    return doctor_id


def load_doctor_profile(doctor_id):
    return fetch_one(
        """
        SELECT dc.dc_ID AS doctor_id, dc.dc_first_name, dc.dc_last_name, dc.dc_department,
               dc.h_ID AS hospital_id, h.h_name
        FROM doctor dc
        JOIN hospital h ON h.h_ID = dc.h_ID
        WHERE dc.dc_ID = %s
        """,
        [doctor_id],
    )


def load_doctor_patients(doctor_id):
    return fetch_all(
        """
        SELECT pat_ID AS patient_id, pat_name, pat_age, pat_department, pat_allergy
        FROM patient
        WHERE dc_ID = %s
        ORDER BY pat_name, pat_ID
        """,
        [doctor_id],
    )


def load_available_medicines(query=""):
    params = []
    where = ""
    if query:
        where = """
        WHERE m.m_ID LIKE %s OR m.m_name LIKE %s OR m.manufacturer LIKE %s
        """
        keyword = f"%{query}%"
        params = [keyword, keyword, keyword]
    return fetch_all(
        f"""
        SELECT m.m_ID AS medicine_id, m.m_name, m.manufacturer, m.unit_price,
               MIN(s.inventory) AS inventory, SUM(s.inventory) AS total_inventory
        FROM medicine m
        JOIN store s ON s.m_ID = m.m_ID
        {where}
        GROUP BY m.m_ID, m.m_name, m.manufacturer, m.unit_price
        HAVING MIN(s.inventory) > 0
        ORDER BY m.m_name, m.m_ID
        LIMIT 300
        """,
        params,
    )


def load_pharmacists():
    return fetch_all(
        """
        SELECT ph.ph_ID AS pharmacist_id,
               CONCAT(ph.ph_firstname, ' ', ph.ph_lastname) AS pharmacist_name,
               ph.p_ID AS pharmacy_id,
               p.p_location
        FROM pharmacist ph
        JOIN pharmacy p ON p.p_ID = ph.p_ID
        ORDER BY ph.ph_ID
        """
    )


def assign_hospital_pharmacist(doctor_id):
    return fetch_one(
        """
        SELECT ph.ph_ID AS pharmacist_id,
               CONCAT(ph.ph_firstname, ' ', ph.ph_lastname) AS pharmacist_name,
               ph.p_ID AS pharmacy_id
        FROM doctor dc
        JOIN pharmacy p ON p.h_ID = dc.h_ID
        JOIN pharmacist ph ON ph.p_ID = p.p_ID
        WHERE dc.dc_ID = %s
        ORDER BY RAND()
        LIMIT 1
        """,
        [doctor_id],
    )


def hospital_pharmacist_count(doctor_id):
    row = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM doctor dc
        JOIN pharmacy p ON p.h_ID = dc.h_ID
        JOIN pharmacist ph ON ph.p_ID = p.p_ID
        WHERE dc.dc_ID = %s
        """,
        [doctor_id],
    )
    return row["total"] if row else 0


def doctor_prescribe(request):
    doctor_id = require_doctor_session(request)
    if not doctor_id:
        return redirect("login")

    doctor = load_doctor_profile(doctor_id)
    if not doctor:
        messages.error(request, "Doctor profile was not found.")
        return redirect("login")

    if request.method == "POST":
        patient_id = (request.POST.get("patient_id") or "").strip()
        symptom = (request.POST.get("symptom") or "").strip()
        medicine_id = (request.POST.get("medicine_id") or "").strip()
        quantity_raw = (request.POST.get("quantity") or "").strip()

        if not all([patient_id, symptom, medicine_id, quantity_raw]):
            messages.error(request, "Patient, symptom, medicine, and quantity are required.")
            return redirect("doctor_prescribe")

        try:
            quantity = int(quantity_raw)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Quantity must be a positive integer.")
            return redirect("doctor_prescribe")

        patient = fetch_one(
            """
            SELECT pat_ID
            FROM patient
            WHERE pat_ID = %s AND dc_ID = %s
            """,
            [patient_id, doctor_id],
        )
        if not patient:
            messages.error(request, "Selected patient is not assigned to this doctor.")
            return redirect("doctor_prescribe")

        pharmacist = assign_hospital_pharmacist(doctor_id)
        if not pharmacist:
            messages.error(request, "No pharmacist is available in this doctor's hospital.")
            return redirect("doctor_prescribe")

        medicine = fetch_one(
            """
            SELECT m.m_ID AS medicine_id, MIN(s.inventory) AS inventory
            FROM medicine m
            JOIN store s ON s.m_ID = m.m_ID
            WHERE m.m_ID = %s
            GROUP BY m.m_ID
            """,
            [medicine_id],
        )
        if not medicine:
            messages.error(request, "Selected medicine is not available in inventory.")
            return redirect("doctor_prescribe")

        if int(medicine["inventory"] or 0) < quantity:
            messages.error(request, "Cannot prescribe: insufficient stock for the selected medicine.")
            return redirect("doctor_prescribe")

        try:
            with transaction.atomic():
                prescription_id = next_code("prescription", "pr_ID", "PR-", 8)
                execute_sql(
                    """
                    INSERT INTO prescription
                        (pr_ID, pr_date, pr_symptom, pat_ID, dc_ID, ph_ID)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        prescription_id,
                        PROJECT_TODAY,
                        symptom,
                        patient_id,
                        doctor_id,
                        pharmacist["pharmacist_id"],
                    ],
                )
                execute_sql(
                    """
                    INSERT INTO contain (pr_ID, m_ID, quantity)
                    VALUES (%s, %s, %s)
                    """,
                    [prescription_id, medicine_id, quantity],
                )
        except DatabaseError as error:
            messages.error(request, readable_database_error(error))
            return redirect("doctor_prescribe")

        messages.success(
            request,
            f"Prescription {prescription_id} created and assigned to {pharmacist['pharmacist_name']}.",
        )
        return redirect("doctor_history")

    medicine_query = request.GET.get("medicine_q", "").strip()
    context = {
        "doctor": doctor,
        "patients": load_doctor_patients(doctor_id),
        "medicines": load_available_medicines(medicine_query),
        "medicine_query": medicine_query,
        "hospital_pharmacist_count": hospital_pharmacist_count(doctor_id),
    }
    return render(request, "doctor/prescribe.html", context)


def doctor_history(request):
    doctor_id = require_doctor_session(request)
    if not doctor_id:
        return redirect("login")

    query = request.GET.get("q", "").strip()
    params = [doctor_id]
    where = "WHERE pr.dc_ID = %s"
    if query:
        where += """
            AND (
                pr.pr_ID LIKE %s OR
                pat.pat_name LIKE %s OR
                pr.pr_symptom LIKE %s OR
                py.py_status LIKE %s
            )
        """
        keyword = f"%{query}%"
        params.extend([keyword, keyword, keyword, keyword])

    prescriptions = fetch_all(
        f"""
        SELECT pr.pr_ID AS prescription_id, pr.pr_date, pr.pr_symptom,
               pat.pat_ID AS patient_id, pat.pat_name,
               CONCAT(ph.ph_firstname, ' ', ph.ph_lastname) AS pharmacist_name,
               GROUP_CONCAT(
                   CONCAT(m.m_name, ' x', c.quantity)
                   ORDER BY m.m_name
                   SEPARATOR ', '
               ) AS medicines,
               py.py_status, py.price
        FROM prescription pr
        JOIN patient pat ON pat.pat_ID = pr.pat_ID
        JOIN pharmacist ph ON ph.ph_ID = pr.ph_ID
        LEFT JOIN contain c ON c.pr_ID = pr.pr_ID
        LEFT JOIN medicine m ON m.m_ID = c.m_ID
        LEFT JOIN payment py ON py.pr_ID = pr.pr_ID
        {where}
        GROUP BY pr.pr_ID, pr.pr_date, pr.pr_symptom, pat.pat_ID, pat.pat_name,
                 ph.ph_firstname, ph.ph_lastname, py.py_status, py.price
        ORDER BY pr.pr_date DESC, pr.pr_ID DESC
        LIMIT 300
        """,
        params,
    )
    return render(
        request,
        "doctor/history.html",
        {"prescriptions": prescriptions, "query": query},
    )


def doctor_patients(request):
    doctor_id = require_doctor_session(request)
    if not doctor_id:
        return redirect("login")

    query = request.GET.get("q", "").strip()
    params = [doctor_id]
    where = "WHERE dc_ID = %s"
    if query:
        where += """
            AND (
                pat_ID LIKE %s OR
                pat_name LIKE %s OR
                pat_department LIKE %s OR
                pat_allergy LIKE %s
            )
        """
        keyword = f"%{query}%"
        params.extend([keyword, keyword, keyword, keyword])

    patients = fetch_all(
        f"""
        SELECT pat_ID AS patient_id, pat_name, pat_age, pat_department, pat_allergy
        FROM patient
        {where}
        ORDER BY pat_name, pat_ID
        LIMIT 300
        """,
        params,
    )
    return render(
        request,
        "doctor/patients.html",
        {"patients": patients, "query": query},
    )


# Pharmacist pages.


def current_pharmacist_id(request):
    try:
        return request.session["user_id"]
    except KeyError:
        return None


def require_pharmacist_session(request):
    pharmacist_id = current_pharmacist_id(request)
    if not pharmacist_id:
        messages.error(request, "Please log in as a pharmacist first.")
        return None
    return pharmacist_id


def load_pharmacist_profile(pharmacist_id):
    return fetch_one(
        """
        SELECT ph.ph_ID AS pharmacist_id,
               CONCAT(ph.ph_firstname, ' ', ph.ph_lastname) AS pharmacist_name,
               ph.p_ID AS pharmacy_id, p.p_location
        FROM pharmacist ph
        JOIN pharmacy p ON p.p_ID = ph.p_ID
        WHERE ph.ph_ID = %s
        """,
        [pharmacist_id],
    )


def pharmacist_inventory(request):
    pharmacist_id = require_pharmacist_session(request)
    if not pharmacist_id:
        return redirect("login")

    pharmacist = load_pharmacist_profile(pharmacist_id)
    if not pharmacist:
        messages.error(request, "Pharmacist profile was not found.")
        return redirect("login")

    query = request.GET.get("q", "").strip()
    params = [pharmacist_id]
    where = "WHERE ph.ph_ID = %s"
    if query:
        where += """
            AND (
                m.m_ID LIKE %s OR
                m.m_name LIKE %s OR
                m.manufacturer LIKE %s
            )
        """
        keyword = f"%{query}%"
        params.extend([keyword, keyword, keyword])

    stores = fetch_all(
        f"""
        SELECT s.s_ID AS s_id, s.inventory, s.store_date,
               m.m_ID AS m_id, m.m_name, m.manufacturer, m.unit_price,
               p.p_ID AS p_id, p.p_location
        FROM pharmacist ph
        JOIN pharmacy p ON p.p_ID = ph.p_ID
        JOIN store s ON s.p_ID = p.p_ID
        JOIN medicine m ON m.m_ID = s.m_ID
        {where}
        ORDER BY s.inventory ASC, m.m_name
        LIMIT 300
        """,
        params,
    )
    return render(
        request,
        "pharmacist/inventory.html",
        {
            "stores": stores,
            "pharmacist": pharmacist,
            "query": query,
            "low_stock_limit": LOW_STOCK_LIMIT,
        },
    )


def pharmacist_audit(request):
    pharmacist_id = require_pharmacist_session(request)
    if not pharmacist_id:
        return redirect("login")

    if request.method == "POST":
        prescription_id = request.POST.get("prescription_id")
        try:
            prescription = fetch_one(
                """
                SELECT pr.pr_ID AS prescription_id, py.py_status
                FROM prescription pr
                LEFT JOIN payment py ON py.pr_ID = pr.pr_ID
                WHERE pr.pr_ID = %s AND pr.ph_ID = %s
                """,
                [prescription_id, pharmacist_id],
            )
            if not prescription:
                messages.error(request, "Prescription was not found for this pharmacist.")
                return redirect("pharmacist_audit")
            if prescription["py_status"] != "paid":
                messages.error(request, "Only paid prescriptions can be confirmed for dispensing.")
                return redirect("pharmacist_audit")
        except DatabaseError as error:
            messages.error(request, readable_database_error(error))
            return redirect("pharmacist_audit")

        messages.success(
            request,
            "Prescription confirmed for dispensing. Inventory was already reduced when the prescription was created.",
        )
        return redirect("pharmacist_audit")

    query = request.GET.get("q", "").strip()
    params = [pharmacist_id]
    where = "WHERE pr.ph_ID = %s"
    if query:
        where += """
            AND (
                pr.pr_ID LIKE %s OR
                pat.pat_name LIKE %s OR
                CONCAT(dc.dc_first_name, ' ', dc.dc_last_name) LIKE %s OR
                pr.pr_symptom LIKE %s OR
                py.py_status LIKE %s
            )
        """
        keyword = f"%{query}%"
        params.extend([keyword, keyword, keyword, keyword, keyword])

    prescriptions = fetch_all(
        f"""
        SELECT pr.pr_ID AS prescription_id, pr.pr_date, pr.pr_symptom,
               pat.pat_name,
               CONCAT(dc.dc_first_name, ' ', dc.dc_last_name) AS doctor_name,
               GROUP_CONCAT(
                   CONCAT(m.m_name, ' x', c.quantity)
                   ORDER BY m.m_name
                   SEPARATOR ', '
               ) AS medicines,
               py.py_status, py.price
        FROM prescription pr
        JOIN patient pat ON pat.pat_ID = pr.pat_ID
        JOIN doctor dc ON dc.dc_ID = pr.dc_ID
        LEFT JOIN contain c ON c.pr_ID = pr.pr_ID
        LEFT JOIN medicine m ON m.m_ID = c.m_ID
        LEFT JOIN payment py ON py.pr_ID = pr.pr_ID
        {where}
        GROUP BY pr.pr_ID, pr.pr_date, pr.pr_symptom, pat.pat_name,
                 dc.dc_first_name, dc.dc_last_name, py.py_status, py.price
        ORDER BY pr.pr_date DESC, pr.pr_ID DESC
        LIMIT 300
        """,
        params,
    )
    return render(
        request,
        "pharmacist/audit.html",
        {"prescriptions": prescriptions, "query": query},
    )


def pharmacist_batches(request):
    pharmacist_id = require_pharmacist_session(request)
    if not pharmacist_id:
        return redirect("login")

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if request.method == "POST":
        mb_id = (request.POST.get("mb_id") or "").strip()
        medicine_id = (request.POST.get("medicine_id") or "").strip()
        production_date = (request.POST.get("production_date") or "").strip()
        expiration_date = (request.POST.get("expiration_date") or "").strip()

        if not all([medicine_id, production_date, expiration_date]):
            messages.error(request, "Medicine, production date, and expiration date are required.")
            return redirect("pharmacist_batches")

        try:
            with transaction.atomic():
                execute_sql(
                    """
                    INSERT INTO medicine_batch (mb_ID, m_ID, production_date, expiration_date)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [
                        mb_id or next_code("medicine_batch", "mb_ID", "MB-", 5),
                        medicine_id,
                        production_date,
                        expiration_date,
                    ],
                )
        except DatabaseError as error:
            messages.error(request, readable_database_error(error))
            return redirect("pharmacist_batches")

        messages.success(request, "Medicine batch recorded.")
        return redirect("pharmacist_batches")

    batch_params = [PROJECT_TODAY, PROJECT_TODAY, PROJECT_TODAY]
    batch_where = ""
    batch_filters = []
    if query:
        batch_filters.append("(m.m_ID LIKE %s OR m.m_name LIKE %s)")
        keyword = f"%{query}%"
        batch_params.extend([keyword, keyword])
    if status in {"Expired", "Near Expiry", "Valid"}:
        batch_filters.append("""
            CASE
                WHEN mb.expiration_date < %s THEN 'Expired'
                WHEN mb.expiration_date <= DATE_ADD(%s, INTERVAL 90 DAY) THEN 'Near Expiry'
                ELSE 'Valid'
            END = %s
        """)
        batch_params.extend([PROJECT_TODAY, PROJECT_TODAY, status])
    else:
        status = ""
    if batch_filters:
        batch_where = "WHERE " + " AND ".join(batch_filters)
    batches = fetch_all(
        f"""
        SELECT mb.mb_ID AS mb_id, mb.m_ID AS m_id, m.m_name,
               mb.production_date, mb.expiration_date,
               DATEDIFF(mb.expiration_date, %s) AS days_left,
               CASE
                   WHEN mb.expiration_date < %s THEN 'Expired'
                   WHEN mb.expiration_date <= DATE_ADD(%s, INTERVAL 90 DAY) THEN 'Near Expiry'
                   ELSE 'Valid'
               END AS batch_status
        FROM medicine_batch mb
        JOIN medicine m ON m.m_ID = mb.m_ID
        {batch_where}
        ORDER BY
            CASE batch_status
                WHEN 'Near Expiry' THEN 0
                WHEN 'Expired' THEN 1
                ELSE 2
            END,
            days_left ASC,
            mb.expiration_date ASC
        """,
        batch_params,
    )
    medicine_params = []
    medicine_where = ""
    if query:
        medicine_where = "WHERE m_ID LIKE %s OR m_name LIKE %s"
        keyword = f"%{query}%"
        medicine_params = [keyword, keyword]
    medicines = fetch_all(
        f"""
        SELECT m_ID AS medicine_id, m_name, manufacturer
        FROM medicine
        {medicine_where}
        ORDER BY m_name, m_ID
        LIMIT 300
        """,
        medicine_params,
    )
    return render(
        request,
        "pharmacist/batches.html",
        {
            "batches": batches,
            "medicines": medicines,
            "query": query,
            "status": status,
            "project_today": PROJECT_TODAY,
        },
    )


def pharmacist_payments(request):
    pharmacist_id = require_pharmacist_session(request)
    if not pharmacist_id:
        return redirect("login")

    if request.method == "POST":
        action = request.POST.get("action", "update")

        if action == "create_unpaid":
            prescription_id = request.POST.get("prescription_id")
            try:
                with transaction.atomic():
                    prescription = fetch_one(
                        """
                        SELECT pr_ID AS prescription_id
                        FROM prescription
                        WHERE pr_ID = %s AND ph_ID = %s
                        FOR UPDATE
                        """,
                        [prescription_id, pharmacist_id],
                    )
                    if not prescription:
                        messages.error(request, "Prescription was not found for this pharmacist.")
                        return redirect("pharmacist_payments")

                    existing_payment = fetch_one(
                        """
                        SELECT py_ID AS payment_id
                        FROM payment
                        WHERE pr_ID = %s
                        LIMIT 1
                        """,
                        [prescription_id],
                    )
                    if existing_payment:
                        messages.error(request, "This prescription already has a payment record.")
                        return redirect("pharmacist_payments")

                    price = fetch_one(
                        """
                        SELECT COALESCE(SUM(c.quantity * m.unit_price), 0) AS total_price
                        FROM contain c
                        JOIN medicine m ON m.m_ID = c.m_ID
                        WHERE c.pr_ID = %s
                        """,
                        [prescription_id],
                    )
                    payment_id = next_code("payment", "py_ID", "PAY-", 8)
                    execute_sql(
                        """
                        INSERT INTO payment (py_ID, pr_ID, price, py_status, py_date)
                        VALUES (%s, %s, %s, 'unpaid', %s)
                        """,
                        [payment_id, prescription_id, price["total_price"], PROJECT_TODAY],
                    )
            except DatabaseError as error:
                messages.error(request, readable_database_error(error))
                return redirect("pharmacist_payments")

            messages.success(request, f"Unpaid payment {payment_id} created.")
            return redirect("pharmacist_payments")

        if action != "update":
            messages.error(request, "Invalid payment action.")
            return redirect("pharmacist_payments")

        payment_id = request.POST.get("payment_id")
        new_status = request.POST.get("py_status")
        if new_status not in {"paid", "unpaid", "delayed"}:
            messages.error(request, "Invalid payment status.")
            return redirect("pharmacist_payments")

        try:
            payment = fetch_one(
                """
                SELECT py.py_ID AS payment_id
                FROM payment py
                JOIN prescription pr ON pr.pr_ID = py.pr_ID
                WHERE py.py_ID = %s AND pr.ph_ID = %s
                """,
                [payment_id, pharmacist_id],
            )
            if not payment:
                messages.error(request, "Payment record was not found for this pharmacist.")
                return redirect("pharmacist_payments")

            with transaction.atomic():
                execute_sql(
                    """
                    UPDATE payment
                    SET py_status = %s,
                        py_date = CASE WHEN %s = 'paid' THEN %s ELSE NULL END
                    WHERE py_ID = %s
                    """,
                    [new_status, new_status, PROJECT_TODAY, payment_id],
                )
        except DatabaseError as error:
            messages.error(request, readable_database_error(error))
            return redirect("pharmacist_payments")

        messages.success(request, "Payment status updated.")
        return redirect("pharmacist_payments")

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    params = [pharmacist_id]
    where = "WHERE pr.ph_ID = %s"
    if status in {"paid", "unpaid", "delayed"}:
        where += " AND py.py_status = %s"
        params.append(status)
    elif status == "no_payment":
        where += " AND py.py_ID IS NULL"
    else:
        status = ""
    if query:
        where += """
            AND (
                py.py_ID LIKE %s OR
                pr.pr_ID LIKE %s OR
                pat.pat_name LIKE %s OR
                COALESCE(py.py_status, 'No payment') LIKE %s
            )
        """
        keyword = f"%{query}%"
        params.extend([keyword, keyword, keyword, keyword])

    payments = fetch_all(
        f"""
        SELECT py.py_ID AS payment_id, pr.pr_ID AS prescription_id,
               pat.pat_name, py.price, py.py_status, py.py_date
        FROM prescription pr
        JOIN patient pat ON pat.pat_ID = pr.pat_ID
        LEFT JOIN payment py ON py.pr_ID = pr.pr_ID
        {where}
        ORDER BY COALESCE(py.py_date, pr.pr_date) DESC, pr.pr_ID DESC
        LIMIT 300
        """,
        params,
    )
    return render(
        request,
        "pharmacist/payments.html",
        {"payments": payments, "query": query, "status": status},
    )


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

    query = request.GET.get("q", "").strip()
    keyword = f"%{query}%"
    params = []
    where = "WHERE LOWER(ho.ho_status) IN ('shipping', 'completed', 'delivered')"
    if distributor_id:
        where += " AND ho.d_ID = %s"
        params.append(distributor_id)
    if query:
        where += """
            AND (
                ho.ho_ID LIKE %s OR
                h.h_name LIKE %s OR
                ho.ho_status LIKE %s OR
                s.supply_ID LIKE %s OR
                s.p_ID LIKE %s OR
                CAST(s.quantity AS CHAR) LIKE %s
            )
        """
        params.extend([keyword, keyword, keyword, keyword, keyword, keyword])
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
    batch_params = []
    batch_where = ""
    if query:
        batch_where = """
        WHERE mb.mb_ID LIKE %s OR mb.m_ID LIKE %s OR m.m_name LIKE %s
        """
        batch_params = [keyword, keyword, keyword]
    batches = fetch_all(
        f"""
        SELECT mb.mb_ID AS mb_id, mb.production_date, mb.expiration_date, m.m_ID AS m_id, m.m_name
        FROM medicine_batch mb
        JOIN medicine m ON m.m_ID = mb.m_ID
        {batch_where}
        ORDER BY mb.production_date DESC, mb.mb_ID DESC
        LIMIT 80
        """,
        batch_params,
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
            "query": query,
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
