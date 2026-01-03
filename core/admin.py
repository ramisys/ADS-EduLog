from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import *


@admin.register(YearLevel)
class YearLevelAdmin(admin.ModelAdmin):
    list_display = ['level', 'name', 'order', 'is_active', 'section_count', 'student_count']
    list_filter = ['is_active', 'level']
    search_fields = ['name', 'level']
    ordering = ['order']
    readonly_fields = ['section_count', 'student_count']
    
    fieldsets = (
        ('Year Level Information', {
            'fields': ('level', 'name', 'order', 'is_active')
        }),
        ('Statistics', {
            'fields': ('section_count', 'student_count'),
            'classes': ('collapse',)
        }),
    )
    
    def section_count(self, obj):
        """Count sections for this year level"""
        return obj.sections.count()
    section_count.short_description = 'Sections'
    
    def student_count(self, obj):
        """Count students for this year level"""
        return obj.students.count()
    student_count.short_description = 'Students'


@admin.register(ClassSection)
class ClassSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'year_level', 'adviser', 'student_count']
    list_filter = ['year_level', 'adviser']
    search_fields = ['name', 'year_level__name']
    autocomplete_fields = ['adviser', 'year_level']
    
    fieldsets = (
        ('Section Information', {
            'fields': ('name', 'year_level', 'adviser')
        }),
    )
    
    def student_count(self, obj):
        """Count students in this section"""
        return obj.students.count()
    student_count.short_description = 'Students'


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'user', 'year_level', 'section', 'course', 'parent']
    list_filter = ['year_level', 'section', 'course']
    search_fields = ['student_id', 'user__username', 'user__first_name', 'user__last_name', 'user__email']
    autocomplete_fields = ['user', 'parent', 'year_level', 'section']
    readonly_fields = ['student_id']
    
    fieldsets = (
        ('Student Information', {
            'fields': ('user', 'student_id', 'parent', 'course')
        }),
        ('Academic Information', {
            'fields': ('year_level', 'section'),
            'description': 'Year level must match section\'s year level. If section is selected, year level will be auto-set.'
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-set year level from section if section is provided"""
        if obj.section and not obj.year_level:
            obj.year_level = obj.section.year_level
        super().save_model(request, obj, form, change)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    list_filter = ['role', 'is_active', 'is_staff']


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ['parent_id', 'user', 'contact_number']
    search_fields = ['parent_id', 'user__username', 'user__first_name', 'user__last_name', 'user__email', 'contact_number']


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['teacher_id', 'user', 'department']
    search_fields = ['teacher_id', 'user__username', 'user__first_name', 'user__last_name', 'user__email', 'department']
    list_filter = ['department']


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'start_date', 'end_date', 'status', 'is_current', 'created_at']
    list_filter = ['status', 'is_current', 'academic_year']
    search_fields = ['name', 'academic_year']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Semester Information', {
            'fields': ('name', 'academic_year', 'start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('status', 'is_current')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Override save to handle validation"""
        try:
            obj.full_clean()
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            from django.contrib import messages
            messages.error(request, f'Error saving semester: {"; ".join(e.messages)}')
            raise


admin.site.register(Subject)
admin.site.register(Attendance)
admin.site.register(Grade)
admin.site.register(Notification)
admin.site.register(TeacherSubjectAssignment)
admin.site.register(StudentEnrollment)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user_display', 'feedback_type', 'rating', 'subject', 'is_read', 'is_archived', 'created_at']
    list_filter = ['feedback_type', 'is_read', 'is_archived', 'rating', 'created_at']
    search_fields = ['subject', 'message', 'user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at', 'responded_at']
    list_per_page = 25
    
    fieldsets = (
        ('Feedback Information', {
            'fields': ('user', 'feedback_type', 'rating', 'subject', 'message', 'is_anonymous')
        }),
        ('Status', {
            'fields': ('is_read', 'is_archived')
        }),
        ('Admin Response', {
            'fields': ('admin_response', 'responded_by', 'responded_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_user_display(self, obj):
        if obj.is_anonymous:
            return 'Anonymous'
        return obj.user.get_full_name() if obj.user else 'Unknown'
    get_user_display.short_description = 'User'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'responded_by')