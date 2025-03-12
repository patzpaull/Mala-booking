# import pytest
# from sqlalchemy import Date, Time
# from httpx import AsyncClient
# from app.main import app
# from app.database import SessionLocal
# from app.models import User, Appointment


# @pytest.fixture
# def test_db():
#     db = SessionLocal()
#     yield db
#     db.close()


# @pytest.fixture
# def test_user(test_db):
#     user = User(username="testuser", email="test@example.com")
#     user.set_password("password")
#     test_db.add(user)
#     test_db.commit()
#     test_db.refresh(user)
#     return user


# @pytest.fixture
# def test_appointment(test_db, test_user):
#     appointment = Appointment(
#         appointment_time=Time.utcnow(),
#         duration=60,
#         client_id=test_user.user_id,
#         service_id=1,
#         status="pending",
#     )
#     test_db.add(appointment)
#     test_db.commit()
#     test_db.refresh(appointment)
#     return appointment


# @pytest.mark.asyncio
# async def test_send_message(test_user, test_appointment):
#     # Authenticate
#     async with AsyncClient(app=app, base_url="http://test") as ac:
#         login_response = await ac.post("/token", data={"username": test_user.username, "password": "password"})
#         token = login_response.json()["access_token"]

#         # Send a message
#         message_data = {"message_text":"Hello, this is a test message."}
#         response = await ac.post(
#             f"/appointments/{test_appointment.appointment_id}/messages/",
#             json=message_data,
#             headers={"Authorization": f"Bearer {token}"}
#         )

#     assert response.status_code == 200 
#     assert response.json(["message_text"] == "Hello, this is a test message.")


# @pytest.mark.asyncio
# async def test_unauthorized_message_access(test_user,test_appointment):
#     # Create another User 
#     db = SessionLocal()
#     other_user = User(username="otheruser", email="other@example.com")
#     other_user.set_password("password")
#     db.add(other_user)
#     db.commit()
#     db.refresh(other_user)


#     # Authenticate as other user 
#     async with AsyncClient(app=app, base_url="http://test") as ac:
#         login_response = await ac.post("/token", data={"username": "otheruser", "password":"password"})
#         token = login_response.json()["access_token"]


#         # Attempt to send a message 
#         message_data = {"message_text":"Unauthorized: Man's not even allowed to step foot let alone chat shit on here "}
#         response = await ac.post(
#             f"/appointments/{test_appointment.appointment_id}/messages/",
#             json=message_data,
#             headers={"Authorization": f"Bearer {token}"}
#         )
#     assert response.status_code ==403
#     assert response.json()["detail"] == "Not authorized to send messages for this appointment"