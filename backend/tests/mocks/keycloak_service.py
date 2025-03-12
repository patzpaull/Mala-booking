from fastapi import HTTPException



class MockKeycloakService:
    async def authenticate_user(self, username: str, password: str):
        if username == "testuser" and password == "password":
            return {
                "access_token": "sample_access_token",
                "refresh_token": "sample_refresh_token",
                "id_token": "sample_id_token",
                "expires_in": 360,
                "refresh_expires_in": 1800,
            }
        raise HTTPException(status_code=401, detail="Invalid credentials")

    async def logout(self, refresh_token: str):
        return True