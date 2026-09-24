from app.services import auth_service
import uuid

h = auth_service.hash_password("test123")
print("Verify correct:", auth_service.verify_password("test123", h))
print("Verify wrong:", auth_service.verify_password("wrong", h))

token = auth_service.create_access_token(uuid.uuid4(), "ADMIN")
print("Decoded:", auth_service.decode_access_token(token))