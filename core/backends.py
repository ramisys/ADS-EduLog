from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class PlainTextPasswordBackend(ModelBackend):
    """
    Custom authentication backend that handles both hashed and plain text passwords.
    This allows Django admin to work with users who have plain text passwords.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username')
        if username is None or password is None:
            return None
        
        # Try to get user by username first
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # If username doesn't work, try email (for Django admin compatibility)
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                # Run the default password hasher once to reduce the timing
                # difference between an existing and a non-existing user
                User().set_password(password)
                return None
        
        # First try Django's standard password check (for hashed passwords)
        if user.check_password(password):
            return user if self.user_can_authenticate(user) else None
        
        # If check_password fails, check if password is stored as plain text
        stored_password = user.password
        if not stored_password.startswith('pbkdf2_') and not stored_password.startswith('bcrypt$') and not stored_password.startswith('argon2'):
            # Password appears to be stored as plain text
            if stored_password == password:
                # Password matches plain text, hash it and save for future use
                user.set_password(password)
                user.save()
                return user if self.user_can_authenticate(user) else None
        
        return None

