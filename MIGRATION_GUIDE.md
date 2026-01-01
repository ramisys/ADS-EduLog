# Migration Guide: Refactoring to TeacherSubjectAssignment Architecture

## 🚨 Current Issue
Django is asking for a default value when adding non-nullable fields because existing records need to be migrated.

## ✅ Solution: Multi-Step Migration

### Step 1: Create Initial Migration (Fields Nullable)
The models are now set with nullable fields. Run:

```bash
python manage.py makemigrations
```

This will create a migration that:
- Adds new nullable fields (`assignment`, `enrollment`)
- Keeps old fields temporarily (if they exist)

### Step 2: Create Data Migration
After Step 1, we need to create a data migration to populate the new fields from existing data.

**Important:** Before running migrations, check what old fields exist in your database. The old Subject model had `teacher` and `section` fields that we removed.

### Step 3: Migration Strategy

#### Option A: If Subject still has `teacher` and `section` fields in database

1. **First Migration**: Add new nullable fields, keep old fields
2. **Data Migration**: Populate new fields from old relationships
3. **Final Migration**: Remove old fields, make new fields non-nullable

#### Option B: If Subject no longer has `teacher` and `section` fields

We need to create TeacherSubjectAssignment records from existing data first, then link everything.

## 📝 Detailed Migration Steps

### Step 1: Run Initial Migration
```bash
python manage.py makemigrations core
```

When prompted, choose option **1** and provide a temporary default (we'll fix it in data migration):
- For Assessment.assignment: Enter `1` (we'll update it in data migration)
- For StudentEnrollment.assignment: Enter `1`
- For Attendance.enrollment: Enter `1`
- For Grade.enrollment: Enter `1`
- For AssessmentScore.enrollment: Enter `1`
- For CategoryWeights.assignment: Enter `1`

### Step 2: Create Data Migration Script

After the initial migration, we'll need to create a data migration file manually. Here's what it should do:

1. **Create TeacherSubjectAssignment records** from existing Subject records (if Subject has teacher/section)
2. **Update StudentEnrollment** to link to assignments
3. **Update Attendance** to link to enrollments
4. **Update Grade** to link to enrollments
5. **Update Assessment** to link to assignments
6. **Update AssessmentScore** to link to enrollments
7. **Update CategoryWeights** to link to assignments

### Step 3: Make Fields Non-Nullable

After data migration, create another migration to:
- Remove old fields (if they exist)
- Make new fields non-nullable

## 🔧 Quick Fix: Run Makemigrations Now

Since we've made fields nullable, you can now run:

```bash
python manage.py makemigrations
```

**When prompted**, choose option **1** and enter `1` as the default (temporary - we'll fix in data migration).

Then we'll create a proper data migration to populate the fields correctly.

## ⚠️ Important Notes

1. **Backup your database** before running migrations
2. **Test in development** first
3. The nullable fields are **temporary** - we'll make them required after data migration
4. Old fields (if they exist) will be removed in a later migration

## 🎯 Next Steps After Initial Migration

1. Create a data migration file to populate new fields
2. Run the data migration
3. Create final migration to make fields non-nullable and remove old fields

