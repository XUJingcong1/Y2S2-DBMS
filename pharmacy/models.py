# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Admin(models.Model):
    admin_id = models.CharField(primary_key=True, max_length=20)
    admin_name = models.CharField(max_length=50, blank=True, null=True)
    admin_password = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'admin'


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class Contain(models.Model):
    pr = models.OneToOneField('Prescription', models.DO_NOTHING, db_column='pr_ID', primary_key=True)  # Field name made lowercase. The composite primary key (pr_ID, m_ID) found, that is not supported. The first column is selected.
    m = models.ForeignKey('Medicine', models.DO_NOTHING, db_column='m_ID')  # Field name made lowercase.
    quantity = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'contain'
        unique_together = (('pr', 'm'),)


class Distributor(models.Model):
    d_id = models.CharField(db_column='d_ID', primary_key=True, max_length=10)  # Field name made lowercase.
    d_name = models.CharField(max_length=100)
    d_address = models.CharField(max_length=200)
    d_password = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'distributor'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class Doctor(models.Model):
    dc_id = models.CharField(db_column='dc_ID', primary_key=True, max_length=10)  # Field name made lowercase.
    dc_first_name = models.CharField(max_length=50)
    dc_last_name = models.CharField(max_length=50)
    dc_department = models.CharField(max_length=50)
    dc_phone1 = models.CharField(max_length=20)
    dc_phone2 = models.CharField(max_length=20)
    h = models.ForeignKey('Hospital', models.DO_NOTHING, db_column='h_ID')  # Field name made lowercase.
    dc_password = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'doctor'


class Hospital(models.Model):
    h_id = models.CharField(db_column='h_ID', primary_key=True, max_length=10)  # Field name made lowercase.
    h_name = models.CharField(max_length=100)
    h_address = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'hospital'


class HospitalOrder(models.Model):
    ho_id = models.CharField(db_column='ho_ID', primary_key=True, max_length=10)  # Field name made lowercase.
    h = models.ForeignKey(Hospital, models.DO_NOTHING, db_column='h_ID')  # Field name made lowercase.
    ho_date = models.DateField()
    ho_status = models.CharField(max_length=50)
    d = models.ForeignKey(Distributor, models.DO_NOTHING, db_column='d_ID')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'hospital_order'


class Medicine(models.Model):
    m_id = models.CharField(db_column='m_ID', primary_key=True, max_length=20)  # Field name made lowercase.
    m_name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    manufacturer = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'medicine'


class MedicineBatch(models.Model):
    mb_id = models.CharField(db_column='mb_ID', primary_key=True, max_length=20)  # Field name made lowercase.
    m = models.ForeignKey(Medicine, models.DO_NOTHING, db_column='m_ID')  # Field name made lowercase.
    production_date = models.DateField()
    expiration_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'medicine_batch'


class Patient(models.Model):
    pat_id = models.CharField(db_column='pat_ID', primary_key=True, max_length=20)  # Field name made lowercase.
    pat_name = models.CharField(max_length=100)
    pat_age = models.IntegerField()
    pat_gender = models.CharField(max_length=1)
    pat_department = models.CharField(max_length=100, blank=True, null=True)
    pat_allergy = models.CharField(max_length=200, blank=True, null=True)
    dc = models.ForeignKey(Doctor, models.DO_NOTHING, db_column='dc_ID')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'patient'


class Payment(models.Model):
    py_id = models.CharField(db_column='py_ID', primary_key=True, max_length=20)  # Field name made lowercase.
    pr = models.ForeignKey('Prescription', models.DO_NOTHING, db_column='pr_ID')  # Field name made lowercase.
    price = models.DecimalField(max_digits=10, decimal_places=2)
    py_status = models.CharField(max_length=7)
    py_date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment'


class Pharmacist(models.Model):
    p = models.ForeignKey('Pharmacy', models.DO_NOTHING, db_column='p_ID')  # Field name made lowercase.
    ph_firstname = models.CharField(max_length=100)
    ph_lastname = models.CharField(max_length=100)
    ph_id = models.CharField(db_column='ph_ID', primary_key=True, max_length=10)  # Field name made lowercase.
    ph_phone1 = models.CharField(max_length=20)
    ph_phone2 = models.CharField(max_length=20, blank=True, null=True)
    ph_password = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'pharmacist'


class Pharmacy(models.Model):
    p_id = models.CharField(db_column='p_ID', primary_key=True, max_length=10)  # Field name made lowercase.
    p_phone = models.CharField(max_length=20)
    p_location = models.CharField(max_length=200)
    h = models.ForeignKey(Hospital, models.DO_NOTHING, db_column='h_ID')  # Field name made lowercase.
    p_type = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'pharmacy'


class Prescription(models.Model):
    pr_id = models.CharField(db_column='pr_ID', primary_key=True, max_length=20)  # Field name made lowercase.
    pr_date = models.DateField()
    pr_symptom = models.CharField(max_length=100)
    pat = models.ForeignKey(Patient, models.DO_NOTHING, db_column='pat_ID')  # Field name made lowercase.
    dc = models.ForeignKey(Doctor, models.DO_NOTHING, db_column='dc_ID')  # Field name made lowercase.
    ph = models.ForeignKey(Pharmacist, models.DO_NOTHING, db_column='ph_ID')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'prescription'


class Store(models.Model):
    s_id = models.CharField(db_column='s_ID', primary_key=True, max_length=10)  # Field name made lowercase.
    p = models.ForeignKey(Pharmacy, models.DO_NOTHING, db_column='p_ID')  # Field name made lowercase.
    inventory = models.IntegerField()
    store_date = models.DateField()
    m = models.ForeignKey(Medicine, models.DO_NOTHING, db_column='m_ID')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'store'


class Supply(models.Model):
    ho = models.ForeignKey(HospitalOrder, models.DO_NOTHING, db_column='ho_ID')  # Field name made lowercase.
    quantity = models.CharField(max_length=10)
    p = models.ForeignKey(Pharmacy, models.DO_NOTHING, db_column='p_ID')  # Field name made lowercase.
    supply_id = models.AutoField(db_column='supply_ID', primary_key=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'supply'
