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
        'dashboard/',
        views.dashboard_redirect,
        name='dashboard_redirect'
    ),

    path(
        'admin/dashboard/',
        views.admin_dashboard,
        name='admin_dashboard'
    ),

    path(
        'admin/statistics/api/',
        views.admin_statistics_api,
        name='admin_statistics_api'
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

    path(
        'admin/suppliers/',
        views.admin_suppliers,
        name='admin_suppliers'
    ),

    # =====================================================
    # DOCTOR MODULE
    # =====================================================

    path(
        'doctor/prescribe/',
        views.doctor_prescribe,
        name='doctor_prescribe'
    ),

    path(
        'doctor/history/',
        views.doctor_history,
        name='doctor_history'
    ),

    path(
        'doctor/patients/',
        views.doctor_patients,
        name='doctor_patients'
    ),

    path(
        'doctor/dashboard/',
        views.doctor_prescribe,
        name='doctor_dashboard'
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
        'pharmacist/dashboard/',
        views.pharmacist_inventory,
        name='pharmacist_dashboard'
    ),

    path(
        'pharmacist/audit/',
        views.pharmacist_audit,
        name='pharmacist_audit'
    ),

    path(
        'pharmacist/batches/',
        views.pharmacist_batches,
        name='pharmacist_batches'
    ),

    path(
        'pharmacist/payments/',
        views.pharmacist_payments,
        name='pharmacist_payments'
    ),

    # =====================================================
    # DISTRIBUTOR MODULE
    # =====================================================

    path(
        'distributor/orders/',
        views.distributor_orders,
        name='distributor_orders'
    ),

    path(
        'distributor/dashboard/',
        views.distributor_orders,
        name='distributor_dashboard'
    ),

    path(
        'distributor/shipments/',
        views.distributor_shipments,
        name='distributor_shipments'
    ),

]
