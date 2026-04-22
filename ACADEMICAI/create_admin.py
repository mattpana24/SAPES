from auth import register_user

success, message = register_user("admin", "admin123", "admin")
print(message)