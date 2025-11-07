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