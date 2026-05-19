from django.shortcuts import render, redirect

from .models import (
    Medicine,
    Doctor,
    Pharmacist,
    Distributor,
    Admin,
    Store,
    Prescription
)
from django.db import connection
from .forms import MedicineForm

# ADMIN DASHBOARD

def admin_dashboard(request):

    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT COUNT(*)
            FROM prescription
            WHERE DATE(pr_date) = CURDATE()
        """)

        prescription_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM store
            WHERE inventory < 50
        """)

        low_stock_count = cursor.fetchone()[0]
        filter_type = request.GET.get('type', 'month')
        filter_value = request.GET.get('value', '2024')
        if filter_type == 'month':
            cursor.execute("""
            SELECT MONTH(pr_date) AS month,
               COUNT(*) AS total
            FROM prescription
            WHERE YEAR(pr_date) = %s
            GROUP BY MONTH(pr_date)
            ORDER BY MONTH(pr_date)
            """, [filter_value])

        else:

            cursor.execute("""
            SELECT YEAR(pr_date) AS year,
               COUNT(*) AS total
            FROM prescription
            GROUP BY YEAR(pr_date)
            ORDER BY YEAR(pr_date)
            """)

        monthly_data = cursor.fetchall()
        chart_labels = []
        chart_data = []

        month_names = [
        'Jan', 'Feb', 'Mar',
        'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep',
        'Oct', 'Nov', 'Dec'
        ]

    for row in monthly_data:

        month_number = row[0]
        total = row[1]

        if filter_type == 'month':
            chart_labels.append(
            month_names[month_number - 1]
        )
        else:
            chart_labels.append(str(month_number))

        chart_data.append(total)
    pending_orders = 0
        
    context = {
        'prescription_count': prescription_count,
        'low_stock_count': low_stock_count,
        'pending_orders': pending_orders,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'filter_type': filter_type,
        'filter_value': filter_value
    }

    return render(
        request,
        'admin/dashboard.html',
        context
    )
# MEDICINE MANAGEMENT


def admin_medicines(request):

    medicines = Medicine.objects.all()

    return render(
        request,
        'admin/medicines.html',
        {
            'medicines': medicines
        }
    )


def medicine_management(request):

    medicines = Medicine.objects.all()

    if request.method == 'POST':

        form = MedicineForm(request.POST)

        if form.is_valid():

            form.save()

            return redirect('medicine_management')

    else:

        form = MedicineForm()

    return render(
        request,
        'admin/medicine_management.html',
        {
            'medicines': medicines,
            'form': form
        }
    )


# USER MANAGEMENT

def doctor_users(request):

    doctors = Doctor.objects.all()

    return render(
        request,
        'admin/users/doctors.html',
        {
            'doctors': doctors
        }
    )


def pharmacist_users(request):

    pharmacists = Pharmacist.objects.all()

    return render(
        request,
        'admin/users/pharmacists.html',
        {
            'pharmacists': pharmacists
        }
    )


def distributor_users(request):

    distributors = Distributor.objects.all()

    return render(
        request,
        'admin/users/distributors.html',
        {
            'distributors': distributors
        }
    )


def admin_users_admins(request):

    admins = Admin.objects.all()

    return render(
        request,
        'admin/users/admins.html',
        {
            'admins': admins
        }
    )


# DOCTOR MODULE

def doctor_prescribe(request):

    return render(
        request,
        'doctor/prescribe.html'
    )


# PHARMACIST MODULE

def pharmacist_inventory(request):

    stores = Store.objects.all()

    return render(
        request,
        'pharmacist/inventory.html',
        {
            'stores': stores
        }
    )


def pharmacist_audit(request):

    return render(
        request,
        'pharmacist/audit.html'
    )


# DISTRIBUTOR MODULE


def distributor_orders(request):

    return render(
        request,
        'distributor/orders.html'
    )


# LOGIN / LOGOUT

def login_view(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        if role == 'Admin':

            admin = Admin.objects.filter(
                admin_id=username,
                admin_password=password
            ).first()

            if admin:

                request.session['role'] = 'Admin'

                return redirect('/admin/dashboard/')

        return render(
            request,
            'login.html',
            {
                'error': 'Invalid username or password'
            }
        )

    return render(
        request,
        'login.html'
    )