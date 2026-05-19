from django.urls import path

from . import views


urlpatterns = [

    # =====================================================
    # LOGIN
    # =====================================================

    path(
        '',
        views.login_view,
        name='login'
    ),

    # =====================================================
    # ADMIN DASHBOARD
    # =====================================================

    path(
        'admin/dashboard/',
        views.admin_dashboard,
        name='admin_dashboard'
    ),

    # =====================================================
    # MEDICINES
    # =====================================================

    path(
        'admin/medicines/',
        views.admin_medicines,
        name='admin_medicines'
    ),

    path(
        'admin/medicine-management/',
        views.medicine_management,
        name='medicine_management'
    ),

    # =====================================================
    # USER MANAGEMENT
    # =====================================================

    path(
        'admin/users/doctors/',
        views.doctor_users,
        name='doctor_users'
    ),

    path(
        'admin/users/pharmacists/',
        views.pharmacist_users,
        name='pharmacist_users'
    ),

    path(
        'admin/users/distributors/',
        views.distributor_users,
        name='distributor_users'
    ),

    path(
        'admin/users/admins/',
        views.admin_users_admins,
        name='admin_users_admins'
    ),

    # =====================================================
    # DOCTOR MODULE
    # =====================================================

    path(
        'doctor/prescribe/',
        views.doctor_prescribe,
        name='doctor_prescribe'
    ),

    # =====================================================
    # PHARMACIST MODULE
    # =====================================================

    path(
        'pharmacist/inventory/',
        views.pharmacist_inventory,
        name='pharmacist_inventory'
    ),

    path(
        'pharmacist/audit/',
        views.pharmacist_audit,
        name='pharmacist_audit'
    ),

    # =====================================================
    # DISTRIBUTOR MODULE
    # =====================================================

    path(
        'distributor/orders/',
        views.distributor_orders,
        name='distributor_orders'
    ),

]