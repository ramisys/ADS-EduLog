from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(ParentProfile)
admin.site.register(StudentProfile)
admin.site.register(TeacherProfile)
admin.site.register(ClassSection)
admin.site.register(Subject)
admin.site.register(Attendance)
admin.site.register(Grade)
admin.site.register(Notification)
admin.site.register(TeacherSubjectAssignment)


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