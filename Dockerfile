FROM python:3.9

WORKDIR /

COPY requirements.txt /

RUN pip install --no-cache-dir -r requirements.txt

COPY . /

EXPOSE 8000 

CMD [ "fastapi", "run", "app/main.py", "--port", "8000" ]