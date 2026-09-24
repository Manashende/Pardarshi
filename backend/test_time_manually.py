from app.config import settings
from app.services.time_verification import get_verified_time, is_acceptable_for_standard_unlock

result = get_verified_time(settings.ntp_server_list)
print("Level:", result.verification_level)
print("Sources used:", result.sources_used)
print("Epoch:", result.epoch)
print("Acceptable for standard unlock:", is_acceptable_for_standard_unlock(result.verification_level))