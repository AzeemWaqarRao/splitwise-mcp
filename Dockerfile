FROM python:3.11.15-slim-trixie
WORKDIR /app
COPY server.py ./
COPY requirements.txt ./
RUN pip install fastmcp
EXPOSE 8000
CMD ["python3", "server.py"]

