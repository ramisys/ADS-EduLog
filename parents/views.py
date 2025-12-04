import json
from datetime import date

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from core.models import (
    ParentProfile,
    StudentProfile,
    Grade,
    Attendance,
    Notification,
    Subject,
    Assessment,
    AssessmentScore,
)

@login_required
def dashboard(request):
    # Ensure user is a parent
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get all children (students) of this parent
    children = StudentProfile.objects.filter(parent=parent_profile)
    
    # Get grades for all children (recent)
    children_grades = (
        Grade.objects
        .filter(student__in=children)
        .select_related('student', 'subject')
        .order_by('-id')[:10]
    )
    
    # Get attendance for all children (recent)
    children_attendance = (
        Attendance.objects
        .filter(student__in=children)
        .select_related('student', 'subject')
        .order_by('-date')[:10]
    )
    
    # Get unread notifications (for alerts widget)
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    alerts_count = notifications.count()
    
    # Statistics for each child
    children_stats = []
    for child in children:
        child_grades = Grade.objects.filter(student=child)
        child_avg = child_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        
        child_attendance = Attendance.objects.filter(student=child)
        present_count = child_attendance.filter(status='present').count()
        absent_count = child_attendance.filter(status='absent').count()
        late_count = child_attendance.filter(status='late').count()
        total_attendance = child_attendance.count()
        attendance_percentage = (
            (present_count / total_attendance) * 100
            if total_attendance > 0 else 0
        )
        
        children_stats.append({
            'child': child,
            'average_grade': round(child_avg, 2),
            'grades_count': child_grades.count(),
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'attendance_percentage': round(attendance_percentage, 1),
            'total_attendance': total_attendance,
        })
    
    # Overall statistics across all children
    all_grades = Grade.objects.filter(student__in=children)
    overall_avg_value = all_grades.aggregate(avg_grade=Avg('grade'))['avg_grade']
    has_grade_data = overall_avg_value is not None
    overall_avg = round(float(overall_avg_value), 2) if has_grade_data else None
    
    # Grade distribution (A/B/C/D as percentages)
    total_grades = all_grades.count()
    if total_grades > 0:
        a_count = all_grades.filter(grade__gte=90).count()
        b_count = all_grades.filter(grade__gte=80, grade__lt=90).count()
        c_count = all_grades.filter(grade__gte=70, grade__lt=80).count()
        d_count = all_grades.filter(grade__lt=70).count()
        
        grade_a_percent = round((a_count / total_grades) * 100, 1)
        grade_b_percent = round((b_count / total_grades) * 100, 1)
        grade_c_percent = round((c_count / total_grades) * 100, 1)
        grade_d_percent = round((d_count / total_grades) * 100, 1)
    else:
        a_count = b_count = c_count = d_count = 0
        grade_a_percent = grade_b_percent = grade_c_percent = grade_d_percent = 0
    
    all_attendance = Attendance.objects.filter(student__in=children)
    total_present = all_attendance.filter(status='present').count()
    total_absent = all_attendance.filter(status='absent').count()
    total_late = all_attendance.filter(status='late').count()
    total_attendance_overall = total_present + total_absent + total_late
    has_attendance_data = total_attendance_overall > 0
    overall_attendance_percentage = (
        round((total_present / total_attendance_overall) * 100, 1)
        if has_attendance_data else None
    )

    # Overall progress for the progress bar (use average grade as %)
    overall_progress = round(float(overall_avg_value), 1) if has_grade_data else 0
    progress_display = overall_progress if has_grade_data else 89
    progress_width = progress_display
    progress_status_text = "On track for semester goals"
    progress_alert_text = "Great progress! Improved in 4 out of 6 subjects."

    # Number of distinct subjects across all children
    subjects_count = (
        all_grades.values('subject')
        .distinct()
        .count()
        if children.exists() else 0
    )

    # Build month labels for last six months
    month_pointer = timezone.now().date().replace(day=1)
    month_starts = []
    for _ in range(6):
        month_starts.append(month_pointer)
        if month_pointer.month == 1:
            month_pointer = month_pointer.replace(year=month_pointer.year - 1, month=12)
        else:
            month_pointer = month_pointer.replace(month=month_pointer.month - 1)
    month_starts.reverse()

    attendance_map = {}
    if children.exists():
        attendance_qs = (
            Attendance.objects
            .filter(student__in=children, date__gte=month_starts[0])
            .annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(
                total=Count('id'),
                present=Count('id', filter=Q(status='present'))
            )
            .order_by('month')
        )
        attendance_map = {
            entry['month'].strftime('%Y-%m'): entry
            for entry in attendance_qs
        }

    month_labels = []
    attendance_rates = []
    for start_date in month_starts:
        month_key = start_date.strftime('%Y-%m')
        month_label = start_date.strftime('%b')
        summary = attendance_map.get(month_key)
        if summary:
            total = summary['total']
            present = summary['present']
        else:
            total = present = 0
        rate = round((present / total) * 100, 1) if total else 0
        month_labels.append(month_label)
        attendance_rates.append(rate)

    # Subject performance data for charts
    subject_avg_qs = (
        all_grades
        .values('subject__name')
        .annotate(avg_grade=Avg('grade'))
        .order_by('subject__name')
    )

    subject_labels = []
    subject_values = []
    for item in subject_avg_qs:
        subject_name = item['subject__name'] or 'Subject'
        subject_labels.append(subject_name)
        subject_values.append(round(float(item['avg_grade']), 2) if item['avg_grade'] is not None else 0)

    subject_term_qs = (
        all_grades
        .values('subject__name', 'term')
        .annotate(avg_grade=Avg('grade'))
    )

    subject_term_map = {}
    terms_present = set()
    for entry in subject_term_qs:
        subject_name = entry['subject__name'] or 'Subject'
        term_name = entry['term'] or 'Term'
        subject_term_map.setdefault(subject_name, {})[term_name] = round(float(entry['avg_grade']), 2)
        terms_present.add(term_name)

    term_hierarchy = ['Midterm', 'Final']
    term_rank = {term: idx for idx, term in enumerate(term_hierarchy, start=1)}

    if terms_present:
        sorted_terms_global = sorted(terms_present, key=lambda term: term_rank.get(term, len(term_rank) + 1))
        if len(sorted_terms_global) == 1:
            current_term_label = sorted_terms_global[0]
            previous_term_label = 'Previous Term'
        else:
            previous_term_label = sorted_terms_global[-2]
            current_term_label = sorted_terms_global[-1]
    else:
        current_term_label = 'Current Term'
        previous_term_label = 'Previous Term'

    subject_prev_values = []
    subject_current_values = []

    for subject_name in subject_labels:
        term_values = subject_term_map.get(subject_name, {})
        if term_values:
            sorted_terms_local = sorted(
                term_values.items(),
                key=lambda kv: term_rank.get(kv[0], len(term_rank) + 1)
            )
            current_value = sorted_terms_local[-1][1]
            previous_value = (
                sorted_terms_local[-2][1]
                if len(sorted_terms_local) >= 2
                else sorted_terms_local[-1][1]
            )
        else:
            current_value = 0
            previous_value = 0

        subject_current_values.append(current_value)
        subject_prev_values.append(previous_value)

    # Default "selected" child for the dashboard widgets (first child if any)
    selected_child_stats = children_stats[0] if children_stats else None
    
    grade_buckets = [
        {'label': 'Excellent (90-100)', 'count': a_count, 'color': '#10b981', 'css_class': 'legend-excellent'},
        {'label': 'Good (80-89)', 'count': b_count, 'color': '#3b82f6', 'css_class': 'legend-good'},
        {'label': 'Average (70-79)', 'count': c_count, 'color': '#f59e0b', 'css_class': 'legend-average'},
        {'label': 'Needs Improvement (<70)', 'count': d_count, 'color': '#ef4444', 'css_class': 'legend-needs'},
    ]

    context = {
        'parent_profile': parent_profile,
        'children': children,
        'children_grades': children_grades,
        'children_attendance': children_attendance,
        'notifications': notifications,
        'children_stats': children_stats,
        'selected_child_stats': selected_child_stats,
        'overall_avg': overall_avg,
        'total_present': total_present,
        'total_absent': total_absent,
        'total_late': total_late,
        'overall_attendance_percentage': overall_attendance_percentage,
        'alerts_count': alerts_count,
        'grade_a_percent': grade_a_percent,
        'grade_b_percent': grade_b_percent,
        'grade_c_percent': grade_c_percent,
        'grade_d_percent': grade_d_percent,
        'overall_progress': overall_progress,
        'progress_width': progress_width,
        'progress_display': progress_display,
        'progress_status_text': progress_status_text,
        'progress_alert_text': progress_alert_text,
        'subjects_count': subjects_count,
        'has_grade_data': has_grade_data,
        'has_attendance_data': has_attendance_data,
        'attendance_chart_labels': json.dumps(month_labels),
        'attendance_chart_data': json.dumps(attendance_rates),
        'subject_chart_labels': json.dumps(subject_labels),
        'subject_chart_data': json.dumps(subject_values),
        'subject_prev_term_data': json.dumps(subject_prev_values),
        'subject_current_term_data': json.dumps(subject_current_values),
        'subject_prev_term_label': previous_term_label,
        'subject_current_term_label': current_term_label,
        'grade_distribution_data': json.dumps([
            a_count,
            b_count,
            c_count,
            d_count,
        ]),
        'grade_buckets': grade_buckets,
        'grade_labels_json': json.dumps([bucket['label'] for bucket in grade_buckets]),
        'grade_colors_json': json.dumps([bucket['color'] for bucket in grade_buckets]),
    }
    
    return render(request, 'parents/dashboard.html', context)


@login_required
def child_subjects(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get child_id from query parameters
    child_id = request.GET.get('child_id')
    
    # Get all children for the parent
    all_children = (
        StudentProfile.objects
        .filter(parent=parent_profile)
        .select_related('user', 'section')
    )
    
    # If child_id is provided, filter to that child only
    if child_id:
        try:
            children = all_children.filter(id=child_id)
            if not children.exists():
                # If invalid child_id, redirect to show first child or all
                children = all_children[:1] if all_children.exists() else all_children
        except (ValueError, StudentProfile.DoesNotExist):
            children = all_children[:1] if all_children.exists() else all_children
    else:
        # If no child_id, show first child by default
        children = all_children[:1] if all_children.exists() else all_children

    # Process subjects for the selected child(ren) - should be only one now
    children_subjects = []
    for child in children:
        subjects_qs = Subject.objects.filter(section=child.section).select_related('teacher__user')

        subject_cards = []
        for subject in subjects_qs:
            avg_grade = (
                Grade.objects
                .filter(student=child, subject=subject)
                .aggregate(avg_value=Avg('grade'))['avg_value']
            )
            avg_grade = round(float(avg_grade), 2) if avg_grade is not None else None

            attendance_qs = Attendance.objects.filter(student=child, subject=subject)
            total_attendance = attendance_qs.count()
            present_attendance = attendance_qs.filter(status='present').count()
            attendance_rate = (
                round((present_attendance / total_attendance) * 100, 1)
                if total_attendance > 0 else None
            )

            total_assessments = Assessment.objects.filter(subject=subject).count()
            completed_assessments = AssessmentScore.objects.filter(
                student=child,
                assessment__subject=subject
            ).count()

            assignment_summary = (
                f"{completed_assessments}/{total_assessments} completed"
                if total_assessments > 0 else "No assessments yet"
            )

            teacher_name = subject.teacher.user.get_full_name() if subject.teacher and subject.teacher.user else "N/A"
            teacher_email = subject.teacher.user.email if subject.teacher and subject.teacher.user else ""

            subject_cards.append({
                'subject': subject,
                'avg_grade': avg_grade,
                'attendance_rate': attendance_rate,
                'assignment_summary': assignment_summary,
                'teacher_name': teacher_name,
                'teacher_email': teacher_email,
            })

        children_subjects.append({
            'child': child,
            'subjects': subject_cards,
        })

    context = {
        'page_title': 'Child Subjects',
        'page_description': 'View all subjects your children are enrolled in.',
        'children_subjects': children_subjects,
        'all_children': all_children,  # For dropdown if needed
        'selected_child_id': child_id,
    }
    return render(request, 'parents/child_subjects.html', context)


@login_required
def attendance(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get child_id from query parameters
    child_id = request.GET.get('child_id')
    
    # Get all children for the parent
    all_children = (
        StudentProfile.objects
        .filter(parent=parent_profile)
        .select_related('user', 'section')
    )
    
    # If child_id is provided, filter to that child only
    if child_id:
        try:
            child = all_children.filter(id=child_id).first()
            if not child:
                # If invalid child_id, use first child if available
                child = all_children.first()
        except (ValueError, StudentProfile.DoesNotExist):
            child = all_children.first()
    else:
        # If no child_id, show first child by default
        child = all_children.first()

    # Get attendance data for the selected child
    attendance_data = None
    subject_attendance = []
    recent_attendance = []
    
    if child:
        
        # Overall attendance statistics
        all_attendance = Attendance.objects.filter(student=child)
        present_count = all_attendance.filter(status='present').count()
        absent_count = all_attendance.filter(status='absent').count()
        late_count = all_attendance.filter(status='late').count()
        total_count = all_attendance.count()
        
        overall_rate = (
            round((present_count / total_count) * 100, 1)
            if total_count > 0 else 0
        )
        
        attendance_data = {
            'child': child,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'overall_rate': overall_rate,
        }
        
        # Subject-wise attendance
        subjects_qs = Subject.objects.filter(section=child.section).select_related('teacher__user')
        
        for subject in subjects_qs:
            subject_attendance_qs = Attendance.objects.filter(student=child, subject=subject)
            subject_total = subject_attendance_qs.count()
            subject_present = subject_attendance_qs.filter(status='present').count()
            subject_rate = (
                round((subject_present / subject_total) * 100, 1)
                if subject_total > 0 else 0
            )
            
            teacher_name = subject.teacher.user.get_full_name() if subject.teacher and subject.teacher.user else "N/A"
            
            subject_attendance.append({
                'subject': subject,
                'teacher_name': teacher_name,
                'rate': subject_rate,
                'total': subject_total,
                'present': subject_present,
            })
        
        # Recent attendance records (last 20)
        recent_attendance = (
            Attendance.objects
            .filter(student=child)
            .select_related('subject', 'subject__teacher__user')
            .order_by('-date')[:20]
        )

    context = {
        'page_title': 'Attendance',
        'page_description': 'View attendance records for your child.',
        'attendance_data': attendance_data,
        'subject_attendance': subject_attendance,
        'recent_attendance': recent_attendance,
        'all_children': all_children,
        'selected_child_id': child_id,
    }
    return render(request, 'parents/attendance.html', context)


@login_required
def grades(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get child_id from query parameters
    child_id = request.GET.get('child_id')
    
    # Get all children for the parent
    all_children = (
        StudentProfile.objects
        .filter(parent=parent_profile)
        .select_related('user', 'section')
    )
    
    # If child_id is provided, filter to that child only
    if child_id:
        try:
            child = all_children.filter(id=child_id).first()
            if not child:
                # If invalid child_id, use first child if available
                child = all_children.first()
        except (ValueError, StudentProfile.DoesNotExist):
            child = all_children.first()
    else:
        # If no child_id, show first child by default
        child = all_children.first()

    # Get grade data for the selected child
    subject_grades = []
    detailed_grades = []
    
    if child:
        # Get subject-wise average grades
        subjects_qs = Subject.objects.filter(section=child.section).select_related('teacher__user')
        
        for subject in subjects_qs:
            # Get average grade for this subject (across all terms or latest term)
            grade_qs = Grade.objects.filter(student=child, subject=subject)
            avg_grade = grade_qs.aggregate(avg_value=Avg('grade'))['avg_value']
            
            # Get latest term grade
            latest_grade = grade_qs.order_by('-term').first()
            
            if avg_grade is not None:
                avg_grade = round(float(avg_grade), 2)
            else:
                avg_grade = None
            
            teacher_name = subject.teacher.user.get_full_name() if subject.teacher and subject.teacher.user else "N/A"
            
            subject_grades.append({
                'subject': subject,
                'teacher_name': teacher_name,
                'avg_grade': avg_grade,
                'latest_grade': latest_grade.grade if latest_grade else None,
                'latest_term': latest_grade.term if latest_grade else None,
            })
        
        # Get detailed assessment scores
        assessment_scores = (
            AssessmentScore.objects
            .filter(student=child)
            .select_related('assessment', 'assessment__subject', 'assessment__subject__teacher__user', 'recorded_by__user')
            .order_by('-assessment__date', '-created_at')[:50]
        )
        
        for score in assessment_scores:
            assessment = score.assessment
            percentage = round(float(score.percentage), 2) if score.percentage else 0
            
            teacher_name = "N/A"
            if assessment.subject.teacher and assessment.subject.teacher.user:
                teacher_name = assessment.subject.teacher.user.get_full_name()
            elif score.recorded_by and score.recorded_by.user:
                teacher_name = score.recorded_by.user.get_full_name()
            
            detailed_grades.append({
                'assessment': assessment,
                'score': score.score,
                'max_score': assessment.max_score,
                'percentage': percentage,
                'date': assessment.date,
                'subject': assessment.subject,
                'teacher_name': teacher_name,
                'category': assessment.category,
                'term': assessment.term,
            })

    context = {
        'page_title': 'Grades',
        'page_description': 'View grades and academic performance for your child.',
        'subject_grades': subject_grades,
        'detailed_grades': detailed_grades,
        'all_children': all_children,
        'selected_child_id': child_id,
        'child': child,
    }
    return render(request, 'parents/grades.html', context)


@login_required
def reports(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get child_id from query parameters
    child_id = request.GET.get('child_id')
    
    # Get all children for the parent
    all_children = (
        StudentProfile.objects
        .filter(parent=parent_profile)
        .select_related('user', 'section')
    )
    
    # If child_id is provided, filter to that child only
    if child_id:
        try:
            child = all_children.filter(id=child_id).first()
            if not child:
                # If invalid child_id, use first child if available
                child = all_children.first()
        except (ValueError, StudentProfile.DoesNotExist):
            child = all_children.first()
    else:
        # If no child_id, show first child by default
        child = all_children.first()

    # Get performance data for the selected child
    overall_gpa = None
    overall_attendance = None
    avg_grade = None
    subjects_count = 0
    subject_performance = []
    concern_subjects = []
    
    if child:
        # Calculate overall GPA (average of all grades)
        all_grades = Grade.objects.filter(student=child)
        if all_grades.exists():
            avg_grade_value = all_grades.aggregate(avg_value=Avg('grade'))['avg_value']
            if avg_grade_value:
                avg_grade = round(float(avg_grade_value), 2)
                # Convert to GPA scale (assuming 100-point scale, convert to 4.0 scale)
                overall_gpa = round((avg_grade / 100) * 4.0, 2)
        
        # Calculate overall attendance
        all_attendance = Attendance.objects.filter(student=child)
        total_attendance = all_attendance.count()
        present_count = all_attendance.filter(status='present').count()
        if total_attendance > 0:
            overall_attendance = round((present_count / total_attendance) * 100, 1)
        
        # Get subject-wise performance
        subjects_qs = Subject.objects.filter(section=child.section).select_related('teacher__user')
        subjects_count = subjects_qs.count()
        
        for subject in subjects_qs:
            # Get grade for this subject
            subject_grades = Grade.objects.filter(student=child, subject=subject)
            subject_avg_grade = None
            if subject_grades.exists():
                avg = subject_grades.aggregate(avg_value=Avg('grade'))['avg_value']
                if avg:
                    subject_avg_grade = round(float(avg), 2)
            
            # Get attendance for this subject
            subject_attendance_qs = Attendance.objects.filter(student=child, subject=subject)
            subject_total = subject_attendance_qs.count()
            subject_present = subject_attendance_qs.filter(status='present').count()
            subject_attendance_rate = None
            if subject_total > 0:
                subject_attendance_rate = round((subject_present / subject_total) * 100, 1)
            
            teacher_name = subject.teacher.user.get_full_name() if subject.teacher and subject.teacher.user else "N/A"
            teacher_email = subject.teacher.user.email if subject.teacher and subject.teacher.user else ""
            
            # Calculate improvement (compare latest term with previous term if available)
            improvement = None
            if subject_grades.count() >= 2:
                latest_grade = subject_grades.order_by('-term').first()
                previous_grade = subject_grades.order_by('-term')[1] if subject_grades.count() > 1 else None
                if latest_grade and previous_grade:
                    improvement = round(float(latest_grade.grade) - float(previous_grade.grade), 2)
            
            subject_performance.append({
                'subject': subject,
                'grade': subject_avg_grade,
                'attendance': subject_attendance_rate,
                'teacher_name': teacher_name,
                'teacher_email': teacher_email,
                'improvement': improvement,
            })
            
            # Check if this subject needs attention
            if (subject_avg_grade and subject_avg_grade < 80) or (subject_attendance_rate and subject_attendance_rate < 75):
                concern_subjects.append({
                    'subject': subject,
                    'grade': subject_avg_grade,
                    'attendance': subject_attendance_rate,
                    'teacher_name': teacher_name,
                    'teacher_email': teacher_email,
                })
        
        # Generate historical performance reports (by term)
        historical_reports = []
        terms = Grade.objects.filter(student=child).values_list('term', flat=True).distinct().order_by('-term')
        
        for term in terms:
            # Get grades for this term
            term_grades = Grade.objects.filter(student=child, term=term)
            term_avg = term_grades.aggregate(avg_value=Avg('grade'))['avg_value']
            term_gpa = None
            if term_avg:
                term_gpa = round((float(term_avg) / 100) * 4.0, 2)
            
            # Get attendance for this term period (approximate - using all attendance)
            # In a real system, you'd filter by date range for the term
            term_attendance_rate = overall_attendance  # Using overall for now
            
            # Determine period (semester/year)
            from datetime import datetime
            current_year = datetime.now().year
            period = f"{term} {current_year}"
            
            historical_reports.append({
                'term': term,
                'period': period,
                'date_issued': datetime.now().date(),  # In real system, use actual report date
                'overall_gpa': term_gpa,
                'attendance': term_attendance_rate or 0,
            })

    context = {
        'page_title': 'Performance Reports',
        'page_description': 'Generate and view comprehensive performance reports for your child.',
        'child': child,
        'all_children': all_children,
        'selected_child_id': child_id,
        'overall_gpa': overall_gpa,
        'overall_attendance': overall_attendance,
        'avg_grade': avg_grade,
        'subjects_count': subjects_count,
        'subject_performance': subject_performance,
        'concern_subjects': concern_subjects,
        'has_concern_subjects': len(concern_subjects) > 0,
        'historical_reports': historical_reports,
    }
    return render(request, 'parents/reports.html', context)


@login_required
def notifications(request):
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    try:
        parent_profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return redirect('dashboard')
    
    # Get all notifications for the parent
    all_notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Handle mark as read
    if request.method == 'POST' and 'mark_read' in request.POST:
        notification_id = request.POST.get('mark_read')
        try:
            notification = Notification.objects.get(id=notification_id, recipient=request.user)
            notification.is_read = True
            notification.save()
            return redirect('parents:notifications')
        except Notification.DoesNotExist:
            pass
    
    # Handle mark all as read
    if request.method == 'POST' and 'mark_all_read' in request.POST:
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return redirect('parents:notifications')
    
    unread_count = all_notifications.filter(is_read=False).count()
    
    context = {
        'page_title': 'Notifications',
        'page_description': 'View and manage all your notifications and alerts.',
        'notifications': all_notifications,
        'unread_count': unread_count,
    }
    return render(request, 'parents/notifications.html', context)