# EduLog - Educational Management System

EduLog is a comprehensive educational management system designed to streamline student attendance tracking, grade management, and performance monitoring. It provides separate dashboards for students, teachers, and parents, enabling real-time access to academic information.

## 📋 Table of Contents

- [Features](#features)
- [Technologies Used](#technologies-used)
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
- [Semester Management](#semester-management)
- [Assessment System](#assessment-system)
- [Feedback System](#feedback-system)
- [Project Structure](#project-structure)
- [User Roles](#user-roles)
- [Security Notes](#security-notes)
- [Troubleshooting](#troubleshooting)
- [Additional Notes](#additional-notes)
- [Contributing](#contributing)
- [License](#license)
- [Authors](#authors)

## ✨ Features

### For Students
- **Personal Dashboard**: View grades, attendance, and academic performance
- **Grade Tracking**: See grades by subject with term-wise breakdown
- **Attendance Monitoring**: Track attendance status (Present, Absent, Late) with statistics
- **Subject Information**: View all enrolled subjects
- **Notifications**: Receive important updates and announcements

### For Teachers
- **Teaching Dashboard**: Manage subjects, classes, and student records
- **Subject Management**: View and manage assigned subjects
- **Student Enrollment**: Enroll students in your subject offerings
- **Attendance Recording**: Track student attendance for your subjects
- **Grade Management**: Record and view student grades
- **Assessment Management**: Create and manage assessments (Activities, Quizzes, Projects, Exams)
- **Assessment Scoring**: Record student scores for assessments with automatic grade calculation
- **Category Weights**: Configure weight percentages for different assessment categories
- **Class Adviser**: Manage advised sections/classes
- **Performance Analytics**: View average grades and attendance statistics
- **Notifications**: Receive and send important notifications

### For Parents
- **Parent Dashboard**: Monitor children's academic progress
- **Multi-Child Support**: View information for all registered children
- **Grade Tracking**: See grades for all children with subject-wise breakdown
- **Attendance Monitoring**: Track attendance for all children
- **Performance Overview**: View overall statistics and attendance rates
- **Notifications**: Stay informed about children's academic activities

### General Features
- **Role-Based Access Control**: Separate dashboards and permissions for each user type
- **Secure Authentication**: Custom authentication system with role-based login
- **Password Recovery**: Forgot password functionality for account recovery
- **Semester Management**: Comprehensive semester system with status tracking (Upcoming, Active, Closed, Archived)
- **Student Enrollment**: Students enroll in subject offerings per semester
- **Assessment System**: Create assessments with categories (Activities, Quizzes, Projects, Exams) and terms (Midterm, Final)
- **Grade Calculation**: Automatic grade calculation based on assessment scores and category weights
- **Feedback System**: Submit feedback, bug reports, feature requests, and improvement suggestions
- **Audit Logging**: Track system changes and user actions
- **Auto-Dismissing Alerts**: User-friendly notification system
- **Responsive Design**: Modern, mobile-friendly interface
- **Custom ID Generation**: Automatic generation of Student, Teacher, and Parent IDs
- **Year Level Normalization**: Normalized year level management for better data integrity

## 🛠 Technologies Used

- **Backend**: Django 5.2.8
- **Database**: SQLite (default, can be configured for PostgreSQL/MySQL)
- **Frontend**: Bootstrap 5.3.0, Bootstrap Icons
- **Python**: 3.x
- **Other**: python-dotenv (for environment variables)

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd ADS-EduLog
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## ⚙️ Setup

### Step 1: Create Environment File

Create a `.env` file in the project root directory:

```env
DJANGO_SECRET_KEY=your-secret-key-here
```

Generate a secret key by running:

```bash
python generate_secret_key.py
```

This will output a secret key that you can copy and paste into your `.env` file.

### Step 2: Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 3: Create Superuser (Admin)

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account.

### Step 4: Run the Development Server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

### Step 5: Seed Database (Optional)

To populate the database with sample data for testing, run the seed script:

```bash
python seed_data.py
```

This script will generate:
- **10 Teachers** - Each teacher is assigned to multiple sections and subjects
- **5 Parents** - Each parent has at least one student
- **120 Students** - Distributed across different sections
- **6 Sections** - BSIT 1A, BSIT 1B, BSIT 2A, BSIT 2B, BSIT 3A, BSIT 3B
- **18 Subjects** - 3 subjects per section, with teachers assigned across multiple sections

**Note**: The seed script will clear existing data before generating new data. All generated users have default passwords:
- Teachers: `TeacherPass123`
- Students: `StudentPass123`
- Parents: `ParentPass123`

**Login Credentials**:
- Teachers: `teacher1`, `teacher2`, etc. (or use Teacher ID)
- Students: `student1`, `student2`, etc. (or use Student ID)
- Parents: `parent1`, `parent2`, etc. (use email to login)

## 📖 Usage

### Accessing the Application

1. **Home Page**: Navigate to `http://127.0.0.1:8000/`
2. **Login Page**: Click "Login" or go to `http://127.0.0.1:8000/login/`
3. **Sign Up**: Click "Sign Up" to create a new account

### Creating Accounts

#### For Students

1. Go to the Sign Up page
2. Select "Student" role
3. Fill in the required information:
   - Username
   - Email
   - Password
   - First Name
   - Last Name
   - Course
   - Year Level
   - Section (optional)
4. Click "Sign Up"
5. Student ID will be automatically generated (format: `STD-YYYY-XXXXX`)

#### For Teachers

1. Go to the Sign Up page
2. Select "Teacher" role
3. Fill in the required information:
   - Username
   - Email
   - Password
   - First Name
   - Last Name
   - Department
4. Click "Sign Up"
5. Teacher ID will be automatically generated (format: `TCH-YYYY-XXXXX`)

#### For Parents

1. Go to the Sign Up page
2. Select "Parent" role
3. Fill in the required information:
   - Username
   - Email
   - Password
   - First Name
   - Last Name
   - Contact Number
4. Click "Sign Up"
5. Parent ID will be automatically generated (format: `PRT-YYYY-XXXXX`)

### Logging In

#### Students and Teachers

You can log in using:
- Username
- Email
- Student ID / Teacher ID (e.g., `STD-2025-00001`, `TCH-2025-00001`)

#### Parents

You can log in using:
- Email

### Password Recovery

If you forget your password:

1. Go to the Login page
2. Click "Forgot Password?" link
3. Enter your email address
4. Follow the instructions sent to your email to reset your password

**Note**: Password recovery is available for all user types (Students, Teachers, Parents).

### Using the Dashboards

#### Student Dashboard

After logging in as a student, you can:

1. **View Statistics**:
   - Average Grade
   - Attendance Rate (percentage)
   - Number of Subjects
   - Unread Notifications

2. **View Grades**:
   - Recent grades in all subjects
   - Grades by subject with term-wise breakdown (Midterm, Final)
   - Subject averages
   - Assessment scores and breakdowns

3. **View Attendance**:
   - Recent attendance records
   - Attendance statistics (Present, Absent, Late)
   - Attendance percentage

4. **View Subjects**:
   - View all enrolled subjects
   - Subject details and information

5. **View Notifications**:
   - See unread notifications
   - Stay updated with important information

6. **Submit Feedback**:
   - Submit feedback, bug reports, or feature requests
   - Rate the system (1-5 stars)
   - Submit anonymously if desired

#### Teacher Dashboard

After logging in as a teacher, you can:

1. **View Statistics**:
   - Number of subjects taught
   - Total students
   - Average grade across all subjects
   - Unread notifications

2. **Manage Subjects**:
   - View all assigned subjects
   - Assign subjects to sections
   - See sections for each subject
   - View subject statistics

3. **Student Enrollment**:
   - Enroll students in your subject offerings
   - View enrolled students per subject
   - Manage student enrollments

4. **Manage Assessments**:
   - Create assessments (Activities, Quizzes, Projects, Exams)
   - Set assessment dates and maximum scores
   - Organize by term (Midterm, Final)
   - Record student scores for assessments

5. **Category Weights**:
   - Configure weight percentages for assessment categories
   - Set custom weights per subject offering
   - Automatic grade calculation based on weights

6. **Manage Classes**:
   - View advised sections (if class adviser)
   - See student counts per section

7. **View Attendance**:
   - Recent attendance records for your subjects
   - Attendance overview (Present, Absent, Late counts)
   - Record attendance for enrolled students

8. **View Grades**:
   - Grade statistics for your subjects
   - Average grades per subject
   - View individual student grades and assessment scores

9. **Submit Feedback**:
   - Submit feedback, bug reports, or feature requests
   - Rate the system (1-5 stars)

#### Parent Dashboard

After logging in as a parent, you can:

1. **View Statistics**:
   - Number of children
   - Overall average grade
   - Total present days
   - Unread notifications

2. **Monitor Children**:
   - View all registered children
   - See individual statistics for each child:
     - Average grade
     - Attendance rate
     - Present/Absent/Late counts

3. **View Grades**:
   - Recent grades for all children
   - Subject-wise grade information

4. **View Attendance**:
   - Recent attendance records for all children
   - Overall attendance statistics

5. **Submit Feedback**:
   - Submit feedback about the system
   - Rate the system (1-5 stars)
   - Submit anonymously if desired

### Admin Panel

Access the Django admin panel at `http://127.0.0.1:8000/admin/` using your superuser credentials to:

- Manage users (Students, Teachers, Parents)
- Create and manage subjects
- Create and manage class sections
- Manage semesters (create, activate, close, archive)
- Manage year levels
- Record attendance
- Record grades
- Manage assessments and assessment scores
- Configure category weights
- Manage student enrollments
- Send notifications
- View and respond to feedback
- View audit logs
- Manage all database records

### Semester Management

The system includes comprehensive semester management:

- **Create Semesters**: Set up new academic semesters with start/end dates
- **Semester Status**: Track semester status (Upcoming, Active, Closed, Archived)
- **Current Semester**: Mark one semester as current for active operations
- **Status Transitions**: Enforce proper status transitions (Upcoming → Active → Closed → Archived)
- **Data Protection**: Prevent modifications to closed/archived semesters
- **Semester-Scoped Data**: All academic data (enrollments, attendance, grades, assessments) is tied to specific semesters

Access semester management through the admin panel or dedicated management interface.

### Assessment System

Teachers can create and manage assessments:

- **Assessment Categories**: Activities, Quizzes, Projects, Exams
- **Terms**: Organize assessments by Midterm or Final term
- **Scoring**: Record student scores with automatic percentage calculation
- **Grade Calculation**: Automatic grade calculation based on category weights
- **Flexible Weights**: Configure custom weight percentages per subject offering

### Feedback System

All users can submit feedback:

- **Feedback Types**: General Feedback, Bug Report, Feature Request, Improvement Suggestion, Compliment
- **Rating System**: Rate the system from 1-5 stars
- **Anonymous Option**: Submit feedback anonymously
- **Admin Response**: Admins can view and respond to feedback
- **Feedback Management**: Track read/unread status and archive old feedback

## 📁 Project Structure

```
ADS-EduLog/
│
├── core/                   # Core application
│   ├── models.py          # Database models (User, StudentProfile, TeacherProfile, Semester, Assessment, Feedback, etc.)
│   ├── views.py           # Core views (login, signup, dashboard routing, semester management, feedback)
│   ├── urls.py            # Core URL routing
│   ├── admin.py           # Admin configuration
│   ├── backends.py        # Custom authentication backend
│   ├── middleware.py      # Custom middleware
│   ├── notifications.py   # Notification utilities
│   ├── permissions.py     # Permission utilities
│   ├── db_functions.py    # Database utility functions
│   ├── templates/         # Core templates (base, login, signup, feedback, semester management, etc.)
│   ├── static/            # Static files (CSS, JS, images)
│   └── management/        # Custom management commands
│       └── commands/      # Django management commands
│
├── students/              # Student application
│   ├── views.py           # Student dashboard view
│   ├── urls.py            # Student URL routing
│   └── templates/         # Student templates
│
├── teachers/              # Teacher application
│   ├── views.py           # Teacher dashboard views (subjects, students, attendance, grades, assessments)
│   ├── urls.py            # Teacher URL routing
│   ├── forms.py           # Teacher forms
│   ├── models.py          # Teacher-specific models (if any)
│   └── templates/         # Teacher templates (dashboard, subjects, students, attendance, grades, assessments, etc.)
│
├── parents/               # Parent application
│   ├── views.py           # Parent dashboard view
│   ├── urls.py            # Parent URL routing
│   └── templates/         # Parent templates
│
├── edulog/                # Django project settings
│   ├── settings.py        # Project settings
│   ├── urls.py            # Main URL configuration
│   └── wsgi.py            # WSGI configuration
│
├── manage.py              # Django management script
├── seed_data.py           # Database seeding script for test data
├── generate_secret_key.py # Script to generate Django secret key
├── db.sqlite3             # SQLite database (created after migrations)
├── .env                   # Environment variables (create this)
└── README.md              # This file
```

## 👥 User Roles

### Student
- View personal grades and attendance
- View assessment scores and breakdowns
- Access subject information
- View enrolled subjects
- Receive notifications
- Submit feedback

### Teacher
- Manage subjects and classes
- Enroll students in subject offerings
- Create and manage assessments
- Record assessment scores
- Configure category weights
- Record attendance and grades
- View student performance
- Send notifications
- Submit feedback

### Parent
- Monitor children's academic progress
- View grades and attendance for all children
- View assessment scores for all children
- Receive notifications about children
- Submit feedback

### Admin
- Full access to admin panel
- Manage all users and data
- Manage semesters and year levels
- Manage subjects and class sections
- View and respond to feedback
- View audit logs
- System configuration

## 🔒 Security Notes

- **Secret Key**: Always keep your `DJANGO_SECRET_KEY` secure and never commit it to version control
- **Production**: Before deploying to production:
  - Set `DEBUG = False` in settings.py
  - Configure `ALLOWED_HOSTS`
  - Use a production database (PostgreSQL/MySQL)
  - Set up proper SSL/HTTPS
  - Use environment variables for sensitive data

## 🐛 Troubleshooting

### Common Issues

1. **Migration Errors**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Secret Key Error**:
   - Ensure `.env` file exists with `DJANGO_SECRET_KEY` set

3. **Template Not Found**:
   - Ensure all apps are added to `INSTALLED_APPS` in settings.py
   - Check that template directories are correctly structured

4. **Database Errors**:
   - Delete `db.sqlite3` and run migrations again (development only)
   - Ensure database permissions are correct

## 📝 Additional Notes

- **Custom ID Format**: IDs are automatically generated in the format `PREFIX-YYYY-XXXXX` (e.g., `STD-2025-00001`)
- **Password Storage**: The system supports both hashed and plain text passwords (for migration purposes)
- **Auto-Dismissing Alerts**: Alert messages on the login page automatically disappear after 5 seconds
- **Role-Based Redirects**: Users are automatically redirected to their role-specific dashboard after login
- **Database Seeding**: Use `seed_data.py` to quickly populate the database with test data for development and testing purposes
- **Semester-Based Operations**: All academic operations (enrollments, attendance, grades, assessments) are scoped to specific semesters
- **Assessment Categories**: Default category weights are Activities (20%), Quizzes (20%), Projects (30%), Exams (30%) - can be customized per subject
- **Grade Calculation**: Final grades are automatically calculated based on assessment scores and their category weights
- **Data Integrity**: The system enforces data integrity through foreign key relationships and validation rules
- **Audit Trail**: System changes are logged in the audit log for tracking and compliance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 👥 Authors

**ADS-EduLog Development Team**
- Fat, Ramcez James L.
- Cagadas, Earl Rusty M.
- Delmiguez, Ivan O.

This project is developed and maintained by the ADS-EduLog Development Team.

### Contributors

We welcome contributions from the community! If you'd like to contribute to this project, please see the [Contributing](#-contributing) section above.

## 🙏 Acknowledgments

- Django Framework
- Bootstrap for UI components
- Bootstrap Icons for icons

---

**Note**: This is a development version. For production deployment, ensure proper security measures are implemented.
